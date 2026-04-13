from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.module_clients.dtos.vehicle_dtos import VehicleCreateDTO, VehicleUpdateDTO
from app.module_clients.models.models import Vehicle
from app.module_clients.repositories import vehicle_repository, client_repository
from app.module_users.models.models import User


def create_vehicle(db: Session, data: VehicleCreateDTO) -> Vehicle:
    # Validar que el cliente exista
    client = client_repository.get_client_by_id(db, data.client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )

    # Validar placa única
    if vehicle_repository.get_vehicle_by_license_plate(db, data.license_plate):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La placa '{data.license_plate}' ya está registrada",
        )

    # Validar VIN único (si se proporciona)
    if data.vin and vehicle_repository.get_vehicle_by_vin(db, data.vin):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El VIN '{data.vin}' ya está registrado",
        )

    vehicle = Vehicle(
        client_id=data.client_id,
        make=data.make,
        model=data.model,
        year=data.year,
        license_plate=data.license_plate,
        color=data.color,
        transmission_type=data.transmission_type,
        fuel_type=data.fuel_type,
        vin=data.vin,
    )

    return vehicle_repository.save_vehicle(db, vehicle)


def get_all_vehicles(db: Session, current_user: User) -> list[Vehicle]:
    """
    Obtiene vehículos según el rol del usuario:
    - Admin: ve todos los vehículos
    - Client: ve solo sus propios vehículos
    """
    # Verificar si el usuario tiene rol 'admin'
    user_roles = {r.name for r in current_user.roles}

    if "admin" in user_roles:
        # Admin puede ver todos los vehículos
        return vehicle_repository.get_all_vehicles(db)
    elif "client" in user_roles:
        # Cliente solo ve sus propios vehículos
        return vehicle_repository.get_vehicles_by_client_id(db, current_user.id)
    else:
        # Otros roles no tienen acceso
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a los vehículos",
        )


def get_vehicle_by_id(db: Session, vehicle_id: UUID) -> Vehicle:
    vehicle = vehicle_repository.get_vehicle_by_id(db, vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehículo no encontrado",
        )
    return vehicle


def get_vehicles_by_client_id(db: Session, client_id: UUID) -> list[Vehicle]:
    # Validar que el cliente exista
    client = client_repository.get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )
    return vehicle_repository.get_vehicles_by_client_id(db, client_id)


def update_vehicle(db: Session, vehicle_id: UUID, data: VehicleUpdateDTO) -> Vehicle:
    vehicle = get_vehicle_by_id(db, vehicle_id)

    if data.make is not None:
        vehicle.make = data.make
    if data.model is not None:
        vehicle.model = data.model
    if data.year is not None:
        vehicle.year = data.year
    if data.license_plate is not None:
        existing = vehicle_repository.get_vehicle_by_license_plate(db, data.license_plate)
        if existing and existing.id != vehicle_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La placa '{data.license_plate}' ya está registrada",
            )
        vehicle.license_plate = data.license_plate
    if data.color is not None:
        vehicle.color = data.color
    if data.transmission_type is not None:
        vehicle.transmission_type = data.transmission_type
    if data.fuel_type is not None:
        vehicle.fuel_type = data.fuel_type
    if data.vin is not None:
        existing = vehicle_repository.get_vehicle_by_vin(db, data.vin)
        if existing and existing.id != vehicle_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El VIN '{data.vin}' ya está registrado",
            )
        vehicle.vin = data.vin
    if data.is_active is not None:
        vehicle.is_active = data.is_active

    return vehicle_repository.save_vehicle(db, vehicle)


def delete_vehicle(db: Session, vehicle_id: UUID) -> None:
    vehicle = get_vehicle_by_id(db, vehicle_id)
    vehicle_repository.delete_vehicle(db, vehicle)
