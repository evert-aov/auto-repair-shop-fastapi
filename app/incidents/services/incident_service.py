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

    def cancel_incident(self, incident_id: uuid.UUID, current_user: User) -> Incident:
        incident = self.incident_repository.get_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")

        from app.clients.models import Client
        client = self.db.query(Client).filter(Client.id == current_user.id).first()
        is_owner = client and incident.client_id == client.id
        is_admin = any(role.name == "admin" for role in current_user.roles)
        
        if not is_owner and not is_admin:
            raise HTTPException(status_code=403, detail="No tienes permiso para cancelar este incidente")

        if incident.status in [IncidentStatus.COMPLETED, IncidentStatus.CANCELLED, IncidentStatus.NO_OFFERS, IncidentStatus.ERROR]:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede cancelar el incidente en su estado actual: {incident.status.value}"
            )

        if incident.status == IncidentStatus.IN_PROGRESS:
            raise HTTPException(
                status_code=400,
                detail="El mecánico ya ha llegado al lugar de asistencia o el servicio ya se encuentra en proceso, no se puede cancelar."
            )

        prev_status = incident.status.value
        
        if incident.assigned_technician_id:
            from app.workshops.models import Technician
            tech = self.db.query(Technician).filter(Technician.id == incident.assigned_technician_id).first()
            if tech:
                tech.is_available = True
                logger.info(f"🔓 Técnico {tech.name} liberado tras cancelación")

        from app.incidents.models.workshop_offer import WorkshopOffer, OfferStatus
        active_offers = self.db.query(WorkshopOffer).filter(
            WorkshopOffer.incident_id == incident.id,
            WorkshopOffer.status == OfferStatus.NOTIFIED
        ).all()
        for offer in active_offers:
            offer.status = OfferStatus.EXPIRED
            self.db.add(offer)

        incident.status = IncidentStatus.CANCELLED
        self.incident_repository.save(incident)

        from app.incidents.repositories.status_history_repository import StatusHistoryRepository
        StatusHistoryRepository(self.db).log_status_change(
            incident_id=incident.id,
            previous_status=prev_status,
            new_status=IncidentStatus.CANCELLED.value,
            reason="Cancelado por el cliente antes del arribo del técnico",
        )

        return incident
