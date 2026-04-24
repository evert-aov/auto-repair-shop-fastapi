import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
# [MODIFICADO] Inyectando servicios de IA (Vertex & Storage)
from app.module_incidents.ai.services import (
    audio_service,
    vertex_service,
    storage_service,
    transcription_job_service,
)
from app.module_incidents.dtos.incident_dtos import (
    IncidentCreateDto, IncidentResponseDto, IncidentEvidenceAddDto
)
# [MODIFICADO] Inyectando DTOs de IA
from app.module_incidents.ai.dtos.ai_dtos import (
    AudioTranscriptionRequest,
    AudioTranscriptionResponse,
    AudioUploadResponse,
    ImageUploadResponse,
    AudioUploadAsyncResponse,
    TranscriptionJobStatusResponse,
)
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

# [NUEVO] Lógica de jobs de transcripción
def _process_transcription_job(job_id: str, file_url: str):
    try:
        transcript = audio_service.transcribe_audio(file_url)
        if transcript:
            transcription_job_service.update_job_success(job_id, transcript)
        else:
            transcription_job_service.update_job_error(job_id, "No se genero transcripcion")
    except Exception as e:
        logger.error(f"Error procesando audio {job_id}: {e}")
        transcription_job_service.update_job_error(job_id, str(e))

