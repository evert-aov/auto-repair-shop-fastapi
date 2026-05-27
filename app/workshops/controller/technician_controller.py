import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.workshops.dtos.technician_dto import (
    TechnicianResponse, TechnicianCreate, TechnicianUpdate
)
from app.workshops.services.technician_service import TechnicianService
from app.security.config.security import require_permission, get_current_user

router = APIRouter(prefix="/api/technicians", tags=["Technicians"])


@router.post("/", response_model=TechnicianResponse, status_code=status.HTTP_201_CREATED)
def create_technician(
    dto: TechnicianCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _auth=Depends(require_permission("technicians:create")),
):
    """Owner only: Create a technician for their workshop."""
    service = TechnicianService(db)
    workshop_id = service.get_owner_workshop_id(current_user.id)
    return service.create(workshop_id, dto)


@router.get("/", response_model=List[TechnicianResponse], status_code=status.HTTP_200_OK)
def list_technicians(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _auth=Depends(require_permission("technicians:read")),
):
    """Owner only: List all technicians from their workshop."""
    service = TechnicianService(db)
    workshop_id = service.get_owner_workshop_id(current_user.id)
    return service.get_all_by_workshop(workshop_id)


@router.get("/available", response_model=List[TechnicianResponse], status_code=status.HTTP_200_OK)
def list_available_technicians(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _auth=Depends(require_permission("technicians:read")),
):
    """Owner only: List only AVAILABLE technicians (is_available=True) from their workshop."""
    service = TechnicianService(db)
    workshop_id = service.get_owner_workshop_id(current_user.id)
    all_techs = service.get_all_by_workshop(workshop_id)
    return [t for t in all_techs if t.is_available]


@router.get("/{technician_id}", response_model=TechnicianResponse, status_code=status.HTTP_200_OK)
def get_technician(
    technician_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _auth=Depends(require_permission("technicians:read")),
):
    """Owner only: Get technician details."""
    service = TechnicianService(db)
    workshop_id = service.get_owner_workshop_id(current_user.id)
    return service.get_by_id_and_workshop(technician_id, workshop_id)


@router.put("/{technician_id}", response_model=TechnicianResponse, status_code=status.HTTP_200_OK)
def update_technician(
    technician_id: uuid.UUID,
    dto: TechnicianUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _auth=Depends(require_permission("technicians:update")),
):
    """Owner only: Update technician details."""
    service = TechnicianService(db)
    workshop_id = service.get_owner_workshop_id(current_user.id)
    return service.update(workshop_id, technician_id, dto)


@router.delete("/{technician_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_technician(
    technician_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _auth=Depends(require_permission("technicians:delete")),
):
    """Owner only: Soft delete technician."""
    service = TechnicianService(db)
    workshop_id = service.get_owner_workshop_id(current_user.id)
    service.delete(workshop_id, technician_id)
