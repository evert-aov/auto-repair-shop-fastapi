import math
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session, selectinload
from app.module_workshops.models.models import Workshop, Technician, WorkshopSpecialty, Specialty


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_workshop_by_id(db: Session, workshop_id: uuid.UUID) -> Workshop | None:
    return db.query(Workshop).filter(Workshop.id == workshop_id).first()


def get_specialty_by_name(db: Session, name: str) -> Specialty | None:
    return db.query(Specialty).filter(Specialty.name == name).first()


def find_nearby_workshops(
    db: Session,
    latitude: float,
    longitude: float,
    specialty_id: int,
    radius_km: float = 50.0,
    min_rating: float = 3.5,
) -> list[Workshop]:
    workshops = (
        db.query(Workshop)
        .join(WorkshopSpecialty, Workshop.id == WorkshopSpecialty.workshop_id)
        .filter(
            WorkshopSpecialty.specialty_id == specialty_id,
            Workshop.rating_avg >= min_rating,
            Workshop.is_active.is_(True),
        )
        .all()
    )
    return [
        w for w in workshops
        if _haversine(latitude, longitude, float(w.latitude or 0), float(w.longitude or 0)) <= radius_km
    ]


def save_workshop(db: Session, workshop: Workshop) -> Workshop:
    db.add(workshop)
    db.commit()
    db.refresh(workshop)
    return workshop


class WorkshopRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, workshop: Workshop) -> Workshop:
        self.db.add(workshop)
        self.db.commit()
        self.db.refresh(workshop)
        return workshop

    def get_by_id(self, workshop_id: uuid.UUID) -> Optional[Workshop]:
        return self.db.query(Workshop).options(
            selectinload(Workshop.workshop_specialties).selectinload(WorkshopSpecialty.specialty),
            selectinload(Workshop.technicians).selectinload(Technician.roles),
        ).filter(Workshop.id == workshop_id).first()

    def get_all(self, verified_only: Optional[bool] = None) -> List[Workshop]:
        query = self.db.query(Workshop).options(
            selectinload(Workshop.workshop_specialties).selectinload(WorkshopSpecialty.specialty),
            selectinload(Workshop.technicians).selectinload(Technician.roles),
        )
        if verified_only is not None:
            query = query.filter(Workshop.is_verified == verified_only)
        return query.all()

    def update(self, workshop: Workshop) -> Workshop:
        self.db.commit()
        self.db.refresh(workshop)
        return workshop
