import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.module_incidents.ai.services import audio_service, classification_service, vision_service
from app.module_incidents.dtos.incident_dtos import IncidentCreateDto, IncidentResponseDto
from app.module_incidents.models import IncidentStatus
from app.module_incidents.repositories import (
    evidence_repository,
    incident_repository,
    status_history_repository,
)
from app.module_incidents.services import assignment_service, incident_service
from app.module_users.models import User
from app.security.config.security import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

def _process_incident_with_ai(incident_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        incident = incident_repository.get_incident_by_id(db, incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found in background task")
            return

        evidences = evidence_repository.get_evidences_by_incident(db, incident_id)

        audio_transcript = None
        image_analysis = None

        try:
            for ev in evidences:
                if ev.evidence_type.value == "audio":
                    audio_transcript = audio_service.transcribe_audio(ev.file_url)
                    if audio_transcript:
                        ev.transcription = audio_transcript
                        evidence_repository.save_evidence(db, ev)
                elif ev.evidence_type.value == "image":
                    image_analysis = vision_service.analyze_image(ev.file_url)
                    if image_analysis:
                        ev.ai_analysis = image_analysis
                        evidence_repository.save_evidence(db, ev)
        except Exception as exc:
            logger.error(f"Evidence processing error for incident {incident_id}: {exc}")
            incident.status = IncidentStatus.ERROR
            incident_repository.save_incident(db, incident)
            status_history_repository.log_status_change(
                db,
                incident_id=incident_id,
                previous_status=IncidentStatus.ANALYZING.value,
                new_status=IncidentStatus.ERROR.value,
                reason=f"Evidence processing error: {exc}",
            )
            return

        classification = classification_service.classify_incident(
            description=incident.description,
            audio_transcript=audio_transcript,
            image_analysis=image_analysis,
        )

        incident.ai_category = classification.category
        incident.ai_priority = classification.priority
        incident.ai_confidence = classification.confidence
        incident.ai_summary = classification.summary

        if classification.confidence > 0.4:
            incident.status = IncidentStatus.MATCHED
            incident_repository.save_incident(db, incident)
            status_history_repository.log_status_change(
                db,
                incident_id=incident_id,
                previous_status=IncidentStatus.ANALYZING.value,
                new_status=IncidentStatus.MATCHED.value,
                reason="AI classification successful",
            )
            assignment_service.find_and_create_offers(db, incident)
        else:
            incident.status = IncidentStatus.PENDING_INFO
            incident_repository.save_incident(db, incident)
            status_history_repository.log_status_change(
                db,
                incident_id=incident_id,
                previous_status=IncidentStatus.ANALYZING.value,
                new_status=IncidentStatus.PENDING_INFO.value,
                reason="AI confidence below threshold",
            )

    except Exception as exc:
        logger.error(f"Background AI task failed for incident {incident_id}: {exc}")
    finally:
        db.close()


@router.post(
    "/request-help",
    response_model=IncidentResponseDto,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("client"))],
)
def request_help(
    incident_data: IncidentCreateDto,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = incident_service.create_incident_request(db, current_user, incident_data)

    status_history_repository.log_status_change(
        db,
        incident_id=incident.id,
        previous_status=None,
        new_status=IncidentStatus.PENDING.value,
        reason="Incident created",
    )

    incident.status = IncidentStatus.ANALYZING
    incident = incident_repository.save_incident(db, incident)

    status_history_repository.log_status_change(
        db,
        incident_id=incident.id,
        previous_status=IncidentStatus.PENDING.value,
        new_status=IncidentStatus.ANALYZING.value,
        reason="AI processing started",
    )

    background_tasks.add_task(_process_incident_with_ai, incident.id)

    return IncidentResponseDto(
        id=incident.id,
        status=incident.status.value,
        created_at=incident.created_at,
        message="Solicitud de auxilio recibida. Analizando...",
    )
