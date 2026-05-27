from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.workshops.models import Technician
from .location_manager import location_manager

router = APIRouter()


def _resolve_user(token: str):
    """Decode JWT and return the User object, or None on failure."""
    db = SessionLocal()
    try:
        from app.security.config.security import decode_token
        from app.users.repositories.user_repository import get_user_by_username
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            return None
        return get_user_by_username(db, username)
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
                from app.incidents.models.enums import Incident
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

