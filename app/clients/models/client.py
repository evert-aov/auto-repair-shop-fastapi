import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.users.models.user import User

if TYPE_CHECKING:
    from app.clients.models.vehicle import Vehicle
    from app.incidents.models import Rating, Payment

class Client(User):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )

    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_policy_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_request: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)

    __mapper_args__ = {
        "polymorphic_identity": "client",
    }

    vehicles: Mapped[list["Vehicle"]] = relationship("Vehicle", back_populates="client", lazy="selectin")
    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="client")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="client")
