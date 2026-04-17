from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.dto.client_dtos import ClientCreateDTO, ClientResponseDTO
from app.module_users.dtos.user_dtos import UserResponseDto
from app.security.config.security import get_current_user, require_role
from app.security.dto.auth_dtos import LoginRequestDto, LoginResponseDto
from app.security.service import auth_service, client_service

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponseDto)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    data = LoginRequestDto(username=form.username, password=form.password)
    return auth_service.login(db, data)
@router.post("/register_client", response_model=ClientResponseDTO, status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreateDTO, db: Session = Depends(get_db)):
    """Registrar un cliente. Endpoint público (registro)."""
    return client_service.create_client(db, data)

@router.get("/me", response_model=UserResponseDto, status_code=status.HTTP_200_OK)
def me(current_user=Depends(get_current_user)) -> UserResponseDto:
    """Devuelve los datos del usuario autenticado a partir del JWT."""
    return current_user


# ── Endpoints protegidos por rol (ejemplos de uso de require_role) ──────────

@router.get(
    "/client/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del cliente",
)
def client_area(current_user=Depends(require_role("client"))):
    return {"message": f"Bienvenido cliente {current_user.username}"}


@router.get(
    "/workshop/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del dueño de taller",
)
def workshop_area(current_user=Depends(require_role("workshop_owner"))):
    return {"message": f"Bienvenido dueño de taller {current_user.username}"}


@router.get(
    "/technician/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del técnico",
)
def technician_area(current_user=Depends(require_role("technician"))):
    return {"message": f"Bienvenido técnico {current_user.username}"}


@router.get(
    "/admin/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Área exclusiva del administrador",
)
def admin_area(current_user=Depends(require_role("admin"))):
    return {"message": f"Bienvenido administrador {current_user.username}"}