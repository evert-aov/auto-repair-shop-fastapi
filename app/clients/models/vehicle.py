import enum
from datetime import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, SmallInteger, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.clients.models.client import Client

class TransmissionType(enum.Enum):
    manual    = "manual"
    automatic = "automatic"

class FuelType(enum.Enum):
    gasoline = "gasoline"
    diesel   = "diesel"
    electric = "electric"
    hybrid   = "hybrid"

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    make: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    license_plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transmission_type: Mapped[TransmissionType | None] = mapped_column(
        Enum(TransmissionType, name="transmission_type_enum"), nullable=True
    )
    fuel_type: Mapped[FuelType | None] = mapped_column(
        Enum(FuelType, name="fuel_type_enum"), nullable=True
    )
    vin: Mapped[str | None] = mapped_column(String(17), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship("Client", back_populates="vehicles")
