from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.incidents.models import Rating, Payment, WorkshopOffer


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    workshop_specialties: Mapped[list["WorkshopSpecialty"]] = relationship(
        "WorkshopSpecialty", back_populates="specialty"
    )