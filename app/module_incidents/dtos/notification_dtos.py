import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class NotificationDto(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    incident_id: Optional[uuid.UUID] = None
    type: str
    title: str
    body: str
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime] = None
    payment_status: Optional[str] = "pending"

    class Config:
        from_attributes = True

class NotificationReadDto(BaseModel):
    id: uuid.UUID
