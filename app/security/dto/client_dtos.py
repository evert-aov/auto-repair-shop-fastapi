from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.module_users.dtos.user_dtos import UserBase


# ── Create / Update ──────────────────────────────────────────────────────────

class ClientCreateDTO(BaseModel):
    """Crea el cliente + su User base asociado (joined-table inheritance)."""
    # Datos del usuario base
    user: UserBase
    password: str

    # Datos propios del cliente
    address: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None


class ClientUpdateDTO(BaseModel):
    """Actualiza campos propios del cliente y/o del usuario base."""
    # Campos del usuario base
    user: UserBase | None = None
    password: str | None = None
    is_active: bool | None = None

    # Campos propios del cliente
    address: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None


# ── Response ─────────────────────────────────────────────────────────────────

class ClientResponseDTO(BaseModel):
    """Refleja todos los campos heredados de User + los propios de Client."""
    # Campos heredados de User (joined-table inheritance → flat)
    id: UUID
    username: str
    name: str
    last_name: str
    email: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Campos propios de Client
    address: str | None
    insurance_provider: str | None
    insurance_policy_number: str | None
    total_request: int | None

    class Config:
        from_attributes = True