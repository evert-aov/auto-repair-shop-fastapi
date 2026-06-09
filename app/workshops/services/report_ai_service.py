import json
import logging
import os
import vertexai
from typing import Optional
from google.oauth2 import service_account
from vertexai.generative_models import GenerationConfig, GenerativeModel
from pydantic import BaseModel, Field

from app.workshops.repositories.report_repository import CATALOG
from app.workshops.dtos.report_dtos import ReportRunRequest, ReportFilter

logger = logging.getLogger(__name__)

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_NAME = os.getenv("VERTEX_MODEL_NAME", "gemini-2.5-flash")

class AIReportFilter(BaseModel):
    field: str = Field(description="El campo/columna por el que filtrar, ej: status, gross_amount, rating")
    operator: str = Field(description="Operador de comparación. Valores válidos: eq, ne, gt, lt, gte, lte, like, is_null, is_not_null")
    value: Optional[str] = Field(None, description="El valor del filtro en formato string, ej: 'completed', '100', etc.")

class AIReportRunRequest(BaseModel):
    report_type: str = Field(description="El tipo de reporte de la base de datos. Valores válidos: 'incidents', 'payments', 'ratings', 'users', 'workshops', 'clients', 'vehicles', 'technicians'")
    selected_fields: list[str] = Field(description="Lista de campos/columnas seleccionadas. Deben pertenecer a los campos permitidos del reporte.")
    filters: list[AIReportFilter] = Field(default=[], description="Filtros aplicados al reporte.")
    sort_field: Optional[str] = Field(None, description="Campo por el cual ordenar.")
    sort_order: str = Field(default="asc", description="Ordenamiento: 'asc' o 'desc'")
    limit: Optional[int] = Field(50, description="Límite máximo de registros a retornar, ej: 'últimos 10' -> limit=10. Si el usuario no pide cantidad o límite, usar 50 por defecto.")
    offset: Optional[int] = Field(0, description="Desplazamiento para paginación. Por defecto es 0.")


class ReportAIService:
    @staticmethod
    def get_catalog_description() -> str:
        lines = []
        for report_type, info in CATALOG.items():
            lines.append(f"Tipo de Reporte (report_type): '{report_type}' (Etiqueta: {info['label']})")
            lines.append("Campos/Columnas permitidas:")
            for field_name, f_info in info["fields"].items():
                options_str = ""
                if "options" in f_info:
                    opts = [o["value"] for o in f_info["options"]]
                    options_str = f" (Valores posibles/opciones: {opts})"
                lines.append(f"  - '{field_name}' ({f_info['label']}) [Tipo: {f_info.get('type', 'STRING')}]{options_str}")
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def parse_prompt(cls, prompt: str) -> Optional[ReportRunRequest]:
        if not VERTEX_PROJECT_ID:
            logger.warning("VERTEX_PROJECT_ID is not configured")
            return None

        catalog_desc = cls.get_catalog_description()

        instruction = (
            "Eres un asistente experto en análisis de datos para un taller mecánico y servicios de auxilio mecánico.\n"
            "Tu tarea es interpretar la solicitud en lenguaje natural del usuario (en español o inglés) y traducirla a una consulta estructurada de reportes en formato JSON.\n\n"
            "Esquema del catálogo de reportes disponible:\n"
            f"{catalog_desc}\n\n"
            "INSTRUCCIONES DE TRADUCCIÓN:\n"
            "1. Determina el 'report_type' más adecuado según la solicitud.\n"
            "2. Selecciona en 'selected_fields' las columnas solicitadas por el usuario. Si no se especifican campos, selecciona al menos 3 a 5 campos clave por defecto (como ID, descripción, estado, fecha de creación).\n"
            "3. Identifica filtros y mapea operadores:\n"
            "   - 'igual a' -> 'eq'\n"
            "   - 'diferente de' -> 'ne'\n"
            "   - 'mayor que' -> 'gt'\n"
            "   - 'menor que' -> 'lt'\n"
            "   - 'mayor o igual que' -> 'gte'\n"
            "   - 'menor o igual que' -> 'lte'\n"
            "   - 'que contenga' o 'contiene' -> 'like'\n"
            "   - 'es nulo' -> 'is_null'\n"
            "   - 'no es nulo' -> 'is_not_null'\n"
            "4. Define el ordenamiento en 'sort_field' y 'sort_order' ('asc' o 'desc') si el usuario lo solicita.\n"
            "   - IMPORTANTE: Si el usuario pide 'los últimos X registrados' o similar, debes ordenar por el campo de fecha correspondiente (generalmente 'created_at') de forma descendente ('sort_order': 'desc') y definir el 'limit' con la cantidad solicitada (ej. 10).\n"
            "5. Si el usuario pide una cantidad limitada de registros (ej. 'los primeros 5', 'los últimos 10'), asigna ese número al campo 'limit'.\n"
            "6. Genera la salida respetando estrictamente el formato JSON especificado."
        )

        try:
            # Inicializar Vertex AI
            key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEX")
            creds = None
            if key_path and os.path.exists(key_path):
                creds = service_account.Credentials.from_service_account_file(key_path)

            vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION, credentials=creds)
            model = GenerativeModel(VERTEX_MODEL_NAME)

            # Generar contenido con esquema estructurado
            response = model.generate_content(
                [instruction, f"Solicitud del usuario: {prompt}"],
                generation_config=GenerationConfig(
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",
                )
            )

            raw_text = response.text.strip() if response.text else "{}"
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.lower().startswith("json"):
                    raw_text = raw_text[4:].strip()

            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw_text = raw_text[start : end + 1]

            result_dict = json.loads(raw_text)

            # Mapear a ReportRunRequest DTO
            filters_dto = [
                ReportFilter(
                    field=f["field"],
                    operator=f["operator"],
                    value=f.get("value")
                )
                for f in result_dict.get("filters", [])
            ]

            limit_val = result_dict.get("limit")
            if limit_val is None:
                limit_val = 50

            offset_val = result_dict.get("offset")
            if offset_val is None:
                offset_val = 0

            return ReportRunRequest(
                report_type=result_dict["report_type"],
                selected_fields=result_dict["selected_fields"],
                filters=filters_dto,
                sort_field=result_dict.get("sort_field"),
                sort_order=result_dict.get("sort_order", "asc"),
                limit=limit_val,
                offset=offset_val
            )

        except Exception as e:
            logger.exception("Error parsing report prompt using Gemini: %s", e)
            return None
