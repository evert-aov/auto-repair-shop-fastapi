import logging
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.users.repositories.user_repository import UserRepository
from app.users.services.user_service import UserService
from app.clients.repositories.client_repository import ClientRepository
from app.security.config.security import create_access_token
from app.security.dto.auth_dtos import (
    LoginRequestDto, LoginResponseDto, ProfileUpdateDto, RoleDto,
    ForgotPasswordRequestDto, VerifyRecoveryCodeRequestDto,
    SendCodeRequestDto, SendCodeResponseDto,
)
from app.config.mail.code_store import code_store
from app.config.mail.email_service import email_service

logger = logging.getLogger(__name__)

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


class AuthService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)
        self.client_repository = ClientRepository(db)

    def _resolve_redirect(self, role_names: set[str]) -> str:
        """Devuelve la ruta de redirección según el rol de mayor jerarquía."""
        for role in ROLE_PRIORITY:
            if role in role_names:
                return REDIRECT_MAP[role]
        return "/app/dashboard"

    def login(self, data: LoginRequestDto) -> LoginResponseDto:
        user = self.user_repository.get_by_username(data.username)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta desactivada. Contacta al administrador.",
            )

        if not UserService.verify_password(data.password, user.password):
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

        # Extract unique permissions from all roles assigned to user
        permissions_actions = {p.action for r in user.roles for p in r.permissions}

        token = create_access_token(data={
            "sub": user.username,
            "user_id": str(user.id),
            "roles": list(role_names),
            "permissions": list(permissions_actions),
        })

        return LoginResponseDto(
            access_token=token,
            redirect_to=self._resolve_redirect(role_names),
            user_id=str(user.id),
            user_name=user.username,
            roles=[RoleDto.model_validate(r) for r in user.roles],
        )

    def update_profile(self, current_user, data: ProfileUpdateDto):
        if data.name is not None:
            current_user.name = data.name
        if data.last_name is not None:
            current_user.last_name = data.last_name
        if data.phone is not None:
            current_user.phone = data.phone
        if data.password is not None:
            current_user.password = UserService.hash_password(data.password)

        if current_user.type == "client":
            if data.address is not None:
                current_user.address = data.address
            if data.insurance_provider is not None:
                current_user.insurance_provider = data.insurance_provider
            if data.insurance_policy_number is not None:
                current_user.insurance_policy_number = data.insurance_policy_number
            return self.client_repository.save(current_user)

        return self.user_repository.update(current_user)

    def _is_dev(self) -> bool:
        return os.getenv("SPRING_PROFILES_ACTIVE", "") == "dev" or os.getenv("ENV", "") == "dev"

    def send_password_recovery_code(self, request: ForgotPasswordRequestDto) -> SendCodeResponseDto:
        email = request.email
        user = self.user_repository.get_by_email(email)

        if user is None:
            if self._is_dev():
                return SendCodeResponseDto(message="Usuario no encontrado (solo dev)", code=None)
            return SendCodeResponseDto(message="Si el correo existe, se enviará un código", code=None)

        key = f"recovery_code:{email}"
        code = code_store.generate_and_store(key)

        if self._is_dev():
            return SendCodeResponseDto(message="Código generado para pruebas", code=code)
        else:
            email_service.send_verification_code(email, code)
            return SendCodeResponseDto(message="Si el correo existe, se enviará un código", code=None)

    def reset_password(self, request: VerifyRecoveryCodeRequestDto) -> dict:
        email = request.email
        key = f"recovery_code:{email}"
        saved_code = code_store.get(key)

        if saved_code is None or saved_code != request.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El código de verificación es incorrecto o ha expirado.",
            )

        user = self.user_repository.get_by_email(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario no encontrado",
            )

        user.password = UserService.hash_password(request.new_password)
        self.user_repository.update(user)

        code_store.delete(key)

        return {"message": "Contraseña actualizada exitosamente."}

    def send_verification_code(self, request: SendCodeRequestDto) -> SendCodeResponseDto:
        email = request.email
        key = f"verification_code:{email}"
        code = code_store.generate_and_store(key)

        if self._is_dev():
            logger.info("Entorno dev: Código generado para %s: %s", email, code)
            return SendCodeResponseDto(message="Código generado para pruebas", code=code)
        else:
            sent = email_service.send_verification_code(email, code)
            if not sent:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al enviar el correo de verificación. Intente nuevamente.",
                )
            return SendCodeResponseDto(message="Código enviado exitosamente", code=None)