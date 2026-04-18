import uuid

from sqlalchemy.orm import Session

from app.module_incidents.models import IncidentEvidence


def get_evidences_by_incident(db: Session, incident_id: uuid.UUID) -> list[IncidentEvidence]:
    return (
        db.query(IncidentEvidence)
        .filter(IncidentEvidence.incident_id == incident_id)
        .all()
    )


def save_evidence(db: Session, evidence: IncidentEvidence) -> IncidentEvidence:
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence
