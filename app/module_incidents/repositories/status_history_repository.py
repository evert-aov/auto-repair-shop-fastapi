import uuid

from sqlalchemy.orm import Session

from app.module_incidents.models import IncidentStatusHistory


def log_status_change(
    db: Session,
    incident_id: uuid.UUID,
    previous_status: str | None,
    new_status: str,
    changed_by: uuid.UUID | None = None,
    reason: str | None = None,
) -> IncidentStatusHistory:
    entry = IncidentStatusHistory(
        incident_id=incident_id,
        previous_status=previous_status,
        new_status=new_status,
        changed_by=changed_by,
        reason=reason,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_history_by_incident(
    db: Session, incident_id: uuid.UUID
) -> list[IncidentStatusHistory]:
    return (
        db.query(IncidentStatusHistory)
        .filter(IncidentStatusHistory.incident_id == incident_id)
        .order_by(IncidentStatusHistory.created_at)
        .all()
    )
