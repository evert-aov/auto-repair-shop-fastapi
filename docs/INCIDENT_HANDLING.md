# Guía de Manejo de Incidentes - Auto Repair Shop FastAPI

## Resumen Ejecutivo

El sistema maneja incidentes de reparación de vehículos mediante un flujo automatizado que:
1. **Captura** solicitudes de auxilio desde clientes con ubicación en tiempo real
2. **Analiza** evidencias (fotos, audio, descripciones) con IA
3. **Clasifica** el tipo y prioridad del problema
4. **Busca** talleres cercanos geográficamente con especialidades compatibles
5. **Selecciona** el mejor taller basado en distancia, rating y disponibilidad
6. **Notifica** al taller y monitorea aceptación/rechazo

---

## 1. Ciclo de Vida del Incidente

### Estados Principales

```
PENDING
   ↓ (se inicia análisis IA)
ANALYZING
   ├─→ MATCHED (IA clasificó con confianza > 40%)
   ├─→ PENDING_INFO (confianza ≤ 40%, solicita más información)
   └─→ ERROR (falló procesamiento de evidencias)
   
MATCHED
   ├─→ ASSIGNED (taller aceptó oferta)
   ├─→ NO_OFFERS (no hay talleres disponibles)
   └─→ (fallida timeout sin respuesta → CANCELLED)

ASSIGNED
   ├─→ IN_PROGRESS (taller llegó/inició trabajo)
   └─→ COMPLETED (trabajo terminado y pagado)
```

### Transiciones de Estado

| Estado Anterior | Estado Nuevo | Condición |
|---|---|---|
| PENDING | ANALYZING | Incidente creado, inicia procesamiento IA |
| ANALYZING | MATCHED | AI confidence > 40% y especialidad válida |
| ANALYZING | PENDING_INFO | AI confidence ≤ 40% |
| ANALYZING | ERROR | Excepción en procesamiento de evidencias |
| MATCHED | ASSIGNED | Taller acepta oferta en 30 segundos |
| MATCHED | NO_OFFERS | No hay talleres compatibles en 50km |
| MATCHED | CANCELLED | Timeout 30s sin respuesta del taller |
| ASSIGNED | IN_PROGRESS | Técnico inicia servicio |
| IN_PROGRESS | COMPLETED | Trabajo completado, pago procesado |

---

## 2. Obtención de Ubicación del Cliente

### Flujo de Captura

```json
POST /api/incidents/request-help
{
  "vehicle_id": "uuid",
  "description": "Se pinchó la llanta frontal izquierda",
  "latitude": -17.7833,          // Coordenada del cliente AHORA
  "longitude": -63.1812,         // Coordenada del cliente AHORA
  "evidences": [
    {
      "evidence_type": "image",
      "file_url": "https://bucket/photo.jpg",
      "transcription": null
    }
  ]
}
```

### Campos de Ubicación

- **`incident_lat` / `incident_lng`**: Coordenadas del incidente (donde se sitúa el cliente al reportar)
  - Se capturan en el cliente mobile/web (GPS)
  - Se guardan en la tabla `incidents`
  - Son inmutables después de creación

### Método de Geolocalización

1. **Cliente Frontend** obtiene coordenadas:
   - Geolocation API del navegador (web)
   - GPS nativo (mobile)
   - Fallback a última ubicación conocida

2. **Servidor** recibe y valida:
   ```python
   # En incident_service.py:create_incident_request()
   incident = Incident(
       client_id=client.id,
       vehicle_id=vehicle.id,
       description=data.description,
       incident_lat=data.latitude,      # ← Almacena ubicación
       incident_lng=data.longitude,     # ← Almacena ubicación
       status=IncidentStatus.PENDING,
   )
   ```

3. **Busca talleres** cercanos a estas coordenadas:
   ```python
   # assignment_service.find_and_create_offer()
   workshops = workshop_repository.find_nearby_workshops(
       db,
       latitude=incident.incident_lat,  # ← Usa coordenadas del incidente
       longitude=incident.incident_lng,
       specialty_id=specialty.id,
       radius_km=50.0,
       min_rating=3.5
   )
   ```

---

## 3. Proceso de Búsqueda y Asignación de Talleres

### Algoritmo YANGO Real N=1

El sistema implementa un modelo de **asignación exclusiva** (solo 1 taller recibe oferta):

#### Paso 1: Filtrar talleres candidatos

```
Criterios:
├─ Ubicación: radio máximo 50km del incidente
├─ Especialidad: compatible con categoría IA
├─ Rating: mínimo 3.5 estrellas
├─ Actividad: puntos > 0 (no bloqueado)
├─ Cooldown: no rechazó recientemente
└─ Técnicos: al menos 1 disponible
```

#### Paso 2: Calcular score de cada candidato

**Score Base** (0-1):
```
score_base = distancia*0.4 + rating*0.4 + prioridad*0.2

donde:
  distancia = max(0, 1 - km/50)
  rating = valor_actual / 5.0
  prioridad = {LOW:0.3, MEDIUM:0.5, HIGH:0.8, CRITICAL:1.0}
```

