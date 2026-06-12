import io
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.audit.database import AuditSessionLocal, get_audit_db
from app.audit.dependencies import require_admin
from app.audit.schemas.audit_schemas import (
    AuditFilter,
    AuditLogResponse,
    AuditPage,
    IntegrityCheckResult,
)
from app.audit.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/api/audit", tags=["Audit"])


def _get_audit_service() -> AuditLogService:
    return AuditLogService.get_instance()


def _parse_workshop_id(raw: str | None) -> uuid.UUID | None:
    if not raw or not raw.strip():
        return None
    try:
        return uuid.UUID(raw.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"workshop_id inválido: '{raw}' no es un UUID válido")


@router.get(
    "",
    response_model=AuditPage,
    dependencies=[Depends(require_admin)],
)
def list_audit_logs(
    workshop_id: str | None = Query(None),
    user_identifier: str | None = Query(None),
    action_type: str | None = Query(None),
    resource_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_audit_db),
    service: AuditLogService = Depends(_get_audit_service),
):
    ws_id = _parse_workshop_id(workshop_id)
    filtro = AuditFilter(
        workshop_id=ws_id,
        user_identifier=user_identifier,
        action_type=action_type,
        resource_type=resource_type,
        date_from=datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc) if date_from else None,
        date_to=datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc) if date_to else None,
    )
    return service.find_all(db, filtro, page, size)


@router.get(
    "/{entry_id}",
    response_model=AuditLogResponse,
    dependencies=[Depends(require_admin)],
)
def get_audit_log(
    entry_id: uuid.UUID,
    db: Session = Depends(get_audit_db),
    service: AuditLogService = Depends(_get_audit_service),
):
    return service.find_by_id(db, entry_id)


@router.get(
    "/{entry_id}/verify",
    dependencies=[Depends(require_admin)],
)
def verify_integrity(
    entry_id: uuid.UUID,
    db: Session = Depends(get_audit_db),
    service: AuditLogService = Depends(_get_audit_service),
):
    result = service.verify_integrity(db, entry_id)
    return {"id": str(result.id), "valid": result.valid, "message": result.message}


@router.post(
    "/verify-all",
    dependencies=[Depends(require_admin)],
)
def verify_all(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_audit_db),
    service: AuditLogService = Depends(_get_audit_service),
):
    results = service.verify_all(db, limit)
    return [
        {"id": str(r.id), "valid": r.valid, "message": r.message}
        for r in results
    ]


@router.get(
    "/export",
    dependencies=[Depends(require_admin)],
)
def export_csv(
    workshop_id: str | None = Query(None),
    user_identifier: str | None = Query(None),
    action_type: str | None = Query(None),
    resource_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_audit_db),
    service: AuditLogService = Depends(_get_audit_service),
):
    ws_id = _parse_workshop_id(workshop_id)
    filtro = AuditFilter(
        workshop_id=ws_id,
        user_identifier=user_identifier,
        action_type=action_type,
        resource_type=resource_type,
        date_from=datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc) if date_from else None,
        date_to=datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc) if date_to else None,
    )
    csv_bytes = service.export_csv(db, filtro)

    filename = f"audit_log_{date.today().isoformat()}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
