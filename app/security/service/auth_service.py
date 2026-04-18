from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.module_users.repositories.user_repository import get_user_by_username
from app.module_users.services.user_service import verify_password
from app.security.config.security import create_access_token
from app.security.dto.auth_dtos import LoginRequestDto, LoginResponseDto, ProfileUpdateDto, RoleDto

ROLE_CLIENT = "client"
ROLE_WORKSHOP_OWNER = "workshop_owner"
ROLE_TECHNICIAN = "technician"
ROLE_ADMIN = "admin"

# Páginas destino por rol (rutas del frontend Angular / Flutter deep-link)
REDIRECT_MAP = {
    ROLE_CLIENT: "/app/client/dashboard",
    ROLE_WORKSHOP_OWNER: "/app/workshop/dashboard",
    ROLE_TECHNICIAN: "/app/technician/dashboard",
    ROLE_ADMIN: "/app/admin/dashboard",
}

# Prioridad cuando un usuario tiene varios roles (el de mayor jerarquía manda)
ROLE_PRIORITY = [ROLE_ADMIN, ROLE_WORKSHOP_OWNER, ROLE_TECHNICIAN, ROLE_CLIENT]

def _resolve_redirect(role_names: set[str]) -> str:
    """Devuelve la ruta de redirección según el rol de mayor jerarquía."""
    for role in ROLE_PRIORITY:
        if role in role_names:
            return REDIRECT_MAP[role]
    return "/app/dashboard"

def login(db: Session, data: LoginRequestDto) -> LoginResponseDto:
    user = get_user_by_username(db, data.username)

    if not user:
        raise  HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada. Contacta al administrador.",
        )

    if not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    role_names = {r.name for r in user.roles}

    if not role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sin roles asignados. Contacta al administrador.",
        )

    token = create_access_token(data={
        "sub": user.username,
        "user_id": str(user.id),
        "roles": list(role_names),
    })

    return LoginResponseDto(
        access_token=token,
        redirect_to=_resolve_redirect(role_names),
        user_id=str(user.id),
        user_name=user.username,
        roles=[RoleDto.model_validate(r) for r in user.roles],
    )


def update_profile(db: Session, current_user, data: ProfileUpdateDto):
    from app.module_users.services.user_service import get_password_hash
    from app.security.repository import client_repository
    from app.module_users.repositories import user_repository

    if data.name is not None:
        current_user.name = data.name
    if data.last_name is not None:
        current_user.last_name = data.last_name
    if data.phone is not None:
        current_user.phone = data.phone
    if data.password is not None:
        current_user.password = get_password_hash(data.password)

    if current_user.type == "client":
        if data.address is not None:
            current_user.address = data.address
        if data.insurance_provider is not None:
            current_user.insurance_provider = data.insurance_provider
        if data.insurance_policy_number is not None:
            current_user.insurance_policy_number = data.insurance_policy_number
        return client_repository.save_client(db, current_user)

    return user_repository.save_user(db, current_user)