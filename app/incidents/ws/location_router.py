from datetime import datetime, timezone
import math

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.workshops.models import Technician
from .location_manager import location_manager

router = APIRouter()

# Distance threshold in meters: when the technician is within this radius
# of the client's incident location, we auto-transition to IN_PROGRESS.
ARRIVAL_THRESHOLD_METERS = 200.0


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in meters between two points."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _resolve_user(token: str):
    """Decode JWT and return the User object, or None on failure."""
    db = SessionLocal()
    try:
        from app.security.config.security import decode_token
        from app.users.repositories.user_repository import UserRepository
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            return None
        return UserRepository(db).get_by_username(username)
    except Exception:
        return None
    finally:
        db.close()


@router.websocket("/ws/location/{incident_id}")
async def location_ws(
    websocket: WebSocket,
    incident_id: str,
    token: str = Query(...),
    role: str = Query("viewer"),
):
    """
    Real-time location channel for an incident.

    - role=technician  → sends GPS updates; server broadcasts to viewers and
                         persists lat/lng on the Technician row.
                         Auto-transitions incident ASSIGNED → IN_PROGRESS when
                         technician is within ARRIVAL_THRESHOLD_METERS of the client.
    - role=viewer      → receives location broadcasts (workshop_owner, client).

    Auth: JWT passed as `?token=<jwt>` query parameter.
    """
    user = _resolve_user(token)
    if user is None:
        await websocket.accept()
        await websocket.close(code=4001)
        return

    if role == "technician":
        await location_manager.connect_technician(websocket, incident_id)
        # Track whether we already triggered the arrival for this session
        _arrival_triggered = False
        try:
            await websocket.send_json({"type": "connected", "role": "technician"})
            while True:
                data = await websocket.receive_json()
                if data.get("type") != "update_location":
                    continue

                lat = float(data["lat"])
                lng = float(data["lng"])

                db = SessionLocal()
                try:
                    tech = db.query(Technician).filter(Technician.id == user.id).first()
                    if tech:
                        tech.current_latitude = lat
                        tech.current_longitude = lng
                        db.commit()

                    # ── Auto-arrival: ASSIGNED → IN_PROGRESS ──────────────
                    if not _arrival_triggered:
                        from app.incidents.models.incident import Incident
                        from app.incidents.models import IncidentStatus
                        incident = db.query(Incident).filter(
                            Incident.id == incident_id
                        ).first()

                        if (incident
                                and incident.status == IncidentStatus.ASSIGNED
                                and incident.incident_lat is not None
                                and incident.incident_lng is not None):
                            distance = _haversine_meters(
                                lat, lng,
                                float(incident.incident_lat),
                                float(incident.incident_lng),
                            )
                            if distance <= ARRIVAL_THRESHOLD_METERS:
                                prev_status = incident.status.value
                                incident.status = IncidentStatus.IN_PROGRESS
                                db.add(incident)

                                from app.incidents.repositories.status_history_repository import StatusHistoryRepository
                                StatusHistoryRepository(db).log_status_change(
                                    incident_id=incident.id,
                                    previous_status=prev_status,
                                    new_status=IncidentStatus.IN_PROGRESS.value,
                                    reason="El técnico ha llegado a la ubicación del cliente (detección automática por GPS)",
                                )
                                db.commit()
                                _arrival_triggered = True

                                # Notify viewers that the technician arrived
                                await location_manager.broadcast_location(incident_id, {
                                    "type": "arrived",
                                    "message": "El técnico ha llegado a tu ubicación",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                })
                    # ──────────────────────────────────────────────────────
                finally:
                    db.close()

                await location_manager.broadcast_location(incident_id, {
                    "type": "location",
                    "lat": lat,
                    "lng": lng,
                    "technician_name": f"{user.name} {user.last_name}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except WebSocketDisconnect:
            location_manager.disconnect_technician(incident_id)

    else:
        await location_manager.connect_viewer(websocket, incident_id)
        try:
            await websocket.send_json({"type": "connected", "role": "viewer"})

            # ── Send last known location immediately ──────────────────────────
            db = SessionLocal()
            try:
                from app.incidents.models.incident import Incident
                incident = db.query(Incident).filter(
                    Incident.id == incident_id
                ).first()
                if incident and incident.assigned_technician_id:
                    tech = db.query(Technician).filter(
                        Technician.id == incident.assigned_technician_id
                    ).first()
                    if tech and tech.current_latitude is not None and tech.current_longitude is not None:
                        # Technician inherits from User — name fields are directly on tech
                        tech_name = f"{tech.name} {tech.last_name}".strip() or "Técnico"
                        await websocket.send_json({
                            "type": "location",
                            "lat": float(tech.current_latitude),
                            "lng": float(tech.current_longitude),
                            "technician_name": tech_name,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
            finally:
                db.close()
            # ─────────────────────────────────────────────────────────────────

            while True:
                # Block until the client disconnects; ignore any incoming messages.
                await websocket.receive_text()
        except WebSocketDisconnect:
            location_manager.disconnect_viewer(websocket, incident_id)


