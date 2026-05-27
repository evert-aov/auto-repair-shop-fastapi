from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.users.dtos.role_dtos import RoleCreateDto, RoleUpdateDto
from app.users.models.role import Role
from app.users.repositories.role_repository import RoleRepository
from app.users.repositories.permission_repository import PermissionRepository
from app.users.repositories.user_repository import UserRepository


class RoleService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.role_repository = RoleRepository(db)
        self.permission_repository = PermissionRepository(db)
        self.user_repository = UserRepository(db)

    def _resolve_permissions(self, permission_ids: list[int]):
        """Devuelve los objetos Permission correspondientes; lanza 404 si alguno no existe."""
        permissions = []
        for pid in permission_ids:
            perm = self.permission_repository.get_by_id(pid)
            if not perm:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Permiso con id {pid} no encontrado",
                )
            permissions.append(perm)
        return permissions

    def create_role(self, dto: RoleCreateDto) -> Role:
        if self.role_repository.exists_by_name(dto.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un rol con el nombre '{dto.name}'",
            )
        role = Role(name=dto.name, description=dto.description)

        # Asignar permisos si vienen en el request
        if dto.permission_ids:
            role.permissions = self._resolve_permissions(dto.permission_ids)

        return self.role_repository.save(role)

    def get_all_roles(self) -> list[Role]:
        return self.role_repository.get_all()

    def get_role_by_id(self, role_id: int) -> Role:
        role = self.role_repository.get_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rol no encontrado",
            )
        return role

    def update_role(self, role_id: int, dto: RoleUpdateDto) -> Role:
        role = self.get_role_by_id(role_id)

        if dto.name is not None:
            existing = self.role_repository.get_by_name(dto.name)
            if existing and existing.id != role_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un rol con el nombre '{dto.name}'",
                )
            role.name = dto.name

        if dto.description is not None:
            role.description = dto.description

        # Reemplazar permisos si vienen en el request
        if dto.permission_ids is not None:
            role.permissions = self._resolve_permissions(dto.permission_ids)

        return self.role_repository.save(role)

    def delete_role(self, role_id: int) -> None:
        role = self.get_role_by_id(role_id)
        self.role_repository.delete(role)

    def assign_permission_to_role(self, role_id: int, permission_id: int) -> Role:
        role = self.get_role_by_id(role_id)
        permission = self.permission_repository.get_by_id(permission_id)
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permiso no encontrado",
            )
        if permission in role.permissions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El permiso ya está asignado a este rol",
            )
        role.permissions.append(permission)
        return self.role_repository.save(role)

    def remove_permission_from_role(self, role_id: int, permission_id: int) -> Role:
        role = self.get_role_by_id(role_id)
        permission = self.permission_repository.get_by_id(permission_id)
        if not permission or permission not in role.permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El permiso no está asignado a este rol",
            )
        role.permissions.remove(permission)
        return self.role_repository.save(role)

    def assign_role_to_user(self, user_id: UUID, role_id: int) -> Role:
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        role = self.get_role_by_id(role_id)
        if role in user.roles:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El rol ya está asignado a este usuario",
            )
        user.roles.append(role)
        self.db.commit()
        self.db.refresh(user)
        return role

    def remove_role_from_user(self, user_id: UUID, role_id: int) -> None:
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        role = self.get_role_by_id(role_id)
        if role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El rol no está asignado a este usuario",
            )
        user.roles.remove(role)
        self.db.commit()
