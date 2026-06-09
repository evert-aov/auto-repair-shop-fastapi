import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import  Boolean, ForeignKey,  Numeric, UUID, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.users.models.user import User

if TYPE_CHECKING:
    from app.incidents.models import Rating, Payment, WorkshopOffer

class Technician(User):
    __tablename__ = "technicians"

    id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        primary_key=True,
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workshops.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    current_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    current_longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 8), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))

    workshop: Mapped["Workshop"] = relationship(
        "Workshop", back_populates="technicians", foreign_keys="Technician.workshop_id"
    )

    __mapper_args__ = {
        "polymorphic_identity": "technician",
    }