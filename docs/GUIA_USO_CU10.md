# Guía de Uso — CU10: Solicitar Auxilio Mecánico

---

## 1. Preparación Inicial

### 1.1 Levantar el servidor

```bash
fastapi run app/main.py
```

El servidor estará disponible en `http://localhost:8000`

Documentación interactiva: `http://localhost:8000/docs`

### 1.2 Aplicar migraciones

```bash
# Generar migración para nuevas tablas
alembic revision --autogenerate -m "add workshops and incidents modules"

# Aplicar
alembic upgrade head
```

### 1.3 Cargar datos iniciales (opcional)

```bash
python -m app.seed
```

Crea admin, roles, permisos. Detalles en CLAUDE.md.

---

## 2. Obtener Token JWT

### 2.1 Login como cliente

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=client_user&password=password123"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Guardar el token para los próximos requests.

### 2.2 Alternativa: crear cliente nuevo

```bash
curl -X POST http://localhost:8000/api/auth/register_client \
  -H "Content-Type: application/json" \
  -d '{
    "email": "cliente@example.com",
    "name": "Juan",
    "last_name": "Pérez",
    "password": "securepass123"
  }'
```

---

## 3. Verificar vehículos del cliente

Antes de reportar una emergencia, el cliente debe tener vehículos registrados.

```bash
curl -X GET http://localhost:8000/api/vehicles \
  -H "Authorization: Bearer $TOKEN"
```

Si no hay vehículos, crear uno:

```bash
curl -X POST http://localhost:8000/api/vehicles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "make": "Toyota",
    "model": "Corolla",
    "year": 2020,
    "license_plate": "ABC-1234",
    "color": "Blanco",
    "transmission_type": "automatic",
    "fuel_type": "gasoline"
  }'
```

Guardar el `vehicle_id` para el siguiente paso.

---

## 4. Reportar Emergencia — POST /api/incidents/request-help

### Endpoint

```
POST /api/incidents/request-help
Authorization: Bearer <TOKEN>
Content-Type: application/json
```

### Request mínimo (sin evidencias)

```json
{
  "description": "Se me pinchó una llanta en la avenida principal",
  "vehicle_id": "550e8400-e29b-41d4-a716-446655440000",
  "latitude": -17.8,
  "longitude": -63.2,
  "evidences": []
}
```

### Request completo (con evidencias)

```json
{
  "description": "Llanta pinchada, vehículo inmóvil en ruta",
  "vehicle_id": "550e8400-e29b-41d4-a716-446655440000",
  "latitude": -17.8,
  "longitude": -63.2,
  "evidences": [
    {
      "evidence_type": "image",
      "file_url": "s3://my-bucket/photo-2026-04-17.jpg"
    },
    {
      "evidence_type": "audio",
      "file_url": "s3://my-bucket/voice-memo-001.wav"
    },
    {
      "evidence_type": "text",
      "file_url": "s3://my-bucket/description.txt"
    }
  ]
}
```

### Response (201 Created)

```json
{
  "id": "98765432-abcd-efgh-ijkl-mnopqrstuvwx",
  "status": "analyzing",
  "created_at": "2026-04-17T10:35:22.123456Z",
  "message": "Solicitud de auxilio recibida. Analizando...",
  "ai_category": null,
  "ai_priority": null,
  "ai_confidence": null,
  "ai_summary": null,
  "estimated_arrival_min": null
}
```

**IMPORTANTE:** El cliente recibe esta respuesta **inmediatamente**. El procesamiento de IA ocurre en background.

---

## 5. Verificar Estado del Incidente

### Endpoint (aún no implementado, para CU11)

```
GET /api/incidents/{incident_id}
```

**Mientras se procesa (primeros segundos):**
```json
{
  "id": "98765432-abcd-efgh-ijkl-mnopqrstuvwx",
  "status": "analyzing",
  ...
}
```

**Después de clasificación exitosa:**
```json
{
  "id": "98765432-abcd-efgh-ijkl-mnopqrstuvwx",
  "status": "matched",
  "ai_category": "tire",
  "ai_priority": "HIGH",
  "ai_confidence": 0.85,
  "ai_summary": "Detected tire issue — llanta pinchada",
  "estimated_arrival_min": 15,
  ...
}
```

**Si confianza baja:**
```json
{
  "id": "98765432-abcd-efgh-ijkl-mnopqrstuvwx",
  "status": "pending_info",
  "ai_confidence": 0.25,
  ...
}
```

