import random
from typing import Any
from uuid import UUID

import bcrypt
from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.audit import auditable
from app.users.audit_mappers import user_to_audit_map, user_from_dto
from app.users.dtos.user_dtos import UserCreateDto, UserUpdateDto, UserResponseDto
from app.users.models.user import User
from app.users.repositories.role_repository import RoleRepository
from app.users.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, db: Session) -> None:
        self.user_repository = UserRepository(db)
        self.role_repository = RoleRepository(db)

    def get_entity(self, id: UUID) -> User | None:
        return self.user_repository.get_by_id(id)

    def to_audit_map(self, entity: User) -> dict[str, Any]:
        return user_to_audit_map(entity)

    def to_audit_map_from_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, UserResponseDto):
            return user_from_dto(result)
        if isinstance(result, User):
            return user_to_audit_map(result)
        return {}

    # ── Utilidades de contraseña ─────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    # ── Generar Username ──────────────────────────────────────────────────────────

    def _generate_username(self) -> str:
        while True:
            username = f"user{random.randint(1000, 9999)}"
            if not self.user_repository.exists_by_username(username):
                return username

    def generate_username(self) -> str:
        return self._generate_username()

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _resolve_roles(self, role_ids: list[int]):
        """Devuelve los objetos Role correspondientes a los IDs; lanza 404 si alguno no existe."""
        roles = []
        for rid in role_ids:
            role = self.role_repository.get_by_id(rid)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Rol con id {rid} no encontrado",
                )
            roles.append(role)
        return roles

    def _get_user_or_404(self, user_id: UUID) -> User:
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        return user

    # ── CRUD ─────────────────────────────────────────────────────────────────────

    @auditable(resource_type="USER", action_type="CREATE")
    def create_user(self, data: UserCreateDto) -> User:
        if self.user_repository.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El email '{data.email}' ya está registrado",
            )

        user = User(
            username=self._generate_username(),
            name=data.name,
            last_name=data.last_name,
            email=data.email,
            password=self.hash_password(data.password),
            phone=data.phone,
        )

        if data.role_ids:
            user.roles = self._resolve_roles(data.role_ids)

        return self.user_repository.create(user)

    def get_all_users(self) -> list[User]:
        return self.user_repository.get_all()

    def get_user_by_id(self, user_id: UUID) -> User:
        return self._get_user_or_404(user_id)

    @auditable(resource_type="USER", action_type="UPDATE", id_param_name="user_id")
    def update_user(self, user_id: UUID, data: UserUpdateDto) -> User:
        user = self._get_user_or_404(user_id)

        if data.name is not None:
            user.name = data.name
        if data.last_name is not None:
            user.last_name = data.last_name
        if data.phone is not None:
            user.phone = data.phone
        if data.password is not None:
            user.password = self.hash_password(data.password)
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.role_ids is not None:
            user.roles = self._resolve_roles(data.role_ids)

        return self.user_repository.update(user)

    @auditable(resource_type="USER", action_type="DELETE", id_param_name="user_id")
    def delete_user(self, user_id: UUID) -> None:
        user = self._get_user_or_404(user_id)
        self.user_repository.delete(user)