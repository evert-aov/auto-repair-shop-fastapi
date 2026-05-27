import uuid

from sqlalchemy.orm import Session

from app.incidents.models import IncidentStatusHistory


class StatusHistoryRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def log_status_change(
        self,
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
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_history_by_incident(
        self, incident_id: uuid.UUID
    ) -> list[IncidentStatusHistory]:
        return (
            self.db.query(IncidentStatusHistory)
            .filter(IncidentStatusHistory.incident_id == incident_id)
            .order_by(IncidentStatusHistory.created_at)
            .all()
        )
