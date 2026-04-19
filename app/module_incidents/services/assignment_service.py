import logging
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.module_incidents.models import Incident, WorkshopOffer, IncidentStatus, OfferStatus
from app.module_incidents.repositories import (
    incident_repository,
    offer_repository,
    status_history_repository,
)
from app.module_workshops.repositories import workshop_repository, technician_repository

logger = logging.getLogger(__name__)

_CATEGORY_TO_SPECIALTY: dict[str, str | None] = {
    "battery": "battery",
    "tire": "tire",
    "engine": "engine",
    "ac": "ac",
    "transmission": "transmission",
    "towing": "towing",
    "locksmith": "locksmith",
    "general": "general",
    "collision": "general",
    "uncertain": None,
}

_COOLDOWN_DURATIONS: dict[str, timedelta] = {
    "no_reason": timedelta(hours=1),
    "busy": timedelta(hours=2),
    "far_from_zone": timedelta(hours=6),
    "no_parts": timedelta(minutes=30),
    "no_technician": timedelta(hours=1),
    "timeout_no_response": timedelta(hours=3),
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


def _calculate_ai_score(distance_km: float, workshop_rating: float, incident_priority: str) -> float:
    distance_score = max(0.0, 1.0 - distance_km / 50.0)
    rating_score = workshop_rating / 5.0
    priority_weights = {"LOW": 0.3, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}
    priority_weight = priority_weights.get(incident_priority, 0.5)
    return round(distance_score * 0.4 + rating_score * 0.4 + priority_weight * 0.2, 3)


def _calculate_activity_penalty(activity_points: int) -> float:
    """
    Returns penalty fraction (0.0 = no penalty, 1.0 = fully blocked).
    - >= 50 pts: 0% penalty (normal)
    - 0 pts: 100% penalty (blocked)
    - Linear below 50
    """
    if activity_points <= 0:
        return 1.0
    if activity_points >= 50:
        return 0.0
    return (50 - activity_points) / 50.0


def _is_in_cooldown(db: Session, workshop_id: uuid.UUID) -> bool:
    last_rejection = (
        db.query(WorkshopOffer)
        .filter(
            WorkshopOffer.workshop_id == workshop_id,
            WorkshopOffer.status.in_([OfferStatus.REJECTED, OfferStatus.TIMEOUT]),
            WorkshopOffer.rejected_at.isnot(None),
        )
        .order_by(WorkshopOffer.rejected_at.desc())
        .first()
    )

    if not last_rejection:
        return False

    reason = last_rejection.rejection_reason or "no_reason"
    duration = _COOLDOWN_DURATIONS.get(reason, timedelta(hours=1))
    expires_at = last_rejection.rejected_at + duration
    return datetime.now(timezone.utc) < expires_at


async def find_and_create_offer(db: Session, incident: Incident) -> WorkshopOffer | None:
    """
    YANGO REAL N=1: find the best workshop, create a single exclusive offer.
    Returns the created offer, or None if no candidates found.
    """
    from app.module_incidents.services.notification_service import NotificationService

    specialty_name = _CATEGORY_TO_SPECIALTY.get(incident.ai_category or "")
    if not specialty_name:
        logger.warning(f"No specialty mapping for ai_category={incident.ai_category!r}")
        await _mark_no_offers(db, incident)
        return None

    specialty = workshop_repository.get_specialty_by_name(db, specialty_name)
    if not specialty:
        logger.warning(f"Specialty '{specialty_name}' not in database")
        await _mark_no_offers(db, incident)
        return None

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
        pts = workshop.activity_points if workshop.activity_points is not None else 50
        if pts <= 0:
            logger.debug(f"Workshop {workshop.id} blocked (activity_points=0)")
            continue
        if _is_in_cooldown(db, workshop.id):
            logger.debug(f"Workshop {workshop.id} in cooldown, skipping")
            continue
        technician = technician_repository.get_available_technician(db, workshop.id)
        if not technician:
            continue

        distance_km = _haversine(
            incident.incident_lat,
            incident.incident_lng,
            float(workshop.latitude or 0),
            float(workshop.longitude or 0),
        )
        priority_value = incident.ai_priority.value if incident.ai_priority else "MEDIUM"
        base_score = _calculate_ai_score(distance_km, float(workshop.rating_avg), priority_value)
        penalty = _calculate_activity_penalty(pts)
        final_score = round(base_score * (1.0 - penalty), 3)
        scored.append((workshop, distance_km, final_score))

    if not scored:
        await _mark_no_offers(db, incident)
        return None

    winner_workshop, winner_distance, winner_score = max(scored, key=lambda x: x[2])

    offer = WorkshopOffer(
        incident_id=incident.id,
        workshop_id=winner_workshop.id,
        status=OfferStatus.NOTIFIED,
        distance_km=winner_distance,
        ai_score=winner_score,
        notified_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        timeout_minutes=30,
    )
    offer_repository.save_offer(db, offer)

    incident.estimated_arrival_min = int(winner_distance * 1.2)
    incident.status = IncidentStatus.MATCHED
    incident_repository.save_incident(db, incident)

    logger.info(
        f"[YANGO N=1] Offer → workshop={winner_workshop.id} "
        f"score={winner_score} dist={winner_distance:.1f}km "
        f"activity_pts={winner_workshop.activity_points}"
    )

    notification_service = NotificationService(db)
    await notification_service.notify_workshop_new_offer(
        workshop=winner_workshop,
        incident=incident,
        offer=offer,
    )

    return offer


async def _mark_no_offers(db: Session, incident: Incident) -> None:
    from app.module_incidents.services.notification_service import NotificationService

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

    notification_service = NotificationService(db)
    await notification_service.notify_client_no_workshops(incident)
