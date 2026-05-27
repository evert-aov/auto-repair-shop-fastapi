import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.incidents.models import Rating


class RatingRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def save(self, rating: Rating) -> Rating:
        self.db.add(rating)
        self.db.commit()
        self.db.refresh(rating)
        return rating

    def get_ratings_by_workshop(self, workshop_id: uuid.UUID) -> list[Rating]:
        return (
            self.db.query(Rating)
            .filter(Rating.workshop_id == workshop_id)
            .order_by(Rating.created_at.desc())
            .all()
        )

    def get_workshop_rating_stats(self, workshop_id: uuid.UUID):
        return (
            self.db.query(func.avg(Rating.score).label("avg_score"))
            .filter(Rating.workshop_id == workshop_id)
            .first()
        )
