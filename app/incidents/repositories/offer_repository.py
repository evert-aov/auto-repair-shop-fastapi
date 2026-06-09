import uuid

from sqlalchemy.orm import Session

from app.incidents.models import WorkshopOffer


class OfferRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, offer_id: uuid.UUID) -> WorkshopOffer | None:
        return self.db.query(WorkshopOffer).filter(WorkshopOffer.id == offer_id).first()

    def get_offers_by_incident(self, incident_id: uuid.UUID) -> list[WorkshopOffer]:
        return (
            self.db.query(WorkshopOffer)
            .filter(WorkshopOffer.incident_id == incident_id)
            .all()
        )

    def save(self, offer: WorkshopOffer) -> WorkshopOffer:
        self.db.add(offer)
        self.db.commit()
        self.db.refresh(offer)
        return offer

    def get_active_offers_by_workshop(self, workshop_id: uuid.UUID) -> list[WorkshopOffer]:
        from app.incidents.models import OfferStatus, Incident, IncidentStatus
        return (
            self.db.query(WorkshopOffer)
            .join(Incident)
            .filter(
                WorkshopOffer.workshop_id == workshop_id,
                WorkshopOffer.status == OfferStatus.ACCEPTED,
                Incident.status.in_([IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS])
            )
            .order_by(Incident.created_at.desc())
            .all()
        )
