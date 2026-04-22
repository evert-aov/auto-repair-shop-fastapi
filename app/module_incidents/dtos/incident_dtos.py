from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class EvidenceDto(BaseModel):
    evidence_type: str
    file_url: str
    transcription: Optional[str] = None


class IncidentCreateDto(BaseModel):
    description: str
    vehicle_id: UUID
    latitude: float
    longitude: float
    evidences: List[EvidenceDto] = []


class IncidentEvidenceAddDto(BaseModel):
    evidences: List[EvidenceDto]


class IncidentResponseDto(BaseModel):
    id: UUID
    status: str
    ai_category: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_summary: Optional[str] = None
    estimated_arrival_min: Optional[int] = None
    created_at: datetime
    message: str
    evidence_urls: List[str] = []

    class Config:
        from_attributes = True
