import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr

class TechnicianBase(BaseModel):
    name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    is_available: bool = True

class TechnicianCreate(TechnicianBase):
    password: str = Field(..., min_length=6)

class TechnicianUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_available: Optional[bool] = None

class TechnicianResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    is_available: bool
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    workshop_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
