import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Boolean, Column, DateTime, ForeignKey, BigInteger, String, Table, func, text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base

if TYPE_CHECKING:
    from app.users.models.role import Role
    from app.incidents.models.notification import Notification
else:
    # Import at runtime so SQLAlchemy registry registers the class name 'Notification'
    import app.incidents.models.enums as _incidents_models  # noqa: F401

role_user = Table(
    'role_user', Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', BigInteger, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('TRUE'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                 onupdate=func.now())
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    fcm_token: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "user",
    }

    roles: Mapped[list["Role"]] = relationship(
        'Role',
        secondary=role_user,  # Aquí usamos el objeto Table directamente
        back_populates='users'
    )

    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
