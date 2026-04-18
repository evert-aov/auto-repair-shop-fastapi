# CU10 — Solicitar Auxilio Mecánico

## Descripción General

El cliente reporta una emergencia vehicular adjuntando evidencias (fotos, audio, texto). El sistema:

1. Crea un registro de incidente
2. Almacena las evidencias en S3
3. Procesa asincronicamente con IA para clasificar la emergencia
4. Si la confianza > 0.4, busca talleres compatibles (specialty + ubicación)
5. Calcula `ai_score` para cada taller y crea ofertas
6. Retorna estado inicial al cliente

---

## Arquitectura

### Módulos Involucrados

**`module_workshops/`** — Gestión de talleres
- `Specialty` — catálogo de especialidades (battery, tire, engine, ac, transmission, towing, locksmith, general)
- `Workshop` — datos del taller (ubicación, rating, comisión)
- `WorkshopSpecialty` — relación M:M con `is_mobile` flag
- `Technician` — técnicos disponibles con geolocalización

**`module_incidents/`** — Gestión de emergencias
- `Incident` — tabla principal con estados (pending → analyzing → matched → assigned → in_progress → completed)
- `IncidentEvidence` — fotos, audios, textos con transcripción y análisis JSONB
- `IncidentStatusHistory` — auditoría de cambios de estado
- `WorkshopOffer` — ofertas de talleres (notified, accepted, rejected, expired)

**`module_incidents/ai/`** — Procesamiento con IA (stubs, implementar con APIs reales)
- `audio_service.py` — Whisper para transcripción
- `vision_service.py` — Vision API para análisis de imágenes
- `classification_service.py` — NLP/LLM para clasificación de categoría y prioridad

---

## Estados del Incidente

```
pending
  ↓
analyzing        (AI processing en background)
  ├─→ matched    (confidence > 0.4, se crean ofertas)
  │   ↓
  │   assigned   (taller acepta)
  │   ↓
  │   in_progress (técnico en camino o en lugar)
  │   ↓
  │   completed  (servicio finalizado)
  │
  ├─→ pending_info (confidence ≤ 0.4, se solicita más info)
  │
  └─→ no_offers  (no hay talleres disponibles)
     error       (error en IA processing)
     cancelled   (cancelado por cliente)
```

---

## Flujo de Datos

### 1. POST `/api/incidents/request-help`

**Request:**
```json
{
  "description": "Se me pinchó una llanta en la avenida",
  "vehicle_id": "550e8400-e29b-41d4-a716-446655440000",
  "latitude": -17.8,
  "longitude": -63.2,
  "evidences": [
    {
      "evidence_type": "image",
      "file_url": "s3://bucket/photo.jpg"
    },
    {
      "evidence_type": "audio",
      "file_url": "s3://bucket/audio.wav"
    }
  ]
}
```

**Response (201):**
```json
{
  "id": "12345678-1234-1234-1234-123456789012",
  "status": "analyzing",
  "created_at": "2026-04-17T10:30:00Z",
  "message": "Solicitud de auxilio recibida. Analizando...",
  "ai_category": null,
  "ai_priority": null,
  "ai_confidence": null,
  "ai_summary": null,
  "estimated_arrival_min": null
}
```

---

### 2. Background Task: `_process_incident_with_ai(incident_id)`

Se ejecuta después de que la respuesta se envíe al cliente. **No bloquea la request.**

**Pasos:**

a) **Procesar evidencias**
   - Audio → `audio_service.transcribe_audio()` → transcripción en `IncidentEvidence.transcription`
   - Imagen → `vision_service.analyze_image()` → análisis JSONB en `IncidentEvidence.ai_analysis`

b) **Clasificar incidente**
   ```python
   classification = classification_service.classify_incident(
       description=incident.description,
       audio_transcript=audio_transcript,
       image_analysis=image_analysis,
   )
   ```
   
   Retorna:
   ```python
   {
       "category": "tire",
       "priority": "HIGH",
       "confidence": 0.85,
       "summary": "Detected tire issue — se me pinchó una llanta"
   }
   ```

c) **Decisión: ¿proceder al matchmaking?**
   
   - Si `confidence > 0.4`:
     - Status → `matched`
     - Llamar `assignment_service.find_and_create_offers(db, incident)`
   
   - Si `confidence ≤ 0.4`:
     - Status → `pending_info`
     - Esperar más información del cliente

---

### 3. Matchmaking: `find_and_create_offers(db, incident)`

**Algoritmo:**

a) **Mapear categoría IA → especialidad taller**
   ```
   tire → tire
   battery → battery
   engine → engine
   ... etc
   uncertain → None (sin ofertas)
   ```

b) **Buscar talleres**
   - Specialty coincide
   - En radio de 50 km (Haversine)
   - Rating ≥ 3.5
   - Tiene técnico disponible

c) **Calcular `ai_score` para cada taller**
   ```
   ai_score = (
       distance_score * 0.4 +    # 0-1 (inverso a distancia)
       rating_score * 0.4 +       # 0-5 → 0-1
       priority_weight * 0.2      # LOW:0.3, MEDIUM:0.5, HIGH:0.8, CRITICAL:1.0
   )
   ```

