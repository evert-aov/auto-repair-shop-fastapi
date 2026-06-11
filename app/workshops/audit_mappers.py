from collections import OrderedDict
from typing import Any

from app.workshops.models.workshop import Workshop
from app.workshops.models.technician import Technician
from app.workshops.models.specialty import Specialty


def workshop_to_audit_map(entity: Workshop) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["owner_user_id"] = str(entity.owner_user_id)
    m["name"] = entity.name
    m["business_name"] = entity.business_name
    m["ruc_nit"] = entity.ruc_nit
    m["address"] = entity.address
    m["phone"] = entity.phone
    m["latitude"] = float(entity.latitude) if entity.latitude else None
    m["longitude"] = float(entity.longitude) if entity.longitude else None
    m["commission_rate"] = float(entity.commission_rate) if entity.commission_rate else None
    m["rating_avg"] = float(entity.rating_avg) if entity.rating_avg else None
    m["total_services"] = entity.total_services
    m["rejection_count"] = entity.rejection_count
    m["rejection_rate"] = entity.rejection_rate
    m["activity_points"] = entity.activity_points
    m["paypal_email"] = entity.paypal_email
    m["is_active"] = entity.is_active
    m["is_available"] = entity.is_available
    m["is_verified"] = entity.is_verified
    specialities = [s.name for s in entity.specialties] if entity.specialties else []
    m["specialties"] = specialities
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    m["updated_at"] = entity.updated_at.isoformat() if entity.updated_at else None
    return m


def workshop_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["name"] = getattr(dto, "name", None)
    m["business_name"] = getattr(dto, "business_name", None)
    m["ruc_nit"] = getattr(dto, "ruc_nit", None)
    m["address"] = getattr(dto, "address", None)
    m["phone"] = getattr(dto, "phone", None)
    m["commission_rate"] = getattr(dto, "commission_rate", None)
    m["is_active"] = getattr(dto, "is_active", None)
    m["is_available"] = getattr(dto, "is_available", None)
    m["is_verified"] = getattr(dto, "is_verified", None)
    return m


def technician_to_audit_map(entity: Technician) -> dict[str, Any]:
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
    m["workshop_id"] = str(entity.workshop_id) if entity.workshop_id else None
    m["current_latitude"] = float(entity.current_latitude) if entity.current_latitude else None
    m["current_longitude"] = float(entity.current_longitude) if entity.current_longitude else None
    m["is_available"] = entity.is_available
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    m["updated_at"] = entity.updated_at.isoformat() if entity.updated_at else None
    return m


def technician_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["username"] = getattr(dto, "username", None)
    m["name"] = getattr(dto, "name", None)
    m["last_name"] = getattr(dto, "last_name", None)
    m["email"] = getattr(dto, "email", None)
    m["phone"] = getattr(dto, "phone", None)
    m["workshop_id"] = str(getattr(dto, "workshop_id", None)) if getattr(dto, "workshop_id", None) else None
    m["is_available"] = getattr(dto, "is_available", None)
    return m


def specialty_to_audit_map(entity: Specialty) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = entity.id
    m["name"] = entity.name
    return m
