from collections import OrderedDict
from typing import Any

from app.payments.models.payment import Payment


def payment_to_audit_map(entity: Payment) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["incident_id"] = str(entity.incident_id)
    m["client_id"] = str(entity.client_id)
    m["workshop_id"] = str(entity.workshop_id)
    m["gross_amount"] = entity.gross_amount
    m["commission_amount"] = entity.commission_amount
    m["net_amount"] = entity.net_amount
    m["currency"] = entity.currency
    m["payment_method"] = entity.payment_method.name if entity.payment_method else None
    m["status"] = entity.status.name if entity.status else None
    m["gateway_transaction_id"] = entity.gateway_transaction_id
    m["payout_id"] = entity.payout_id
    m["payout_status"] = entity.payout_status
    m["paid_at"] = entity.paid_at.isoformat() if entity.paid_at else None
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    return m


def payment_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["incident_id"] = str(getattr(dto, "incident_id", None)) if getattr(dto, "incident_id", None) else None
    m["client_id"] = str(getattr(dto, "client_id", None)) if getattr(dto, "client_id", None) else None
    m["workshop_id"] = str(getattr(dto, "workshop_id", None)) if getattr(dto, "workshop_id", None) else None
    m["gross_amount"] = getattr(dto, "gross_amount", None)
    m["commission_amount"] = getattr(dto, "commission_amount", None)
    m["net_amount"] = getattr(dto, "net_amount", None)
    m["currency"] = getattr(dto, "currency", None)
    m["payment_method"] = getattr(dto, "payment_method", None)
    m["status"] = getattr(dto, "status", None)
    m["payout_status"] = getattr(dto, "payout_status", None)
    return m
