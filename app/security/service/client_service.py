from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.security.dto.client_dtos import ClientCreateDTO, ClientUpdateDTO
from app.security.models import Client
from app.security.repository import client_repository
from app.module_users.repositories import user_repository, role_repository
from app.module_users.services.user_service import get_password_hash, _generate_username

ROLE_CLIENT = "client"


def create_client(db: Session, data: ClientCreateDTO) -> Client:
    # 1. Validar que email no exista
    if user_repository.get_user_by_email(db, data.user.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El email '{data.user.email}' ya está registrado",
        )

    # 2. Obtener rol "client"
    role = role_repository.get_role_by_name(db, ROLE_CLIENT)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Rol 'client' no encontrado. Ejecuta el seed primero.",
        )

    # 3. Crear el Client directamente (hereda dye User via joined-table inheritance)
    #    SQLAlchemy inserta automáticamente en 'users' y 'clients'.
    client = Client(
        username=_generate_username(db),
        name=data.user.name,
        last_name=data.user.last_name,
        email=data.user.email,
        password=get_password_hash(data.password),
        phone=data.user.phone,
        address=data.address,
        insurance_provider=data.insurance_provider,
        insurance_policy_number=data.insurance_policy_number,
        total_request=0,
    )
    client.roles = [role]

    return client_repository.save_client(db, client)


def get_all_clients(db: Session) -> list[Client]:
    return client_repository.get_all_clients(db)


def get_client_by_id(db: Session, client_id: UUID) -> Client:
    client = client_repository.get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )
    return client


def update_client(db: Session, client_id: UUID, data: ClientUpdateDTO) -> Client:
    client = get_client_by_id(db, client_id)

    # Campos del usuario base
    if data.user.name is not None:
        client.name = data.user.name
    if data.user.last_name is not None:
        client.last_name = data.user.last_name
    if data.user.phone is not None:
        client.phone = data.user.phone

    # Campos propios del cliente
    if data.address is not None:
        client.address = data.address
    if data.insurance_provider is not None:
        client.insurance_provider = data.insurance_provider
    if data.insurance_policy_number is not None:
        client.insurance_policy_number = data.insurance_policy_number

    return client_repository.save_client(db, client)


def delete_client(db: Session, client_id: UUID) -> None:
    client = get_client_by_id(db, client_id)
    client_repository.delete_client(db, client)