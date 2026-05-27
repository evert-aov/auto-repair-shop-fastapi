import uuid
from typing import List

import bcrypt
from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.users.models.role import Role
from app.users.repositories.user_repository import UserRepository
from app.users.services.user_service import UserService
from app.workshops.dtos.technician_dto import TechnicianCreate, TechnicianUpdate
from app.workshops.models import Technician
from app.workshops.repositories.technician_repository import TechnicianRepository


class TechnicianService:
    def __init__(self, db: Session):
        self.repository = TechnicianRepository(db)
        self.user_repository = UserRepository(db)
        self.user_service = UserService(db)
        self.db = db

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
        owner_profile = self.user_repository.get_by_id(owner_user_id)
        if not owner_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perfil de dueño de taller no encontrado",
            )
        if not any(role.name == "workshop_owner" for role in owner_profile.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario no es dueño de taller",
            )
        return owner_profile.workshop_id

    # ── CRUD ─────────────────────────────────────────────────────────────────────

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

        return self.repository.create(technician)

    def get_by_id_and_workshop(self, technician_id: uuid.UUID, workshop_id: uuid.UUID) -> Technician:
        return self._get_technician_or_404(technician_id, workshop_id)

    def get_all_by_workshop(self, workshop_id: uuid.UUID) -> List[Technician]:
        return self.repository.get_by_workshop(workshop_id)

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

    def delete(self, workshop_id: uuid.UUID, technician_id: uuid.UUID) -> None:
        technician = self._get_technician_or_404(technician_id, workshop_id)
        self.repository.delete(technician)