---

## 6. Ejemplos con `curl`

### 6.1 Crear incidente sin evidencias

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
VEHICLE_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST http://localhost:8000/api/incidents/request-help \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Llanta pinchada\",
    \"vehicle_id\": \"$VEHICLE_ID\",
    \"latitude\": -17.8,
    \"longitude\": -63.2,
    \"evidences\": []
  }"
```

### 6.2 Crear incidente con imagen

```bash
curl -X POST http://localhost:8000/api/incidents/request-help \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Motor no enciende\",
    \"vehicle_id\": \"$VEHICLE_ID\",
    \"latitude\": -17.8,
    \"longitude\": -63.2,
    \"evidences\": [
      {
        \"evidence_type\": \"image\",
        \"file_url\": \"https://s3.amazonaws.com/bucket/engine-photo.jpg\"
      }
    ]
  }"
```

---

## 7. Testing con Python

### 7.1 Script de test básico

```python
import requests
import json

BASE_URL = "http://localhost:8000/api"
TOKEN = "your_jwt_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Crear incidente
payload = {
    "description": "Aire acondicionado no funciona",
    "vehicle_id": "550e8400-e29b-41d4-a716-446655440000",
    "latitude": -17.8,
    "longitude": -63.2,
    "evidences": [
        {
            "evidence_type": "audio",
            "file_url": "s3://bucket/voice-record.wav"
        }
    ]
}