**Penalización por Actividad** (cooldown):
```
penalty = max(0, min(1, (50 - activity_points) / 50))
         = 0 si activity_points ≥ 50
         = 1 si activity_points ≤ 0

score_final = score_base * (1 - penalty)
```

**Cooldown por Rechazo**:
```
Si el taller rechazó hace poco:
├─ no_reason: 1 hora
├─ busy: 2 horas
├─ far_from_zone: 6 horas
├─ no_parts: 30 min
├─ no_technician: 1 hora
└─ timeout: 3 horas
```

#### Paso 3: Seleccionar ganador

```python
# Obtiene taller con score máximo
winner_workshop, winner_distance, winner_score = max(
    scored,
    key=lambda x: x[2]  # score final
)

# Crea oferta exclusiva
offer = WorkshopOffer(
    incident_id=incident.id,
    workshop_id=winner_workshop.id,
    status=OfferStatus.NOTIFIED,
    distance_km=winner_distance,
    ai_score=winner_score,
    expires_at=now + 30 segundos,  # Tiempo para responder
)
```

#### Paso 4: Notificar al taller

```
Taller tiene 30 segundos para:
├─ Aceptar (ACCEPTED)
├─ Rechazar con razón (REJECTED)
└─ Expirar sin responder (TIMEOUT)
```

---

## 4. Cálculo de Distancia: Fórmula de Haversine

```python
def _haversine(lat1, lon1, lat2, lon2) -> float:
    """
    Calcula distancia en km entre dos puntos geográficos.
    
    Parámetros:
      lat1, lon1: Coordenadas del incidente
      lat2, lon2: Coordenadas del taller
    
    Retorna: Distancia en kilómetros
    """
    R = 6371.0  # Radio de la Tierra en km
    
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    
    a = sin²(dlat/2) + cos(lat1) * cos(lat2) * sin²(dlon/2)
    c = 2 * atan2(√a, √(1-a))
    
    return R * c
```

### Ejemplo

```
Incidente:   La Paz (-17.7833, -63.1812)
Taller A:    (-17.8000, -63.1900) → 3.2 km
Taller B:    (-17.7500, -63.1500) → 5.1 km
Taller C:    (-17.6000, -62.9000) → 35.8 km (fuera de 50km?)
```

---

## 5. Diagrama de Secuencia (ASCII)

```
CLIENTE                     SERVIDOR                IA SERVICE              TALLER
   │                           │                          │                    │
   ├─ POST /request-help ─────>│                          │                    │
   │                           │ create_incident()        │                    │
   │                           │ IncidentStatus=PENDING   │                    │
   │ <─ 201 Created ────────────┤                          │                    │
   │ (id, status=ANALYZING)    │                          │                    │
   │                           │ (background task)        │                    │
   │                           ├─ get_evidences() ──────>│                    │
   │                           │<─ analysis results ──────┤                    │
   │                           │                          │                    │
   │                           │ classify_incident()      │                    │
   │                           │<─ category, priority ────┤                    │
   │                           │                          │                    │
   │ (polling GET /incidents   │ if confidence > 0.4:     │                    │
   │  para ver progreso)       │   status = MATCHED       │                    │
   │<──────────────────────────┤                          │                    │
   │ (status: MATCHED)         │   find_nearby_workshops()                     │
   │                           │   ├─ haversine(dist)     │                    │
   │                           │   ├─ calculate_score()   │                    │
   │                           │   └─ select_winner()     │                    │
   │                           │                          │                    │
   │                           │ create_offer(winner)     │                    │
   │                           │ expires_at = now + 30s   │                    │
   │                           │                          │                    │
   │                           ├──────────────────────────────> notify_workshop│
   │                           │    (offer, incident)     │                    │
   │                           │                          │                    │
   │                           │                          │          [TALLER RESPONDE]
   │                           │<──────────────────────────────  accept_offer
   │                           │  (OfferStatus=ACCEPTED)  │                    │
   │                           │                          │                    │
   │ (polling)                 │                          │                    │
   │<──────────────────────────┤                          │                    │
   │ (status: ASSIGNED,        │ incident.status=ASSIGNED │                    │
   │  workshop info)           │ assigned_workshop_id set │                    │
   │                           │                          │                    │
   │  [CLIENTE ESPERA]         │                          │                    │
   │                           │<─────────────────────────────── status_update│
   │                           │  (taller llegando)       │                    │
   │                           │                          │                    │
   │ (polling)                 │                          │                    │
   │<──────────────────────────┤                          │                    │
   │ (status: IN_PROGRESS)     │ incident.status=IN_PROG  │                    │
   │ (eta_arrival)             │ estimated_arrival_min    │                    │
   │                           │                          │                    │
   │  [TALLER TRABAJANDO]      │                          │                    │
   │                           │                          │                    │
   │                           │<─────────────────────────────── status_update│
   │                           │  (trabajo completado)    │                    │
   │                           │                          │                    │
   │ (polling)                 │                          │                    │
   │<──────────────────────────┤                          │                    │
   │ (status: COMPLETED)       │ create_payment()         │                    │
   │ (rating link)             │ incident.status=COMPLETE │                    │
   │                           │                          │                    │
   │ PUT /rate (rating)        │                          │                    │
   ├──────────────────────────>│                          │                    │
   │ <─ 200 OK ─────────────────┤                          │                    │
```

