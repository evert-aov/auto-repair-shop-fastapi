import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ActionTypeEnum(str, enum.Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SIGN = "SIGN"
    DOWNLOAD = "DOWNLOAD"
    EXPORT = "EXPORT"


class AuditFilter(BaseModel):
    workshop_id: uuid.UUID | None = None
    user_identifier: str | None = None
    action_type: str | None = None
    resource_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    workshop_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    user_name: str | None = None
    action_type: str
    resource_type: str
    resource_id: str | None = None
    resource_name: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    request_body: dict[str, Any] | None = None
    changes_before: dict[str, Any] | None = None
    changes_after: dict[str, Any] | None = None
    response_status: int | None = None
    error_message: str | None = None
    integrity_hash: str | None = None
    created_at: datetime
    client_time: datetime | None = None
    session_id: uuid.UUID | None = None
    severity: str | None = "INFO"
    execution_time_ms: int | None = None
    valid: bool = False

    model_config = {"from_attributes": True}


class AuditPage(BaseModel):
    content: list[AuditLogResponse]
    total_elements: int
    total_pages: int
    number: int
    size: int


class IntegrityCheckResult(BaseModel):
    id: uuid.UUID
    valid: bool
    message: str
