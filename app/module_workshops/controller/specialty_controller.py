from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.module_workshops.dtos.specialty_dto import (
    SpecialtyResponse, SpecialtyCreate, SpecialtyUpdate
)
from app.module_workshops.services.specialty_service import SpecialtyService
from app.security.config.security import require_role

router = APIRouter(prefix="/api/specialties", tags=["Specialties"])

@router.post("/", response_model=SpecialtyResponse, status_code=status.HTTP_201_CREATED)
def create_specialty(
    dto: SpecialtyCreate, 
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin"))
):
    """Admin only: Create a global specialty."""
    service = SpecialtyService(db)
    return service.create(dto)

@router.get("/", response_model=List[SpecialtyResponse], status_code=status.HTTP_200_OK)
def list_specialties(db: Session = Depends(get_db)):
    """Public/Authenticated: List all global specialties."""
    service = SpecialtyService(db)
    return service.get_all()

@router.get("/{specialty_id}", response_model=SpecialtyResponse, status_code=status.HTTP_200_OK)
def get_specialty(specialty_id: int, db: Session = Depends(get_db)):
    """Public/Authenticated: Get specialty details."""
    service = SpecialtyService(db)
    return service.get_by_id(specialty_id)

@router.put("/{specialty_id}", response_model=SpecialtyResponse, status_code=status.HTTP_200_OK)
def update_specialty(
    specialty_id: int,
    dto: SpecialtyUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin"))
):
    """Admin only: Update a global specialty."""
    service = SpecialtyService(db)
    return service.update(specialty_id, dto)

@router.delete("/{specialty_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_specialty(
    specialty_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin"))
):
    """Admin only: Delete a global specialty."""
    service = SpecialtyService(db)
    service.delete(specialty_id)
