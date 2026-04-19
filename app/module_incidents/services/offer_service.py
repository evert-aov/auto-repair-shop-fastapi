import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.module_incidents.models import (
    Incident,
    IncidentStatus,
    OfferStatus,
    WorkshopOffer,
    RejectionReason,
)
from app.module_incidents.repositories import (
    incident_repository,
    offer_repository,
    status_history_repository,
)
from app.module_incidents.services.notification_service import NotificationService
from app.module_workshops.repositories import workshop_repository

logger = logging.getLogger(__name__)

# Activity Points deducted per rejection reason (YANGO REAL)
ACTIVITY_PENALTIES: dict[RejectionReason, int] = {
    RejectionReason.NO_REASON: 5,
    RejectionReason.BUSY: 8,
    RejectionReason.FAR_FROM_ZONE: 15,
    RejectionReason.NO_PARTS: 3,
    RejectionReason.NO_TECHNICIAN: 5,
    RejectionReason.TIMEOUT_NO_RESPONSE: 20,
}


class OfferService:

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    # =================================================================
    # ACCEPT
    # =================================================================

    async def accept_offer(
        self,
        offer_id: uuid.UUID,
        technician_id: Optional[uuid.UUID] = None,
        estimated_arrival_min: Optional[int] = None,
    ) -> Incident:
        offer = offer_repository.get_offer_by_id(self.db, offer_id)
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")
        if offer.status != OfferStatus.NOTIFIED:
            raise ValueError(f"Offer {offer_id} cannot be accepted (status: {offer.status.value})")

        incident = incident_repository.get_incident_by_id(self.db, offer.incident_id)
        workshop = workshop_repository.get_workshop_by_id(self.db, offer.workshop_id)

        offer.status = OfferStatus.ACCEPTED
        offer.accepted_at = datetime.now(timezone.utc)
        offer_repository.save_offer(self.db, offer)

        logger.info(f"Workshop {workshop.id} ({workshop.name}) accepted offer {offer_id}")

        prev_status = incident.status.value if incident.status else None
        incident.status = IncidentStatus.ASSIGNED
        incident.assigned_workshop_id = workshop.id
        if technician_id:
            incident.assigned_technician_id = technician_id
        if estimated_arrival_min:
            incident.estimated_arrival_min = estimated_arrival_min
        elif offer.distance_km:
            incident.estimated_arrival_min = int(offer.distance_km * 1.2)

        incident = incident_repository.save_incident(self.db, incident)

        status_history_repository.log_status_change(
            self.db,
            incident_id=incident.id,
            previous_status=prev_status,
            new_status=IncidentStatus.ASSIGNED.value,
            reason=f"Workshop {workshop.name} accepted offer",
        )

        await self.notification_service.notify_client_offer_accepted(
            incident=incident,
            workshop=workshop,
            estimated_arrival_min=incident.estimated_arrival_min or 15,
        )

        return incident

    # =================================================================
    # REJECT (triggers YANGO REAL re-matching)
    # =================================================================

    async def reject_offer(
        self,
        offer_id: uuid.UUID,
        rejection_reason: Optional[RejectionReason] = None,
    ) -> Optional[WorkshopOffer]:
        offer = offer_repository.get_offer_by_id(self.db, offer_id)
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")
        if offer.status != OfferStatus.NOTIFIED:
            raise ValueError(f"Offer {offer_id} cannot be rejected (status: {offer.status.value})")

        incident = incident_repository.get_incident_by_id(self.db, offer.incident_id)
        workshop = workshop_repository.get_workshop_by_id(self.db, offer.workshop_id)
        reason_enum = rejection_reason or RejectionReason.NO_REASON

        offer.status = OfferStatus.REJECTED
        offer.rejected_at = datetime.now(timezone.utc)
        offer.rejection_reason = reason_enum.value
        offer_repository.save_offer(self.db, offer)

        logger.info(
            f"Workshop {workshop.id} ({workshop.name}) rejected offer {offer_id}. "
            f"Reason: {reason_enum.value}"
        )

        await self._penalize_workshop(workshop.id, reason_enum)

        # YANGO REAL re-matching: recalculate batch, pick new winner
        from app.module_incidents.services import assignment_service

        next_offer = await assignment_service.find_and_create_offer(self.db, incident)
        return next_offer

    # =================================================================
    # TIMEOUT DETECTION (called by scheduler every 5s)
    # =================================================================

    async def process_timeouts(self) -> int:
        now = datetime.now(timezone.utc)
        expired_offers = (
            self.db.query(WorkshopOffer)
            .filter(
                WorkshopOffer.status == OfferStatus.NOTIFIED,
                WorkshopOffer.expires_at < now,
                WorkshopOffer.accepted_at.is_(None),
                WorkshopOffer.rejected_at.is_(None),
            )
            .all()
        )

        count = 0
        for offer in expired_offers:
            logger.warning(
                f"Offer {offer.id} timeout — workshop {offer.workshop_id} did not respond"
            )
            try:
                await self.reject_offer(offer.id, rejection_reason=RejectionReason.TIMEOUT_NO_RESPONSE)
                count += 1
            except Exception as e:
                logger.error(f"Error processing timeout for offer {offer.id}: {e}")

        if count > 0:
            logger.info(f"Processed {count} timeouts")
        return count

    # =================================================================
    # HELPERS
    # =================================================================

    async def _penalize_workshop(
        self, workshop_id: uuid.UUID, rejection_reason: RejectionReason
    ) -> None:
        workshop = workshop_repository.get_workshop_by_id(self.db, workshop_id)
        if not workshop:
            return

        workshop.rejection_count = (workshop.rejection_count or 0) + 1
        workshop.last_rejection_at = datetime.now(timezone.utc)

        pts_penalty = ACTIVITY_PENALTIES.get(rejection_reason, 5)
        current_pts = workshop.activity_points if workshop.activity_points is not None else 50
        workshop.activity_points = max(0, current_pts - pts_penalty)

        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        total = (
            self.db.query(WorkshopOffer)
            .filter(WorkshopOffer.workshop_id == workshop_id, WorkshopOffer.created_at > thirty_days_ago)
            .count()
        )
        rejected = (
            self.db.query(WorkshopOffer)
            .filter(
                WorkshopOffer.workshop_id == workshop_id,
                WorkshopOffer.status.in_([OfferStatus.REJECTED, OfferStatus.TIMEOUT]),
                WorkshopOffer.created_at > thirty_days_ago,
            )
            .count()
        )
        workshop.rejection_rate = rejected / total if total > 0 else 0.0

        workshop_repository.save_workshop(self.db, workshop)

        logger.info(
            f"Workshop {workshop_id} penalized: -{pts_penalty} pts → "
            f"activity_points={workshop.activity_points}, "
            f"rejection_rate={workshop.rejection_rate:.2%}"
        )
