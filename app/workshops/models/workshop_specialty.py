import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, UUID, func, text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.users.models.user import User

if TYPE_CHECKING:
    from app.incidents.models import Rating, Payment, WorkshopOffer

class WorkshopSpecialty(Base):
    __tablename__ = "workshop_specialties"

    workshop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workshops.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        primary_key=True,
    )
    specialty_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("specialties.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        primary_key=True,
    )
    is_mobile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))

    workshop: Mapped["Workshop"] = relationship("Workshop", back_populates="workshop_specialties")
    specialty: Mapped["Specialty"] = relationship("Specialty", back_populates="workshop_specialties")
