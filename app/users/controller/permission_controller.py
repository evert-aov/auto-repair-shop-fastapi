from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.users.dtos.permission_dtos import (
    PermissionCreateDto,
    PermissionResponseDto,
    PermissionUpdateDto,
)
from app.users.services.permission_service import PermissionService
from app.security.config.security import require_permission

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])


@router.post("/", response_model=PermissionResponseDto, status_code=status.HTTP_201_CREATED)
def create_permission(
    data: PermissionCreateDto,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("permissions:create"))
):
    return PermissionService(db).create_permission(data)


@router.get("/", response_model=list[PermissionResponseDto], status_code=status.HTTP_200_OK)
def get_all_permissions(
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("permissions:read"))
):
    return PermissionService(db).get_all_permissions()


@router.get("/{permission_id}", response_model=PermissionResponseDto, status_code=status.HTTP_200_OK)
def get_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("permissions:read"))
):
    return PermissionService(db).get_permission_by_id(permission_id)


@router.put("/{permission_id}", response_model=PermissionResponseDto, status_code=status.HTTP_200_OK)
def update_permission(
    permission_id: int,
    data: PermissionUpdateDto,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("permissions:update"))
):
    return PermissionService(db).update_permission(permission_id, data)


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("permissions:delete"))
):
    PermissionService(db).delete_permission(permission_id)
