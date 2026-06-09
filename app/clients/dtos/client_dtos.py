from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.users.dtos.user_dtos import UserBase


class ClientCreateDTO(BaseModel):
    user: UserBase
    password: str

    address: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None


class ClientUpdateDTO(BaseModel):
    user: UserBase | None = None
    password: str | None = None
    is_active: bool | None = None

    address: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None


class ClientResponseDTO(BaseModel):
    id: UUID
    username: str
    name: str
    last_name: str
    email: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    address: str | None
    insurance_provider: str | None
    insurance_policy_number: str | None
    total_request: int | None

    class Config:
        from_attributes = True
