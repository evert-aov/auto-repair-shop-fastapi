from datetime import datetime
from pydantic import BaseModel


class PermissionBase(BaseModel):
    name: str
    description: str | None = None
    action: str


class PermissionCreateDto(PermissionBase):
    pass


class PermissionUpdateDto(BaseModel):
    name: str | None = None
    description: str | None = None
    action: str | None = None


class PermissionResponseDto(PermissionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
