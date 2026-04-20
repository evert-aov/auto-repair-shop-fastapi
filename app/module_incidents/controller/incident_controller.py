import logging
import uuid
import concurrent.futures
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.module_incidents.ai.dtos.ai_dtos import (
    AudioTranscriptionRequest,
    AudioTranscriptionResponse,
    AudioUploadAsyncResponse,
    AudioUploadResponse,
    ImageUploadResponse,
    TranscriptionJobStatusResponse,
)

from app.module_incidents.ai.services import (
    audio_service,
    classification_service,
    estimation_service,
    storage_service,
    transcription_job_service,
    vision_service,
)
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


def _process_audio_evidences(evidences) -> tuple[str | None, dict[uuid.UUID, str]]:
    transcripts_by_evidence: dict[uuid.UUID, str] = {}
    merged: list[str] = []

    for evidence in evidences:
        transcript = audio_service.transcribe_audio(evidence.file_url)
        if transcript:
            transcripts_by_evidence[evidence.id] = transcript
            merged.append(transcript)

    merged_transcript = " ".join(merged).strip()
    return (merged_transcript or None, transcripts_by_evidence)


def _process_image_evidences(evidences) -> tuple[list[vision_service.PreparedImage], dict[uuid.UUID, dict[str, Any]]]:
    prepared_images: list[vision_service.PreparedImage] = []
    analyses_by_evidence: dict[uuid.UUID, dict[str, Any]] = {}

    for evidence in evidences:
        prepared = vision_service.prepare_image_for_vertex(evidence.file_url)
        prepared_images.append(prepared)
        analyses_by_evidence[evidence.id] = {
            "source_url": evidence.file_url,
            "preprocessing": prepared.preprocessing,
        }

    return prepared_images, analyses_by_evidence


def _process_transcription_job(job_id: str, file_url: str) -> None:
    transcription_job_service.mark_processing(job_id)
    try:
        transcript = audio_service.transcribe_audio(file_url)
        transcription_job_service.mark_completed(job_id, transcript)
    except Exception as exc:
        logger.exception("Async transcription job failed for %s: %s", job_id, exc)
        transcription_job_service.mark_failed(job_id, str(exc))

def _process_incident_with_ai(incident_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        incident = incident_repository.get_incident_by_id(db, incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found in background task")
            return

        evidences = evidence_repository.get_evidences_by_incident(db, incident_id)

        audio_evidences = [ev for ev in evidences if ev.evidence_type.value == "audio"]
        image_evidences = [ev for ev in evidences if ev.evidence_type.value == "image"]

        audio_transcript: str | None = None
        transcripts_by_evidence: dict[uuid.UUID, str] = {}
        prepared_images: list[vision_service.PreparedImage] = []
        image_analysis_by_evidence: dict[uuid.UUID, dict[str, Any]] = {}

        try:
            futures: dict[str, concurrent.futures.Future] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                if audio_evidences:
                    futures["audio"] = executor.submit(_process_audio_evidences, audio_evidences)
                if image_evidences:
                    futures["image"] = executor.submit(_process_image_evidences, image_evidences)

                if "audio" in futures:
                    audio_transcript, transcripts_by_evidence = futures["audio"].result()
                if "image" in futures:
                    prepared_images, image_analysis_by_evidence = futures["image"].result()

            for ev in audio_evidences:
                transcript = transcripts_by_evidence.get(ev.id)
                if transcript:
                    ev.transcription = transcript
                    evidence_repository.save_evidence(db, ev)

            for ev in image_evidences:
                base_analysis = image_analysis_by_evidence.get(ev.id)
                if base_analysis:
                    ev.ai_analysis = base_analysis
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

        vertex_analysis = vision_service.analyze_incident_with_vertex(
            description=incident.description,
            audio_transcript=audio_transcript,
            prepared_images=prepared_images,
        )

        if vertex_analysis:
            for ev in image_evidences:
                current = dict(ev.ai_analysis) if ev.ai_analysis else {}
                current["vertex"] = vertex_analysis
                ev.ai_analysis = current
                evidence_repository.save_evidence(db, ev)

        classification = classification_service.classify_incident(
            description=incident.description,
            audio_transcript=audio_transcript,
            image_analysis=vertex_analysis,
        )

        incident.ai_category = classification.category
        incident.ai_priority = classification.priority
        incident.ai_confidence = classification.confidence
        if vertex_analysis and "tecnico" in vertex_analysis:
            tecnico = vertex_analysis["tecnico"]
            diag = tecnico.get("diagnostico_tecnico", "Sin diagnóstico")
            herramientas = ", ".join(tecnico.get("herramientas_sugeridas", []))
            proc = tecnico.get("procedimiento_recomendado", "")
            incident.ai_summary = f"DIAGNÓSTICO TÉCNICO:\n{diag}\n\nHERRAMIENTAS:\n{herramientas}\n\nPROCEDIMIENTO:\n{proc}"
        else:
            incident.ai_summary = classification.summary

        # Llama a la estimación de costo (Paso 5)
        diagnostic = getattr(classification, "summary", "Diagnóstico general")
        if vertex_analysis and "tecnico" in vertex_analysis:
            diagnostic = vertex_analysis["tecnico"].get("diagnostico_tecnico", diagnostic)
            
        estimation = estimation_service.estimate_cost(diagnostic, classification.category)
        if estimation and "costo_estimado" in estimation:
            # Inject it into vertex_analysis so the frontend gets it fully structured
            if vertex_analysis is not None:
                vertex_analysis["costo_estimado"] = estimation["costo_estimado"]
                # Must update evidence again to save the new node
                for ev in image_evidences:
                    current = dict(ev.ai_analysis) if ev.ai_analysis else {}
                    current["vertex"] = vertex_analysis
                    ev.ai_analysis = current
                    evidence_repository.save_evidence(db, ev)

        # Lógica de incertidumbre estricta (Paso 4)
        if classification.category == "incierto" or classification.confidence < 0.6:
            incident.status = IncidentStatus.PENDING_INFO
            incident_repository.save_incident(db, incident)
            status_history_repository.log_status_change(
                db,
                incident_id=incident_id,
                previous_status=IncidentStatus.ANALYZING.value,
                new_status=IncidentStatus.PENDING_INFO.value,
                reason="AI confidence below 0.6 or category incierto",
            )
        else:
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

    except Exception as exc:
        logger.error(f"Background AI task failed for incident {incident_id}: {exc}")
    finally:
        db.close()


@router.post(
    "/ai/transcribe",
    response_model=AudioTranscriptionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("admin", "client", "workshop_owner", "technician"))],
)
def transcribe_audio_test(
    payload: AudioTranscriptionRequest,
):
    transcript = audio_service.transcribe_audio(payload.file_url)
    return AudioTranscriptionResponse(transcript=transcript, stt_mode="fast")


