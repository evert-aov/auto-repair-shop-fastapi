from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.module_users.dtos.role_dtos import (
    RoleCreateDto,
    RoleDetailDto,
    RoleUpdateDto,
)
from app.module_users.services import role_service
from app.security.config.security import require_role

router = APIRouter(prefix="/api/roles", tags=["Roles"])

# Solo admin puede gestionar roles
_admin_only = Depends(require_role("admin"))


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=RoleDetailDto, status_code=status.HTTP_201_CREATED, dependencies=[_admin_only])
def create_role(data: RoleCreateDto, db: Session = Depends(get_db)):
    return role_service.create_role(db, data)


@router.get("/", response_model=list[RoleDetailDto], status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def get_all_roles(db: Session = Depends(get_db)):
    return role_service.get_all_roles(db)


@router.get("/{role_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def get_role(role_id: int, db: Session = Depends(get_db)):
    return role_service.get_role_by_id(db, role_id)


@router.put("/{role_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def update_role(role_id: int, data: RoleUpdateDto, db: Session = Depends(get_db)):
    return role_service.update_role(db, role_id, data)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin_only])
def delete_role(role_id: int, db: Session = Depends(get_db)):
    role_service.delete_role(db, role_id)


# ── Permisos del rol ──────────────────────────────────────────────────────────

@router.post("/{role_id}/permissions/{permission_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def assign_permission(role_id: int, permission_id: int, db: Session = Depends(get_db)):
    """Asigna un permiso a un rol."""
    return role_service.assign_permission_to_role(db, role_id, permission_id)


@router.delete("/{role_id}/permissions/{permission_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def remove_permission(role_id: int, permission_id: int, db: Session = Depends(get_db)):
    """Quita un permiso de un rol."""
    return role_service.remove_permission_from_role(db, role_id, permission_id)


# ── Roles de usuario ──────────────────────────────────────────────────────────

@router.post("/users/{user_id}/roles/{role_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def assign_role_to_user(user_id: UUID, role_id: int, db: Session = Depends(get_db)):
    """Asigna un rol a un usuario."""
    return role_service.assign_role_to_user(db, user_id, role_id)


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin_only])
def remove_role_from_user(user_id: UUID, role_id: int, db: Session = Depends(get_db)):
    """Quita un rol de un usuario."""
    role_service.remove_role_from_user(db, user_id, role_id)
