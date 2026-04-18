import uuid

from sqlalchemy.orm import Session

from app.module_incidents.models import Incident


def get_incident_by_id(db: Session, incident_id: uuid.UUID) -> Incident | None:
    return db.query(Incident).filter(Incident.id == incident_id).first()


def get_incidents_by_client(db: Session, client_id: uuid.UUID) -> list[Incident]:
    return db.query(Incident).filter(Incident.client_id == client_id).all()


def save_incident(db: Session, incident: Incident) -> Incident:
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident
