import uuid
from datetime import datetime
from pydantic import BaseModel


class CreateOrderDTO(BaseModel):
    incident_id: uuid.UUID


class OrderCreatedDTO(BaseModel):
    payment_id: uuid.UUID
    order_id: str
    approve_url: str
    amount: float
    currency: str


class PaymentResponseDTO(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    status: str
    gross_amount: float
    commission_amount: float
    net_amount: float
    currency: str
    payment_method: str
    gateway_transaction_id: str | None
    paid_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
