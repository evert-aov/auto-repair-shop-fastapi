import json
import logging
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

from app.audit.database import AuditSessionLocal
from app.audit.models.audit_log import AuditLog
from app.audit.middleware.audit_middleware import (
    get_current_request,
)
from app.audit.services.audit_log_service import AuditLogService
from app.audit.utils.auditoria_utils import AuditoriaUtils

logger = logging.getLogger("audit.decorator")


def _mark_request_audited() -> None:
    request = get_current_request()
    if request is not None:
        request.state._audited = True


def auditable(
    resource_type: str,
    action_type: str,
    id_param_name: str = "id",
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            self_obj = args[0] if args else None
            resource_id = _extract_id(args, kwargs, id_param_name)

            state_antes = None
            if _has_audit_methods(self_obj) and resource_id is not None and action_type in ("UPDATE", "DELETE"):
                try:
                    entity = self_obj.get_entity(resource_id)
                    if entity is not None:
                        state_antes = self_obj.to_audit_map(entity)
                    else:
                        logger.warning(
                            "get_entity returned None for %s id=%s — entity may have been deleted already",
                            resource_type, resource_id,
                        )
                except Exception as e:
                    logger.error(
                        "Could not get before state for %s id=%s: %s",
                        resource_type, resource_id, e, exc_info=True,
                    )

            start = time.time()
            result = None
            error: Exception | None = None
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                error = e
                execution_time_ms = int((time.time() - start) * 1000)
                _build_and_save(
                    resource_type=resource_type,
                    action_type=action_type,
                    resource_id=resource_id,
                    state_antes=state_antes,
                    state_despues=None,
                    execution_time_ms=execution_time_ms,
                    error=error,
                    func=func,
                )
                raise

            execution_time_ms = int((time.time() - start) * 1000)

            id_final = resource_id
            if id_final is None and result is not None and action_type == "CREATE":
                id_final = _extract_id_from_result(result)

            state_despues = None
            if _has_audit_methods(self_obj) and result is not None and action_type != "DELETE":
                try:
                    if hasattr(self_obj, "to_audit_map_from_result"):
                        state_despues = self_obj.to_audit_map_from_result(result)
                    if (state_despues is None or len(state_despues) == 0) and id_final is not None:
                        entity_after = self_obj.get_entity(id_final)
                        if entity_after is not None:
                            state_despues = self_obj.to_audit_map(entity_after)
                except Exception as e:
                    logger.error(
                        "Could not get after state for %s id=%s: %s",
                        resource_type, id_final, e, exc_info=True,
                    )

            _build_and_save(
                resource_type=resource_type,
                action_type=action_type,
                resource_id=id_final,
                state_antes=state_antes,
                state_despues=state_despues,
                execution_time_ms=execution_time_ms,
                error=None,
                func=func,
            )

            return result

        return wrapper

    return decorator


def _has_audit_methods(obj: Any) -> bool:
    return obj is not None and hasattr(obj, "get_entity") and hasattr(obj, "to_audit_map")


def _extract_id(args: tuple, kwargs: dict, id_param_name: str) -> Any:
    if id_param_name in kwargs:
        return kwargs[id_param_name]
    if len(args) > 1:
        candidate = args[1]
        if isinstance(candidate, (str, int, uuid.UUID)):
            return candidate
        logger.warning(
            "Could not extract ID from positional args: id_param_name=%s, args[1] type=%s",
            id_param_name, type(candidate).__name__,
        )
    return None


def _build_and_save(
    resource_type: str,
    action_type: str,
    resource_id: Any,
    state_antes: dict | None,
    state_despues: dict | None,
    execution_time_ms: int,
    error: Exception | None,
    func: Callable,
) -> None:
    try:
        datos_antes = state_antes
        datos_nuevos = state_despues

        if action_type in ("UPDATE", "DELETE") and resource_id is not None and (datos_antes is None or len(datos_antes) == 0):
            logger.warning(
                "Audit warning: %s %s id=%s has no before-state data captured",
                action_type, resource_type, resource_id,
            )

        if action_type == "UPDATE" and state_antes is not None and state_despues is not None:
            diff = AuditoriaUtils.calculate_diff(state_antes, state_despues)
            datos_antes = diff[0]
            datos_nuevos = diff[1]

        entry = AuditLog()
        entry.id = uuid.uuid4()
        entry.action_type = action_type
        entry.resource_type = resource_type
        entry.resource_id = str(resource_id) if resource_id else None

        if datos_antes:
            readable_name = datos_antes.get("name") or datos_antes.get("business_name") or datos_antes.get("username")
            if readable_name:
                entry.resource_name = f"{readable_name} ({resource_type}/{resource_id})" if resource_id else readable_name
            else:
                entry.resource_name = f"{resource_type}/{resource_id}" if resource_id else resource_type
        else:
            entry.resource_name = f"{resource_type}/{resource_id}" if resource_id else resource_type

        entry.response_status = 500 if error else 200
        entry.execution_time_ms = execution_time_ms
        entry.severity = "CRITICAL" if error else "INFO"
        entry.error_message = str(error) if error else None

        if datos_antes:
            entry.changes_before = json.dumps(datos_antes, default=str).encode("utf-8")
        if datos_nuevos:
            entry.changes_after = json.dumps(datos_nuevos, default=str).encode("utf-8")

        if action_type == "UPDATE" and resource_id is not None:
            req_json = json.dumps({"id": str(resource_id), "action": action_type})
            entry.request_body = req_json.encode("utf-8")

        _capture_http_context(entry, func)

        _mark_request_audited()
        db = AuditSessionLocal()
        try:
            AuditLogService.get_instance().log_action(entry, db)
        finally:
            db.close()

    except Exception as e:
        logger.error("Error building @auditable audit log: %s", e, exc_info=True)


def _capture_http_context(entry: AuditLog, func: Callable) -> None:
    request = get_current_request()
    if request is None:
        entry.request_method = "ASPECT"
        entry.request_path = func.__qualname__
        return

    try:
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            entry.ip_address = x_forwarded_for.split(",")[0].strip()
        else:
            client = getattr(request, "client", None)
            if client and client.host:
                entry.ip_address = client.host

        user_agent = request.headers.get("User-Agent")
        if user_agent:
            entry.user_agent = user_agent

        entry.request_method = request.method
        query_str = request.url.query
        entry.request_path = str(request.url.path) + ("?" + query_str if query_str else "")

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
    except Exception as e:
        logger.debug("Could not extract HTTP context in decorator: %s", e)

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
    except Exception as e:
        logger.debug("Could not resolve user in decorator: %s", e)


def _extract_id_from_result(result: Any) -> Any:
    if result is None:
        return None
    for attr in ("id", "Id", "ID"):
        if hasattr(result, attr):
            return getattr(result, attr)
    if isinstance(result, dict):
        return result.get("id") or result.get("Id")
    return None
