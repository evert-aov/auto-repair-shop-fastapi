import io
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse
from urllib.request import urlopen

import vertexai
from google.cloud import storage
from PIL import Image, ImageEnhance, ImageOps
from vertexai.generative_models import GenerationConfig, GenerativeModel, Part, Tool

from app.module_incidents.ai.dtos.ai_dtos import ClassificationResult
from app.module_incidents.ai.services.storage_service import get_storage_client, enhance_image

logger = logging.getLogger(__name__)

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_NAME = os.getenv("VERTEX_MODEL_NAME", "gemini-1.5-flash")
HTTP_IMAGE_TIMEOUT = float(os.getenv("GOOGLE_VISION_HTTP_TIMEOUT", "20"))


@dataclass
class PreparedImage:
    source_url: str
    content: bytes
    mime_type: str
    preprocessing: dict


_ALLOWED_CATEGORIES = {
    "battery",
    "tire",
    "engine",
    "ac",
    "transmission",
    "towing",
    "locksmith",
    "general",
    "collision",
    "uncertain",
}
_ALLOWED_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

_KEYWORD_MAP: dict[str, tuple[str, str]] = {
    "llanta": ("tire", "HIGH"),
    "pinch": ("tire", "MEDIUM"),
    "tire": ("tire", "HIGH"),
    "flat": ("tire", "MEDIUM"),
    "bateria": ("battery", "HIGH"),
    "battery": ("battery", "HIGH"),
    "motor": ("engine", "CRITICAL"),
    "engine": ("engine", "CRITICAL"),
    "freno": ("general", "HIGH"),
    "brake": ("general", "HIGH"),
    "aire": ("ac", "LOW"),
    " ac ": ("ac", "LOW"),
    "a/c": ("ac", "LOW"),
    "climatiz": ("ac", "LOW"),
    "transmision": ("transmission", "HIGH"),
    "transmission": ("transmission", "HIGH"),
    "grua": ("towing", "MEDIUM"),
    "tow": ("towing", "MEDIUM"),
    "llave": ("locksmith", "MEDIUM"),
    "lock": ("locksmith", "MEDIUM"),
    "mecanico": ("general", "MEDIUM"),
    "choca": ("general", "HIGH"),
    "golpe": ("general", "HIGH"),
    "choque": ("general", "HIGH"),
    "collision": ("general", "HIGH"),
}


# --- Image Utilities ---

def _download_image(file_url: str) -> bytes:
    parsed = urlparse(file_url)
    if parsed.scheme == "gs":
        client = get_storage_client()
        bucket = client.bucket(parsed.netloc)
        blob = bucket.blob(parsed.path.lstrip("/"))
        return blob.download_as_bytes()

    if parsed.scheme in {"http", "https"}:
        with urlopen(file_url, timeout=HTTP_IMAGE_TIMEOUT) as response:
            return response.read()

    # Soporte para archivos locales (uploads)
    if file_url.startswith("/uploads/"):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        local_path = os.path.join(project_root, file_url.lstrip("/"))
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"Local evidence file not found: {local_path}")

    raise ValueError("Only gs://, http://, https://, and local /uploads/ URLs are supported for images")


# Eliminado enhance_image de aquí, movido a storage_service.py para evitar importes circulares.


def prepare_image_for_vertex(file_url: str) -> PreparedImage:
    original = _download_image(file_url)
    enhanced, preprocessing = enhance_image(original)
    return PreparedImage(
        source_url=file_url,
        content=enhanced,
        mime_type="image/jpeg",
        preprocessing=preprocessing,
    )


# --- AI Logic ---

