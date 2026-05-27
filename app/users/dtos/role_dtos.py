from datetime import datetime
from pydantic import BaseModel
from app.users.dtos.permission_dtos import PermissionResponseDto


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreateDto(RoleBase):
    permission_ids: list[int] = []


class RoleUpdateDto(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_ids: list[int] | None = None


class RoleResponseDto(RoleBase):
    id: int
    create_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleDetailDto(RoleResponseDto):
    """Role with its permissions."""
    permissions: list[PermissionResponseDto] = []
