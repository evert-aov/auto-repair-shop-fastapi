import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, UUID, func, text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.users.models.user import User
from app.workshops.models.workshop_specialty import WorkshopSpecialty

from app.workshops.models.technician import Technician

if TYPE_CHECKING:
    from app.incidents.models import Rating, Payment, WorkshopOffer

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
    activity_points: Mapped[int] = mapped_column(Integer, nullable=False, default=50, server_default=text("50"))
    paypal_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
        "Technician", back_populates="workshop", foreign_keys="Technician.workshop_id"
    )
    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="workshop")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="workshop")
    offers: Mapped[list["WorkshopOffer"]] = relationship("WorkshopOffer", back_populates="workshop")
