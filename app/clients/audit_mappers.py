from collections import OrderedDict
from typing import Any

from app.clients.models.client import Client
from app.clients.models.vehicle import Vehicle


def client_to_audit_map(entity: Client) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["username"] = entity.username
    m["name"] = entity.name
    m["last_name"] = entity.last_name
    m["email"] = entity.email
    m["password"] = entity.password
    m["phone"] = entity.phone
    m["is_active"] = entity.is_active
    m["type"] = entity.type
    m["fcm_token"] = entity.fcm_token
    m["address"] = entity.address
    m["insurance_provider"] = entity.insurance_provider
    m["insurance_policy_number"] = entity.insurance_policy_number
    m["total_request"] = entity.total_request
    m["vehicles_count"] = len(entity.vehicles) if entity.vehicles else 0
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    m["updated_at"] = entity.updated_at.isoformat() if entity.updated_at else None
    return m


def client_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["username"] = getattr(dto, "username", None)
    m["name"] = getattr(dto, "name", None)
    m["last_name"] = getattr(dto, "last_name", None)
    m["email"] = getattr(dto, "email", None)
    m["phone"] = getattr(dto, "phone", None)
    m["address"] = getattr(dto, "address", None)
    m["insurance_provider"] = getattr(dto, "insurance_provider", None)
    m["insurance_policy_number"] = getattr(dto, "insurance_policy_number", None)
    return m


def vehicle_to_audit_map(entity: Vehicle) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["client_id"] = str(entity.client_id)
    m["make"] = entity.make
    m["model"] = entity.model
    m["year"] = entity.year
    m["license_plate"] = entity.license_plate
    m["color"] = entity.color
    m["transmission_type"] = entity.transmission_type.name if entity.transmission_type else None
    m["fuel_type"] = entity.fuel_type.name if entity.fuel_type else None
    m["vin"] = entity.vin
    m["is_active"] = entity.is_active
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    m["updated_at"] = entity.updated_at.isoformat() if entity.updated_at else None
    return m


def vehicle_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["client_id"] = str(dto.client_id) if hasattr(dto, "client_id") else None
    m["make"] = getattr(dto, "make", None)
    m["model"] = getattr(dto, "model", None)
    m["year"] = getattr(dto, "year", None)
    m["license_plate"] = getattr(dto, "license_plate", None)
    m["color"] = getattr(dto, "color", None)
    m["transmission_type"] = getattr(dto, "transmission_type", None)
    m["fuel_type"] = getattr(dto, "fuel_type", None)
    m["vin"] = getattr(dto, "vin", None)
    return m
