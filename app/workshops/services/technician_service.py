import uuid
from typing import Any, List

import bcrypt
from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.audit import auditable
from app.users.models.role import Role
from app.users.repositories.user_repository import UserRepository
from app.users.services.user_service import UserService
from app.workshops.audit_mappers import technician_to_audit_map
from app.workshops.dtos.technician_dto import TechnicianCreate, TechnicianUpdate
from app.workshops.models import Technician
from app.workshops.repositories.technician_repository import TechnicianRepository
from app.config.mail.email_service import email_service


class TechnicianService:
    def __init__(self, db: Session):
        self.repository = TechnicianRepository(db)
        self.user_repository = UserRepository(db)
        self.user_service = UserService(db)
        self.db = db

    def get_entity(self, id: uuid.UUID) -> Technician | None:
        return self.repository.get_by_id(id)

    def to_audit_map(self, entity: Technician) -> dict[str, Any]:
        return technician_to_audit_map(entity)

    def to_audit_map_from_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, Technician):
            return technician_to_audit_map(result)
        return {}

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _get_technician_or_404(self, technician_id: uuid.UUID, workshop_id: uuid.UUID) -> Technician:
        technician = self.repository.get_by_id(technician_id)
        if not technician or technician.workshop_id != workshop_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Técnico no encontrado para este taller",
            )
        return technician

    def _get_technician_role(self) -> Role:
        role = self.db.query(Role).filter(Role.name == "technician").first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rol 'technician' no existe en el sistema",
            )
        return role

    # ── Owner ─────────────────────────────────────────────────────────────────────

    def get_owner_workshop_id(self, owner_user_id: uuid.UUID) -> uuid.UUID:
        from app.workshops.models.workshop import Workshop
        workshop = self.db.query(Workshop).filter(
            Workshop.owner_user_id == owner_user_id
        ).first()
        if not workshop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taller no encontrado para este propietario",
            )
        return workshop.id

    # ── CRUD ─────────────────────────────────────────────────────────────────────

    @auditable(resource_type="TECHNICIAN", action_type="CREATE")
    def create(self, workshop_id: uuid.UUID, dto: TechnicianCreate) -> Technician:
        if self.user_repository.get_by_email(dto.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El email '{dto.email}' ya está registrado",
            )

        technician = Technician(
            username=self.user_service.generate_username(),
            name=dto.name,
            last_name=dto.last_name,
            email=dto.email,
            password=self.user_service.hash_password(dto.password),
            phone=dto.phone,
            is_active=True,
            is_available=dto.is_available,
            workshop_id=workshop_id,
        )
        technician.roles = [self._get_technician_role()]

        technician = self.repository.create(technician)

        email_service.send_new_password(technician.email, technician.username, dto.password)

        return technician

    def get_by_id_and_workshop(self, technician_id: uuid.UUID, workshop_id: uuid.UUID) -> Technician:
        return self._get_technician_or_404(technician_id, workshop_id)

    def get_all_by_workshop(self, workshop_id: uuid.UUID) -> List[Technician]:
        return self.repository.get_by_workshop(workshop_id)

    @auditable(resource_type="TECHNICIAN", action_type="UPDATE", id_param_name="technician_id")
    def update(self, workshop_id: uuid.UUID, technician_id: uuid.UUID, dto: TechnicianUpdate) -> Technician:
        technician = self._get_technician_or_404(technician_id, workshop_id)

        if dto.name is not None:
            technician.name = dto.name
        if dto.last_name is not None:
            technician.last_name = dto.last_name
        if dto.phone is not None:
            technician.phone = dto.phone
        if dto.is_available is not None:
            technician.is_available = dto.is_available

        return self.repository.update(technician)

    @auditable(resource_type="TECHNICIAN", action_type="DELETE", id_param_name="technician_id")
    def delete(self, workshop_id: uuid.UUID, technician_id: uuid.UUID) -> None:
        technician = self._get_technician_or_404(technician_id, workshop_id)
        self.repository.delete(technician)