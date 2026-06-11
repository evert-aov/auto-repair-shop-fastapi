import logging
from typing import Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import auditable
from app.incidents.audit_mappers import rating_to_audit_map, rating_from_dto
from app.incidents.dtos.rating_dtos import RatingCreateDto, RatingResponseDto
from app.incidents.models import Rating, Incident, IncidentStatus
from app.payments.models import Payment, PaymentStatus
from app.incidents.repositories.rating_repository import RatingRepository
from app.incidents.repositories.incident_repository import IncidentRepository
from app.payments.repositories.payment_repository import PaymentRepository
from app.workshops.models import Workshop
from app.users.models import User

logger = logging.getLogger(__name__)


class RatingService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.rating_repository = RatingRepository(db)
        self.incident_repository = IncidentRepository(db)
        self.payment_repository = PaymentRepository(db)

    def get_entity(self, id: Any) -> Rating | None:
        return self.rating_repository.get_by_id(id)

    def to_audit_map(self, entity: Rating) -> dict[str, Any]:
        return rating_to_audit_map(entity)

    def to_audit_map_from_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, RatingResponseDto):
            return rating_from_dto(result)
        if isinstance(result, Rating):
            return rating_to_audit_map(result)
        return {}

    @auditable(resource_type="RATING", action_type="CREATE")
    def create_rating(self, current_user: User, data: RatingCreateDto) -> Rating:
        # 1. Obtener incidente y validar
        incident = self.incident_repository.get_by_id(data.incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # 2. Validar que el cliente sea el dueño del incidente
        if str(incident.client_id) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to rate this incident")

        # 3. Validar que el incidente esté completado
        if incident.status != IncidentStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Cannot rate an incident that is not completed")

        # 3.1 Validar que el incidente esté pagado
        payment = self.payment_repository.get_by_incident(incident.id)
        if not payment or payment.status != PaymentStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Cannot rate an incident that has not been paid via platform")

        # 4. Validar que tenga un taller asignado
        if not incident.assigned_workshop_id:
            raise HTTPException(status_code=400, detail="Incident has no assigned workshop to rate")

        # 5. Verificar si ya existe una reseña para este incidente
        existing_rating = self.db.query(Rating).filter(Rating.incident_id == data.incident_id).first()
        if existing_rating:
            raise HTTPException(status_code=400, detail="Incident already has a rating")

        # 6. Crear la reseña
        rating = Rating(
            incident_id=incident.id,
            client_id=current_user.id,
            workshop_id=incident.assigned_workshop_id,
            score=data.score,
            response_time_score=data.response_time_score,
            quality_score=data.quality_score,
            comment=data.comment,
        )

        rating = self.rating_repository.save(rating)

        # 7. Actualizar promedio del taller
        self._update_workshop_rating(incident.assigned_workshop_id)

        return rating

    def _update_workshop_rating(self, workshop_id):
        stats = self.rating_repository.get_workshop_rating_stats(workshop_id)
        if stats and stats.avg_score is not None:
            workshop = self.db.query(Workshop).filter(Workshop.id == workshop_id).first()
            if workshop:
                workshop.rating_avg = stats.avg_score
        self.db.commit()
        return True
