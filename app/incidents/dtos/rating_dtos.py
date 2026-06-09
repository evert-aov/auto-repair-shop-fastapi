from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RatingCreateDto(BaseModel):
    incident_id: UUID
    score: int = Field(..., ge=1, le=5)
    response_time_score: Optional[int] = Field(None, ge=1, le=5)
    quality_score: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


class RatingResponseDto(BaseModel):
    id: UUID
    incident_id: UUID
    client_id: UUID
    workshop_id: UUID
    score: int
    response_time_score: Optional[int]
    quality_score: Optional[int]
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