response = requests.post(
    f"{BASE_URL}/incidents/request-help",
    headers=headers,
    json=payload
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

incident_id = response.json()["id"]
print(f"Incident ID: {incident_id}")
```

### 7.2 Esperar a que se procese (con polling)

```python
import time

incident_id = "98765432-abcd-efgh-ijkl-mnopqrstuvwx"

for i in range(10):
    response = requests.get(
        f"{BASE_URL}/incidents/{incident_id}",
        headers=headers
    )
    
    data = response.json()
    print(f"[{i}] Status: {data['status']}, Confidence: {data.get('ai_confidence')}")
    
    if data['status'] != 'analyzing':
        print(f"Procesamiento terminado: {data['status']}")
        print(f"Categoría: {data.get('ai_category')}")
        print(f"Prioridad: {data.get('ai_priority')}")
        break
    
    time.sleep(2)
```

---

## 8. Verificar Ofertas de Talleres

### Endpoint (para CU11)

```
GET /api/incidents/{incident_id}/offers
```

**Response:**
```json
[
  {
    "id": "offer-123",
    "workshop_id": "workshop-456",
    "workshop_name": "Taller Juan - Especialista en llantas",
    "distance_km": 2.5,
    "ai_score": 0.92,
    "status": "notified",
    "expires_at": "2026-04-17T11:05:22Z"
  },
  {
    "id": "offer-124",
    "workshop_id": "workshop-789",
    "workshop_name": "Taller Rápido",
    "distance_km": 5.0,
    "ai_score": 0.78,
    "status": "notified",
    "expires_at": "2026-04-17T11:05:22Z"
  }
]
```

---

## 9. Simular Talleres en BD

Para testing, insertar datos en `workshops`, `specialties`, `technicians`:

### SQL

```sql
-- Crear especialidades
INSERT INTO specialties (name) VALUES ('tire'), ('battery'), ('engine'), ('ac'), ('transmission'), ('towing'), ('locksmith'), ('general');

-- Crear taller
INSERT INTO workshops (id, owner_user_id, business_name, latitude, longitude, rating_avg, is_active)
VALUES (
  'ws-001-uuid',
  'user-uuid',
  'Taller Especialista en Llantas',
  -17.8,
  -63.2,
  4.8,
  TRUE
);

-- Asignar especialidad
INSERT INTO workshop_specialties (workshop_id, specialty_id, is_mobile)
VALUES ('ws-001-uuid', 1, FALSE);  -- 1 es tire

-- Crear técnico
INSERT INTO technicians (id, user_id, workshop_id, is_available)
VALUES ('tech-001-uuid', 'user-uuid', 'ws-001-uuid', TRUE);
```

### Python (con SQLAlchemy)

```python
from app.database import SessionLocal
from app.module_workshops.models import Workshop, Specialty, WorkshopSpecialty, Technician
from uuid import uuid4

db = SessionLocal()

# Crear especialidad
specialty = Specialty(name="tire")
db.add(specialty)
db.commit()

# Crear taller
workshop = Workshop(
    id=uuid4(),
    owner_user_id=user_id,
    business_name="Taller Llantas Express",
    latitude=-17.8,
    longitude=-63.2,
    rating_avg=4.8,
    is_active=True
)
db.add(workshop)
db.commit()

# Asignar especialidad
ws_spec = WorkshopSpecialty(
    workshop_id=workshop.id,
    specialty_id=specialty.id,
    is_mobile=False
)
db.add(ws_spec)
db.commit()

# Crear técnico
technician = Technician(
    id=uuid4(),
    user_id=tech_user_id,
    workshop_id=workshop.id,
    is_available=True
)
db.add(technician)
db.commit()

print(f"Workshop created: {workshop.id}")
```

---

## 10. Casos de Prueba

### Caso 1: Emergencia con confianza alta (>0.4)

**Request:**
```json
{
  "description": "Llanta pinchada",
  "vehicle_id": "...",
  "latitude": -17.8,
  "longitude": -63.2,
  "evidences": []
}
```

**Expected Flow:**
1. Status: `pending` → `analyzing` → `matched`
2. `ai_confidence` ≈ 0.85
3. Se crean ofertas en `workshop_offers`
4. `estimated_arrival_min` se calcula

### Caso 2: Emergencia con baja confianza (≤0.4)

**Request:**
```json
{
  "description": "Algo raro pasa con el auto",
  "vehicle_id": "...",
  "latitude": -17.8,
  "longitude": -63.2,
  "evidences": []
}
```

**Expected Flow:**
1. Status: `pending` → `analyzing` → `pending_info`
2. `ai_confidence` ≈ 0.45
3. `ai_category`: "general"
4. NO se crean ofertas
5. Sistema espera más información del cliente

### Caso 3: Sin vehículo válido

**Request:**
```json
{
  "description": "Emergencia",
  "vehicle_id": "non-existent-uuid",
  "latitude": -17.8,
  "longitude": -63.2,
  "evidences": []
}
```

**Expected Response:** `404 - Vehicle not found`

### Caso 4: Usuario no es cliente

**Request:**
```
Con TOKEN de usuario admin
```

**Expected Response:** `403 - Access denied`

---

## 11. Logs y Debugging

### Verificar logs de procesamiento

En la terminal donde corre FastAPI:

```
INFO:app.module_incidents.ai.services.classification_service:Classification: category=tire, priority=HIGH, confidence=0.85
INFO:app.module_incidents.services.assignment_service:Offer → workshop=... score=0.92 dist=2.5km
```

### Base de datos — verificar registros

```sql
-- Ver incidentes
SELECT id, client_id, status, ai_category, ai_priority, ai_confidence FROM incidents;

-- Ver evidencias
SELECT incident_id, evidence_type, transcription, ai_analysis FROM incident_evidence;

-- Ver ofertas
SELECT incident_id, workshop_id, status, ai_score, distance_km FROM workshop_offers;

-- Ver historial de estados
SELECT incident_id, previous_status, new_status, reason, created_at FROM incident_status_history;
```

---

## 12. Próximos CU

- **CU11**: Cliente acepta/rechaza ofertas
- **CU12**: Taller responde a oferta (aceptar/rechazar)
- **CU13**: Técnico actualiza ubicación, cliente recibe ETA
- **CU14**: Servicio completado, calificación del taller
- **CU15**: Reportes y analytics

---

## Troubleshooting

### ❌ "Client not found"
- Verificar que el token sea de un usuario con rol `client`
- Ver que exista el registro en tabla `clients`

### ❌ "Vehicle not found"
- Listar vehículos: `GET /api/vehicles`
- Crear vehículo si no existe

### ❌ Background task no procesa
- Verificar que FastAPI esté corriendo sin errores
- Ver logs en la terminal
- Nota: `BackgroundTasks` solo funciona en modo servidor (no en tests sync)

### ❌ Ofertas no se crean
- Verificar que `ai_confidence > 0.4`
- Verificar que existan `specialties` en BD
- Verificar que existan `workshops` con la especialidad
- Verificar que los workshops tengan `rating_avg >= 3.5`
- Verificar que haya `technicians` disponibles

---

**¡Listo!** CU10 está operativo. 🚗
