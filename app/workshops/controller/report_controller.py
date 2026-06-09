import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.security.config.security import require_permission
from app.workshops.dtos.report_dtos import (
    FieldDefinition,
    ReportResult,
    ReportRunRequest,
    ReportTemplateCreate,
    ReportTemplateResponse,
    ReportTemplateUpdate,
    ReportTypeDefinition,
    ScheduledReportCreate,
    ScheduledReportResponse,
)
from app.workshops.repositories.report_repository import (
    CATALOG,
    ReportRepository,
)
from app.workshops.services.report_service import ReportService
from app.workshops.services.report_ai_service import ReportAIService
from app.incidents.ai.services.storage_service import upload_audio_file
from app.incidents.ai.services.audio_service import transcribe_audio


router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _get_workshop_id(db: Session, user_id: uuid.UUID) -> str | None:
    result = db.execute(
        text("SELECT id FROM workshops WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": str(user_id)},
    ).fetchone()
    return str(result[0]) if result else None


def _user_roles(current_user) -> list[str]:  # type: ignore[type-arg]
    return [r.name for r in current_user.roles]


@router.get("/catalog", response_model=list[ReportTypeDefinition])
def get_catalog(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:read", "reports:create", "reports:update", "reports:delete")),
):
    roles = _user_roles(current_user)
    repo = ReportRepository(db)
    catalog = repo.get_catalog_for_roles(roles)
    result = []
    for key, entry in catalog.items():
        fields = [
            FieldDefinition(
                key=k,
                label=v["label"],
                type=v.get("type", "STRING"),
                options=v.get("options")
            )
            for k, v in entry["fields"].items()
        ]
        result.append(ReportTypeDefinition(key=key, label=entry["label"], fields=fields))
    return result


@router.post("/run", response_model=ReportResult)
def run_report(
    req: ReportRunRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:read", "reports:create", "reports:update", "reports:delete")),
):
    roles = _user_roles(current_user)
    workshop_id = (
        _get_workshop_id(db, current_user.id) if "workshop_owner" in roles else None
    )
    repo = ReportRepository(db)
    total = repo.count_query(req, roles, workshop_id)
    columns, column_labels, rows = repo.build_and_run_query(req, roles, workshop_id)
    return ReportResult(
        columns=columns,
        column_labels=column_labels,
        rows=rows,
        total=total,
        offset=req.offset,
        limit=req.limit,
    )


_EXPORT_I18N: dict[str, dict[str, str]] = {
    "es": {"sheet": "Reporte", "total": "Total de registros"},
    "en": {"sheet": "Report",  "total": "Total records"},
}


@router.post("/export")
def export_report(
    req: ReportRunRequest,
    format: str = Query("csv", pattern="^(csv|excel|pdf|html)$"),
    title: str = Query("Reporte"),
    lang: str = Query("es", pattern="^(es|en)$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:create", "reports:update", "reports:delete")),
):
    roles = _user_roles(current_user)
    workshop_id = (
        _get_workshop_id(db, current_user.id) if "workshop_owner" in roles else None
    )
    # For export, remove pagination limits
    req.limit = 5000
    req.offset = 0
    repo = ReportRepository(db)
    columns, column_labels, rows = repo.build_and_run_query(req, roles, workshop_id)
    if req.column_labels_override:
        column_labels = {k: req.column_labels_override.get(k, v) for k, v in column_labels.items()}

    i18n = _EXPORT_I18N.get(lang, _EXPORT_I18N["es"])

    if format == "csv":
        data = ReportService.generate_csv(columns, column_labels, rows)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{title}.csv"'},
        )
    elif format == "excel":
        data = ReportService.generate_excel(columns, column_labels, rows, sheet_name=i18n["sheet"])
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{title}.xlsx"'},
        )
    elif format == "pdf":
        data = ReportService.generate_pdf(columns, column_labels, rows, title, total_label=i18n["total"])
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{title}.pdf"'},
        )
    else:  # html
        data = ReportService.generate_html(columns, column_labels, rows, title, total_label=i18n["total"])
        return StreamingResponse(
            io.BytesIO(data),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{title}.html"'},
        )


@router.get("/templates", response_model=list[ReportTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:read", "reports:create", "reports:update", "reports:delete")),
):
    repo = ReportRepository(db)
    return repo.get_templates(current_user.id)


@router.post("/templates", response_model=ReportTemplateResponse, status_code=201)
def save_template(
    data: ReportTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:create", "reports:update", "reports:delete")),
):
    roles = _user_roles(current_user)
    if data.report_type not in CATALOG:
        raise HTTPException(400, "Tipo de reporte inválido")
    entry = CATALOG[data.report_type]
    if not any(r in entry["roles"] for r in roles):
        raise HTTPException(403, "No tienes acceso a este tipo de reporte")
    repo = ReportRepository(db)
    return repo.create_template(data, current_user.id)


@router.get("/templates/{template_id}", response_model=ReportTemplateResponse)
def get_one_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:read", "reports:create", "reports:update", "reports:delete")),
):
    repo = ReportRepository(db)
    tpl = repo.get_template(template_id, current_user.id)
    if not tpl:
        raise HTTPException(404, "Plantilla no encontrada")
    return tpl


@router.put("/templates/{template_id}", response_model=ReportTemplateResponse)
def edit_template(
    template_id: uuid.UUID,
    data: ReportTemplateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:create", "reports:update", "reports:delete")),
):
    repo = ReportRepository(db)
    tpl = repo.get_template(template_id, current_user.id)
    if not tpl:
        raise HTTPException(404, "Plantilla no encontrada")
    if tpl.owner_id != current_user.id:
        raise HTTPException(403, "Solo el propietario puede editar esta plantilla")
    return repo.update_template(tpl, data)


