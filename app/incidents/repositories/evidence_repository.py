import uuid

from sqlalchemy.orm import Session

from app.incidents.models import IncidentEvidence


class EvidenceRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def get_evidences_by_incident(self, incident_id: uuid.UUID) -> list[IncidentEvidence]:
        return (
            self.db.query(IncidentEvidence)
            .filter(IncidentEvidence.incident_id == incident_id)
            .all()
        )

    def save(self, evidence: IncidentEvidence) -> IncidentEvidence:
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence
