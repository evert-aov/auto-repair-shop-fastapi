import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ReportFilter(BaseModel):
    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, like, is_null, is_not_null
    value: Optional[Any] = None


class ReportRunRequest(BaseModel):
    report_type: str
    selected_fields: list[str] = Field(min_length=1)
    filters: list[ReportFilter] = []
    sort_field: Optional[str] = None
    sort_order: str = "asc"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=500, le=5000)
    offset: int = 0
    column_labels_override: Optional[dict[str, str]] = None


class ReportTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    report_type: str
    selected_fields: list[str] = Field(min_length=1)
    filters: list[ReportFilter] = []
    sort_field: Optional[str] = None
    sort_order: str = "asc"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_shared: bool = False


class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    selected_fields: Optional[list[str]] = None
    filters: Optional[list[ReportFilter]] = None
    sort_field: Optional[str] = None
    sort_order: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_shared: Optional[bool] = None


class ReportTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    owner_id: uuid.UUID
    report_type: str
    selected_fields: list[str]
    filters: list[Any]
    sort_field: Optional[str]
    sort_order: str
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    is_shared: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FieldDefinition(BaseModel):
    key: str
    label: str


class ReportTypeDefinition(BaseModel):
    key: str
    label: str
    fields: list[FieldDefinition]


class ReportResult(BaseModel):
    columns: list[str]
    column_labels: dict[str, str]
    rows: list[dict[str, Any]]
    total: int
    offset: int
    limit: int
