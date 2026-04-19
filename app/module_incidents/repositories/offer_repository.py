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
