import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID, Enum, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.incidents.models import EvidenceType

if TYPE_CHECKING:
    from app.incidents.models import Incident


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(EvidenceType, name="evidence_type_enum"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="evidences")
