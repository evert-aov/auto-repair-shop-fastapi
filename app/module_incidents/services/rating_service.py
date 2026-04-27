import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.module_incidents.dtos.rating_dtos import RatingCreateDto
from app.module_incidents.models import Rating, Incident, IncidentStatus, Payment, PaymentStatus
from app.module_incidents.repositories import rating_repository, incident_repository
from app.module_payments.repositories import payment_repository
from app.module_workshops.models import Workshop
from app.module_users.models import User

logger = logging.getLogger(__name__)


def create_rating(db: Session, current_user: User, data: RatingCreateDto) -> Rating:
    # 1. Obtener incidente y validar
    incident = incident_repository.get_incident_by_id(db, data.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # 2. Validar que el cliente sea el dueño del incidente
    if str(incident.client_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to rate this incident")

    # 3. Validar que el incidente esté completado
    if incident.status != IncidentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot rate an incident that is not completed")

    # [NUEVO] 3.1 Validar que el incidente esté pagado
    payment = payment_repository.get_by_incident(db, incident.id)
    if not payment or payment.status != PaymentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot rate an incident that has not been paid via platform")

    # 4. Validar que tenga un taller asignado
    if not incident.assigned_workshop_id:
        raise HTTPException(status_code=400, detail="Incident has no assigned workshop to rate")

    # 5. Verificar si ya existe una reseña para este incidente
    existing_rating = db.query(Rating).filter(Rating.incident_id == data.incident_id).first()
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
        comment=data.comment
    )
    
    rating = rating_repository.save_rating(db, rating)

    # 7. Actualizar promedio del taller
    _update_workshop_rating(db, incident.assigned_workshop_id)

    return rating


def _update_workshop_rating(db: Session, workshop_id):
    stats = rating_repository.get_workshop_rating_stats(db, workshop_id)
    if stats and stats.avg_score is not None:
        workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
        if workshop:
            workshop.rating_avg = stats.avg_score
    db.commit()
    return True
