import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID, Boolean, DateTime, Enum, ForeignKey, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.users.models.user import User
    from app.incidents.models.incident import Incident



class NotificationType(str, enum.Enum):
    NEW_REQUEST = "new_request"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STATUS_UPDATE = "status_update"
    PAYMENT = "payment"
    SYSTEM = "system"
    SERVICE_COMPLETED = "service_completed"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type_enum"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="notifications")
    user: Mapped["User"] = relationship("User", back_populates="notifications")


# Import Incident for relationship registration at runtime
import app.incidents.models  # noqa: F401
