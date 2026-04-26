import logging
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status
from app.module_workshops.repositories.workshop_repository import WorkshopRepository
from app.module_workshops.models.models import Workshop, Technician

logger = logging.getLogger(__name__)
from app.module_workshops.dtos.workshop_dto import WorkshopUpdate, WorkshopAdminUpdate, WorkshopRegisterPublic
from app.module_workshops.repositories.technician_repository import TechnicianRepository
from app.module_users.repositories import user_repository, role_repository
from app.module_users.services.user_service import get_password_hash, _generate_username
from app.module_workshops.repositories.specialty_repository import SpecialtyRepository

class WorkshopService:
    def __init__(self, db: Session):
        self.repository = WorkshopRepository(db)
        self.specialty_repo = SpecialtyRepository(db)
        self.technician_repo = TechnicianRepository(db)
        self.db = db

    def _get_owner_profile(self, owner_user_id: uuid.UUID) -> Technician:
        owner_profile = self.technician_repo.get_by_id(owner_user_id)
        if not owner_profile:
            raise HTTPException(status_code=404, detail="Perfil de taller no encontrado")
        if not any(role.name == "workshop_owner" for role in owner_profile.roles):
            raise HTTPException(status_code=403, detail="El usuario no es dueño de taller")
        return owner_profile

    def register_public(self, dto: WorkshopRegisterPublic) -> Workshop:
        # Verify email uniqueness for User (Technician inherits from User)
        if user_repository.get_user_by_email(self.db, dto.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El email '{dto.email}' ya está registrado"
            )

        owner_role = role_repository.get_role_by_name(self.db, "workshop_owner")
        technician_role = role_repository.get_role_by_name(self.db, "technician")
        if not owner_role or not technician_role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Roles requeridos ('workshop_owner' y 'technician') no existen en el sistema.",
            )

        try:
            owner_id = uuid.uuid4()
            workshop_id = uuid.uuid4()

            workshop = Workshop(
                id=workshop_id,
                owner_user_id=owner_id,
                name=dto.name,
                business_name=dto.business_name,
                ruc_nit=dto.ruc_nit,
                address=dto.address,
                phone=dto.phone,
                latitude=dto.latitude,
                longitude=dto.longitude,
                is_active=True,
                is_available=True,
                is_verified=False,
                commission_rate=10.0,
                rating_avg=0.0,
                total_services=0,
            )

            technician = Technician(
                id=owner_id,
                username=_generate_username(self.db),
                name=dto.owner_name,
                last_name=dto.owner_last_name,
                email=dto.email,
                password=get_password_hash(dto.owner_password),
                phone=dto.owner_phone,
                is_active=False,
                is_available=True,
                workshop_id=workshop_id,
            )
            technician.roles = [owner_role, technician_role]
            self.db.add_all([workshop, technician])
            self.db.commit()
            self.db.refresh(workshop)
        except Exception:
            self.db.rollback()
            raise

        return workshop

    def get_by_owner_user_id(self, owner_user_id: uuid.UUID) -> Workshop:
        owner_profile = self._get_owner_profile(owner_user_id)
        return self.get_by_id(owner_profile.workshop_id)

    def update_by_owner_user_id(self, owner_user_id: uuid.UUID, dto: WorkshopUpdate) -> Workshop:
        owner_profile = self._get_owner_profile(owner_user_id)
        return self.update_owner(owner_profile.workshop_id, dto)

    def get_by_id(self, workshop_id: uuid.UUID) -> Workshop:
        workshop = self.repository.get_by_id(workshop_id)
        if not workshop:
            raise HTTPException(status_code=404, detail="Workshop not found")
        
        # Populate owner info and tech count
        owner = None
        for tech in workshop.technicians:
            if any(role.name == "workshop_owner" for role in tech.roles):
                owner = tech
                break
        
        if owner:
            workshop.owner_name = f"{owner.name} {owner.last_name}"
            workshop.owner_email = owner.email
            workshop.owner_phone = owner.phone
        
        workshop.technicians_count = len(workshop.technicians)
        
        return workshop

    def get_all(self, verified_only: bool = None) -> List[Workshop]:
        return self.repository.get_all(verified_only)

    def update_admin(self, workshop_id: uuid.UUID, dto: WorkshopAdminUpdate) -> Workshop:
        workshop = self.get_by_id(workshop_id)
        if dto.name is not None:
            workshop.name = dto.name
        if dto.business_name is not None:
            workshop.business_name = dto.business_name
        if dto.ruc_nit is not None:
            workshop.ruc_nit = dto.ruc_nit
        if dto.address is not None:
            workshop.address = dto.address
        if dto.phone is not None:
            workshop.phone = dto.phone
        if dto.latitude is not None:
            workshop.latitude = dto.latitude
        if dto.longitude is not None:
            workshop.longitude = dto.longitude
        if dto.is_available is not None:
            workshop.is_available = dto.is_available
        if dto.is_verified is not None:
            workshop.is_verified = dto.is_verified
            # Synchronize owner activation status
            for tech in workshop.technicians:
                if any(role.name == "workshop_owner" for role in tech.roles):
                    tech.is_active = dto.is_verified
                    break
        if dto.commission_rate is not None:
            workshop.commission_rate = dto.commission_rate
            
        if dto.specialty_ids is not None:
            specialties = self.specialty_repo.get_by_ids(dto.specialty_ids)
            workshop.specialties = specialties
            
        return self.repository.update(workshop)

    def update_owner(self, workshop_id: uuid.UUID, dto: WorkshopUpdate) -> Workshop:
        workshop = self.get_by_id(workshop_id)
        if dto.name is not None:
            workshop.name = dto.name
        if dto.business_name is not None:
            workshop.business_name = dto.business_name
        if dto.ruc_nit is not None:
            workshop.ruc_nit = dto.ruc_nit
        if dto.address is not None:
            workshop.address = dto.address
        if dto.phone is not None:
            workshop.phone = dto.phone
        if dto.latitude is not None:
            workshop.latitude = dto.latitude
        if dto.longitude is not None:
            workshop.longitude = dto.longitude
            
        if dto.specialty_ids is not None:
            specialties = self.specialty_repo.get_by_ids(dto.specialty_ids)
            workshop.specialties = specialties
            
        return self.repository.update(workshop)

    def clear_cooldown(self, workshop_id: uuid.UUID) -> dict:
        """Admin: cancela el cooldown activo del taller anulando el rejected_at de las offers vigentes."""
        from app.module_incidents.models import WorkshopOffer, OfferStatus
        from app.module_incidents.services.assignment_service import _COOLDOWN_DURATIONS

        workshop = self.get_by_id(workshop_id)

        rejected_offers = (
            self.db.query(WorkshopOffer)
            .filter(
                WorkshopOffer.workshop_id == workshop_id,
                WorkshopOffer.status.in_([OfferStatus.REJECTED, OfferStatus.TIMEOUT]),
                WorkshopOffer.rejected_at.isnot(None),
            )
            .all()
        )

        now = datetime.now(timezone.utc)
        cleared = 0
        for offer in rejected_offers:
            reason = offer.rejection_reason or "no_reason"
            duration = _COOLDOWN_DURATIONS.get(reason, __import__("datetime").timedelta(hours=1))
            if now < offer.rejected_at + duration:
                offer.rejected_at = None
                cleared += 1

        self.db.commit()
        logger.info(
            f"[ADMIN] Cooldown limpiado para taller '{workshop.name}' ({workshop_id}) — "
            f"{cleared} offer(s) afectadas"
        )
        return {"workshop_id": str(workshop_id), "workshop_name": workshop.name, "offers_cleared": cleared}

    def delete(self, workshop_id: uuid.UUID) -> None:
        workshop = self.get_by_id(workshop_id)
        self.db.delete(workshop)
        self.db.commit()
