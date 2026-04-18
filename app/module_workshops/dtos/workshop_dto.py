import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from app.module_workshops.dtos.specialty_dto import SpecialtyResponse

class WorkshopBase(BaseModel):
    name: str = Field(..., max_length=150)
    business_name: str = Field(..., max_length=255)
    ruc_nit: str = Field(..., max_length=50)
    address: str = Field(...) # TEXT
    phone: str = Field(..., max_length=50)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class WorkshopCreate(WorkshopBase):
    pass

class WorkshopRegisterPublic(WorkshopBase):
    # This DTO is used when a workshop owner registers publicly
    email: EmailStr # Used for the owner's account (User/Technician)
    owner_name: str = Field(..., max_length=100)
    owner_last_name: str = Field(..., max_length=100)
    owner_phone: str = Field(..., max_length=20)
    owner_password: str = Field(..., min_length=6)
    # The actual workshop email is in `email`, and the owner email could be the same
    # But usually owner wants their own email, let's reuse `email` for the owner to keep it simple,
    # as per instructions: "email (el mismo que el del taller)".

class WorkshopUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    business_name: Optional[str] = Field(None, max_length=255)
    ruc_nit: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None)
    phone: Optional[str] = Field(None, max_length=50)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    specialty_ids: Optional[List[int]] = None

class WorkshopAdminUpdate(WorkshopUpdate):
    is_available: Optional[bool] = None
    is_verified: Optional[bool] = None
    commission_rate: Optional[float] = Field(None, ge=0.0)

class WorkshopResponse(WorkshopBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_user_id: uuid.UUID
    is_available: bool
    is_verified: bool
    is_active: bool
    commission_rate: float
    rating_avg: Optional[float] = None
    total_services: int
    rejection_count: int
    last_rejection_at: Optional[datetime] = None
    rejection_rate: float
    created_at: datetime
    updated_at: datetime
    specialties: List[SpecialtyResponse] = Field(default_factory=list)
    
    # New fields for Admin Detail View
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_phone: Optional[str] = None
    technicians_count: int = 0