@router.post(
    "/ai/upload-audio",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "client", "workshop_owner", "technician"))],
)
def upload_audio_test(
    file: UploadFile = File(...),
    auto_transcribe: bool = True,
):
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser de tipo audio")

    try:
        upload_result = storage_service.upload_audio_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error uploading audio to storage: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo subir el audio a storage") from exc

    transcript = audio_service.transcribe_audio(upload_result.file_url) if auto_transcribe else None
    return AudioUploadResponse(
        file_url=upload_result.file_url,
        transcript=transcript,
        stt_mode="fast",
        converted_to_flac=upload_result.converted_to_flac,
        stored_content_type=upload_result.stored_content_type,
    )


@router.post(
    "/ai/upload-image",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "client", "workshop_owner", "technician"))],
)
def upload_image_test(
    file: UploadFile = File(...),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser de tipo imagen")

    try:
        file_url = storage_service.upload_image_file(file)
        return ImageUploadResponse(file_url=file_url)
    except Exception as exc:
        logger.exception("Error uploading image to storage: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo subir la imagen a storage") from exc



@router.post(
    "/ai/upload-audio-async",
    response_model=AudioUploadAsyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role("admin", "client", "workshop_owner", "technician"))],
)
def upload_audio_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser de tipo audio")

    try:
        upload_result = storage_service.upload_audio_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error uploading audio to storage: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo subir el audio a storage") from exc

    job = transcription_job_service.create_job(
        file_url=upload_result.file_url,
        converted_to_flac=upload_result.converted_to_flac,
        stored_content_type=upload_result.stored_content_type,
    )
    background_tasks.add_task(_process_transcription_job, job["job_id"], upload_result.file_url)

    return AudioUploadAsyncResponse(
        job_id=job["job_id"],
        status=job["status"],
        file_url=job["file_url"],
        stt_mode="fast",
        converted_to_flac=job["converted_to_flac"],
        stored_content_type=job["stored_content_type"],
    )


@router.get(
    "/ai/transcription-jobs/{job_id}",
    response_model=TranscriptionJobStatusResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("admin", "client", "workshop_owner", "technician"))],
)
def get_transcription_job_status(job_id: str):
    job = transcription_job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo de transcripcion no encontrado")

    return TranscriptionJobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        file_url=job["file_url"],
        stt_mode="fast",
        transcript=job["transcript"],
        error=job["error"],
        converted_to_flac=job["converted_to_flac"],
        stored_content_type=job["stored_content_type"],
    )


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


@router.get(
    "/{incident_id}",
    response_model=dict, # Usamos dict para flexibilidad o IncidentResponseDto si lo permite
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("client", "admin", "workshop_owner", "technician"))],
)
def get_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    incident = incident_repository.get_incident_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    
    evidences = evidence_repository.get_evidences_by_incident(db, incident.id)
    vertex_analysis = None
    for ev in evidences:
        if ev.ai_analysis and "vertex" in ev.ai_analysis:
            vertex_analysis = ev.ai_analysis["vertex"]
            break
            
    return {
        "id": incident.id,
        "status": incident.status.value,
        "description": incident.description,
        "ai_category": incident.ai_category,
        "ai_priority": incident.ai_priority.value if incident.ai_priority else None,
        "ai_confidence": incident.ai_confidence,
        "ai_summary": incident.ai_summary,
        "estimated_arrival_min": incident.estimated_arrival_min,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "vertex_analysis": vertex_analysis
    }

