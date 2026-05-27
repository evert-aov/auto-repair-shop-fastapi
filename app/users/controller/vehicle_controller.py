from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.users.dtos.vehicle_dtos import VehicleCreateDTO, VehicleResponseDTO, VehicleUpdateDTO
from app.users.services.vehicle_service import VehicleService
from app.security.config.security import require_permission, get_current_user

router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])


@router.post("/", response_model=VehicleResponseDTO, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    data: VehicleCreateDTO,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("vehicles:create"))
):
    return VehicleService(db).create_vehicle(data)


@router.get("/", response_model=list[VehicleResponseDTO], status_code=status.HTTP_200_OK)
def get_all_vehicles(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    _auth=Depends(require_permission("vehicles:read"))
):
    return VehicleService(db).get_all_vehicles(current_user)


@router.get("/{vehicle_id}", response_model=VehicleResponseDTO, status_code=status.HTTP_200_OK)
def get_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("vehicles:read"))
):
    return VehicleService(db).get_vehicle_by_id(vehicle_id)


@router.get("/client/{client_id}", response_model=list[VehicleResponseDTO], status_code=status.HTTP_200_OK)
def get_vehicles_by_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("vehicles:read"))
):
    return VehicleService(db).get_vehicles_by_client_id(client_id)


@router.put("/{vehicle_id}", response_model=VehicleResponseDTO, status_code=status.HTTP_200_OK)
def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdateDTO,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("vehicles:update"))
):
    return VehicleService(db).update_vehicle(vehicle_id, data)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("vehicles:delete"))
):
    VehicleService(db).delete_vehicle(vehicle_id)
