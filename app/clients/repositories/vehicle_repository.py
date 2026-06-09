from uuid import UUID
from sqlalchemy.orm import Session
from app.clients.models import Vehicle

class VehicleRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Vehicle]:
        return self.db.query(Vehicle).all()

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self.db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

    def get_by_client_id(self, client_id: UUID) -> list[Vehicle]:
        return self.db.query(Vehicle).filter(Vehicle.client_id == client_id).all()

    def get_by_license_plate(self, license_plate: str) -> Vehicle | None:
        return self.db.query(Vehicle).filter(Vehicle.license_plate == license_plate).first()

    def get_by_vin(self, vin: str) -> Vehicle | None:
        return self.db.query(Vehicle).filter(Vehicle.vin == vin).first()

    def save(self, vehicle: Vehicle) -> Vehicle:
        self.db.add(vehicle)
        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    def delete(self, vehicle: Vehicle) -> None:
        self.db.delete(vehicle)
        self.db.commit()
