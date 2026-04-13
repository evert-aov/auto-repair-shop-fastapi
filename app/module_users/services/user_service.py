import random
from uuid import UUID
import bcrypt

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.module_users.dtos.user_dtos import UserCreateDto, UserUpdateDto
from app.module_users.models.models import User
from app.module_users.repositories import user_repository, role_repository


# ── Utilidades de contraseña ─────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ── Generar Username ──────────────────────────────────────────────────────────

def _generate_username(db: Session) -> str:
    while True:
        username = f"user{random.randint(1000, 9999)}"
        if not user_repository.exists_user_by_username(db, username):
            return username


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_roles(db: Session, role_ids: list[int]):
    """Devuelve los objetos Role correspondientes a los IDs; lanza 404 si alguno no existe."""
    roles = []
    for rid in role_ids:
        role = role_repository.get_role_by_id(db, rid)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rol con id {rid} no encontrado",
            )
        roles.append(role)
    return roles


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_user(db: Session, data: UserCreateDto) -> User:
    if user_repository.get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El email '{data.email}' ya está registrado",
        )

    user = User(
        username=_generate_username(db),
        name=data.name,
        last_name=data.last_name,
        email=data.email,
        password=get_password_hash(data.password),
        phone=data.phone,
    )

    # Asignar roles si vienen en el request
    if data.role_ids:
        user.roles = _resolve_roles(db, data.role_ids)

    return user_repository.save_user(db, user)


def get_all_users(db: Session) -> list[User]:
    return user_repository.get_all_users(db)


def get_user_by_id(db: Session, user_id: UUID) -> User:
    user = user_repository.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return user


def update_user(db: Session, user_id: UUID, data: UserUpdateDto) -> User:
    user = get_user_by_id(db, user_id)
    if data.name is not None:
        user.name = data.name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.phone is not None:
        user.phone = data.phone
    if data.password is not None:
        user.password = get_password_hash(data.password)
    if data.is_active is not None:
        user.is_active = data.is_active

    # Reemplazar roles si vienen en el request
    if data.role_ids is not None:
        user.roles = _resolve_roles(db, data.role_ids)

    return user_repository.save_user(db, user)


def delete_user(db: Session, user_id: UUID) -> None:
    user = get_user_by_id(db, user_id)
    db.delete(user)
    db.commit()
