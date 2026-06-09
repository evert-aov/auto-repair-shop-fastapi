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
            "id": {"label": "ID Incidente", "sql": "CAST(i.id AS TEXT)", "joins": [], "type": "STRING"},
            "description": {"label": "Descripción", "sql": "i.description", "joins": [], "type": "STRING"},
            "status": {
                "label": "Estado",
                "sql": "CAST(i.status AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "pending", "label": "Pendiente"},
                    {"value": "analyzing", "label": "Analizando"},
                    {"value": "pending_info", "label": "Pendiente de Información"},
                    {"value": "matched", "label": "Emparejado"},
                    {"value": "assigned", "label": "Asignado"},
                    {"value": "in_progress", "label": "En Progreso"},
                    {"value": "completed", "label": "Completado"},
                    {"value": "cancelled", "label": "Cancelado"},
                    {"value": "no_offers", "label": "Sin Ofertas"},
                    {"value": "error", "label": "Error"}
                ]
            },
            "ai_category": {"label": "Categoría IA", "sql": "i.ai_category", "joins": [], "type": "STRING"},
            "ai_priority": {
                "label": "Prioridad IA",
                "sql": "CAST(i.ai_priority AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "LOW", "label": "Baja"},
                    {"value": "MEDIUM", "label": "Media"},
                    {"value": "HIGH", "label": "Alta"},
                    {"value": "CRITICAL", "label": "Crítica"}
                ]
            },
            "created_at": {"label": "Fecha Creación", "sql": "i.created_at", "joins": [], "type": "DATE"},
            "updated_at": {"label": "Última Actualización", "sql": "i.updated_at", "joins": [], "type": "DATE"},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"], "type": "STRING"},
            "client_email": {"label": "Email Cliente", "sql": "u.email", "joins": ["client"], "type": "STRING"},
            "vehicle_info": {
                "label": "Vehículo",
                "sql": "CONCAT(COALESCE(v.make,''), ' ', COALESCE(v.model,''), ' - ', COALESCE(v.license_plate,''))",
                "joins": ["vehicle"],
                "type": "STRING"
            },
            "workshop_name": {"label": "Taller Asignado", "sql": "w.name", "joins": ["workshop"], "type": "STRING"},
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
            "id": {"label": "ID Pago", "sql": "CAST(p.id AS TEXT)", "joins": [], "type": "STRING"},
            "gross_amount": {"label": "Monto Bruto", "sql": "p.gross_amount", "joins": [], "type": "NUMBER"},
            "commission_amount": {"label": "Comisión", "sql": "p.commission_amount", "joins": [], "type": "NUMBER"},
            "net_amount": {"label": "Monto Neto", "sql": "p.net_amount", "joins": [], "type": "NUMBER"},
            "payment_method": {
                "label": "Método de Pago",
                "sql": "CAST(p.payment_method AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "qr", "label": "QR"},
                    {"value": "card", "label": "Tarjeta"},
                    {"value": "cash", "label": "Efectivo"},
                    {"value": "transfer", "label": "Transferencia"},
                    {"value": "paypal", "label": "PayPal"}
                ]
            },
            "status": {
                "label": "Estado Pago",
                "sql": "CAST(p.status AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "pending", "label": "Pendiente"},
                    {"value": "processing", "label": "Procesando"},
                    {"value": "completed", "label": "Completado"},
                    {"value": "failed", "label": "Fallido"},
                    {"value": "refunded", "label": "Reembolsado"}
                ]
            },
            "currency": {"label": "Moneda", "sql": "p.currency", "joins": [], "type": "STRING"},
            "paid_at": {"label": "Fecha de Pago", "sql": "p.paid_at", "joins": [], "type": "DATE"},
            "created_at": {"label": "Fecha Creación", "sql": "p.created_at", "joins": [], "type": "DATE"},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"], "type": "STRING"},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"], "type": "STRING"},
            "incident_status": {
                "label": "Estado Incidente",
                "sql": "CAST(i.status AS TEXT)",
                "joins": ["incident"],
                "type": "ENUM",
                "options": [
                    {"value": "pending", "label": "Pendiente"},
                    {"value": "analyzing", "label": "Analizando"},
                    {"value": "pending_info", "label": "Pendiente de Información"},
                    {"value": "matched", "label": "Emparejado"},
                    {"value": "assigned", "label": "Asignado"},
                    {"value": "in_progress", "label": "En Progreso"},
                    {"value": "completed", "label": "Completado"},
                    {"value": "cancelled", "label": "Cancelado"},
                    {"value": "no_offers", "label": "Sin Ofertas"},
                    {"value": "error", "label": "Error"}
                ]
            },
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
            "id": {"label": "ID Calificación", "sql": "CAST(r.id AS TEXT)", "joins": [], "type": "STRING"},
            "score": {"label": "Puntuación General", "sql": "r.score", "joins": [], "type": "NUMBER"},
            "response_time_score": {"label": "Tiempo de Respuesta", "sql": "r.response_time_score", "joins": [], "type": "NUMBER"},
            "quality_score": {"label": "Calidad del Servicio", "sql": "r.quality_score", "joins": [], "type": "NUMBER"},
            "comment": {"label": "Comentario", "sql": "r.comment", "joins": [], "type": "STRING"},
            "created_at": {"label": "Fecha", "sql": "r.created_at", "joins": [], "type": "DATE"},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"], "type": "STRING"},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"], "type": "STRING"},
            "incident_category": {"label": "Categoría Incidente", "sql": "i.ai_category", "joins": ["incident"], "type": "STRING"},
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
            "id": {"label": "ID Taller", "sql": "CAST(ws.id AS TEXT)", "joins": [], "type": "STRING"},
            "name": {"label": "Nombre", "sql": "ws.name", "joins": [], "type": "STRING"},
            "business_name": {"label": "Razón Social", "sql": "ws.business_name", "joins": [], "type": "STRING"},
            "address": {"label": "Dirección", "sql": "ws.address", "joins": [], "type": "STRING"},
            "phone": {"label": "Teléfono", "sql": "ws.phone", "joins": [], "type": "STRING"},
            "commission_rate": {"label": "Tasa Comisión %", "sql": "ws.commission_rate", "joins": [], "type": "NUMBER"},
            "rating_avg": {"label": "Calificación Promedio", "sql": "ws.rating_avg", "joins": [], "type": "NUMBER"},
            "total_services": {"label": "Total Servicios", "sql": "ws.total_services", "joins": [], "type": "NUMBER"},
            "is_active": {"label": "Activo", "sql": "ws.is_active", "joins": [], "type": "BOOLEAN"},
            "is_verified": {"label": "Verificado", "sql": "ws.is_verified", "joins": [], "type": "BOOLEAN"},
            "created_at": {"label": "Fecha Registro", "sql": "ws.created_at", "joins": [], "type": "DATE"},
            "owner_name": {"label": "Propietario", "sql": "CONCAT(ow.name, ' ', ow.last_name)", "joins": ["owner"], "type": "STRING"},
            "owner_email": {"label": "Email Propietario", "sql": "ow.email", "joins": ["owner"], "type": "STRING"},
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
            "id": {"label": "ID", "sql": "CAST(us.id AS TEXT)", "joins": [], "type": "STRING"},
            "username": {"label": "Usuario", "sql": "us.username", "joins": [], "type": "STRING"},
            "name": {"label": "Nombre", "sql": "us.name", "joins": [], "type": "STRING"},
            "last_name": {"label": "Apellido", "sql": "us.last_name", "joins": [], "type": "STRING"},
            "email": {"label": "Email", "sql": "us.email", "joins": [], "type": "STRING"},
            "phone": {"label": "Teléfono", "sql": "us.phone", "joins": [], "type": "STRING"},
            "type": {
                "label": "Tipo",
                "sql": "us.type",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "admin", "label": "Administrador"},
                    {"value": "client", "label": "Cliente"},
                    {"value": "workshop_owner", "label": "Dueño de Taller"},
                    {"value": "technician", "label": "Técnico"}
                ]
            },
            "is_active": {"label": "Activo", "sql": "us.is_active", "joins": [], "type": "BOOLEAN"},
            "created_at": {"label": "Fecha Registro", "sql": "us.created_at", "joins": [], "type": "DATE"},
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
            "id": {"label": "ID", "sql": "CAST(c.id AS TEXT)", "joins": [], "type": "STRING"},
            "name": {"label": "Nombre", "sql": "u.name", "joins": [], "type": "STRING"},
            "last_name": {"label": "Apellido", "sql": "u.last_name", "joins": [], "type": "STRING"},
            "email": {"label": "Email", "sql": "u.email", "joins": [], "type": "STRING"},
            "phone": {"label": "Teléfono", "sql": "u.phone", "joins": [], "type": "STRING"},
            "username": {"label": "Usuario", "sql": "u.username", "joins": [], "type": "STRING"},
            "address": {"label": "Dirección", "sql": "c.address", "joins": [], "type": "STRING"},
            "insurance_provider": {"label": "Aseguradora", "sql": "c.insurance_provider", "joins": [], "type": "STRING"},
            "insurance_policy": {"label": "N° Póliza", "sql": "c.insurance_policy_number", "joins": [], "type": "STRING"},
            "total_request": {"label": "Total Solicitudes", "sql": "c.total_request", "joins": [], "type": "NUMBER"},
            "is_active": {"label": "Activo", "sql": "u.is_active", "joins": [], "type": "BOOLEAN"},
            "created_at": {"label": "Fecha Registro", "sql": "u.created_at", "joins": [], "type": "DATE"},
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
            "id": {"label": "ID", "sql": "CAST(v.id AS TEXT)", "joins": [], "type": "STRING"},
            "make": {"label": "Marca", "sql": "v.make", "joins": [], "type": "STRING"},
            "model": {"label": "Modelo", "sql": "v.model", "joins": [], "type": "STRING"},
            "year": {"label": "Año", "sql": "v.year", "joins": [], "type": "NUMBER"},
            "license_plate": {"label": "Placa", "sql": "v.license_plate", "joins": [], "type": "STRING"},
            "color": {"label": "Color", "sql": "v.color", "joins": [], "type": "STRING"},
            "transmission_type": {
                "label": "Transmisión",
                "sql": "CAST(v.transmission_type AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "manual", "label": "Manual"},
                    {"value": "automatic", "label": "Automático"}
                ]
            },
            "fuel_type": {
                "label": "Combustible",
                "sql": "CAST(v.fuel_type AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "gasoline", "label": "Gasolina"},
                    {"value": "diesel", "label": "Diésel"},
                    {"value": "electric", "label": "Eléctrico"},
                    {"value": "hybrid", "label": "Híbrido"}
                ]
            },
            "vin": {"label": "VIN", "sql": "v.vin", "joins": [], "type": "STRING"},
            "is_active": {"label": "Activo", "sql": "v.is_active", "joins": [], "type": "BOOLEAN"},
            "created_at": {"label": "Fecha Registro", "sql": "v.created_at", "joins": [], "type": "DATE"},
            "client_name": {"label": "Propietario", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"], "type": "STRING"},
            "client_email": {"label": "Email Propietario", "sql": "u.email", "joins": ["client"], "type": "STRING"},
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
            "id": {"label": "ID", "sql": "CAST(t.id AS TEXT)", "joins": [], "type": "STRING"},
            "name": {"label": "Nombre", "sql": "u.name", "joins": [], "type": "STRING"},
            "last_name": {"label": "Apellido", "sql": "u.last_name", "joins": [], "type": "STRING"},
            "email": {"label": "Email", "sql": "u.email", "joins": [], "type": "STRING"},
            "phone": {"label": "Teléfono", "sql": "u.phone", "joins": [], "type": "STRING"},
            "username": {"label": "Usuario", "sql": "u.username", "joins": [], "type": "STRING"},
            "is_available": {"label": "Disponible", "sql": "t.is_available", "joins": [], "type": "BOOLEAN"},
            "is_active": {"label": "Activo", "sql": "u.is_active", "joins": [], "type": "BOOLEAN"},
            "current_latitude": {"label": "Latitud Actual", "sql": "CAST(t.current_latitude AS TEXT)", "joins": [], "type": "STRING"},
            "current_longitude": {"label": "Longitud Actual", "sql": "CAST(t.current_longitude AS TEXT)", "joins": [], "type": "STRING"},
            "created_at": {"label": "Fecha Registro", "sql": "u.created_at", "joins": [], "type": "DATE"},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"], "type": "STRING"},
            "workshop_address": {"label": "Dirección Taller", "sql": "w.address", "joins": ["workshop"], "type": "STRING"},
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
            "id": {"label": "ID Oferta", "sql": "CAST(wo.id AS TEXT)", "joins": [], "type": "STRING"},
            "status": {
                "label": "Estado",
                "sql": "CAST(wo.status AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "notified", "label": "Notificado"},
                    {"value": "accepted", "label": "Aceptado"},
                    {"value": "rejected", "label": "Rechazado"},
                    {"value": "timeout", "label": "Tiempo Agotado"},
                    {"value": "expired", "label": "Expirado"}
                ]
            },
            "distance_km": {"label": "Distancia (km)", "sql": "wo.distance_km", "joins": [], "type": "NUMBER"},
            "ai_score": {"label": "Puntuación IA", "sql": "wo.ai_score", "joins": [], "type": "NUMBER"},
            "timeout_minutes": {"label": "Tiempo Límite (min)", "sql": "wo.timeout_minutes", "joins": [], "type": "NUMBER"},
            "rejection_reason": {
                "label": "Motivo Rechazo",
                "sql": "wo.rejection_reason",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "no_reason", "label": "Sin Motivo"},
                    {"value": "busy", "label": "Ocupado"},
                    {"value": "far_from_zone", "label": "Lejos de la Zona"},
                    {"value": "no_parts", "label": "Sin Repuestos"},
                    {"value": "no_technician", "label": "Sin Técnicos"},
                    {"value": "timeout_no_response", "label": "Sin Respuesta"}
                ]
            },
            "notified_at": {"label": "Fecha Notificación", "sql": "wo.notified_at", "joins": [], "type": "DATE"},
            "accepted_at": {"label": "Fecha Aceptación", "sql": "wo.accepted_at", "joins": [], "type": "DATE"},
            "rejected_at": {"label": "Fecha Rechazo", "sql": "wo.rejected_at", "joins": [], "type": "DATE"},
            "expires_at": {"label": "Fecha Expiración", "sql": "wo.expires_at", "joins": [], "type": "DATE"},
            "created_at": {"label": "Fecha Creación", "sql": "wo.created_at", "joins": [], "type": "DATE"},
            "workshop_name": {"label": "Taller", "sql": "w.name", "joins": ["workshop"], "type": "STRING"},
            "incident_status": {
                "label": "Estado Incidente",
                "sql": "CAST(i.status AS TEXT)",
                "joins": ["incident"],
                "type": "ENUM",
                "options": [
                    {"value": "pending", "label": "Pendiente"},
                    {"value": "analyzing", "label": "Analizando"},
                    {"value": "pending_info", "label": "Pendiente de Información"},
                    {"value": "matched", "label": "Emparejado"},
                    {"value": "assigned", "label": "Asignado"},
                    {"value": "in_progress", "label": "En Progreso"},
                    {"value": "completed", "label": "Completado"},
                    {"value": "cancelled", "label": "Cancelado"},
                    {"value": "no_offers", "label": "Sin Ofertas"},
                    {"value": "error", "label": "Error"}
                ]
            },
            "incident_category": {"label": "Categoría Incidente", "sql": "i.ai_category", "joins": ["incident"], "type": "STRING"},
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
            "id": {"label": "ID", "sql": "CAST(n.id AS TEXT)", "joins": [], "type": "STRING"},
            "type": {
                "label": "Tipo",
                "sql": "CAST(n.type AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "new_request", "label": "Nueva Solicitud"},
                    {"value": "accepted", "label": "Aceptada"},
                    {"value": "rejected", "label": "Rechazada"},
                    {"value": "status_update", "label": "Actualización de Estado"},
                    {"value": "payment", "label": "Pago"},
                    {"value": "system", "label": "Sistema"},
                    {"value": "service_completed", "label": "Servicio Completado"}
                ]
            },
            "title": {"label": "Título", "sql": "n.title", "joins": [], "type": "STRING"},
            "body": {"label": "Mensaje", "sql": "n.body", "joins": [], "type": "STRING"},
            "is_read": {"label": "Leída", "sql": "n.is_read", "joins": [], "type": "BOOLEAN"},
            "sent_at": {"label": "Fecha Envío", "sql": "n.sent_at", "joins": [], "type": "DATE"},
            "read_at": {"label": "Fecha Lectura", "sql": "n.read_at", "joins": [], "type": "DATE"},
            "user_name": {"label": "Destinatario", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["user"], "type": "STRING"},
            "user_email": {"label": "Email Destinatario", "sql": "u.email", "joins": ["user"], "type": "STRING"},
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
            "id": {"label": "ID Incidente", "sql": "CAST(i.id AS TEXT)", "joins": [], "type": "STRING"},
            "description": {"label": "Descripción", "sql": "i.description", "joins": [], "type": "STRING"},
            "status": {
                "label": "Estado",
                "sql": "CAST(i.status AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "pending", "label": "Pendiente"},
                    {"value": "analyzing", "label": "Analizando"},
                    {"value": "pending_info", "label": "Pendiente de Información"},
                    {"value": "matched", "label": "Emparejado"},
                    {"value": "assigned", "label": "Asignado"},
                    {"value": "in_progress", "label": "En Progreso"},
                    {"value": "completed", "label": "Completado"},
                    {"value": "cancelled", "label": "Cancelado"},
                    {"value": "no_offers", "label": "Sin Ofertas"},
                    {"value": "error", "label": "Error"}
                ]
            },
            "ai_category": {"label": "Categoría", "sql": "i.ai_category", "joins": [], "type": "STRING"},
            "ai_priority": {
                "label": "Prioridad",
                "sql": "CAST(i.ai_priority AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "LOW", "label": "Baja"},
                    {"value": "MEDIUM", "label": "Media"},
                    {"value": "HIGH", "label": "Alta"},
                    {"value": "CRITICAL", "label": "Crítica"}
                ]
            },
            "created_at": {"label": "Fecha Creación", "sql": "i.created_at", "joins": [], "type": "DATE"},
            "updated_at": {"label": "Última Actualización", "sql": "i.updated_at", "joins": [], "type": "DATE"},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"], "type": "STRING"},
            "client_email": {"label": "Email Cliente", "sql": "u.email", "joins": ["client"], "type": "STRING"},
            "vehicle_info": {
                "label": "Vehículo",
                "sql": "CONCAT(COALESCE(v.make,''), ' ', COALESCE(v.model,''))",
                "joins": ["vehicle"],
                "type": "STRING"
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
            "id": {"label": "ID Pago", "sql": "CAST(p.id AS TEXT)", "joins": [], "type": "STRING"},
            "gross_amount": {"label": "Monto Bruto", "sql": "p.gross_amount", "joins": [], "type": "NUMBER"},
            "commission_amount": {"label": "Comisión", "sql": "p.commission_amount", "joins": [], "type": "NUMBER"},
            "net_amount": {"label": "Monto Neto", "sql": "p.net_amount", "joins": [], "type": "NUMBER"},
            "payment_method": {
                "label": "Método de Pago",
                "sql": "CAST(p.payment_method AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "qr", "label": "QR"},
                    {"value": "card", "label": "Tarjeta"},
                    {"value": "cash", "label": "Efectivo"},
                    {"value": "transfer", "label": "Transferencia"},
                    {"value": "paypal", "label": "PayPal"}
                ]
            },
            "status": {
                "label": "Estado",
                "sql": "CAST(p.status AS TEXT)",
                "joins": [],
                "type": "ENUM",
                "options": [
                    {"value": "pending", "label": "Pendiente"},
                    {"value": "processing", "label": "Procesando"},
                    {"value": "completed", "label": "Completado"},
                    {"value": "failed", "label": "Fallido"},
                    {"value": "refunded", "label": "Reembolsado"}
                ]
            },
            "paid_at": {"label": "Fecha de Pago", "sql": "p.paid_at", "joins": [], "type": "DATE"},
            "created_at": {"label": "Fecha Creación", "sql": "p.created_at", "joins": [], "type": "DATE"},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"], "type": "STRING"},
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
            "id": {"label": "ID", "sql": "CAST(r.id AS TEXT)", "joins": [], "type": "STRING"},
            "score": {"label": "Puntuación", "sql": "r.score", "joins": [], "type": "NUMBER"},
            "response_time_score": {"label": "Tiempo de Respuesta", "sql": "r.response_time_score", "joins": [], "type": "NUMBER"},
            "quality_score": {"label": "Calidad", "sql": "r.quality_score", "joins": [], "type": "NUMBER"},
            "comment": {"label": "Comentario", "sql": "r.comment", "joins": [], "type": "STRING"},
            "created_at": {"label": "Fecha", "sql": "r.created_at", "joins": [], "type": "DATE"},
            "client_name": {"label": "Cliente", "sql": "CONCAT(u.name, ' ', u.last_name)", "joins": ["client"], "type": "STRING"},
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
            "id": {"label": "ID", "sql": "CAST(t.id AS TEXT)", "joins": [], "type": "STRING"},
            "name": {"label": "Nombre", "sql": "tu.name", "joins": [], "type": "STRING"},
            "last_name": {"label": "Apellido", "sql": "tu.last_name", "joins": [], "type": "STRING"},
            "email": {"label": "Email", "sql": "tu.email", "joins": [], "type": "STRING"},
            "phone": {"label": "Teléfono", "sql": "tu.phone", "joins": [], "type": "STRING"},
            "is_available": {"label": "Disponible", "sql": "t.is_available", "joins": [], "type": "BOOLEAN"},
            "is_active": {"label": "Activo", "sql": "tu.is_active", "joins": [], "type": "BOOLEAN"},
            "created_at": {"label": "Fecha Registro", "sql": "tu.created_at", "joins": [], "type": "DATE"},
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
                
                f_type = valid_fields[flt.field].get("type", "STRING")
                if f_type == "NUMBER":
                    op_sql = op_sql.replace(f":{param_name}", f"CAST(:{param_name} AS numeric)")
                elif f_type == "DATE":
                    if flt.operator == "like":
                        continue
                    op_sql = op_sql.replace(f":{param_name}", f"CAST(:{param_name} AS timestamptz)")
                elif f_type == "BOOLEAN":
                    if flt.operator in ("eq", "ne"):
                        op_sql = op_sql.replace(f":{param_name}", f"CAST(:{param_name} AS boolean)")
                    else:
                        continue

                where_parts.append(f"{field_sql} {op_sql}")
                val = flt.value
                if flt.operator == "like":
                    val = f"%{val}%"
                
                if f_type == "NUMBER" and val is not None:
                    try:
                        from decimal import Decimal
                        val = Decimal(str(val))
                    except Exception:
                        pass
                elif f_type == "BOOLEAN" and val is not None:
                    val = str(val).lower() in ("true", "1", "yes", "sí", "si")

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
                
                f_type = valid_fields[flt.field].get("type", "STRING")
                if f_type == "NUMBER":
                    op_sql = op_sql.replace(f":{param_name}", f"CAST(:{param_name} AS numeric)")
                elif f_type == "DATE":
                    if flt.operator == "like":
                        continue
                    op_sql = op_sql.replace(f":{param_name}", f"CAST(:{param_name} AS timestamptz)")
                elif f_type == "BOOLEAN":
                    if flt.operator in ("eq", "ne"):
                        op_sql = op_sql.replace(f":{param_name}", f"CAST(:{param_name} AS boolean)")
                    else:
                        continue

                where_parts.append(f"{field_sql} {op_sql}")
                val = flt.value
                if flt.operator == "like":
                    val = f"%{val}%"
                
                if f_type == "NUMBER" and val is not None:
                    try:
                        from decimal import Decimal
                        val = Decimal(str(val))
                    except Exception:
                        pass
                elif f_type == "BOOLEAN" and val is not None:
                    val = str(val).lower() in ("true", "1", "yes", "sí", "si")

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
