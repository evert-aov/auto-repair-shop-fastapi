import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID, BigInteger, Boolean, DateTime, Float, ForeignKey, String, func, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.module_incidents.models import Rating, Payment


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    workshop_specialties: Mapped[list["WorkshopSpecialty"]] = relationship(
        "WorkshopSpecialty", back_populates="specialty"
    )


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    rating_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    specialties: Mapped[list["WorkshopSpecialty"]] = relationship(
        "WorkshopSpecialty", back_populates="workshop"
    )
    technicians: Mapped[list["Technician"]] = relationship(
        "Technician", back_populates="workshop"
    )
    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="workshop")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="workshop")


class WorkshopSpecialty(Base):
    __tablename__ = "workshop_specialties"

    workshop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshops.id", ondelete="CASCADE"), primary_key=True
    )
    specialty_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("specialties.id", ondelete="CASCADE"), primary_key=True
    )
    is_mobile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    workshop: Mapped["Workshop"] = relationship("Workshop", back_populates="specialties")
    specialty: Mapped["Specialty"] = relationship("Specialty", back_populates="workshop_specialties")


class Technician(Base):
    __tablename__ = "technicians"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False
    )
    current_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE")
    )

    workshop: Mapped["Workshop"] = relationship("Workshop", back_populates="technicians")
