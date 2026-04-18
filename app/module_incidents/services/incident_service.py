import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.module_incidents.dtos.incident_dtos import IncidentCreateDto
from app.module_incidents.models import (
    Incident, IncidentEvidence, IncidentStatus, EvidenceType
)
from app.module_incidents.repositories import incident_repository, evidence_repository
from app.module_users.models import User
from app.security.models import Client, Vehicle

logger = logging.getLogger(__name__)


def create_incident_request(
    db: Session,
    current_user: User,
    data: IncidentCreateDto,
) -> Incident:
    client = db.query(Client).filter(Client.id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    vehicle = db.query(Vehicle).filter(
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
    incident = incident_repository.save_incident(db, incident)

    for ev in data.evidences:
        evidence = IncidentEvidence(
            incident_id=incident.id,
            evidence_type=EvidenceType(ev.evidence_type),
            file_url=ev.file_url,
            transcription=ev.transcription,
        )
        evidence_repository.save_evidence(db, evidence)

    return incident
