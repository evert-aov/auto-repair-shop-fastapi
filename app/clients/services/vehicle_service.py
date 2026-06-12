from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.audit import auditable
from app.clients.audit_mappers import vehicle_to_audit_map, vehicle_from_dto
from app.clients.dtos.vehicle_dtos import VehicleCreateDTO, VehicleUpdateDTO, VehicleResponseDTO
from app.clients.models import Vehicle
from app.clients.repositories.vehicle_repository import VehicleRepository
from app.clients.repositories.client_repository import ClientRepository
from app.users.models import User


class VehicleService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.vehicle_repository = VehicleRepository(db)
        self.client_repository = ClientRepository(db)

    def get_entity(self, id: UUID) -> Vehicle | None:
        return self.vehicle_repository.get_by_id(id)

    def to_audit_map(self, entity: Vehicle) -> dict[str, Any]:
        return vehicle_to_audit_map(entity)

    def to_audit_map_from_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, VehicleResponseDTO):
            return vehicle_from_dto(result)
        if isinstance(result, Vehicle):
            return vehicle_to_audit_map(result)
        return {}

    @auditable(resource_type="VEHICLE", action_type="CREATE")
    def create_vehicle(self, data: VehicleCreateDTO) -> Vehicle:
        # Validar que el cliente exista
        client = self.client_repository.get_by_id(data.client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado",
            )

        # Validar placa única
        if self.vehicle_repository.get_by_license_plate(data.license_plate):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La placa '{data.license_plate}' ya está registrada",
            )

        # Validar VIN único (si se proporciona)
        if data.vin and self.vehicle_repository.get_by_vin(data.vin):
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

        return self.vehicle_repository.save(vehicle)

    def get_all_vehicles(self, current_user: User) -> list[Vehicle]:
        """
        Obtiene vehículos según el rol del usuario:
        - Admin: ve todos los vehículos
        - Client: ve solo sus propios vehículos
        """
        user_roles = {r.name for r in current_user.roles}

        if "admin" in user_roles:
            return self.vehicle_repository.get_all()
        elif "client" in user_roles:
            return self.vehicle_repository.get_by_client_id(current_user.id)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a los vehículos",
            )

    def get_vehicle_by_id(self, vehicle_id: UUID) -> Vehicle:
        vehicle = self.vehicle_repository.get_by_id(vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehículo no encontrado",
            )
        return vehicle

    def get_vehicles_by_client_id(self, client_id: UUID) -> list[Vehicle]:
        client = self.client_repository.get_by_id(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado",
            )
        return self.vehicle_repository.get_by_client_id(client_id)

    @auditable(resource_type="VEHICLE", action_type="UPDATE", id_param_name="vehicle_id")
    def update_vehicle(self, vehicle_id: UUID, data: VehicleUpdateDTO) -> Vehicle:
        vehicle = self.get_vehicle_by_id(vehicle_id)

        if data.make is not None:
            vehicle.make = data.make
        if data.model is not None:
            vehicle.model = data.model
        if data.year is not None:
            vehicle.year = data.year
        if data.license_plate is not None:
            existing = self.vehicle_repository.get_by_license_plate(data.license_plate)
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
            existing = self.vehicle_repository.get_by_vin(data.vin)
            if existing and existing.id != vehicle_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El VIN '{data.vin}' ya está registrado",
                )
            vehicle.vin = data.vin
        if data.is_active is not None:
            vehicle.is_active = data.is_active

        return self.vehicle_repository.save(vehicle)

    @auditable(resource_type="VEHICLE", action_type="DELETE", id_param_name="vehicle_id")
    def delete_vehicle(self, vehicle_id: UUID) -> None:
        vehicle = self.get_vehicle_by_id(vehicle_id)
        self.vehicle_repository.delete(vehicle)
