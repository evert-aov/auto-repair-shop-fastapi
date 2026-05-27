from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.users.dtos.role_dtos import (
    RoleCreateDto,
    RoleDetailDto,
    RoleUpdateDto,
)
from app.users.services.role_service import RoleService
from app.security.config.security import require_permission

router = APIRouter(prefix="/api/roles", tags=["Roles"])


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=RoleDetailDto, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreateDto,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("roles:create"))
):
    return RoleService(db).create_role(data)


@router.get("/", response_model=list[RoleDetailDto], status_code=status.HTTP_200_OK)
def get_all_roles(
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("roles:read"))
):
    return RoleService(db).get_all_roles()


@router.get("/{role_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("roles:read"))
):
    return RoleService(db).get_role_by_id(role_id)


@router.put("/{role_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK)
def update_role(
    role_id: int,
    data: RoleUpdateDto,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("roles:update"))
):
    return RoleService(db).update_role(role_id, data)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("roles:delete"))
):
    RoleService(db).delete_role(role_id)


# ── Permisos del rol ──────────────────────────────────────────────────────────

@router.post("/{role_id}/permissions/{permission_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK)
def assign_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("roles:update"))
):
    """Asigna un permiso a un rol."""
    return RoleService(db).assign_permission_to_role(role_id, permission_id)


@router.delete("/{role_id}/permissions/{permission_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK)
def remove_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("roles:update"))
):
    """Quita un permiso de un rol."""
    return RoleService(db).remove_permission_from_role(role_id, permission_id)


# ── Roles de usuario ──────────────────────────────────────────────────────────

@router.post("/users/{user_id}/roles/{role_id}", response_model=RoleDetailDto, status_code=status.HTTP_200_OK)
def assign_role_to_user(
    user_id: UUID,
    role_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("users:update"))
):
    """Asigna un rol a un usuario."""
    return RoleService(db).assign_role_to_user(user_id, role_id)


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_role_from_user(
    user_id: UUID,
    role_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("users:update"))
):
    """Quita un rol de un usuario."""
    RoleService(db).remove_role_from_user(user_id, role_id)
