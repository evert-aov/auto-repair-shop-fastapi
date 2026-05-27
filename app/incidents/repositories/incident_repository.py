import uuid

from sqlalchemy.orm import Session, joinedload

from app.incidents.models import Incident


class IncidentRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, incident_id: uuid.UUID) -> Incident | None:
        return self.db.query(Incident).options(joinedload(Incident.evidences)).filter(Incident.id == incident_id).first()

    def get_by_client(self, client_id: uuid.UUID) -> list[Incident]:
        return self.db.query(Incident).filter(Incident.client_id == client_id).all()

    def save(self, incident: Incident) -> Incident:
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def get_pending_incidents(self) -> list[Incident]:
        """Get all incidents with status pending or matched (ready for workshop offers)"""
        from app.incidents.models import IncidentStatus
        return self.db.query(Incident).filter(
            Incident.status.in_([IncidentStatus.PENDING, IncidentStatus.MATCHED])
        ).order_by(Incident.created_at.desc()).all()
