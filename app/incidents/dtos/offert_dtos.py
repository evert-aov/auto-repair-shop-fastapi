import uuid

from pydantic import BaseModel


class AcceptOfferDto(BaseModel):
    """Request body para aceptar una oferta"""
    technician_id: uuid.UUID | None = None
    estimated_arrival_min: int | None = None


class RejectOfferDto(BaseModel):
    """Request body para rechazar una oferta"""
    rejection_reason: str | None = None  # busy | far_from_zone | no_parts | etc.


class CompleteOfferDto(BaseModel):
    """Request body para completar una oferta"""
    cost: float | None = None


class OfferResponseDto(BaseModel):
    """Response estándar para ofertas"""
    offer_id: uuid.UUID
    incident_id: uuid.UUID
    workshop_id: uuid.UUID
    status: str
    message: str

    class Config:
        from_attributes = True
