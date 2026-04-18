import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, UUID, func, text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.module_users.models.models import User

if TYPE_CHECKING:
    from app.module_incidents.models import Payment, Rating


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    workshop_specialties: Mapped[list["WorkshopSpecialty"]] = relationship(
        "WorkshopSpecialty", back_populates="specialty"
    )


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


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ruc_nit: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 8), nullable=True)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=10.0)
    rating_avg: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)
    total_services: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_rejection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0.0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    workshop_specialties: Mapped[list["WorkshopSpecialty"]] = relationship(
        "WorkshopSpecialty", back_populates="workshop", cascade="all, delete-orphan"
    )
    specialties = association_proxy(
        "workshop_specialties",
        "specialty",
        creator=lambda specialty: WorkshopSpecialty(specialty=specialty),
    )
    technicians: Mapped[list["Technician"]] = relationship(
        "Technician", back_populates="workshop"
    )
    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="workshop")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="workshop")


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

    workshop: Mapped["Workshop"] = relationship("Workshop", back_populates="technicians")

    __mapper_args__ = {
        "polymorphic_identity": "technician",
    }