def _process_incident_with_ai(incident_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        incident = incident_repository.get_incident_by_id(db, incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found in background task")
            return

        evidences = evidence_repository.get_evidences_by_incident(db, incident_id)

        audio_transcript = None
        image_evidences = []

        try:
            # 1. Obtener todas las evidencias (usando la relación del modelo)
            evidence_list = incident.evidences
            image_evidences = []
            text_from_evidences = []

            for ev in evidence_list:
                if ev.evidence_type.value == "audio":
                    t = audio_service.transcribe_audio(ev.file_url)
                    if t:
                        ev.transcription = t
                        evidence_repository.save_evidence(db, ev)
                        text_from_evidences.append(f"[Audio]: {t}")
                elif ev.evidence_type.value == "text":
                    if ev.transcription:
                        text_from_evidences.append(f"[Nota adicional]: {ev.transcription}")
                elif ev.evidence_type.value == "image":
                    image_evidences.append(ev)
            
            # Construir el contexto de texto completo
            full_context = [f"Descripción inicial: {incident.description}"]
            full_context.extend(text_from_evidences)
            full_description = "\n".join(full_context)

            # 2. Análisis IA Multimodal
            triage_result = vertex_service.analyze_incident_multimodal(
                description=full_description,
                image_urls=[ev.file_url for ev in image_evidences]
            )

            # 3. Guardar resultados básicos
            sistema = triage_result.get("sistema", {})
            cliente = triage_result.get("cliente", {})
            incident.ai_category = sistema.get("categoria", "general")
            incident.ai_priority = sistema.get("prioridad", "MEDIUM")
            incident.ai_confidence = sistema.get("confianza", 0.5)

            # 4. Formatear resumen y costo
            summary_parts = [cliente.get("mensaje_tranquilizador", "Estamos analizando su problema.")]
            if cliente.get("posible_causa"): summary_parts.append(f"Posible causa: {cliente['posible_causa']}")
            if cliente.get("consejo_seguridad"): summary_parts.append(f"Consejo: {cliente['consejo_seguridad']}")

            # Estimación Grounded
            tecnico_info = triage_result.get("tecnico", {})
            diagnostic = tecnico_info.get("diagnostico_tecnico", full_description)
            estimation = vertex_service.estimate_cost_grounded(diagnostic, incident.ai_category)
            
            if estimation and "costo_estimado" in estimation:
                triage_result["costo_estimado"] = estimation["costo_estimado"]
                costo_data = estimation["costo_estimado"]
                if isinstance(costo_data, dict):
                    min_v, max_v = costo_data.get("min", 0), costo_data.get("max", 0)
                    if max_v > 0:
                        summary_parts.append(f"Estimación inicial: {min_v} - {max_v} BOB")
                else:
                    summary_parts.append(f"Estimación inicial: {costo_data} BOB")
            
            # [CRÍTICO] Separación de campos
            incident.ai_summary = "\n\n".join(summary_parts) # Para el CLIENTE
            incident.vertex_analysis = triage_result        # Para el TALLER (contiene el diagnóstico técnico)
            
            # Guardar también en las evidencias para redundancia
            for ev in image_evidences:
                ev.ai_analysis = {"vertex": triage_result}
                evidence_repository.save_evidence(db, ev)
            if incident.ai_category in ["incierto", "uncertain"] or incident.ai_confidence < 0.4:
                incident.status = IncidentStatus.PENDING_INFO
                incident_repository.save_incident(db, incident)
            else:
                incident.status = IncidentStatus.MATCHED
                incident_repository.save_incident(db, incident)
                
                # Búsqueda de talleres (encapsulada para no romper el flujo)
                try:
                    logger.info(f"✨ IA Finalizada para {incident_id}. Buscando talleres...")
                    asyncio.run(assignment_service.find_and_create_offer(db, incident))
                except Exception as e:
                    logger.error(f"Error en asignación de talleres: {e}")

        except Exception as exc:
            logger.error(f"FALLO CRÍTICO IA para incidente {incident_id}: {exc}")
            incident.status = IncidentStatus.ERROR
            incident_repository.save_incident(db, incident)
        finally:
            db.close()

    except Exception as exc:
        logger.error(f"Background AI task failed for incident {incident_id}: {exc}")
    finally:
        db.close()


@router.post(
    "/{incident_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("client"))],
)
def add_incident_evidence(
    incident_id: uuid.UUID,
    extra_evidence: IncidentEvidenceAddDto,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    [NUEVO] Permite añadir evidencia adicional a un incidente.
    Si el incidente estaba en PENDING_INFO, lo regresa a ANALYZING y re-dispara la IA.
    """
    incident = incident_repository.get_incident_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this incident")

    # Guardar nueva evidencia
    from app.module_incidents.models import IncidentEvidence, EvidenceType
    for ev in extra_evidence.evidences:
        evidence = IncidentEvidence(
            incident_id=incident.id,
            evidence_type=EvidenceType(ev.evidence_type),
            file_url=ev.file_url,
            transcription=ev.transcription,
        )
        evidence_repository.save_evidence(db, evidence)

    # Si estaba en PENDING_INFO, re-procesar
    if incident.status == IncidentStatus.PENDING_INFO:
        prev_status = incident.status
        incident.status = IncidentStatus.ANALYZING
        incident_repository.save_incident(db, incident)
        
        status_history_repository.log_status_change(
            db,
            incident_id=incident.id,
            previous_status=prev_status.value,
            new_status=IncidentStatus.ANALYZING.value,
            reason="Cliente subió evidencia adicional, re-iniciando análisis."
        )
        background_tasks.add_task(_process_incident_with_ai, incident.id)
        return {"message": "Evidencia añadida. Re-analizando incidente...", "status": incident.status.value}

    return {"message": "Evidencia añadida correctamente", "status": incident.status.value}


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
    logger.info(f"Incident request from user {current_user.id}: {incident_data.description[:50]}... vehicle={incident_data.vehicle_id}")
    try:
        incident = incident_service.create_incident_request(db, current_user, incident_data)
    except Exception as e:
        logger.error(f"Error creating incident: {e}", exc_info=True)
        raise

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

    # [CONECTADO] Notificar al cliente que la solicitud fue recibida
    from app.module_incidents.services.notification_service import NotificationService
    notifier = NotificationService(db)
    background_tasks.add_task(notifier.notify_client_incident_created, current_user.id, incident)

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
    
    # [MODIFICADO] Inyectando resolución en caliente de vertex_analysis
    evidences = evidence_repository.get_evidences_by_incident(db, incident_id)
    vertex_analysis = None
    evidence_urls = []
    
    for ev in evidences:
        if ev.evidence_type.value.lower() in ["image", "audio"]:
            evidence_urls.append({
                "url": storage_service.generate_signed_url(ev.file_url),
                "type": ev.evidence_type.value.lower()
            })
        if ev.ai_analysis and "vertex" in ev.ai_analysis:
            vertex_analysis = ev.ai_analysis["vertex"]
            
    return {
        "id": incident.id,
        "status": incident.status.value,
        "description": incident.description,
        "ai_category": incident.ai_category,
        "ai_priority": incident.ai_priority.value if incident.ai_priority else None,
        "ai_confidence": incident.ai_confidence,
        "ai_summary": incident.ai_summary,
        "latitude": incident.incident_lat,
        "longitude": incident.incident_lng,
        "estimated_arrival_min": incident.estimated_arrival_min,
        "total_cost": incident.total_cost,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "vertex_analysis": vertex_analysis,
        "evidence_urls": evidence_urls
    }


_ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "audio/mpeg", "audio/mp4", "audio/aac",
    "audio/wav", "audio/x-wav", "audio/ogg",
    "audio/m4a", "audio/x-m4a",
}

_UPLOADS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "uploads",
)


@router.post(
    "/upload-evidence",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("client"))],
)
async def upload_evidence(file: UploadFile = File(...)):
    if file.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {file.content_type}",
        )

    # [NUEVO] Log para depurar qué está leyendo el sistema
    logger.info(f"Intentando subida. Bucket configurado: '{storage_service.GCS_BUCKET_NAME}'")

    if storage_service.GCS_BUCKET_NAME:
        try:
            if file.content_type.startswith("audio/"):
                logger.info(f"Subiendo audio a GCS: {file.filename}")
                result = storage_service.upload_audio_file(file)
                return JSONResponse(
                    status_code=201,
                    content={"file_url": result.file_url, "evidence_type": "audio"}
                )
            elif file.content_type.startswith("image/"):
                logger.info(f"Subiendo imagen a GCS: {file.filename}")
                file_url = storage_service.upload_image_file(file)
                return JSONResponse(
                    status_code=201,
                    content={"file_url": file_url, "evidence_type": "image"}
                )
        except Exception as e:
            logger.error(f"❌ FALLÓ GCS: {str(e)} - Reintentando local...")

    # Fallback local (anterior) si no hay GCS o falla
    ext = (file.filename or "file").rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    dest = os.path.join(_UPLOADS_DIR, filename)

    os.makedirs(_UPLOADS_DIR, exist_ok=True)
    contents = await file.read()
    
    # [NUEVO] Refinamiento básico local para imágenes si es posible
    if file.content_type.startswith("image/"):
        try:
            enhanced, _ = storage_service.enhance_image(contents)
            contents = enhanced
            filename = filename.rsplit(".", 1)[0] + ".jpg"
            dest = os.path.join(_UPLOADS_DIR, filename)
        except Exception as e:
            logger.warning(f"Local image enhancement failed: {e}")

    with open(dest, "wb") as f:
        f.write(contents)

    evidence_type = "audio" if file.content_type.startswith("audio/") else "image"
    return JSONResponse(
        status_code=201,
        content={"file_url": f"/uploads/{filename}", "evidence_type": evidence_type},
    )


# [NUEVO] Endpoints IA independientes del flujo principal

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
