from collections import OrderedDict
from typing import Any

from app.incidents.models.incident import Incident
from app.incidents.models.workshop_offer import WorkshopOffer
from app.incidents.models.rating import Rating


def incident_to_audit_map(entity: Incident) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["client_id"] = str(entity.client_id)
    m["vehicle_id"] = str(entity.vehicle_id) if entity.vehicle_id else None
    m["description"] = entity.description
    m["incident_lat"] = entity.incident_lat
    m["incident_lng"] = entity.incident_lng
    m["status"] = entity.status.name if entity.status else None
    m["ai_category"] = entity.ai_category
    m["ai_priority"] = entity.ai_priority.name if entity.ai_priority else None
    m["ai_summary"] = entity.ai_summary
    m["ai_confidence"] = entity.ai_confidence
    m["assigned_workshop_id"] = str(entity.assigned_workshop_id) if entity.assigned_workshop_id else None
    m["assigned_technician_id"] = str(entity.assigned_technician_id) if entity.assigned_technician_id else None
    m["estimated_arrival_min"] = entity.estimated_arrival_min
    m["total_cost"] = entity.total_cost
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    m["updated_at"] = entity.updated_at.isoformat() if entity.updated_at else None
    return m


def incident_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["client_id"] = str(getattr(dto, "client_id", None)) if getattr(dto, "client_id", None) else None
    m["vehicle_id"] = str(getattr(dto, "vehicle_id", None)) if getattr(dto, "vehicle_id", None) else None
    m["description"] = getattr(dto, "description", None)
    m["status"] = getattr(dto, "status", None)
    m["ai_category"] = getattr(dto, "ai_category", None)
    m["ai_priority"] = getattr(dto, "ai_priority", None)
    m["assigned_workshop_id"] = str(getattr(dto, "assigned_workshop_id", None)) if getattr(dto, "assigned_workshop_id", None) else None
    m["assigned_technician_id"] = str(getattr(dto, "assigned_technician_id", None)) if getattr(dto, "assigned_technician_id", None) else None
    m["estimated_arrival_min"] = getattr(dto, "estimated_arrival_min", None)
    m["total_cost"] = getattr(dto, "total_cost", None)
    return m


def offer_to_audit_map(entity: WorkshopOffer) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["incident_id"] = str(entity.incident_id)
    m["workshop_id"] = str(entity.workshop_id)
    m["status"] = entity.status.name if entity.status else None
    m["distance_km"] = entity.distance_km
    m["ai_score"] = entity.ai_score
    m["notified_at"] = entity.notified_at.isoformat() if entity.notified_at else None
    m["accepted_at"] = entity.accepted_at.isoformat() if entity.accepted_at else None
    m["rejected_at"] = entity.rejected_at.isoformat() if entity.rejected_at else None
    m["rejection_reason"] = entity.rejection_reason
    m["timeout_minutes"] = entity.timeout_minutes
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    m["expires_at"] = entity.expires_at.isoformat() if entity.expires_at else None
    return m


def offer_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["incident_id"] = str(getattr(dto, "incident_id", None)) if getattr(dto, "incident_id", None) else None
    m["workshop_id"] = str(getattr(dto, "workshop_id", None)) if getattr(dto, "workshop_id", None) else None
    m["status"] = getattr(dto, "status", None)
    m["distance_km"] = getattr(dto, "distance_km", None)
    m["rejection_reason"] = getattr(dto, "rejection_reason", None)
    return m


def rating_to_audit_map(entity: Rating) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["incident_id"] = str(entity.incident_id)
    m["client_id"] = str(entity.client_id)
    m["workshop_id"] = str(entity.workshop_id)
    m["score"] = entity.score
    m["response_time_score"] = entity.response_time_score
    m["quality_score"] = entity.quality_score
    m["comment"] = entity.comment
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    return m


def rating_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["incident_id"] = str(getattr(dto, "incident_id", None)) if getattr(dto, "incident_id", None) else None
    m["client_id"] = str(getattr(dto, "client_id", None)) if getattr(dto, "client_id", None) else None
    m["workshop_id"] = str(getattr(dto, "workshop_id", None)) if getattr(dto, "workshop_id", None) else None
    m["score"] = getattr(dto, "score", None)
    m["comment"] = getattr(dto, "comment", None)
    return m