### Notas del Flujo

1. **Creación (síncrono)**: Responde inmediatamente con estado ANALYZING
2. **Procesamiento IA (asíncrono)**: Ejecuta en background task, sin bloquear cliente
3. **Búsqueda de taller (automático)**: Cuando IA termina con confianza > 40%
4. **Notificación (webhook/push)**: Llega a taller en tiempo real
5. **Polling del cliente**: Consulta periódicamente `/api/incidents/{id}` para updates
6. **Rating (post-incidente)**: Cliente califica después de COMPLETED

---

## 6. Ciclo de Rechazo y Reintento

Si taller rechaza o no responde en 30s:

```
MATCHED
   │ (oferta expira o rechaza)
   ├─ log_cooldown(taller, razón)
   ├─ log_status_change(incident, NO_OFFERS)
   │
   └─ Notificar cliente: "Sin talleres disponibles"
      (Puede reenviar solicitud después de cooldown)
```

**Límites de Reintento**:
- Sistema actual: 1 único taller por incidente
- Si rechaza: incidente queda en NO_OFFERS
- Cliente debe solicitar nueva ayuda manualmente

---

## 7. Gestión de Datos

### Tablas Principales

```
incidents
  ├─ id (UUID)
  ├─ client_id → clients
  ├─ vehicle_id → vehicles
  ├─ incident_lat / incident_lng ← UBICACIÓN DEL CLIENTE
  ├─ description
  ├─ status (IncidentStatus enum)
  ├─ ai_category (battery, tire, engine, ...)
  ├─ ai_priority (LOW, MEDIUM, HIGH, CRITICAL)
  ├─ assigned_workshop_id → workshops
  └─ created_at / updated_at

workshop_offers
  ├─ id (UUID)
  ├─ incident_id → incidents
  ├─ workshop_id → workshops
  ├─ status (NOTIFIED, ACCEPTED, REJECTED, TIMEOUT, EXPIRED)
  ├─ distance_km ← Haversine result
  ├─ ai_score ← Puntuación final
  ├─ rejection_reason (si aplica)
  └─ expires_at (30 segundos desde creación)

incident_evidence
  ├─ id (UUID)
  ├─ incident_id → incidents
  ├─ evidence_type (IMAGE, AUDIO, TEXT)
  ├─ file_url
  ├─ transcription (audio→texto)
  └─ ai_analysis (JSON de visión)

incident_status_history
  ├─ id (UUID)
  ├─ incident_id → incidents
  ├─ previous_status
  ├─ new_status
  ├─ changed_by
  ├─ reason
  └─ created_at
```

---

## 8. Manejo de Errores

### Estados de Error

```
ANALYZING → ERROR
  Causas:
  ├─ Excepción en transcripción de audio
  ├─ Excepción en análisis de imagen
  └─ Excepción en clasificación IA

MATCHED → NO_OFFERS
  Causas:
  ├─ Sin especialidad en BD para categoría IA
  ├─ Sin talleres en 50km con specialty
  ├─ Todos los candidatos en cooldown
  ├─ Todos sin técnicos disponibles
  └─ Todos con activity_points ≤ 0 (bloqueados)
```

### Recuperación

- **ERROR**: Cliente recibe notificación, debe reintentar solicitud
- **NO_OFFERS**: Cliente espera/reinicia, puede cambiar ubicación
- **PENDING_INFO**: Sistema pide clarificación (requiere UI)

---

## 9. Configuración y Límites

### Parámetros Ajustables

```python
# assignment_service.py

# Radio de búsqueda geográfica
radius_km = 50.0

# Puntuación mínima de talleres
min_rating = 3.5

# Timeout para respuesta de taller
timeout_seconds = 30

# Punto de confianza IA para proceder
confidence_threshold = 0.4

# Ponderación en scoring
WEIGHTS = {
    "distance": 0.4,
    "rating": 0.4,
    "priority": 0.2,
}

# Cooldowns por tipo de rechazo
COOLDOWN_DURATIONS = {
    "no_reason": 1 hora,
    "busy": 2 horas,
    "far_from_zone": 6 horas,
    "no_parts": 30 minutos,
    "no_technician": 1 hora,
    "timeout_no_response": 3 horas,
}
```

---

## 10. Conclusión

El sistema logra:

✅ **Ubicación automática** del cliente desde GPS/browser  
✅ **Análisis inteligente** de incidentes con IA  
✅ **Búsqueda geográfica** eficiente usando Haversine  
✅ **Scoring inteligente** balanceando distancia, rating y disponibilidad  
✅ **Asignación exclusiva** (1 taller, máxima calidad)  
✅ **Auditoría completa** de cada cambio de estado  
✅ **Recuperación ante fallos** con notificaciones claras  

Punto clave: **La ubicación es inmutable y se usa como punto de referencia para todas las búsquedas geográficas posteriores.**
