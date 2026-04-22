import uuid
from typing import List, Optional
from sqlalchemy.orm import Session, selectinload
from app.module_workshops.models.models import Technician

class TechnicianRepository:
    def __init__(self, db: Session):
        self.db = db


    def create(self, technician: Technician) -> Technician:
        self.db.add(technician)
        self.db.commit()
        self.db.refresh(technician)
        return technician

    def get_by_id(self, technician_id: uuid.UUID) -> Optional[Technician]:
        return self.db.query(Technician).options(
            selectinload(Technician.roles)
        ).filter(Technician.id == technician_id).first()

    def get_by_workshop(self, workshop_id: uuid.UUID) -> List[Technician]:
        return self.db.query(Technician).options(
            selectinload(Technician.roles)
        ).filter(
            Technician.workshop_id == workshop_id, 
            Technician.is_active == True
        ).all()

    def update(self, technician: Technician) -> Technician:
        self.db.commit()
        self.db.refresh(technician)
        return technician

    def delete(self, technician: Technician):
        # Soft delete
        technician.is_active = False
        self.db.commit()
        self.db.refresh(technician)

    def get_by_workshop(self, workshop_id: uuid.UUID) -> List[Technician]:
        return self.db.query(Technician).options(
            selectinload(Technician.roles)
        ).filter(
            Technician.workshop_id == workshop_id, 
            Technician.is_active == True
        ).all()

    def update(self, technician: Technician) -> Technician:
        self.db.commit()
        self.db.refresh(technician)
        return technician

    def delete(self, technician: Technician):
        # Soft delete
        technician.is_active = False
        self.db.commit()
        self.db.refresh(technician)

def get_available_technician(db: Session, workshop_id: uuid.UUID) -> Optional[Technician]:
    return db.query(Technician).filter(
        Technician.workshop_id == workshop_id,
        Technician.is_active == True,
        Technician.is_available == True
    ).first()
