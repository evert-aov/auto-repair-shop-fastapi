from app.incidents.models import Rating
from app.workshops.models import Technician
from app.workshops.models import Workshop
import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
# [MODIFICADO] Inyectando servicios de IA (Vertex & Storage)
from app.incidents.ai.services import (
    audio_service,
    vertex_service,
    storage_service,
    transcription_job_service,
)
from app.incidents.dtos.incident_dtos import (
    IncidentCreateDto, IncidentResponseDto, IncidentEvidenceAddDto
)
# [MODIFICADO] Inyectando DTOs de IA
from app.incidents.ai.dtos.ai_dtos import (
    AudioTranscriptionRequest,
    AudioTranscriptionResponse,
    AudioUploadResponse,
    ImageUploadResponse,
    AudioUploadAsyncResponse,
    TranscriptionJobStatusResponse,
)
from app.incidents.models import IncidentStatus
from app.incidents.repositories.incident_repository import IncidentRepository
from app.incidents.repositories.evidence_repository import EvidenceRepository
from app.incidents.repositories.status_history_repository import StatusHistoryRepository
from app.incidents.services.incident_service import IncidentService
from app.incidents.services.assignment_service import AssignmentService
from app.users.models import User
from app.security.models import Vehicle
from app.security.config.security import get_current_user, require_permission

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
        incident = IncidentRepository(db).get_by_id(incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found in background task")
            return

        evidences = EvidenceRepository(db).get_evidences_by_incident(incident_id)

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
                        EvidenceRepository(db).save(ev)
                        text_from_evidences.append(f"[Audio]: {t}")
                elif ev.evidence_type.value == "text":
                    if ev.transcription:
                        text_from_evidences.append(f"[Nota adicional]: {ev.transcription}")
                elif ev.evidence_type.value == "image":
                    image_evidences.append(ev)
            
            # Construir información del vehículo (Consulta manual)
            vehicle_info = "No especificado"
            if incident.vehicle_id:
                v = db.query(Vehicle).filter(Vehicle.id == incident.vehicle_id).first()
                if v:
                    vehicle_info = f"{v.make} {v.model} ({v.year})"

            # Extraer el audio transcript por separado (si existe)
            audio_transcript = next((ev.transcription for ev in evidence_list if ev.evidence_type.value == "audio" and ev.transcription), None)

            # 2. Análisis IA Multimodal
            triage_result = vertex_service.analyze_incident_multimodal(
                description=incident.description,
                image_urls=[ev.file_url for ev in image_evidences],
                audio_transcript=audio_transcript,
                vehicle_info=vehicle_info
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
            diagnostic = tecnico_info.get("diagnostico_tecnico", incident.description)
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
                EvidenceRepository(db).save(ev)
            if incident.ai_category in ["incierto", "uncertain"] or incident.ai_confidence < 0.4:
                incident.status = IncidentStatus.PENDING_INFO
                IncidentRepository(db).save(incident)
            else:
                incident.status = IncidentStatus.MATCHED
                IncidentRepository(db).save(incident)
                
                # Búsqueda de talleres (encapsulada para no romper el flujo)
                try:
                    logger.info(f"✨ IA Finalizada para {incident_id}. Buscando talleres...")
                    asyncio.run(AssignmentService(db).find_and_create_offer(incident))
                except Exception as e:
                    logger.error(f"Error en asignación de talleres: {e}")

        except Exception as exc:
            logger.error(f"FALLO CRÍTICO IA para incidente {incident_id}: {exc}")
            incident.status = IncidentStatus.ERROR
            IncidentRepository(db).save(incident)
        finally:
            db.close()

    except Exception as exc:
        logger.error(f"Background AI task failed for incident {incident_id}: {exc}")
    finally:
        db.close()


@router.post(
    "/{incident_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("incidents:update"))],
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
    incident = IncidentRepository(db).get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this incident")

    # Guardar nueva evidencia
    from app.incidents.models import IncidentEvidence, EvidenceType
    for ev in extra_evidence.evidences:
        evidence = IncidentEvidence(
            incident_id=incident.id,
            evidence_type=EvidenceType(ev.evidence_type),
            file_url=ev.file_url,
            transcription=ev.transcription,
        )
        EvidenceRepository(db).save(evidence)

    # Si estaba en PENDING_INFO, re-procesar
    if incident.status == IncidentStatus.PENDING_INFO:
        prev_status = incident.status
        incident.status = IncidentStatus.ANALYZING
        IncidentRepository(db).save(incident)
        
        StatusHistoryRepository(db).log_status_change(
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
    dependencies=[Depends(require_permission("incidents:create"))],
)
def request_help(
    incident_data: IncidentCreateDto,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    desc_preview = (incident_data.description or "")[:50]
    logger.info(f"Incident request from user {current_user.id}: {desc_preview!r} vehicle={incident_data.vehicle_id}")
    try:
        incident = IncidentService(db).create_incident_request(current_user, incident_data)
    except Exception as e:
        logger.error(f"Error creating incident: {e}", exc_info=True)
        raise

    StatusHistoryRepository(db).log_status_change(
        incident_id=incident.id,
        previous_status=None,
        new_status=IncidentStatus.PENDING.value,
        reason="Incident created",
    )

    incident.status = IncidentStatus.ANALYZING
    incident = IncidentRepository(db).save(incident)

    StatusHistoryRepository(db).log_status_change(
        incident_id=incident.id,
        previous_status=IncidentStatus.PENDING.value,
        new_status=IncidentStatus.ANALYZING.value,
        reason="AI processing started",
    )

    # [CONECTADO] Notificar al cliente que la solicitud fue recibida
    from app.notifications.services.notification_service import NotificationService
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
    "/my-active",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:read"))],
)
def get_my_active_incident(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the client's most recent non-final incident, or null."""
    from app.incidents.models.incident import Incident as IncidentModel
    from app.incidents.models.enums import IncidentStatus
    from app.clients.models import Client

    client = db.query(Client).filter(Client.id == current_user.id).first()
    if not client:
        return None

    active_statuses = [
        IncidentStatus.PENDING, IncidentStatus.ANALYZING,
        IncidentStatus.PENDING_INFO, IncidentStatus.MATCHED,
        IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS,
    ]
    incident = (
        db.query(IncidentModel)
        .filter(IncidentModel.client_id == client.id, IncidentModel.status.in_(active_statuses))
        .order_by(IncidentModel.created_at.desc())
        .first()
    )
    if not incident:
        return None

    return _build_incident_response(db, incident)


def _build_incident_response(db, incident):
    """Shared helper: build the full incident dict with workshop/technician names."""
    from app.incidents.repositories.evidence_repository import EvidenceRepository
    from app.workshops.models import Workshop, Technician

    evidences = EvidenceRepository(db).get_evidences_by_incident(incident.id)
    vertex_analysis = None
    evidence_urls = []
    for ev in evidences:
        if ev.evidence_type.value.lower() in ["image", "audio"]:
            evidence_urls.append({
                "url": storage_service.generate_signed_url(ev.file_url),
                "type": ev.evidence_type.value.lower(),
            })
        if ev.ai_analysis and "vertex" in ev.ai_analysis:
            vertex_analysis = ev.ai_analysis["vertex"]

    workshop_name = None
    technician_name = None
    if incident.assigned_workshop_id:
        ws = db.query(Workshop).filter(Workshop.id == incident.assigned_workshop_id).first()
        if ws:
            workshop_name = ws.name
    if incident.assigned_technician_id:
        tech = db.query(Technician).filter(Technician.id == incident.assigned_technician_id).first()
        if tech:
            technician_name = f"{tech.name} {tech.last_name}"

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
        "evidence_urls": evidence_urls,
        "workshop_name": workshop_name,
        "technician_name": technician_name,
        "message": "",
    }

@router.get(
    "/pending",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:update"))],
)
def get_pending_incidents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all pending incidents available for workshop offers.
    Returns incidents with status 'pending' or 'matched'.
    Only accessible to workshop_owner users.
    """
    incidents = IncidentRepository(db).get_pending_incidents()

    return [
        {
            "id": str(incident.id),
            "status": incident.status.value,
            "description": incident.description,
            "ai_category": incident.ai_category,
            "ai_priority": incident.ai_priority.value if incident.ai_priority else None,
            "ai_confidence": incident.ai_confidence,
            "latitude": incident.incident_lat,
            "longitude": incident.incident_lng,
            "estimated_arrival_min": incident.estimated_arrival_min,
            "created_at": incident.created_at.isoformat(),
            "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        }
        for incident in incidents
    ]


@router.get(
    "/{incident_id}",
    response_model=dict, # Usamos dict para flexibilidad o IncidentResponseDto si lo permite
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:read"))],
)
def get_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    incident = IncidentRepository(db).get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    
    # [MODIFICADO] Inyectando resolución en caliente de vertex_analysis y relaciones
    evidences = EvidenceRepository(db).get_evidences_by_incident(incident_id)
    vertex_analysis = None
    evidence_urls = []
    
    for ev in evidences:
        if ev.evidence_type.value.lower() in ["image", "audio"]:
            evidence_urls.append({
                "url": storage_service.generate_signed_url(ev.file_url),
                "type": ev.evidence_type.value.lower(),
                "transcription": ev.transcription
            })
        if ev.ai_analysis and "vertex" in ev.ai_analysis:
            vertex_analysis = ev.ai_analysis["vertex"]

    # Workshop & Tech Info
    workshop_name = None
    if incident.assigned_workshop_id:
        w = db.query(Workshop).filter(Workshop.id == incident.assigned_workshop_id).first()
        if w: workshop_name = w.name

    tech_name = None
    if incident.assigned_technician_id:
        t = db.query(Technician).filter(Technician.id == incident.assigned_technician_id).first()
        if t: tech_name = f"{t.name} {t.last_name}"

    # Rating Info
    rating_data = None
    rating = db.query(Rating).filter(Rating.incident_id == incident_id).first()
    if rating:
        rating_data = {
            "score": rating.score,
            "comment": rating.comment,
            "quality_score": rating.quality_score,
            "response_time_score": rating.response_time_score
        }

    # Vehicle Info
    vehicle_info = None
    if incident.vehicle_id:
        v = db.query(Vehicle).filter(Vehicle.id == incident.vehicle_id).first()
        if v:
            vehicle_info = {
                "make": v.make,
                "model": v.model,
                "year": v.year,
                "license_plate": v.license_plate
            }
            
    # Payment Status Resolution
    from app.payments.models import Payment, PaymentStatus
    payment = db.query(Payment).filter(
        Payment.incident_id == incident_id, 
        Payment.status == PaymentStatus.COMPLETED
    ).first()
    payment_status = "completed" if payment else "pending"

    return {
        "id": str(incident.id),
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
        "payment_status": payment_status,
        "created_at": incident.created_at.isoformat(),
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        "vertex_analysis": vertex_analysis,
        "evidence_urls": evidence_urls,
        "workshop_name": workshop_name,
        "technician_name": tech_name,
        "rating": rating_data,
        "vehicle": vehicle_info
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
    dependencies=[Depends(require_permission("incidents:create"))],
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
    dependencies=[Depends(require_permission("incidents:read"))],
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
    dependencies=[Depends(require_permission("incidents:create"))],
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
    dependencies=[Depends(require_permission("incidents:create"))],
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
    dependencies=[Depends(require_permission("incidents:create"))],
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
    dependencies=[Depends(require_permission("incidents:read"))],
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
    "/{incident_id}/cancel",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:create"))],
)
def cancel_incident(
    incident_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = IncidentService(db)
    updated_incident = service.cancel_incident(incident_id, current_user)
    return {
        "id": str(updated_incident.id),
        "status": updated_incident.status.value,
        "message": "El incidente ha sido cancelado correctamente"
    }

