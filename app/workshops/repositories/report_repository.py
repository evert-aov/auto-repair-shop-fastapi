import datetime as dt
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.workshops.models.report_template import ReportTemplate
from app.workshops.dtos.report_dtos import (
    ReportRunRequest,
    ReportTemplateCreate,
    ReportTemplateUpdate,
)

# ── Report Catalog ────────────────────────────────────────────────────────────
# Each entry: from_clause, date_field, workshop_filter (SQL fragment using :workshop_id param),
# joins_available (name→SQL), fields (key→{label, sql, joins[]})
# roles: which roles can access this report type
CATALOG: dict[str, dict] = {
    "incidents": {
        "label": "Incidentes",
        "roles": ["admin"],
        "from_clause": "incidents i",
        "date_field": "i.created_at",
        "workshop_filter": None,
        "joins_available": {
            "client": "LEFT JOIN users u ON u.id = i.client_id",
            "vehicle": "LEFT JOIN vehicles v ON v.id = i.vehicle_id",
            "workshop": "LEFT JOIN workshops w ON w.id = i.assigned_workshop_id",
        },
        "fields": {
            "id": {"label": "ID Incidente", "sql": "CAST(i.id AS TEXT)", "joins": []},
            "description": {"label": "Descripción", "sql": "i.description", "joins": []},
            "status": {"label": "Estado", "sql": "CAST(i.status AS TEXT)", "joins": []},
            "ai_category": {"label": "Categoría IA", "sql": "i.ai_category", "joins": []},
            "ai_priority": {"label": "Prioridad IA", "sql": "CAST(i.ai_priority AS TEXT)", "joins": []},
            "created_at": {"label": "Fecha Creación", "sql": "i.created_at", "joins": []},
            "updated_at": {"label": "Última Actualización", "sql": "i.updated_at", "joins": []},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"]},
            "client_email": {"label": "Email Cliente", "sql": "u.email", "joins": ["client"]},
            "vehicle_info": {
                "label": "Vehículo",
                "sql": "CONCAT(COALESCE(v.make,''), ' ', COALESCE(v.model,''), ' - ', COALESCE(v.license_plate,''))",
                "joins": ["vehicle"],
            },
            "workshop_name": {"label": "Taller Asignado", "sql": "w.name", "joins": ["workshop"]},
        },
    },
    "payments": {
        "label": "Pagos",
        "roles": ["admin"],
        "from_clause": "payments p",
        "date_field": "p.created_at",
        "workshop_filter": None,
        "joins_available": {
            "client": "LEFT JOIN users u ON u.id = p.client_id",
            "workshop": "LEFT JOIN workshops w ON w.id = p.workshop_id",
            "incident": "LEFT JOIN incidents i ON i.id = p.incident_id",
        },
        "fields": {
            "id": {"label": "ID Pago", "sql": "CAST(p.id AS TEXT)", "joins": []},
            "gross_amount": {"label": "Monto Bruto", "sql": "p.gross_amount", "joins": []},
            "commission_amount": {"label": "Comisión", "sql": "p.commission_amount", "joins": []},
            "net_amount": {"label": "Monto Neto", "sql": "p.net_amount", "joins": []},
            "payment_method": {"label": "Método de Pago", "sql": "CAST(p.payment_method AS TEXT)", "joins": []},
            "status": {"label": "Estado Pago", "sql": "CAST(p.status AS TEXT)", "joins": []},
            "currency": {"label": "Moneda", "sql": "p.currency", "joins": []},
            "paid_at": {"label": "Fecha de Pago", "sql": "p.paid_at", "joins": []},
            "created_at": {"label": "Fecha Creación", "sql": "p.created_at", "joins": []},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"]},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"]},
            "incident_status": {"label": "Estado Incidente", "sql": "CAST(i.status AS TEXT)", "joins": ["incident"]},
        },
    },
    "ratings": {
        "label": "Calificaciones",
        "roles": ["admin"],
        "from_clause": "ratings r",
        "date_field": "r.created_at",
        "workshop_filter": None,
        "joins_available": {
            "client": "LEFT JOIN users u ON u.id = r.client_id",
            "workshop": "LEFT JOIN workshops w ON w.id = r.workshop_id",
            "incident": "LEFT JOIN incidents i ON i.id = r.incident_id",
        },
        "fields": {
            "id": {"label": "ID Calificación", "sql": "CAST(r.id AS TEXT)", "joins": []},
            "score": {"label": "Puntuación General", "sql": "r.score", "joins": []},
            "response_time_score": {"label": "Tiempo de Respuesta", "sql": "r.response_time_score", "joins": []},
            "quality_score": {"label": "Calidad del Servicio", "sql": "r.quality_score", "joins": []},
            "comment": {"label": "Comentario", "sql": "r.comment", "joins": []},
            "created_at": {"label": "Fecha", "sql": "r.created_at", "joins": []},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"]},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"]},
            "incident_category": {"label": "Categoría Incidente", "sql": "i.ai_category", "joins": ["incident"]},
        },
    },
    "workshops": {
        "label": "Talleres",
        "roles": ["admin"],
        "from_clause": "workshops ws",
        "date_field": "ws.created_at",
        "workshop_filter": None,
        "joins_available": {
            "owner": "LEFT JOIN users ow ON ow.id = ws.owner_user_id",
        },
        "fields": {
            "id": {"label": "ID Taller", "sql": "CAST(ws.id AS TEXT)", "joins": []},
            "name": {"label": "Nombre", "sql": "ws.name", "joins": []},
            "business_name": {"label": "Razón Social", "sql": "ws.business_name", "joins": []},
            "address": {"label": "Dirección", "sql": "ws.address", "joins": []},
            "phone": {"label": "Teléfono", "sql": "ws.phone", "joins": []},
            "commission_rate": {"label": "Tasa Comisión %", "sql": "ws.commission_rate", "joins": []},
            "rating_avg": {"label": "Calificación Promedio", "sql": "ws.rating_avg", "joins": []},
            "total_services": {"label": "Total Servicios", "sql": "ws.total_services", "joins": []},
            "is_active": {"label": "Activo", "sql": "ws.is_active", "joins": []},
            "is_verified": {"label": "Verificado", "sql": "ws.is_verified", "joins": []},
            "created_at": {"label": "Fecha Registro", "sql": "ws.created_at", "joins": []},
            "owner_name": {"label": "Propietario", "sql": "CONCAT(ow.name, ' ', ow.last_name)", "joins": ["owner"]},
            "owner_email": {"label": "Email Propietario", "sql": "ow.email", "joins": ["owner"]},
        },
    },
    "users": {
        "label": "Usuarios",
        "roles": ["admin"],
        "from_clause": "users us",
        "date_field": "us.created_at",
        "workshop_filter": None,
        "joins_available": {},
        "fields": {
            "id": {"label": "ID", "sql": "CAST(us.id AS TEXT)", "joins": []},
            "username": {"label": "Usuario", "sql": "us.username", "joins": []},
            "name": {"label": "Nombre", "sql": "us.name", "joins": []},
            "last_name": {"label": "Apellido", "sql": "us.last_name", "joins": []},
            "email": {"label": "Email", "sql": "us.email", "joins": []},
            "phone": {"label": "Teléfono", "sql": "us.phone", "joins": []},
            "type": {"label": "Tipo", "sql": "us.type", "joins": []},
            "is_active": {"label": "Activo", "sql": "us.is_active", "joins": []},
            "created_at": {"label": "Fecha Registro", "sql": "us.created_at", "joins": []},
        },
    },
    "clients": {
        "label": "Clientes",
        "roles": ["admin"],
        "from_clause": "clients c JOIN users u ON u.id = c.id",
        "date_field": "u.created_at",
        "workshop_filter": None,
        "joins_available": {},
        "fields": {
            "id": {"label": "ID", "sql": "CAST(c.id AS TEXT)", "joins": []},
            "name": {"label": "Nombre", "sql": "u.name", "joins": []},
            "last_name": {"label": "Apellido", "sql": "u.last_name", "joins": []},
            "email": {"label": "Email", "sql": "u.email", "joins": []},
            "phone": {"label": "Teléfono", "sql": "u.phone", "joins": []},
            "username": {"label": "Usuario", "sql": "u.username", "joins": []},
            "address": {"label": "Dirección", "sql": "c.address", "joins": []},
            "insurance_provider": {"label": "Aseguradora", "sql": "c.insurance_provider", "joins": []},
            "insurance_policy": {"label": "N° Póliza", "sql": "c.insurance_policy_number", "joins": []},
            "total_request": {"label": "Total Solicitudes", "sql": "c.total_request", "joins": []},
            "is_active": {"label": "Activo", "sql": "u.is_active", "joins": []},
            "created_at": {"label": "Fecha Registro", "sql": "u.created_at", "joins": []},
        },
    },
    "vehicles": {
        "label": "Vehículos",
        "roles": ["admin"],
        "from_clause": "vehicles v",
        "date_field": "v.created_at",
        "workshop_filter": None,
        "joins_available": {
            "client": "LEFT JOIN clients c ON c.id = v.client_id LEFT JOIN users u ON u.id = c.id",
        },
        "fields": {
            "id": {"label": "ID", "sql": "CAST(v.id AS TEXT)", "joins": []},
            "make": {"label": "Marca", "sql": "v.make", "joins": []},
            "model": {"label": "Modelo", "sql": "v.model", "joins": []},
            "year": {"label": "Año", "sql": "v.year", "joins": []},
            "license_plate": {"label": "Placa", "sql": "v.license_plate", "joins": []},
            "color": {"label": "Color", "sql": "v.color", "joins": []},
            "transmission_type": {"label": "Transmisión", "sql": "CAST(v.transmission_type AS TEXT)", "joins": []},
            "fuel_type": {"label": "Combustible", "sql": "CAST(v.fuel_type AS TEXT)", "joins": []},
            "vin": {"label": "VIN", "sql": "v.vin", "joins": []},
            "is_active": {"label": "Activo", "sql": "v.is_active", "joins": []},
            "created_at": {"label": "Fecha Registro", "sql": "v.created_at", "joins": []},
            "client_name": {"label": "Propietario", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"]},
            "client_email": {"label": "Email Propietario", "sql": "u.email", "joins": ["client"]},
        },
    },
    "technicians": {
        "label": "Técnicos",
        "roles": ["admin"],
        "from_clause": "technicians t JOIN users u ON u.id = t.id",
        "date_field": "u.created_at",
        "workshop_filter": None,
        "joins_available": {
            "workshop": "LEFT JOIN workshops w ON w.id = t.workshop_id",
        },
        "fields": {
            "id": {"label": "ID", "sql": "CAST(t.id AS TEXT)", "joins": []},
            "name": {"label": "Nombre", "sql": "u.name", "joins": []},
            "last_name": {"label": "Apellido", "sql": "u.last_name", "joins": []},
            "email": {"label": "Email", "sql": "u.email", "joins": []},
            "phone": {"label": "Teléfono", "sql": "u.phone", "joins": []},
            "username": {"label": "Usuario", "sql": "u.username", "joins": []},
            "is_available": {"label": "Disponible", "sql": "t.is_available", "joins": []},
            "is_active": {"label": "Activo", "sql": "u.is_active", "joins": []},
            "current_latitude": {"label": "Latitud Actual", "sql": "CAST(t.current_latitude AS TEXT)", "joins": []},
            "current_longitude": {"label": "Longitud Actual", "sql": "CAST(t.current_longitude AS TEXT)", "joins": []},
            "created_at": {"label": "Fecha Registro", "sql": "u.created_at", "joins": []},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"]},
            "workshop_address": {"label": "Dirección Taller", "sql": "w.address", "joins": ["workshop"]},
        },
    },
    "workshop_offers": {
        "label": "Ofertas de Talleres",
        "roles": ["admin"],
        "from_clause": "workshop_offers wo",
        "date_field": "wo.created_at",
        "workshop_filter": None,
        "joins_available": {
            "workshop": "LEFT JOIN workshops w ON w.id = wo.workshop_id",
            "incident": "LEFT JOIN incidents i ON i.id = wo.incident_id",
        },
        "fields": {
            "id": {"label": "ID Oferta", "sql": "CAST(wo.id AS TEXT)", "joins": []},
            "status": {"label": "Estado", "sql": "CAST(wo.status AS TEXT)", "joins": []},
            "distance_km": {"label": "Distancia (km)", "sql": "wo.distance_km", "joins": []},
            "ai_score": {"label": "Puntuación IA", "sql": "wo.ai_score", "joins": []},
            "timeout_minutes": {"label": "Tiempo Límite (min)", "sql": "wo.timeout_minutes", "joins": []},
            "rejection_reason": {"label": "Motivo Rechazo", "sql": "wo.rejection_reason", "joins": []},
            "notified_at": {"label": "Fecha Notificación", "sql": "wo.notified_at", "joins": []},
            "accepted_at": {"label": "Fecha Aceptación", "sql": "wo.accepted_at", "joins": []},
            "rejected_at": {"label": "Fecha Rechazo", "sql": "wo.rejected_at", "joins": []},
            "expires_at": {"label": "Fecha Expiración", "sql": "wo.expires_at", "joins": []},
            "created_at": {"label": "Fecha Creación", "sql": "wo.created_at", "joins": []},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"]},
            "incident_status": {"label": "Estado Incidente", "sql": "CAST(i.status AS TEXT)", "joins": ["incident"]},
            "incident_category": {"label": "Categoría Incidente", "sql": "i.ai_category", "joins": ["incident"]},
        },
    },
    "notifications": {
        "label": "Notificaciones",
        "roles": ["admin"],
        "from_clause": "notifications n",
        "date_field": "n.sent_at",
        "workshop_filter": None,
        "joins_available": {
            "user": "LEFT JOIN users u ON u.id = n.user_id",
        },
        "fields": {
            "id": {"label": "ID", "sql": "CAST(n.id AS TEXT)", "joins": []},
            "type": {"label": "Tipo", "sql": "CAST(n.type AS TEXT)", "joins": []},
            "title": {"label": "Título", "sql": "n.title", "joins": []},
            "body": {"label": "Mensaje", "sql": "n.body", "joins": []},
            "is_read": {"label": "Leída", "sql": "n.is_read", "joins": []},
            "sent_at": {"label": "Fecha Envío", "sql": "n.sent_at", "joins": []},
            "read_at": {"label": "Fecha Lectura", "sql": "n.read_at", "joins": []},
            "user_name": {"label": "Destinatario", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["user"]},
            "user_email": {"label": "Email Destinatario", "sql": "u.email", "joins": ["user"]},
        },
    },
    # Workshop owner reports
    "my_incidents": {
        "label": "Mis Incidentes",
        "roles": ["workshop_owner"],
        "from_clause": "incidents i",
        "date_field": "i.created_at",
        "workshop_filter": "i.assigned_workshop_id = :workshop_id",
        "joins_available": {
            "client": "LEFT JOIN users u ON u.id = i.client_id",
            "vehicle": "LEFT JOIN vehicles v ON v.id = i.vehicle_id",
        },
        "fields": {
            "id": {"label": "ID Incidente", "sql": "CAST(i.id AS TEXT)", "joins": []},
            "description": {"label": "Descripción", "sql": "i.description", "joins": []},
            "status": {"label": "Estado", "sql": "CAST(i.status AS TEXT)", "joins": []},
            "ai_category": {"label": "Categoría", "sql": "i.ai_category", "joins": []},
            "ai_priority": {"label": "Prioridad", "sql": "CAST(i.ai_priority AS TEXT)", "joins": []},
            "created_at": {"label": "Fecha Creación", "sql": "i.created_at", "joins": []},
            "updated_at": {"label": "Última Actualización", "sql": "i.updated_at", "joins": []},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"]},
            "client_email": {"label": "Email Cliente", "sql": "u.email", "joins": ["client"]},
            "vehicle_info": {
                "label": "Vehículo",
                "sql": "CONCAT(COALESCE(v.make,''), ' ', COALESCE(v.model,''))",
                "joins": ["vehicle"],
            },
        },
    },
    "my_payments": {
        "label": "Mis Pagos",
        "roles": ["workshop_owner"],
        "from_clause": "payments p",
        "date_field": "p.created_at",
        "workshop_filter": "p.workshop_id = :workshop_id",
        "joins_available": {
            "client": "LEFT JOIN users u ON u.id = p.client_id",
            "incident": "LEFT JOIN incidents i ON i.id = p.incident_id",
        },
        "fields": {
            "id": {"label": "ID Pago", "sql": "CAST(p.id AS TEXT)", "joins": []},
            "gross_amount": {"label": "Monto Bruto", "sql": "p.gross_amount", "joins": []},
            "commission_amount": {"label": "Comisión", "sql": "p.commission_amount", "joins": []},
            "net_amount": {"label": "Monto Neto", "sql": "p.net_amount", "joins": []},
            "payment_method": {"label": "Método de Pago", "sql": "CAST(p.payment_method AS TEXT)", "joins": []},
            "status": {"label": "Estado", "sql": "CAST(p.status AS TEXT)", "joins": []},
            "paid_at": {"label": "Fecha de Pago", "sql": "p.paid_at", "joins": []},
            "created_at": {"label": "Fecha Creación", "sql": "p.created_at", "joins": []},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"]},
        },
    },
    "my_ratings": {
        "label": "Mis Calificaciones",
        "roles": ["workshop_owner"],
        "from_clause": "ratings r",
        "date_field": "r.created_at",
        "workshop_filter": "r.workshop_id = :workshop_id",
        "joins_available": {
            "client": "LEFT JOIN users u ON u.id = r.client_id",
            "incident": "LEFT JOIN incidents i ON i.id = r.incident_id",
        },
        "fields": {
            "id": {"label": "ID", "sql": "CAST(r.id AS TEXT)", "joins": []},
            "score": {"label": "Puntuación", "sql": "r.score", "joins": []},
            "response_time_score": {"label": "Tiempo de Respuesta", "sql": "r.response_time_score", "joins": []},
            "quality_score": {"label": "Calidad", "sql": "r.quality_score", "joins": []},
            "comment": {"label": "Comentario", "sql": "r.comment", "joins": []},
            "created_at": {"label": "Fecha", "sql": "r.created_at", "joins": []},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"]},
        },
    },
    "my_technicians": {
        "label": "Mis Técnicos",
        "roles": ["workshop_owner"],
        "from_clause": "technicians t JOIN users tu ON tu.id = t.id",
        "date_field": "tu.created_at",
        "workshop_filter": "t.workshop_id = :workshop_id",
        "joins_available": {},
        "fields": {
            "id": {"label": "ID", "sql": "CAST(t.id AS TEXT)", "joins": []},
            "name": {"label": "Nombre", "sql": "tu.name", "joins": []},
            "last_name": {"label": "Apellido", "sql": "tu.last_name", "joins": []},
            "email": {"label": "Email", "sql": "tu.email", "joins": []},
            "phone": {"label": "Teléfono", "sql": "tu.phone", "joins": []},
            "is_available": {"label": "Disponible", "sql": "t.is_available", "joins": []},
            "is_active": {"label": "Activo", "sql": "tu.is_active", "joins": []},
            "created_at": {"label": "Fecha Registro", "sql": "tu.created_at", "joins": []},
        },
    },
}

