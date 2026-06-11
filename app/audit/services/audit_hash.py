import hashlib
import hmac
import logging
import os

from app.audit.models.audit_log import AuditLog

logger = logging.getLogger("audit.hash")

AUDIT_INTEGRITY_KEY = os.getenv(
    "AUDIT_INTEGRITY_KEY",
    "SZE2vlhEUJVF8svvD4hG0xigvh1MML2WRGB2z7bimkZvsPqpPWkNzJk2oZXTKfkp",
)


class AuditHashService:

    def __init__(self) -> None:
        key_len = len(AUDIT_INTEGRITY_KEY)
        if key_len < 32:
            logger.warning(
                "Audit integrity key is too short (%d chars < 32). Generate a secure key.", key_len
            )
        if AUDIT_INTEGRITY_KEY == "SZE2vlhEUJVF8svvD4hG0xigvh1MML2WRGB2z7bimkZvsPqpPWkNzJk2oZXTKfkp":
            logger.warning(
                "Using default AUDIT_INTEGRITY_KEY. Set AUDIT_INTEGRITY_KEY env var for production."
            )

    def generate_hash(self, entry: AuditLog) -> str:
        hash_data: dict[str, str] = {}

        hash_data["id"] = str(entry.id) if entry.id else ""
        hash_data["workshopId"] = str(entry.workshop_id) if entry.workshop_id else ""
        hash_data["userId"] = str(entry.user_id) if entry.user_id else ""
        hash_data["userEmail"] = entry.user_email or ""
        hash_data["actionType"] = entry.action_type or ""
        hash_data["resourceType"] = entry.resource_type or ""
        hash_data["resourceId"] = entry.resource_id or ""
        hash_data["createdAt"] = entry.created_at.isoformat() if entry.created_at else ""
        hash_data["ipAddress"] = entry.ip_address or ""
        hash_data["clientTime"] = entry.client_time.isoformat() if entry.client_time else ""
        hash_data["sessionId"] = str(entry.session_id) if entry.session_id else ""
        hash_data["severity"] = entry.severity or ""
        hash_data["executionTimeMs"] = str(entry.execution_time_ms) if entry.execution_time_ms is not None else ""

        if entry.request_body:
            hash_data["requestBodyHash"] = hashlib.sha256(entry.request_body).hexdigest()
        else:
            hash_data["requestBodyHash"] = ""
        if entry.changes_before:
            hash_data["changesBeforeHash"] = hashlib.sha256(entry.changes_before).hexdigest()
        else:
            hash_data["changesBeforeHash"] = ""
        if entry.changes_after:
            hash_data["changesAfterHash"] = hashlib.sha256(entry.changes_after).hexdigest()
        else:
            hash_data["changesAfterHash"] = ""

        canonical = str(sorted(hash_data.items()))
        mac = hmac.new(
            AUDIT_INTEGRITY_KEY.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        )
        return mac.hexdigest()

    def verify_hash(self, entry: AuditLog) -> bool:
        stored_hash = entry.integrity_hash
        if stored_hash is None:
            return False

        entry.integrity_hash = None
        calculated_hash = self.generate_hash(entry)
        entry.integrity_hash = stored_hash

        return stored_hash == calculated_hash
