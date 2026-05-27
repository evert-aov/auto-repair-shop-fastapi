from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, model_validator


class EvidenceDto(BaseModel):
    evidence_type: str
    file_url: str
    transcription: Optional[str] = None


class IncidentCreateDto(BaseModel):
    description: Optional[str] = None
    vehicle_id: UUID
    latitude: float
    longitude: float
    evidences: List[EvidenceDto] = []

    @model_validator(mode="after")
    def at_least_one_input(self) -> "IncidentCreateDto":
        has_text = bool(self.description and self.description.strip())
        has_evidence = any(
            e.evidence_type in ("image", "audio") for e in self.evidences
        )
        if not has_text and not has_evidence:
            raise ValueError(
                "Debes proporcionar al menos uno: texto, imagen o audio"
            )
        return self


class IncidentEvidenceAddDto(BaseModel):
    evidences: List[EvidenceDto]


class IncidentResponseDto(BaseModel):
    id: UUID
    status: str
    ai_category: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_summary: Optional[str] = None
    vertex_analysis: Optional[dict] = None
    estimated_arrival_min: Optional[int] = None
    created_at: datetime
    message: str
    evidence_urls: List[str] = []

    class Config:
        from_attributes = True
