from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.module_users.dtos.permission_dtos import (
    PermissionCreateDto,
    PermissionResponseDto,
    PermissionUpdateDto,
)
from app.module_users.services import permission_service
from app.security.config.security import require_role

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])

# Solo admin puede gestionar permisos
_admin_only = Depends(require_role("admin"))


@router.post("/", response_model=PermissionResponseDto, status_code=status.HTTP_201_CREATED, dependencies=[_admin_only])
def create_permission(data: PermissionCreateDto, db: Session = Depends(get_db)):
    return permission_service.create_permission(db, data)


@router.get("/", response_model=list[PermissionResponseDto], status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def get_all_permissions(db: Session = Depends(get_db)):
    return permission_service.get_all_permissions(db)


@router.get("/{permission_id}", response_model=PermissionResponseDto, status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def get_permission(permission_id: int, db: Session = Depends(get_db)):
    return permission_service.get_permission_by_id(db, permission_id)


@router.put("/{permission_id}", response_model=PermissionResponseDto, status_code=status.HTTP_200_OK, dependencies=[_admin_only])
def update_permission(permission_id: int, data: PermissionUpdateDto, db: Session = Depends(get_db)):
    return permission_service.update_permission(db, permission_id, data)


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin_only])
def delete_permission(permission_id: int, db: Session = Depends(get_db)):
    permission_service.delete_permission(db, permission_id)
