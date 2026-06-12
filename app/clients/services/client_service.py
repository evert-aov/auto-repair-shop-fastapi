from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.audit import auditable
from app.clients.audit_mappers import client_to_audit_map, client_from_dto
from app.clients.dtos.client_dtos import ClientCreateDTO, ClientUpdateDTO, ClientResponseDTO
from app.clients.models import Client
from app.clients.repositories.client_repository import ClientRepository
from app.users.repositories.user_repository import UserRepository
from app.users.repositories.role_repository import RoleRepository
from app.users.services.user_service import UserService
from app.config.mail.email_service import email_service
from app.config.mail.code_store import code_store

ROLE_CLIENT = "client"


class ClientService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.client_repository = ClientRepository(db)
        self.user_repository = UserRepository(db)
        self.role_repository = RoleRepository(db)
        self.user_service = UserService(db)

    def get_entity(self, id: UUID) -> Client | None:
        return self.client_repository.get_by_id(id)

    def to_audit_map(self, entity: Client) -> dict[str, Any]:
        return client_to_audit_map(entity)

    def to_audit_map_from_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, ClientResponseDTO):
            return client_from_dto(result)
        if isinstance(result, Client):
            return client_to_audit_map(result)
        return {}

    @auditable(resource_type="CLIENT", action_type="CREATE")
    def create_client(self, data: ClientCreateDTO) -> Client:
        # 1. Verificar código de verificación (previene registros sin verificar email)
        key = f"verification_code:{data.user.email}"
        saved_code = code_store.get(key)
        if saved_code is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código de verificación expirado o no solicitado. Solicita uno nuevo.",
            )

        # 2. Validar que email no exista
        if self.user_repository.get_by_email(data.user.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El email '{data.user.email}' ya está registrado",
            )

        # 3. Obtener rol "client"
        role = self.role_repository.get_by_name(ROLE_CLIENT)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rol 'client' no encontrado. Ejecuta el seed primero.",
            )

        # 4. Crear el Client directamente (hereda de User via joined-table inheritance)
        client = Client(
            username=self.user_service.generate_username(),
            name=data.user.name,
            last_name=data.user.last_name,
            email=data.user.email,
            password=UserService.hash_password(data.password),
            phone=data.user.phone,
            address=data.address,
            insurance_provider=data.insurance_provider,
            insurance_policy_number=data.insurance_policy_number,
            total_request=0,
        )
        client.roles = [role]

        client = self.client_repository.save(client)

        # 5. Eliminar código de verificación (uso único)
        code_store.delete(key)

        # 6. Enviar email de confirmación (opcional, en prod)
        email_service.send_new_password(client.email, client.username, data.password)

        return client

    def get_all_clients(self) -> list[Client]:
        return self.client_repository.get_all()

    def get_client_by_id(self, client_id: UUID) -> Client:
        client = self.client_repository.get_by_id(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado",
            )
        return client

    @auditable(resource_type="CLIENT", action_type="UPDATE", id_param_name="client_id")
    def update_client(self, client_id: UUID, data: ClientUpdateDTO) -> Client:
        client = self.get_client_by_id(client_id)

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

        return self.client_repository.save(client)

    @auditable(resource_type="CLIENT", action_type="DELETE", id_param_name="client_id")
    def delete_client(self, client_id: UUID) -> None:
        client = self.get_client_by_id(client_id)
        self.client_repository.delete(client)
