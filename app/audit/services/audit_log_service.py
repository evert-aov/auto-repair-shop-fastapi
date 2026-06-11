import csv
import io
import json
import logging
import os
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, and_, or_, func
from sqlalchemy.orm import Session

from app.audit.models.audit_log import AuditLog
from app.audit.services.audit_encryption import AuditEncryptionService
from app.audit.services.audit_hash import AuditHashService
from app.audit.schemas.audit_schemas import AuditFilter, AuditLogResponse, AuditPage
from app.audit.utils.auditoria_utils import AuditoriaUtils

logger = logging.getLogger("audit.service")
audit_struct_logger = logging.getLogger("AUDIT")


class AuditLogService:
    _instance: "AuditLogService | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._encryption = AuditEncryptionService()
        self._hash_service = AuditHashService()
        self._failed_buffer: queue.Queue[AuditLog] = queue.Queue()
        self._max_buffer_size = int(os.getenv("AUDIT_BUFFER_MAX_SIZE", "10000"))
        self._initiated = False

    @classmethod
    def get_instance(cls) -> "AuditLogService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    instance._start_retry_scheduler()
                    cls._instance = instance
        return cls._instance

    def _start_retry_scheduler(self) -> None:
        if self._initiated:
            return
        self._initiated = True

        def _retry_loop() -> None:
            import time
            while True:
                time.sleep(30)
                self._retry_failed_logs()

        t = threading.Thread(target=_retry_loop, daemon=True, name="audit-retry")
        t.start()

    def log_action(self, entry: AuditLog, db: Session) -> None:
        try:
            if entry.id is None:
                entry.id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            if entry.created_at is None:
                entry.created_at = now
            if entry.updated_at is None:
                entry.updated_at = now

            entry.resource_type = _truncate(entry.resource_type, 100)
            entry.resource_id = _truncate(entry.resource_id, 100)
            entry.resource_name = _truncate(entry.resource_name, 255)
            entry.ip_address = _truncate(entry.ip_address, 45)
            entry.request_method = _truncate(entry.request_method, 10)
            entry.request_path = _truncate(entry.request_path, 500)
            entry.user_email = _truncate(entry.user_email, 255)
            entry.user_name = _truncate(entry.user_name, 255)

            self._encrypt_and_sanitize_fields(entry)
            entry.integrity_hash = self._hash_service.generate_hash(entry)

            db.add(entry)
            db.commit()
            self._send_to_structured_logging(entry)

        except Exception as e:
            logger.error("Error saving audit log (non-blocking): %s", e, exc_info=True)
            self._add_to_buffer(entry)

    def log_action_async(self, entry: AuditLog) -> None:
        from app.audit.database import AuditSessionLocal

        def _run() -> None:
            db = AuditSessionLocal()
            try:
                self.log_action(entry, db)
            finally:
                db.close()

        t = threading.Thread(target=_run, daemon=True, name="audit-async")
        t.start()

    def _retry_failed_logs(self) -> None:
        from app.audit.database import AuditSessionLocal

        if self._failed_buffer.empty():
            return

        logger.info("Retrying %s failed audit logs from buffer", self._failed_buffer.qsize())
        to_retry: list[AuditLog] = []
        while not self._failed_buffer.empty():
            try:
                to_retry.append(self._failed_buffer.get_nowait())
            except queue.Empty:
                break

        db = AuditSessionLocal()
        succeeded = 0
        try:
            for e in to_retry:
                try:
                    db.add(e)
                    db.commit()
                    self._send_to_structured_logging(e)
                    succeeded += 1
                except Exception as ex:
                    error_str = str(ex)
                    if "duplicate" in error_str.lower() or "unique" in error_str.lower():
                        logger.error(
                            "Audit log failed with duplicate/unique violation, discarding. Error: %s", ex
                        )
                    else:
                        logger.error("Retry failed for audit log, re-queuing: %s", ex)
                        self._failed_buffer.put(e)
        finally:
            db.close()

        if succeeded > 0:
            logger.info(
                "Recovered %d audit logs from buffer (%d remaining)",
                succeeded,
                self._failed_buffer.qsize(),
            )

    def _add_to_buffer(self, entry: AuditLog) -> None:
        if self._failed_buffer.qsize() >= self._max_buffer_size:
            try:
                self._failed_buffer.get_nowait()
            except queue.Empty:
                pass
            logger.warning("Audit buffer full (%d), oldest entry discarded", self._max_buffer_size)
        self._failed_buffer.put(entry)
        logger.info("Audit log queued to buffer (size: %d)", self._failed_buffer.qsize())

    def _encrypt_and_sanitize_fields(self, entry: AuditLog) -> None:
        if entry.request_body is not None and len(entry.request_body) > 0:
            body_json = self._sanitize_and_serialize(entry.request_body)
            entry.request_body = self._encryption.encrypt(body_json)

        if entry.changes_before is not None and len(entry.changes_before) > 0:
            before_json = self._sanitize_and_serialize(entry.changes_before)
            entry.changes_before = self._encryption.encrypt(before_json)

        if entry.changes_after is not None and len(entry.changes_after) > 0:
            after_json = self._sanitize_and_serialize(entry.changes_after)
            entry.changes_after = self._encryption.encrypt(after_json)

    def _sanitize_and_serialize(self, raw_body: bytes) -> str:
        try:
            body_str = raw_body.decode("utf-8")
            body = json.loads(body_str)
            if isinstance(body, dict):
                sanitized = AuditoriaUtils.sanitize_map(body)
                return json.dumps(sanitized, default=str)
            return body_str
        except Exception:
            return raw_body.decode("utf-8", errors="replace")

    def _send_to_structured_logging(self, entry: AuditLog) -> None:
        try:
            audit_struct_logger.info(
                "AUDIT | workshop=%s | user=%s | action=%s | resource=%s/%s | status=%s | id=%s",
                entry.workshop_id,
                entry.user_name,
                entry.action_type,
                entry.resource_type,
                entry.resource_id,
                entry.response_status,
                entry.id,
            )
        except Exception as e:
            logger.warning("Failed to send structured audit log: %s", e)

    def _to_response(self, entry: AuditLog) -> AuditLogResponse:
        return AuditLogResponse(
            id=entry.id,
            workshop_id=entry.workshop_id,
            user_id=entry.user_id,
            user_email=entry.user_email,
            user_name=entry.user_name,
            action_type=entry.action_type or "",
            resource_type=entry.resource_type or "",
            resource_id=entry.resource_id,
            resource_name=entry.resource_name,
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
            request_method=entry.request_method,
            request_path=entry.request_path,
            request_body=self._encryption.decrypt_map(entry.request_body) if entry.request_body else None,
            changes_before=self._encryption.decrypt_map(entry.changes_before) if entry.changes_before else None,
            changes_after=self._encryption.decrypt_map(entry.changes_after) if entry.changes_after else None,
            response_status=entry.response_status,
            error_message=entry.error_message,
            integrity_hash=entry.integrity_hash,
            created_at=entry.created_at,
            client_time=entry.client_time,
            session_id=entry.session_id,
            severity=entry.severity or "INFO",
            execution_time_ms=entry.execution_time_ms,
            valid=self._hash_service.verify_hash(entry),
        )

    def find_all(self, db: Session, filters: AuditFilter, page: int, size: int) -> AuditPage:
        query = db.query(AuditLog)

        conditions = []
        if filters.workshop_id:
            conditions.append(AuditLog.workshop_id == filters.workshop_id)
        if filters.action_type:
            conditions.append(AuditLog.action_type == filters.action_type)
        if filters.resource_type:
            conditions.append(AuditLog.resource_type.ilike(f"%{filters.resource_type}%"))
        if filters.date_from:
            conditions.append(AuditLog.created_at >= filters.date_from)
        if filters.date_to:
            conditions.append(AuditLog.created_at <= filters.date_to)
        if filters.user_identifier:
            term = f"%{filters.user_identifier.lower()}%"
            user_conditions = [
                func.lower(AuditLog.user_name).like(term),
                func.lower(AuditLog.user_email).like(term),
            ]
            try:
                user_uuid = uuid.UUID(filters.user_identifier)
                user_conditions.append(AuditLog.user_id == user_uuid)
            except (ValueError, AttributeError):
                pass
            conditions.append(or_(*user_conditions))

        if conditions:
            query = query.filter(and_(*conditions))

        total = query.count()
        total_pages = max(1, (total + size - 1) // size)

        entries = (
            query.order_by(desc(AuditLog.created_at))
            .offset(page * size)
            .limit(size)
            .all()
        )

        content = [self._to_response(e) for e in entries]

        return AuditPage(
            content=content,
            total_elements=total,
            total_pages=total_pages,
            number=page,
            size=size,
        )

    def find_by_id(self, db: Session, entry_id: uuid.UUID) -> AuditLogResponse:
        entry = db.query(AuditLog).filter(AuditLog.id == entry_id).first()
        if entry is None:
            raise ValueError(f"Audit log not found: {entry_id}")

        if not self._hash_service.verify_hash(entry):
            logger.warning("Audit log integrity violation detected: %s", entry_id)

        return self._to_response(entry)

    def verify_integrity(self, db: Session, entry_id: uuid.UUID) -> "IntegrityCheckResultAvro":
        entry = db.query(AuditLog).filter(AuditLog.id == entry_id).first()
        if entry is None:
            raise ValueError(f"Audit log not found: {entry_id}")

        is_valid = self._hash_service.verify_hash(entry)
        return IntegrityCheckResultAvro(
            id=entry.id,
            valid=is_valid,
            message="Log integro" if is_valid else "ADVERTENCIA: Log ha sido manipulado",
        )

    def verify_all(self, db: Session, limit: int = 100) -> list["IntegrityCheckResultAvro"]:
        entries = (
            db.query(AuditLog)
            .order_by(desc(AuditLog.created_at))
            .limit(min(limit, 500))
            .all()
        )

        results: list[IntegrityCheckResultAvro] = []
        for entry in entries:
            is_valid = self._hash_service.verify_hash(entry)
            results.append(
                IntegrityCheckResultAvro(
                    id=entry.id,
                    valid=is_valid,
                    message="Log integro" if is_valid else "ADVERTENCIA: Log ha sido manipulado",
                )
            )

        manipulation_count = sum(1 for r in results if not r.valid)
        logger.info(
            "Integrity check completed: %d logs checked, %d manipulations detected",
            len(results),
            manipulation_count,
        )
        return results

    def export_csv(self, db: Session, filters: AuditFilter) -> bytes:
        query = db.query(AuditLog)
        conditions = []
        if filters.workshop_id:
            conditions.append(AuditLog.workshop_id == filters.workshop_id)
        if filters.action_type:
            conditions.append(AuditLog.action_type == filters.action_type)
        if filters.resource_type:
            conditions.append(AuditLog.resource_type.ilike(f"%{filters.resource_type}%"))
        if filters.date_from:
            conditions.append(AuditLog.created_at >= filters.date_from)
        if filters.date_to:
            conditions.append(AuditLog.created_at <= filters.date_to)
        if filters.user_identifier:
            term = f"%{filters.user_identifier.lower()}%"
            user_conditions = [
                func.lower(AuditLog.user_name).like(term),
                func.lower(AuditLog.user_email).like(term),
            ]
            try:
                user_uuid = uuid.UUID(filters.user_identifier)
                user_conditions.append(AuditLog.user_id == user_uuid)
            except (ValueError, AttributeError):
                pass
            conditions.append(or_(*user_conditions))
        if conditions:
            query = query.filter(and_(*conditions))

        entries = query.order_by(desc(AuditLog.created_at)).limit(100000).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "workshopId", "userId", "userEmail", "userName", "actionType",
            "resourceType", "resourceId", "resourceName", "ipAddress",
            "requestMethod", "requestPath", "responseStatus", "errorMessage",
            "createdAt", "clientTime", "integrityValid",
        ])

        for entry in entries:
            writer.writerow([
                str(entry.id),
                str(entry.workshop_id) if entry.workshop_id else "",
                str(entry.user_id) if entry.user_id else "",
                entry.user_email or "",
                entry.user_name or "",
                entry.action_type or "",
                entry.resource_type or "",
                entry.resource_id or "",
                entry.resource_name or "",
                entry.ip_address or "",
                entry.request_method or "",
                entry.request_path or "",
                entry.response_status or "",
                entry.error_message or "",
                entry.created_at.isoformat() if entry.created_at else "",
                entry.client_time.isoformat() if entry.client_time else "",
                "VALID" if self._hash_service.verify_hash(entry) else "MANIPULATED",
            ])

        return output.getvalue().encode("utf-8")


def _truncate(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    return value[:max_len] if len(value) > max_len else value


class IntegrityCheckResultAvro:
    def __init__(self, id: uuid.UUID, valid: bool, message: str):
        self.id = id
        self.valid = valid
        self.message = message
