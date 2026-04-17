from uuid import UUID

from sqlalchemy.orm import Session

from app.security.models import Vehicle


def get_all_vehicles(db: Session) -> list[Vehicle]:
    return db.query(Vehicle).all()


def get_vehicle_by_id(db: Session, vehicle_id: UUID) -> Vehicle | None:
    return db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()


def get_vehicles_by_client_id(db: Session, client_id: UUID) -> list[Vehicle]:
    return db.query(Vehicle).filter(Vehicle.client_id == client_id).all()


def get_vehicle_by_license_plate(db: Session, license_plate: str) -> Vehicle | None:
    return db.query(Vehicle).filter(Vehicle.license_plate == license_plate).first()


def get_vehicle_by_vin(db: Session, vin: str) -> Vehicle | None:
    return db.query(Vehicle).filter(Vehicle.vin == vin).first()


def save_vehicle(db: Session, vehicle: Vehicle) -> Vehicle:
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def delete_vehicle(db: Session, vehicle: Vehicle) -> None:
    db.delete(vehicle)
    db.commit()