def _build_triage_prompt(description: str, audio_transcript: str | None, vehicle_info: str | None = None) -> str:
    transcript = (audio_transcript or "").strip()
    return (
        "Eres un Ingeniero de Soporte Técnico Automotriz con años de experiencia. Tu objetivo es realizar un triaje preciso basado en evidencia visual y textual.\n"
        "INSTRUCCIONES DE ANÁLISIS:\n"
        "1. Analiza las imágenes buscando: luces de advertencia (MIL/Check Engine), deformaciones, quemaduras, fluidos visibles (fugas), o daños estructurales.\n"
        "2. Cruza la descripción del usuario con lo que ves en las fotos.\n"
        "3. Determina la urgencia: ¿Es seguro conducir el vehículo?\n\n"
        "Responde en JSON con esta estructura:\n"
        "{\n"
        "  \"sistema\": {\n"
        "    \"categoria\": \"categoria_elegida\",\n"
        "    \"prioridad\": \"PRIORIDAD_ELEGIDA\",\n"
        "    \"requiere_grua\": false,\n"
        "    \"especialidad_requerida\": \"especialidad\",\n"
        "    \"confianza\": 0.9\n"
        "  },\n"
        "  \"tecnico\": {\n"
        "    \"diagnostico_tecnico\": \"Análisis profundo: Componentes afectados, posibles fallas en cascada y severidad técnica.\",\n"
        "    \"herramientas_sugeridas\": [\"Herramienta 1\", \"Herramienta 2\"],\n"
        "    \"procedimiento_recomendado\": \"Guía paso a paso para el mecánico que recibirá el vehículo.\"\n"
        "  },\n"
        "  \"cliente\": {\n"
        "    \"mensaje_tranquilizador\": \"Mensaje empático y profesional.\",\n"
        "    \"posible_causa\": \"Explicación en lenguaje sencillo pero preciso.\",\n"
        "    \"consejo_seguridad\": \"Acciones inmediatas para el cliente (ej. 'No abra el capó', 'Estaciónese inmediatamente').\"\n"
        "  }\n"
        "}\n"
        "Reglas:\n"
        "- Sé extremadamente específico en el diagnóstico técnico.\n"
        "- Categorías: [battery, tire, collision, engine, ac, transmission, towing, locksmith, general, uncertain].\n"
        f"Vehículo: {vehicle_info or 'No especificado'}\n"
        f"Contexto del usuario: {description}\n"
        f"Transcripción de audio: {transcript or 'N/A'}"
    )


def _build_estimation_prompt(diagnostic: str, category: str) -> str:
    return (
        f"Actúa como un perito tasador de seguros automotrices en Bolivia. "
        f"Tu misión es estimar el costo de reparación basado en el siguiente diagnóstico: {diagnostic}\n"
        f"Categoría: {category}\n\n"
        f"Usa Google Search para obtener precios reales en el mercado boliviano (Santa Cruz, La Paz, Cochabamba).\n"
        "Considera tanto repuestos (originales vs alternativos) como mano de obra promedio.\n\n"
        "Responde SOLAMENTE en JSON:\n"
        "{\n"
        "  \"costo_estimado\": {\n"
        "    \"moneda\": \"BOB\",\n"
        "    \"min\": 0.0,\n"
        "    \"max\": 0.0,\n"
        "    \"desglose\": \"Detalle breve: Repuestos (~X BOB) + Mano de Obra (~Y BOB)\",\n"
        "    \"justificacion\": \"Justificación basada en precios actuales del mercado local.\"\n"
        "  }\n"
        "}\n"
    )


def _extract_json(raw_text: str) -> dict | None:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


def _normalize_triage_result(payload: dict) -> dict:
    sistema = payload.get("sistema", {})
    tecnico = payload.get("tecnico", {})
    cliente = payload.get("cliente", {})

    category_raw = str(sistema.get("categoria", payload.get("category", "incierto"))).lower().strip()

    es_to_en = {
        "bateria": "battery",
        "llanta": "tire",
        "choque": "collision",
        "colision": "collision",
        "motor": "engine",
        "transmision": "transmission",
        "grua": "towing",
        "llave": "locksmith",
        "aire": "ac",
        "freno": "general",
        "incierto": "uncertain"
    }
    category = es_to_en.get(category_raw, category_raw)

    if category not in _ALLOWED_CATEGORIES and category != "uncertain":
        category = "uncertain"

    priority = str(sistema.get("prioridad", payload.get("priority", "MEDIUM"))).upper().strip()
    if priority not in _ALLOWED_PRIORITIES:
        priority = "MEDIUM"

    try:
        confidence = float(sistema.get("confianza", payload.get("confidence", 0.5)))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return {
        "sistema": {
            "categoria": category,
            "prioridad": priority,
            "requiere_grua": bool(sistema.get("requiere_grua", False)),
            "especialidad_requerida": sistema.get("especialidad_requerida", "otro"),
            "confianza": confidence,
        },
        "tecnico": {
            "diagnostico_tecnico": tecnico.get("diagnostico_tecnico", "No evaluado"),
            "herramientas_sugeridas": tecnico.get("herramientas_sugeridas", []),
            "procedimiento_recomendado": tecnico.get("procedimiento_recomendado", ""),
        },
        "cliente": {
            "mensaje_tranquilizador": cliente.get("mensaje_tranquilizador", "Estamos analizando su problema."),
            "posible_causa": cliente.get("posible_causa", ""),
            "consejo_seguridad": cliente.get("consejo_seguridad", "Manténgase en un lugar seguro."),
        }
    }


