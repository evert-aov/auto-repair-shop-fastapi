import contextvars
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.audit.database import AuditSessionLocal
from app.audit.models.audit_log import AuditLog
from app.audit.services.audit_log_service import AuditLogService

logger = logging.getLogger("audit.middleware")

AUDITABLE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_DEFAULT_EXCLUDED = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/schema",
    "/api-docs",
    "/swagger",
    "/health",
    "/metrics",
    "/static",
    "/openapi.json",
    "/docs",
    "/redoc",
}

_extra_excluded_raw = os.getenv("AUDIT_EXCLUDE_PATHS", "")
_extra_excluded = {
    p.strip()
    for p in _extra_excluded_raw.split(",")
    if p.strip()
}

EXCLUDED_PATHS = _DEFAULT_EXCLUDED | _extra_excluded

_TRUSTED_PROXIES_RAW = os.getenv("AUDIT_TRUSTED_PROXIES", "")
TRUSTED_PROXIES = {ip.strip() for ip in _TRUSTED_PROXIES_RAW.split(",") if ip.strip()}

_current_request: contextvars.ContextVar[Request | None] = contextvars.ContextVar(
    "audit_current_request", default=None
)


def get_current_request() -> Request | None:
    return _current_request.get(None)


class AuditMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        _current_request.set(request)
        try:
            if not self._should_audit(request):
                return await call_next(request)

            start_time = time.time()
            is_multipart = request.headers.get("content-type", "").startswith("multipart/")

            body_bytes: bytes | None = None
            if not is_multipart:
                try:
                    body_bytes = await request.body()
                except Exception:
                    pass

            try:
                response = await call_next(request)
            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                self._build_and_save(request, body_bytes, 500, str(e), elapsed_ms)
                raise

            if not getattr(request.state, '_audited', False):
                elapsed_ms = int((time.time() - start_time) * 1000)
                self._build_and_save(request, body_bytes, response.status_code, None, elapsed_ms)
            else:
                logger.debug("Skipping middleware audit: already captured by @auditable")

            return response
        finally:
            _current_request.set(None)

    def _should_audit(self, request: Request) -> bool:
        if request.method not in AUDITABLE_METHODS:
            return False
        path = request.url.path
        if not path.startswith("/api/"):
            return False
        return not any(path.startswith(p) for p in EXCLUDED_PATHS)

    def _build_and_save(
        self,
        request: Request,
        body_bytes: bytes | None,
        status_code: int,
        error_message: str | None,
        duration_ms: int,
    ) -> None:
        try:
            entry = AuditLog()
            entry.id = uuid.uuid4()
            entry.request_method = request.method
            query_str = request.url.query
            entry.request_path = str(request.url.path) + ("?" + query_str if query_str else "")
            entry.ip_address = self._get_client_ip(request)
            entry.user_agent = request.headers.get("User-Agent")
            entry.response_status = status_code
            entry.error_message = error_message
            entry.execution_time_ms = int(duration_ms)

            if status_code >= 500:
                entry.severity = "CRITICAL"
            elif status_code >= 400:
                entry.severity = "WARNING"
            else:
                entry.severity = "INFO"

            client_time_header = request.headers.get("X-Client-Time")
            if client_time_header:
                try:
                    entry.client_time = datetime.fromisoformat(client_time_header)
                except ValueError:
                    pass

            session_id_header = request.headers.get("X-Session-ID")
            if session_id_header:
                try:
                    entry.session_id = uuid.UUID(session_id_header.strip())
                except ValueError:
                    pass

            entry.resource_type = self._extract_resource_type(request.url.path)
            entry.resource_id = self._extract_resource_id(request.url.path)
            entry.action_type = self._infer_action_type(request.method)

            try:
                user = getattr(request.state, "current_user", None)
                if user is not None:
                    entry.user_id = getattr(user, "id", None)
                    entry.user_email = getattr(user, "email", None)
                    entry.user_name = getattr(user, "username", None)
                    workshop_id = getattr(user, "workshop_id", None)
                    if workshop_id is None and hasattr(user, "workshop"):
                        w = getattr(user, "workshop", None)
                        if w:
                            workshop_id = getattr(w, "id", None)
                    entry.workshop_id = workshop_id
            except Exception:
                pass

            if body_bytes:
                entry.request_body = body_bytes

            db = AuditSessionLocal()
            try:
                AuditLogService.get_instance().log_action(entry, db)
            finally:
                db.close()

            if duration_ms > 5000:
                logger.warning(
                    "Slow request: %s %s took %dms [status=%d]",
                    request.method, request.url.path, duration_ms, status_code,
                )

        except Exception as e:
            logger.error("Error building audit log entry in middleware: %s", e, exc_info=True)

    def _get_client_ip(self, request: Request) -> str:
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            ips = [ip.strip() for ip in x_forwarded_for.split(",")]
            if not TRUSTED_PROXIES:
                return ips[0]
            for ip_str in reversed(ips):
                if ip_str not in TRUSTED_PROXIES:
                    return ip_str
        client = getattr(request, "client", None)
        if client and client.host:
            return client.host
        return "unknown"

    def _extract_resource_type(self, path: str) -> str:
        segments = path.lstrip("/api/").split("/")
        if segments and segments[0]:
            primary = segments[0].upper()
            if primary == "MODULE_USERS" and len(segments) > 1:
                return segments[1].upper()
            return primary
        return "UNKNOWN"

    def _extract_resource_id(self, path: str) -> str | None:
        segments = path.lstrip("/api/").split("/")
        for segment in reversed(segments):
            try:
                uuid.UUID(segment)
                return segment
            except (ValueError, AttributeError):
                continue
        return None

    def _infer_action_type(self, method: str) -> str:
        mapping = {
            "POST": "CREATE",
            "PUT": "UPDATE",
            "PATCH": "UPDATE",
            "DELETE": "DELETE",
        }
        return mapping.get(method.upper(), "READ")
