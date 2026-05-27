import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.incidents.dtos.rating_dtos import RatingCreateDto, RatingResponseDto
from app.incidents.services.rating_service import RatingService
from app.incidents.repositories.rating_repository import RatingRepository
from app.users.models import User
from app.security.config.security import get_current_user, require_permission

router = APIRouter(prefix="/api/ratings", tags=["Ratings"])


@router.post(
    "",
    response_model=RatingResponseDto,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("incidents:create"))],
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
    return RatingService(db).create_rating(current_user, data)


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
    return RatingRepository(db).get_ratings_by_workshop(workshop_id)
