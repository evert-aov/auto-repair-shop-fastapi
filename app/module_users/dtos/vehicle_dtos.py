from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.security.models import TransmissionType, FuelType


# ── Create / Update ──────────────────────────────────────────────────────────

class VehicleCreateDTO(BaseModel):
    client_id: UUID
    make: str
    model: str
    year: int
    license_plate: str
    color: str | None = None
    transmission_type: TransmissionType | None = None
    fuel_type: FuelType | None = None
    vin: str | None = None


class VehicleUpdateDTO(BaseModel):
    make: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    color: str | None = None
    transmission_type: TransmissionType | None = None
    fuel_type: FuelType | None = None
    vin: str | None = None
    is_active: bool | None = None


# ── Response ─────────────────────────────────────────────────────────────────

class VehicleResponseDTO(BaseModel):
    id: UUID
    client_id: UUID
    make: str
    model: str
    year: int
    license_plate: str
    color: str | None
    transmission_type: TransmissionType | None
    fuel_type: FuelType | None
    vin: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