def analyze_incident_multimodal(
    description: str,
    image_urls: List[str],
    audio_transcript: str | None = None,
    vehicle_info: str | None = None
) -> Optional[dict]:
    """
    Unified multimodal triage. Handles image preparation internally.
    """
    if not VERTEX_PROJECT_ID:
        logger.warning("VERTEX_PROJECT_ID is not configured")
        return None

    try:
        # 1. Preparar imágenes mejoradas con caché
        prepared_parts = []
        image_cache = {}
        for url in image_urls:
            try:
                if url not in image_cache:
                    prepared = prepare_image_for_vertex(url)
                    image_cache[url] = Part.from_data(data=prepared.content, mime_type=prepared.mime_type)
                prepared_parts.append(image_cache[url])
            except Exception as e:
                logger.warning(f"Could not prepare image {url} for Vertex: {e}")

        # 2. Inicializar modelo con fallback de credenciales
        key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEX")
        creds = None
        if key_path and os.path.exists(key_path):
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(key_path)
            logger.info(f"✅ Vertex AI inicializado usando archivo: {key_path}")
        
        vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION, credentials=creds)
        model = GenerativeModel(VERTEX_MODEL_NAME)

        # 3. Construir prompt y contenido
        prompt = _build_triage_prompt(description, audio_transcript, vehicle_info)
        parts = [prompt] + prepared_parts

        # 4. Generar contenido
        response = model.generate_content(
            parts,
            generation_config=GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            return None

        parsed = _extract_json(response.text)
        return _normalize_triage_result(parsed) if parsed else None

    except Exception as exc:
        logger.exception("Vertex triage analysis failed: %s", exc)
        return {
            "sistema": {"categoria": "general", "prioridad": "MEDIUM", "confianza": 0.1},
            "cliente": {"mensaje_tranquilizador": "Estamos analizando su caso."},
            "tecnico": {"diagnostico_tecnico": f"Error en IA: {exc}"}
        }


def estimate_cost_grounded(diagnostic: str, category: str) -> Optional[dict]:
    """Separate call for cost estimation with Google Search grounding"""
    if not VERTEX_PROJECT_ID:
        logger.warning("VERTEX_PROJECT_ID is not configured for cost estimation")
        return None

    try:
        # Reutilizar lógica de credenciales para estimate
        key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEX")
        creds = None
        if key_path and os.path.exists(key_path):
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(key_path)
        
        vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION, credentials=creds)
        
        try:
            tool = Tool.from_dict({"google_search": {}})
        except Exception:
            from vertexai.generative_models import grounding
            tool = Tool.from_google_search_retrieval(
                google_search_retrieval=grounding.GoogleSearchRetrieval()
            )
            
        model = GenerativeModel(VERTEX_MODEL_NAME, tools=[tool])
        prompt = _build_estimation_prompt(diagnostic, category)

        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=0.2, top_p=0.8),
        )

        return _extract_json(response.text)
    except Exception as exc:
        logger.exception("Grounding estimation failed: %s", exc)
        return None


def classify_text_only(
        description: str,
        audio_transcript: Optional[str] = None
) -> ClassificationResult:
    """Keyword based fallback classification (previously classification_service)"""
    combined = " ".join(filter(None, [description, audio_transcript])).lower()

    category = "general"
    priority = "MEDIUM"
    confidence = 0.60
    summary = description[:200]

    for keyword, (cat, prio) in _KEYWORD_MAP.items():
        if keyword in combined:
            category = cat
            priority = prio
            confidence = 0.85
            summary = f"Detected {cat} issue — {description[:150]}"
            break

    logger.info("Text-only classification: category=%s, priority=%s, confidence=%.2f", category, priority, confidence)
    return ClassificationResult(
        category=category,
        priority=priority,
        confidence=confidence,
        summary=summary,
    )
