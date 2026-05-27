from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, BigInteger, String, Table, func, text, Identity
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base

if TYPE_CHECKING:
    from app.users.models.user import User
    from app.users.models.permission import Permission

permission_role = Table(
    'permission_role', Base.metadata,
    Column('role_id', BigInteger, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', BigInteger, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)


class Role(Base):
    __tablename__ = 'roles'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    create_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    users: Mapped[list["User"]] = relationship(
        'User',
        secondary='role_user',  # Referencia en string a la tabla intermedia de User
        back_populates='roles'
    )
    permissions: Mapped[list["Permission"]] = relationship(
        'Permission',
        secondary=permission_role,  # Aquí sí usamos el objeto Table directamente
        back_populates='roles'
    )
