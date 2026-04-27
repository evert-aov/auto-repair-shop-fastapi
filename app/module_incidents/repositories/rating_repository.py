import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.module_incidents.models import Rating


def save_rating(db: Session, rating: Rating) -> Rating:
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


def get_ratings_by_workshop(db: Session, workshop_id: uuid.UUID) -> list[Rating]:
    return db.query(Rating).filter(Rating.workshop_id == workshop_id).all()


def get_workshop_rating_stats(db: Session, workshop_id: uuid.UUID):
    """Calcula el promedio de puntaje y el total de reseñas para un taller."""
    result = db.query(
        func.avg(Rating.score).label("avg_score"),
        func.count(Rating.id).label("total_count")
    ).filter(Rating.workshop_id == workshop_id).first()
    
    return result