@router.delete("/templates/{template_id}", status_code=204)
def remove_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:create", "reports:update", "reports:delete")),
):
    repo = ReportRepository(db)
    tpl = repo.get_template(template_id, current_user.id)
    if not tpl:
        raise HTTPException(404, "Plantilla no encontrada")
    if tpl.owner_id != current_user.id:
        raise HTTPException(403, "Solo el propietario puede eliminar esta plantilla")
    repo.delete_template(tpl)


class PromptReportRequest(BaseModel):
    prompt: str


class AIReportResponse(BaseModel):
    transcript: Optional[str] = None
    query: ReportRunRequest
    result: ReportResult


@router.post("/prompt", response_model=AIReportResponse)
def run_report_by_prompt(
    req: PromptReportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:read", "reports:create", "reports:update", "reports:delete")),
):
    run_req = ReportAIService.parse_prompt(req.prompt)
    if not run_req:
        raise HTTPException(status_code=400, detail="No se pudo interpretar el prompt del reporte. Intenta ser más específico.")

    roles = _user_roles(current_user)
    workshop_id = (
        _get_workshop_id(db, current_user.id) if "workshop_owner" in roles else None
    )

    entry = CATALOG.get(run_req.report_type)
    if not entry:
        raise HTTPException(status_code=400, detail="Tipo de reporte inválido mapeado por la IA.")
    if not any(r in entry["roles"] for r in roles):
        raise HTTPException(status_code=403, detail="No tienes acceso al tipo de reporte interpretado.")

    repo = ReportRepository(db)
    total = repo.count_query(run_req, roles, workshop_id)
    if run_req.limit is not None:
        total = min(total, run_req.limit)
    columns, column_labels, rows = repo.build_and_run_query(run_req, roles, workshop_id)

    result = ReportResult(
        columns=columns,
        column_labels=column_labels,
        rows=rows,
        total=total,
        offset=run_req.offset,
        limit=run_req.limit,
    )

    return AIReportResponse(query=run_req, result=result)


@router.post("/audio", response_model=AIReportResponse)
def run_report_by_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:read", "reports:create", "reports:update", "reports:delete")),
):
    try:
        upload_res = upload_audio_file(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar el archivo de audio: {str(e)}")

    transcript = transcribe_audio(upload_res.file_url)
    if not transcript:
        raise HTTPException(status_code=400, detail="No se pudo transcribir el audio o el audio no contiene voz legible.")

    run_req = ReportAIService.parse_prompt(transcript)
    if not run_req:
        raise HTTPException(status_code=400, detail=f"Transcripción: '{transcript}'. No se pudo interpretar como un reporte.")

    roles = _user_roles(current_user)
    workshop_id = (
        _get_workshop_id(db, current_user.id) if "workshop_owner" in roles else None
    )

    entry = CATALOG.get(run_req.report_type)
    if not entry:
        raise HTTPException(status_code=400, detail="Tipo de reporte inválido mapeado por la IA.")
    if not any(r in entry["roles"] for r in roles):
        raise HTTPException(status_code=403, detail="No tienes acceso al tipo de reporte interpretado.")

    repo = ReportRepository(db)
    total = repo.count_query(run_req, roles, workshop_id)
    if run_req.limit is not None:
        total = min(total, run_req.limit)
    columns, column_labels, rows = repo.build_and_run_query(run_req, roles, workshop_id)

    result = ReportResult(
        columns=columns,
        column_labels=column_labels,
        rows=rows,
        total=total,
        offset=run_req.offset,
        limit=run_req.limit,
    )

    return AIReportResponse(transcript=transcript, query=run_req, result=result)


@router.get("/templates/{template_id}/schedules", response_model=list[ScheduledReportResponse])
def list_template_schedules(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:read", "reports:create", "reports:update", "reports:delete")),
):
    from app.workshops.models.scheduled_report import ScheduledReport
    repo = ReportRepository(db)
    tpl = repo.get_template(template_id, current_user.id)
    if not tpl:
        raise HTTPException(404, "Plantilla no encontrada")
    
    schedules = db.query(ScheduledReport).filter(ScheduledReport.template_id == template_id).all()
    return schedules


@router.post("/templates/{template_id}/schedules", response_model=ScheduledReportResponse, status_code=201)
def create_template_schedule(
    template_id: uuid.UUID,
    data: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:create", "reports:update", "reports:delete")),
):
    from app.workshops.models.scheduled_report import ScheduledReport
    repo = ReportRepository(db)
    tpl = repo.get_template(template_id, current_user.id)
    if not tpl:
        raise HTTPException(404, "Plantilla no encontrada")
    if tpl.owner_id != current_user.id:
        raise HTTPException(403, "Solo el propietario puede programar esta plantilla")
    
    sched = ScheduledReport(
        template_id=template_id,
        frequency=data.frequency,
        hour=data.hour,
        email=data.email,
        format=data.format,
        is_active=data.is_active
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.delete("/schedules/{schedule_id}", status_code=204)
def remove_schedule(
    schedule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports:create", "reports:update", "reports:delete")),
):
    from app.workshops.models.scheduled_report import ScheduledReport
    from app.workshops.models.report_template import ReportTemplate
    
    sched = db.query(ScheduledReport).filter(ScheduledReport.id == schedule_id).first()
    if not sched:
        raise HTTPException(404, "Programación no encontrada")
    
    tpl = db.query(ReportTemplate).filter(ReportTemplate.id == sched.template_id).first()
    if not tpl or tpl.owner_id != current_user.id:
        raise HTTPException(403, "No tienes permiso para eliminar esta programación")
        
    db.delete(sched)
    db.commit()


