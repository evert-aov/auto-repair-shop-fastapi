from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.users.dtos.permission_dtos import PermissionCreateDto, PermissionUpdateDto
from app.users.models.permission import Permission
from app.users.repositories.permission_repository import PermissionRepository


class PermissionService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.permission_repository = PermissionRepository(db)

    def create_permission(self, dto: PermissionCreateDto) -> Permission:
        if self.permission_repository.get_by_name(dto.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un permiso con el nombre '{dto.name}'",
            )
        if self.permission_repository.get_by_action(dto.action):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un permiso con la acción '{dto.action}'",
            )
        permission = Permission(
            name=dto.name,
            description=dto.description,
            action=dto.action,
        )
        return self.permission_repository.save(permission)

    def get_all_permissions(self) -> list[Permission]:
        return self.permission_repository.get_all()

    def get_permission_by_id(self, permission_id: int) -> Permission:
        permission = self.permission_repository.get_by_id(permission_id)
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permiso no encontrado",
            )
        return permission

    def update_permission(self, permission_id: int, dto: PermissionUpdateDto) -> Permission:
        permission = self.get_permission_by_id(permission_id)

        if dto.name is not None:
            existing = self.permission_repository.get_by_name(dto.name)
            if existing and existing.id != permission_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un permiso con el nombre '{dto.name}'",
                )
            permission.name = dto.name

        if dto.action is not None:
            existing = self.permission_repository.get_by_action(dto.action)
            if existing and existing.id != permission_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un permiso con la acción '{dto.action}'",
                )
            permission.action = dto.action

        if dto.description is not None:
            permission.description = dto.description

        return self.permission_repository.save(permission)

    def delete_permission(self, permission_id: int) -> None:
        permission = self.get_permission_by_id(permission_id)
        self.permission_repository.delete(permission)
