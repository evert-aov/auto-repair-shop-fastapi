import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.module_incidents.dtos import RatingCreateDto, RatingResponseDto
from app.module_incidents.services import rating_service
from app.module_users.models import User
from app.security.config.security import get_current_user, require_role

router = APIRouter(prefix="/api/ratings", tags=["Ratings"])


@router.post(
    "",
    response_model=RatingResponseDto,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("client"))],
)
def create_rating(
    data: RatingCreateDto,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea una nueva reseña para un incidente completado.
    Actualiza automáticamente el promedio del taller asignado.
    """
    return rating_service.create_rating(db, current_user, data)


@router.get(
    "/workshop/{workshop_id}",
    response_model=list[RatingResponseDto],
    status_code=status.HTTP_200_OK,
)
def get_workshop_ratings(
    workshop_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Obtiene todas las reseñas de un taller específico.
    """
    from app.module_incidents.repositories import rating_repository
    return rating_repository.get_ratings_by_workshop(db, workshop_id)
