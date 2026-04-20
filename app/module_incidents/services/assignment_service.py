import logging
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.module_incidents.models import Incident, WorkshopOffer, IncidentStatus
from app.module_incidents.repositories import (
    incident_repository,
    offer_repository,
    status_history_repository,
)
from app.module_workshops.repositories import workshop_repository, technician_repository

logger = logging.getLogger(__name__)

_CATEGORY_TO_SPECIALTY: dict[str, str | None] = {
    "battery": "Electricidad",
    "tire": "Frenos",
    "engine": "Mecánica General",
    "ac": "Electricidad",
    "transmission": "Mecánica General",
    "towing": "Mecánica General",
    "locksmith": "Mecánica General",
    "general": "Mecánica General",
    "collision": "Chapería y Pintura",
    "uncertain": None,
}



def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

## Calificacion de talleres

def _calculate_ai_score(
    distance_km: float,
    workshop_rating: float,
    incident_priority: str,
) -> float:
    distance_score = max(0.0, 1.0 - distance_km / 50.0)
    rating_score = workshop_rating / 5.0
    priority_weights = {"LOW": 0.3, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}
    priority_weight = priority_weights.get(incident_priority, 0.5)
    return round(distance_score * 0.4 + rating_score * 0.4 + priority_weight * 0.2, 3)


def find_and_create_offers(db: Session, incident: Incident) -> None:
    specialty_name = _CATEGORY_TO_SPECIALTY.get(incident.ai_category or "")
    if not specialty_name:
        logger.warning(f"No specialty mapping for ai_category={incident.ai_category!r}")
        _mark_no_offers(db, incident)
        return

    specialty = workshop_repository.get_specialty_by_name(db, specialty_name)
    if not specialty:
        logger.warning(f"Specialty '{specialty_name}' not in database")
        _mark_no_offers(db, incident)
        return

    workshops = workshop_repository.find_nearby_workshops(
        db,
        latitude=incident.incident_lat,
        longitude=incident.incident_lng,
        specialty_id=specialty.id,
        radius_km=50.0,
        min_rating=3.5,
    )

    scored: list[tuple] = []
    for workshop in workshops:
        technician = technician_repository.get_available_technician(db, workshop.id)
        if not technician:
            continue
        distance_km = _haversine(
            incident.incident_lat, incident.incident_lng,
            workshop.latitude, workshop.longitude,
        )
        priority_value = incident.ai_priority.value if incident.ai_priority else "MEDIUM"
        ai_score = _calculate_ai_score(distance_km, workshop.rating_avg, priority_value)
        scored.append((workshop, distance_km, ai_score))

    if not scored:
        _mark_no_offers(db, incident)
        return

    top_three = sorted(scored, key=lambda x: x[2], reverse=True)[:3]

    for workshop, distance_km, ai_score in top_three:
        offer = WorkshopOffer(
            incident_id=incident.id,
            workshop_id=workshop.id,
            status="notified",
            distance_km=distance_km,
            ai_score=ai_score,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        offer_repository.save_offer(db, offer)
        logger.info(
            f"Offer → workshop={workshop.id} score={ai_score} dist={distance_km:.1f}km"
        )

    closest_distance = top_three[0][1]
    incident.estimated_arrival_min = int(closest_distance)
    incident_repository.save_incident(db, incident)


def _mark_no_offers(db: Session, incident: Incident) -> None:
    prev = incident.status.value if incident.status else None
    incident.status = IncidentStatus.NO_OFFERS
    incident_repository.save_incident(db, incident)
    status_history_repository.log_status_change(
        db,
        incident_id=incident.id,
        previous_status=prev,
        new_status=IncidentStatus.NO_OFFERS.value,
        reason="No compatible workshops found",
    )
