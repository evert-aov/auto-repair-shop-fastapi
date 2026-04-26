import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.module_workshops.dtos.workshop_dto import (
    WorkshopResponse, WorkshopRegisterPublic, WorkshopUpdate, WorkshopAdminUpdate
)
from app.module_workshops.services.workshop_service import WorkshopService
from app.security.config.security import require_role

router = APIRouter(prefix="/api/workshops", tags=["Workshops"])
_admin_only = Depends(require_role("admin"))
_owner_only = Depends(require_role("workshop_owner"))

@router.post("/register", response_model=WorkshopResponse, status_code=status.HTTP_201_CREATED)
def register_workshop(dto: WorkshopRegisterPublic, db: Session = Depends(get_db)):
    """Public endpoint for workshop registration."""
    service = WorkshopService(db)
    return service.register_public(dto)

@router.get("/", response_model=List[WorkshopResponse], status_code=status.HTTP_200_OK)
def get_all_workshops(
    verified: bool | None = None,
    db: Session = Depends(get_db),
    current_user=_admin_only,
):
    """Admin only: List all workshops."""
    service = WorkshopService(db)
    return service.get_all(verified)

@router.get("/me", response_model=WorkshopResponse, status_code=status.HTTP_200_OK)
def get_my_workshop(
    db: Session = Depends(get_db),
    current_user=_owner_only,
):
    """Owner only: Get their own workshop details."""
    service = WorkshopService(db)
    return service.get_by_owner_user_id(current_user.id)

@router.get("/{workshop_id}", response_model=WorkshopResponse, status_code=status.HTTP_200_OK)
def get_workshop(
    workshop_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user=_admin_only,
):
    """Admin only: Get workshop details."""
    service = WorkshopService(db)
    return service.get_by_id(workshop_id)

@router.put("/me", response_model=WorkshopResponse, status_code=status.HTTP_200_OK)
def update_my_workshop(
    dto: WorkshopUpdate,
    db: Session = Depends(get_db),
    current_user=_owner_only,
):
    """Owner only: Update their own workshop details."""
    service = WorkshopService(db)
    return service.update_by_owner_user_id(current_user.id, dto)

@router.put("/{workshop_id}", response_model=WorkshopResponse, status_code=status.HTTP_200_OK)
def admin_update_workshop(
    workshop_id: uuid.UUID,
    dto: WorkshopAdminUpdate,
    db: Session = Depends(get_db),
    current_user=_admin_only,
):
    """Admin only: Update any workshop details (including verification)."""
    service = WorkshopService(db)
    return service.update_admin(workshop_id, dto)

@router.post("/{workshop_id}/clear-cooldown", status_code=status.HTTP_200_OK)
def clear_workshop_cooldown(
    workshop_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=_admin_only,
):
    """Admin only: Remove active cooldown from a workshop."""
    service = WorkshopService(db)
    return service.clear_cooldown(workshop_id)

@router.delete("/{workshop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workshop(
    workshop_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=_admin_only,
):
    """Admin only: Permanently delete a workshop."""
    service = WorkshopService(db)
    service.delete(workshop_id)
