from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.module_users.dtos.role_dtos import RoleResponseDto


class UserBase(BaseModel):
    email: EmailStr
    name: str
    last_name: str
    phone: str | None = None


class UserCreateDto(UserBase):
    password: str
    role_ids: list[int] = []


class UserUpdateDto(BaseModel):
    name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    password: str | None = None
    is_active: bool | None = None
    role_ids: list[int] | None = None


class UserResponseDto(UserBase):
    id: UUID
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: list[RoleResponseDto] = []

    class Config:
        from_attributes = True
