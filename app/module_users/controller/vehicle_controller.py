from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.module_users.dtos.vehicle_dtos import VehicleCreateDTO, VehicleResponseDTO, VehicleUpdateDTO
from app.module_users.services import vehicle_service
from app.security.config.security import require_role, get_current_user

router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])

_allowed = Depends(require_role("admin", "client"))


@router.post("/", response_model=VehicleResponseDTO, status_code=status.HTTP_201_CREATED, dependencies=[_allowed])
def create_vehicle(data: VehicleCreateDTO, db: Session = Depends(get_db)):
    return vehicle_service.create_vehicle(db, data)


@router.get("/", response_model=list[VehicleResponseDTO], status_code=status.HTTP_200_OK, dependencies=[_allowed])
def get_all_vehicles(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return vehicle_service.get_all_vehicles(db, current_user)


@router.get("/{vehicle_id}", response_model=VehicleResponseDTO, status_code=status.HTTP_200_OK, dependencies=[_allowed])
def get_vehicle(vehicle_id: UUID, db: Session = Depends(get_db)):
    return vehicle_service.get_vehicle_by_id(db, vehicle_id)


@router.get("/client/{client_id}", response_model=list[VehicleResponseDTO], status_code=status.HTTP_200_OK, dependencies=[_allowed])
def get_vehicles_by_client(client_id: UUID, db: Session = Depends(get_db)):
    return vehicle_service.get_vehicles_by_client_id(db, client_id)


@router.put("/{vehicle_id}", response_model=VehicleResponseDTO, status_code=status.HTTP_200_OK, dependencies=[_allowed])
def update_vehicle(vehicle_id: UUID, data: VehicleUpdateDTO, db: Session = Depends(get_db)):
    return vehicle_service.update_vehicle(db, vehicle_id, data)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_allowed])
def delete_vehicle(vehicle_id: UUID, db: Session = Depends(get_db)):
    vehicle_service.delete_vehicle(db, vehicle_id)
