import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.incidents.dtos.incident_dtos import IncidentCreateDto
from app.incidents.models import (
    Incident, IncidentEvidence, IncidentStatus, EvidenceType
)
from app.incidents.repositories.incident_repository import IncidentRepository
from app.incidents.repositories.evidence_repository import EvidenceRepository
from app.users.models import User
from app.security.models import Client, Vehicle

logger = logging.getLogger(__name__)


class IncidentService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.incident_repository = IncidentRepository(db)
        self.evidence_repository = EvidenceRepository(db)

    def create_incident_request(
        self,
        current_user: User,
        data: IncidentCreateDto,
    ) -> Incident:
        client = self.db.query(Client).filter(Client.id == current_user.id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        vehicle = self.db.query(Vehicle).filter(
            Vehicle.id == data.vehicle_id,
            Vehicle.client_id == client.id,
        ).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        incident = Incident(
            client_id=client.id,
            vehicle_id=vehicle.id,
            description=data.description,
            incident_lat=data.latitude,
            incident_lng=data.longitude,
            status=IncidentStatus.PENDING,
        )
        incident = self.incident_repository.save(incident)

        for ev in data.evidences:
            evidence = IncidentEvidence(
                incident_id=incident.id,
                evidence_type=EvidenceType(ev.evidence_type),
                file_url=ev.file_url,
                transcription=ev.transcription,
            )
            self.evidence_repository.save(evidence)

        return incident
