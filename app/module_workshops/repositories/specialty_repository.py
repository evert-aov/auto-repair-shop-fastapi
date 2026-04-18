from typing import List, Optional
from sqlalchemy.orm import Session
from app.module_workshops.models.models import Specialty

class SpecialtyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, specialty: Specialty) -> Specialty:
        self.db.add(specialty)
        self.db.commit()
        self.db.refresh(specialty)
        return specialty

    def get_by_id(self, specialty_id: int) -> Optional[Specialty]:
        return self.db.query(Specialty).filter(Specialty.id == specialty_id).first()

    def get_all(self) -> List[Specialty]:
        return self.db.query(Specialty).all()
        
    def get_by_ids(self, ids: List[int]) -> List[Specialty]:
        return self.db.query(Specialty).filter(Specialty.id.in_(ids)).all()

    def update(self, specialty: Specialty) -> Specialty:
        self.db.commit()
        self.db.refresh(specialty)
        return specialty
        
    def delete(self, specialty: Specialty):
        self.db.delete(specialty)
        self.db.commit()
