import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID, DateTime, Enum, Float, ForeignKey, Integer, String, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.incidents.models import OfferStatus

if TYPE_CHECKING:
    from app.workshops.models import Workshop
    from app.incidents.models import Incident


class WorkshopOffer(Base):
    __tablename__ = "workshop_offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus, name="offer_status_enum"),
        nullable=False,
        default=OfferStatus.NOTIFIED,
    )
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timeout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="offers")
    workshop: Mapped["Workshop"] = relationship("Workshop", back_populates="offers")
