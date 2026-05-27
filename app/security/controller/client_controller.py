from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.dto.client_dtos import ClientCreateDTO, ClientResponseDTO, ClientUpdateDTO
from app.security.service.client_service import ClientService
from app.security.config.security import require_permission

router = APIRouter(prefix="/api/clients", tags=["Clients"])

_allowed = Depends(require_permission("users:read"))


@router.get("/me", response_model=ClientResponseDTO, status_code=status.HTTP_200_OK)
def get_my_client_profile(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("vehicles:create")),
):
    """Devuelve el perfil de cliente del usuario autenticado (rol client requerido)."""
    return ClientService(db).get_client_by_id(current_user.id)


@router.post("/", response_model=ClientResponseDTO, status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreateDTO, db: Session = Depends(get_db)):
    """Crea un usuario con rol 'client' + su perfil de cliente. Endpoint público (registro)."""
    return ClientService(db).create_client(data)


@router.get("/", response_model=list[ClientResponseDTO], status_code=status.HTTP_200_OK, dependencies=[_allowed])
def get_all_clients(db: Session = Depends(get_db)):
    return ClientService(db).get_all_clients()


@router.get("/{client_id}", response_model=ClientResponseDTO, status_code=status.HTTP_200_OK, dependencies=[_allowed])
def get_client(client_id: UUID, db: Session = Depends(get_db)):
    return ClientService(db).get_client_by_id(client_id)


@router.put("/{client_id}", response_model=ClientResponseDTO, status_code=status.HTTP_200_OK, dependencies=[_allowed])
def update_client(client_id: UUID, data: ClientUpdateDTO, db: Session = Depends(get_db)):
    return ClientService(db).update_client(client_id, data)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_allowed])
def delete_client(client_id: UUID, db: Session = Depends(get_db)):
    ClientService(db).delete_client(client_id)