d) **Crear ofertas**
   - Top 3 talleres por `ai_score`
   - Status: `notified`
   - Expiran en 30 minutos
   - `estimated_arrival_min` = distancia / velocidad (60 km/h)

---

## Base de Datos

### Nuevas tablas

**`workshops`**
```sql
CREATE TABLE workshops (
    id UUID PRIMARY KEY,
    owner_user_id UUID NOT NULL REFERENCES users(id),
    business_name VARCHAR(255),
    latitude FLOAT,
    longitude FLOAT,
    commission_rate FLOAT DEFAULT 10.0,
    rating_avg FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**`specialties`**
```sql
CREATE TABLE specialties (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) UNIQUE
);
```

**`workshop_specialties`**
```sql
CREATE TABLE workshop_specialties (
    workshop_id UUID PRIMARY KEY REFERENCES workshops(id),
    specialty_id BIGINT PRIMARY KEY REFERENCES specialties(id),
    is_mobile BOOLEAN DEFAULT FALSE
);
```

**`technicians`**
```sql
CREATE TABLE technicians (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    workshop_id UUID REFERENCES workshops(id),
    current_latitude FLOAT,
    current_longitude FLOAT,
    is_available BOOLEAN DEFAULT TRUE
);
```

**`incidents`**
```sql
CREATE TABLE incidents (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(id),
    vehicle_id UUID REFERENCES vehicles(id),
    description TEXT,
    incident_lat FLOAT,
    incident_lng FLOAT,
    status ENUM(...),
    ai_category VARCHAR(50),
    ai_priority ENUM(LOW, MEDIUM, HIGH, CRITICAL),
    ai_summary TEXT,
    ai_confidence FLOAT,
    assigned_workshop_id UUID REFERENCES workshops(id),
    assigned_technician_id UUID REFERENCES technicians(id),
    estimated_arrival_min INT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**`incident_evidence`**
```sql
CREATE TABLE incident_evidence (
    id UUID PRIMARY KEY,
    incident_id UUID REFERENCES incidents(id),
    evidence_type ENUM(image, audio, text),
    file_url VARCHAR(500),
    transcription TEXT,
    ai_analysis JSONB
);
```

**`incident_status_history`**
```sql
CREATE TABLE incident_status_history (
    id UUID PRIMARY KEY,
    incident_id UUID REFERENCES incidents(id),
    previous_status VARCHAR(30),
    new_status VARCHAR(30),
    changed_by UUID,
    reason VARCHAR(255),
    created_at TIMESTAMP
);
```

**`workshop_offers`**
```sql
CREATE TABLE workshop_offers (
    id UUID PRIMARY KEY,
    incident_id UUID REFERENCES incidents(id),
    workshop_id UUID REFERENCES workshops(id),
    status ENUM(notified, accepted, rejected, expired),
    distance_km FLOAT,
    ai_score FLOAT,
    created_at TIMESTAMP,
    expires_at TIMESTAMP
);
```

---

## Permiso Requerido

Para usar el endpoint, el usuario debe tener rol **`client`**.

```python
@router.post(
    "/request-help",
    dependencies=[Depends(require_role("client"))]
)
```

---

## Notas de Implementación

### AI Services (Stubs)

Actualmente los servicios de IA retornan `None` o datos mock. Para usar APIs reales:

**`audio_service.py`** — integrar con OpenAI Whisper:
```python
from openai import OpenAI

def transcribe_audio(file_url: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # Descargar archivo de S3, enviarlo a Whisper
    return transcript
```

**`vision_service.py`** — integrar con OpenAI Vision o Google Vision:
```python
def analyze_image(file_url: str) -> dict:
    # Analizar características, daños, ubicación, etc.
    return {"damage_detected": True, "areas": [...]}
```

**`classification_service.py`** — mejorar con LLM:
```python
def classify_incident(...) -> ClassificationResult:
    prompt = f"""
    Analiza este reporte de emergencia vehicular:
    Descripción: {description}
    Transcripción: {audio_transcript}
    Análisis imagen: {image_analysis}
    
    Devuelve JSON con: category, priority, confidence (0-1), summary
    """
    response = openai.ChatCompletion.create(model="gpt-4", messages=[...])
```

### Geolocalización

El cliente envía `latitude` y `longitude` del GPS de su dispositivo.

Los talleres tienen coordenadas fijas en su perfil.

La distancia se calcula con la fórmula de Haversine (sin PostGIS).

### Notificaciones (No implementadas en CU10)

En CU11/CU12 se implementarán notificaciones push a:
- Cliente: "Emergencia clasificada. Buscando talleres..."
- Talleres: "Nueva solicitud de auxilio: [categoría]"

### Expiración de Ofertas

Las ofertas duran 30 minutos. En CU13 un job background marcará las expiradas:

```python
# En algun background task scheduler
def expire_old_offers():
    db = SessionLocal()
    expired = db.query(WorkshopOffer).filter(
        WorkshopOffer.expires_at < now(),
        WorkshopOffer.status == "notified"
    ).all()
    for offer in expired:
        offer.status = "expired"
    db.commit()
```

---

## Validaciones

- Cliente debe existir y estar activo
- Vehículo debe pertenecer al cliente
- Latitud/longitud deben ser números válidos
- Evidencias no pueden estar vacías
- URLs de S3 deben ser válidas
