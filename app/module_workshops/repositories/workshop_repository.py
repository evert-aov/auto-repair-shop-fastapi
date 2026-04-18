import uuid
from typing import List, Optional
from sqlalchemy.orm import Session, selectinload
from app.module_workshops.models.models import Workshop, Technician, WorkshopSpecialty

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
