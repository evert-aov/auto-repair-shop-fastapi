import uuid

from sqlalchemy.orm import Session

from app.module_incidents.models import WorkshopOffer


def get_offer_by_id(db: Session, offer_id: uuid.UUID) -> WorkshopOffer | None:
    return db.query(WorkshopOffer).filter(WorkshopOffer.id == offer_id).first()


def get_offers_by_incident(db: Session, incident_id: uuid.UUID) -> list[WorkshopOffer]:
    return (
        db.query(WorkshopOffer)
        .filter(WorkshopOffer.incident_id == incident_id)
        .all()
    )


def save_offer(db: Session, offer: WorkshopOffer) -> WorkshopOffer:
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer

def get_active_offers_by_workshop(db: Session, workshop_id: uuid.UUID) -> list[WorkshopOffer]:
    from app.module_incidents.models import OfferStatus, Incident, IncidentStatus
    return (
        db.query(WorkshopOffer)
        .join(Incident)
        .filter(
            WorkshopOffer.workshop_id == workshop_id,
            WorkshopOffer.status == OfferStatus.ACCEPTED,
            Incident.status.in_([IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS])
        )
        .order_by(Incident.created_at.desc())
        .all()
    )
