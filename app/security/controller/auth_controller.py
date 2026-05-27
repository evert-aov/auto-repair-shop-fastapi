from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.clients.dtos.client_dtos import ClientCreateDTO, ClientResponseDTO
from app.users.dtos.user_dtos import UserResponseDto
from app.security.config.security import get_current_user, require_permission
from app.security.dto.auth_dtos import LoginRequestDto, LoginResponseDto, ProfileUpdateDto
from app.security.service.auth_service import AuthService
from app.clients.services.client_service import ClientService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class FcmTokenDto(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponseDto)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    data = LoginRequestDto(username=form.username, password=form.password)
    return AuthService(db).login(data)


@router.post("/register_client", response_model=ClientResponseDTO, status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreateDTO, db: Session = Depends(get_db)):
    """Registrar un cliente. Endpoint público (registro)."""
    return ClientService(db).create_client(data)


@router.get("/me", response_model=UserResponseDto, status_code=status.HTTP_200_OK)
def me(current_user=Depends(get_current_user)) -> UserResponseDto: # type: ignore
    """Devuelve los datos del usuario autenticado a partir del JWT."""
    return current_user


@router.get("/profile", status_code=status.HTTP_200_OK)
def get_profile(current_user=Depends(get_current_user)):
    """Devuelve el perfil del usuario autenticado. Clientes incluyen campos adicionales."""
    if current_user.type == "client":
        return ClientResponseDTO.model_validate(current_user)
    return UserResponseDto.model_validate(current_user)


@router.put("/profile", status_code=status.HTTP_200_OK)
def update_profile(
    data: ProfileUpdateDto,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Actualiza el perfil del usuario autenticado."""
    updated = AuthService(db).update_profile(current_user, data)
    if updated.type == "client":
        return ClientResponseDTO.model_validate(updated)
    return UserResponseDto.model_validate(updated)


@router.post("/fcm-token", status_code=status.HTTP_200_OK)
def register_fcm_token(
    data: FcmTokenDto,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Registra o actualiza el FCM token del dispositivo del usuario autenticado.
    Flutter y Angular deben llamar esto justo después del login.
    """
    current_user.fcm_token = data.token
    db.commit()
    return {"message": "FCM token registrado correctamente"}


# ── Endpoints protegidos por rol (ejemplos de uso de require_role) ──────────

@router.get(
    "/client/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del cliente",
)
def client_area(current_user=Depends(require_permission("vehicles:create"))):
    return {"message": f"Bienvenido cliente {current_user.username}"}


@router.get(
    "/workshop/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del dueño de taller",
)
def workshop_area(current_user=Depends(require_permission("workshops:update"))):
    return {"message": f"Bienvenido dueño de taller {current_user.username}"}


@router.get(
    "/technician/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del técnico",
)
def technician_area(current_user=Depends(require_permission("technicians:read"))):
    return {"message": f"Bienvenido técnico {current_user.username}"}


@router.get(
    "/admin/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del administrador",
)
def admin_area(current_user=Depends(require_permission("roles:read"))): # type: ignore
    return {"message": f"Bienvenido administrador {current_user.username}"}