ALLOWED_OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "like", "is_null", "is_not_null"}
OPERATOR_SQL = {
    "eq": "= :fv_{i}",
    "ne": "!= :fv_{i}",
    "gt": "> :fv_{i}",
    "lt": "< :fv_{i}",
    "gte": ">= :fv_{i}",
    "lte": "<= :fv_{i}",
    "like": "ILIKE :fv_{i}",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
}


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def get_catalog_for_roles(roles: list[str]) -> dict:
        """Return catalog entries accessible for the given roles."""
        return {k: v for k, v in CATALOG.items() if any(r in v["roles"] for r in roles)}

    def build_and_run_query(
        self,
        req: ReportRunRequest,
        user_roles: list[str],
        workshop_id: Optional[str] = None,
    ) -> tuple[list[str], dict[str, str], list[dict]]:
        """Build SQL from the request config and return (columns, labels, rows)."""
        from fastapi import HTTPException

        if req.report_type not in CATALOG:
            raise HTTPException(404, f"Tipo de reporte '{req.report_type}' no encontrado")

        entry = CATALOG[req.report_type]
        if not any(r in entry["roles"] for r in user_roles):
            raise HTTPException(403, "No tienes acceso a este tipo de reporte")

        # Validate and collect selected fields
        valid_fields = entry["fields"]
        selected = [f for f in req.selected_fields if f in valid_fields]
        if not selected:
            raise HTTPException(400, "Debes seleccionar al menos un campo válido")

        # Build SELECT
        select_parts = [f"{valid_fields[f]['sql']} AS \"{f}\"" for f in selected]
        column_labels = {f: valid_fields[f]["label"] for f in selected}

        # Determine joins needed
        needed_joins: set[str] = set()
        for f in selected:
            needed_joins.update(valid_fields[f]["joins"])

        # Also check filter fields for needed joins
        for flt in req.filters:
            if flt.field in valid_fields:
                needed_joins.update(valid_fields[flt.field]["joins"])

        join_sql = " ".join(
            entry["joins_available"][j]
            for j in needed_joins
            if j in entry["joins_available"]
        )

        # WHERE clauses
        where_parts: list[str] = []
        params: dict[str, Any] = {}

        if entry["workshop_filter"] and workshop_id:
            where_parts.append(entry["workshop_filter"])
            params["workshop_id"] = workshop_id

        if req.date_from:
            where_parts.append(f"{entry['date_field']} >= :date_from")
            params["date_from"] = req.date_from

        if req.date_to:
            where_parts.append(f"{entry['date_field']} <= :date_to")
            params["date_to"] = req.date_to

        # User-defined filters (only validated fields and whitelisted operators)
        for i, flt in enumerate(req.filters):
            if flt.field not in valid_fields or flt.operator not in ALLOWED_OPERATORS:
                continue
            field_sql = valid_fields[flt.field]["sql"]
            if flt.operator in ("is_null", "is_not_null"):
                where_parts.append(f"{field_sql} {OPERATOR_SQL[flt.operator]}")
            else:
                param_name = f"fv_{i}"
                op_sql = OPERATOR_SQL[flt.operator].replace(":fv_{i}", f":{param_name}")
                where_parts.append(f"{field_sql} {op_sql}")
                val = flt.value
                if flt.operator == "like":
                    val = f"%{val}%"
                params[param_name] = val

        # Build full SQL
        sql = f"SELECT {', '.join(select_parts)} FROM {entry['from_clause']}"
        if join_sql:
            sql += f" {join_sql}"
        if where_parts:
            sql += f" WHERE {' AND '.join(where_parts)}"

        # ORDER BY
        if req.sort_field and req.sort_field in valid_fields:
            order = "DESC" if req.sort_order.lower() == "desc" else "ASC"
            sql += f" ORDER BY {valid_fields[req.sort_field]['sql']} {order}"

        # Pagination
        limit = min(req.limit, 5000)
        sql += f" LIMIT {limit} OFFSET {req.offset}"

        result = self.db.execute(text(sql), params)
        keys = list(result.keys())
        rows = [dict(zip(keys, row)) for row in result.fetchall()]

        # Convert non-serializable types
        for row in rows:
            for k, v in row.items():
                if isinstance(v, (dt.datetime, dt.date)):
                    row[k] = v.isoformat()

        return selected, column_labels, rows

    def count_query(
        self,
        req: ReportRunRequest,
        user_roles: list[str],
        workshop_id: Optional[str] = None,
    ) -> int:
        """Return total row count for pagination."""
        if req.report_type not in CATALOG:
            return 0
        entry = CATALOG[req.report_type]
        if not any(r in entry["roles"] for r in user_roles):
            return 0

        valid_fields = entry["fields"]
        needed_joins: set[str] = set()
        for flt in req.filters:
            if flt.field in valid_fields:
                needed_joins.update(valid_fields[flt.field]["joins"])

        join_sql = " ".join(
            entry["joins_available"][j]
            for j in needed_joins
            if j in entry["joins_available"]
        )

        where_parts: list[str] = []
        params: dict[str, Any] = {}

        if entry["workshop_filter"] and workshop_id:
            where_parts.append(entry["workshop_filter"])
            params["workshop_id"] = workshop_id

        if req.date_from:
            where_parts.append(f"{entry['date_field']} >= :date_from")
            params["date_from"] = req.date_from

        if req.date_to:
            where_parts.append(f"{entry['date_field']} <= :date_to")
            params["date_to"] = req.date_to

        for i, flt in enumerate(req.filters):
            if flt.field not in valid_fields or flt.operator not in ALLOWED_OPERATORS:
                continue
            field_sql = valid_fields[flt.field]["sql"]
            if flt.operator in ("is_null", "is_not_null"):
                where_parts.append(f"{field_sql} {OPERATOR_SQL[flt.operator]}")
            else:
                param_name = f"fv_{i}"
                op_sql = OPERATOR_SQL[flt.operator].replace(":fv_{i}", f":{param_name}")
                where_parts.append(f"{field_sql} {op_sql}")
                val = flt.value
                if flt.operator == "like":
                    val = f"%{val}%"
                params[param_name] = val

        sql = f"SELECT COUNT(*) FROM {entry['from_clause']}"
        if join_sql:
            sql += f" {join_sql}"
        if where_parts:
            sql += f" WHERE {' AND '.join(where_parts)}"

        result = self.db.execute(text(sql), params)
        return result.scalar() or 0

    # ── Template CRUD ─────────────────────────────────────────────────────────────

    def get_templates(self, owner_id: uuid.UUID) -> list[ReportTemplate]:
        return (
            self.db.query(ReportTemplate)
            .filter(
                (ReportTemplate.owner_id == owner_id) | (ReportTemplate.is_shared == True)  # noqa: E712
            )
            .order_by(ReportTemplate.created_at.desc())
            .all()
        )

    def get_template(
        self, template_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Optional[ReportTemplate]:
        return (
            self.db.query(ReportTemplate)
            .filter(
                ReportTemplate.id == template_id,
                (ReportTemplate.owner_id == owner_id) | (ReportTemplate.is_shared == True),  # noqa: E712
            )
            .first()
        )

    def create_template(
        self, data: ReportTemplateCreate, owner_id: uuid.UUID
    ) -> ReportTemplate:
        tpl = ReportTemplate(
            owner_id=owner_id,
            **data.model_dump(),
        )
        self.db.add(tpl)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def update_template(
        self, tpl: ReportTemplate, data: ReportTemplateUpdate
    ) -> ReportTemplate:
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(tpl, k, v)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def delete_template(self, tpl: ReportTemplate) -> None:
        self.db.delete(tpl)
        self.db.commit()
