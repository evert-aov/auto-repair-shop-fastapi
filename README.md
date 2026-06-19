# ARS Backend — Plataforma de Auxilio Mecánico y Gestión de Talleres en FastAPI

**Sistemas de Información II — Universidad Autónoma Gabriel René Moreno (UAGRM)**

## Entregables

| Recurso | Enlace |
|---|---|
| Documento de Reportes e IA (PDF) | [`docs/ai_reports_implementation.md`](docs/ai_reports_implementation.md) |
| Repositorio público | https://github.com/evert-aov/SI2-ARS-backend |

---

## Información del Proyecto

**ARS Backend** es el motor central de la plataforma empresarial de **Auxilio Mecánico y Gestión de Talleres (Auto Repair Shop)**, desarrollado bajo **FastAPI (Python 3.11+)** y respaldado por una base de datos relacional robusta en **PostgreSQL**.

El sistema está diseñado para coordinar asistencia mecánica en tiempo real y la administración de talleres con capacidades avanzadas:
* **Asistente de IA (Voz y Texto)**: Generador inteligente de reportes dinámicos alimentado por **Gemini 2.5 Flash** y **Google Cloud Speech-to-Text**.
* **Coordinación por Geolocalización**: WebSockets para la transmisión y actualización continua de coordenadas de vehículos de auxilio.
* **Seguimiento Multitenant de Talleres**: Aislamiento lógico para la gestión interna de talleres mecánicos, sus especialidades, técnicos y tarifas.
* **Trazabilidad y Auditoría Completa**: Middleware de auditoría automático que registra de forma detallada toda acción, endpoint consumido y usuario actor.

---

## Arquitectura de Ejecución

```
  Petición HTTP / WS (Cliente) 
         │  
         ▼
  CORSMiddleware / AuditMiddleware ──► Registra acciones del usuario e IPs
         │
         ▼
  AuthToken (Dependencia JWT) ──► Valida y extrae payload (User, Roles, Permisos)
         │
         ├── Endpoints Rest ──► Controladores e Inyección SQL Segura en Postgres
         │
         ├── WebSockets Router ──► Sincronización de localización de auxilio en carretera
         │
         └── AI Engine / Google Cloud SDK
               ├─ FFmpeg / Storage ──► Transcodifica y sube audios
               ├─ Speech-to-Text ──► Convierte voz a texto
               └─ Vertex AI (Gemini) ──► Estructura prompts a consultas seguras
```

---

## Estructura del Proyecto

```
auto-repair-shop-fastapi/
├── app/
│   ├── audit/                      # Middleware y endpoints de auditoría
│   ├── clients/                    # Módulo de clientes y registro de vehículos
│   ├── config/                     # Configuraciones base de la API y Google Cloud SDK
│   ├── incidents/                  # Solicitudes de auxilio mecánico, ofertas y calificaciones
│   │   ├── controller/
│   │   ├── ws/                     # WebSockets para envío de localización en tiempo real
│   │   └── models.py
│   ├── notifications/              # Módulo de alertas y pasarela push (FCM)
│   ├── payments/                   # Procesamiento de pagos de ofertas y servicios
│   ├── security/                   # Módulo de Autenticación, hashing y JWT
│   ├── users/                      # Usuarios del sistema, roles, permisos y dashboard
│   ├── workshops/                  # Gestión de talleres, especialidades, técnicos y reportes
│   │   ├── controller/             # Contiene report_controller.py (endpoints de IA)
│   │   └── services/               # Contiene report_ai_service.py (Gemini y STT)
│   │
│   ├── database.py                 # Conector y pool de SQLAlchemy
│   ├── main.py                     # Punto de entrada FastAPI y middlewares
│   └── scheduler.py                # Tareas en segundo plano (APScheduler)
│
├── alembic/                        # Migraciones de esquema de base de datos
├── docs/
│   └── ai_reports_implementation.md # Explicación de la implementación de reportes IA
├── requirements.txt                # Dependencias del sistema
└── README.md
```

---

## Tecnologías

### Backend & Core
| Tecnología | Versión | Uso |
|---|---|---|
| Python | 3.11+ | Lenguaje de desarrollo principal |
| FastAPI | 0.135.x | Framework de alto rendimiento asíncrono para APIs |
| SQLAlchemy | 2.0.x | ORM y motor de consultas seguro |
| PostgreSQL | 18 | Base de datos relacional para persistencia de datos |
| Alembic | 1.14.x | Control de versiones y migraciones del esquema de BD |

### Inteligencia Artificial e Integraciones
| Tecnología | Versión | Uso |
|---|---|---|
| Gemini 2.5 Flash | Vertex AI | Comprensión y traducción de prompts a formato JSON estructurado |
| Google Cloud STT | — | Transcripción de audios de voz a texto plano |
| Google Cloud Storage | — | Repositorio intermedio para audios FLAC optimizados para transcripción |
| WebSockets | Nativo | Comunicación bidireccional para mapas de auxilio mecánico |
| APScheduler | — | Programador de tareas asíncronas del sistema |

---

## Instalación y Ejecución

### 1. Requisitos Previos
* Python 3.11 o superior.
* Base de datos PostgreSQL en ejecución.
* FFmpeg instalado en la máquina (necesario para la conversión de formatos de audio).
* Archivo de credenciales de Google Cloud configurado localmente.

### 2. Configurar Variables de Entorno
Cree un archivo `.env` en el directorio raíz basándose en el archivo `.env.example`:

```env
PORT=8000
DB_URL=postgresql://postgres:postgres@localhost:5432/auto_repair_db
JWT_SECRET=tu_clave_secreta_super_larga
GOOGLE_APPLICATION_CREDENTIALS_VERTEX=ruta/a/tus/credenciales_gemini.json
GOOGLE_APPLICATION_CREDENTIALS_SPEECH=ruta/a/tus/credenciales_stt.json
GOOGLE_CLOUD_PROJECT=tu_proyecto_gcp
GCS_BUCKET_NAME=tu_bucket_gcs
```

### 3. Compilar e Iniciar la Aplicación

Crear y activar el entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

Instalar las dependencias de Python:
```bash
pip install -r requirements.txt
```

Aplicar las migraciones de la base de datos a PostgreSQL:
```bash
alembic upgrade head
```

Ejecutar el script Seed para poblar datos de prueba:
```bash
python -m app.seed
```

Iniciar el servidor local con recarga automática:
```bash
uvicorn app.main:app --reload
```

La documentación de la API interactiva estará disponible en:
* Swagger UI: `http://localhost:8000/docs`
* Redoc: `http://localhost:8000/redoc`

---

## Endpoints Principales

### Asistente de Reportes e IA
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/reports/prompt` | Recibe un texto libre (prompt) y genera datos estructurados QBE |
| `POST` | `/api/reports/audio` | Sube un audio, lo transcribe mediante STT e interpreta y ejecuta con Gemini |
| `POST` | `/api/reports/run` | Ejecuta de manera directa la consulta parametrizada resultante de la base de datos |

### Auxilio Mecánico y Talleres
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/incidents` | Crea una nueva solicitud de auxilio mecánico con geolocalización |
| `POST` | `/api/offers` | Envío de cotizaciones de mecánicos para incidentes abiertos |
| `POST` | `/api/payments` | Procesa el pago y facturación del servicio |
| `GET` | `/api/workshops` | Lista de talleres mecánicos, especialidades y mecánicos activos |

---

## Módulo de Seguridad y Auditoría

### Middleware de Auditoría
La aplicación implementa `AuditMiddleware.py` que intercepta cada llamada de escritura (`POST`, `PUT`, `DELETE`). Extrae dinámicamente el identificador del usuario actor, la ruta consumida, los parámetros recibidos, la dirección IP de origen y la marca de tiempo, insertándolos de manera asíncrona en la base de datos de auditoría sin penalizar la respuesta HTTP al cliente.

### Inyección de Parámetros y Seguridad SQL
Toda consulta ejecutada por el motor analítico dinámico utiliza estrictamente sentencias preparadas de SQLAlchemy. Los prompts estructurados por la IA se validan contra un catálogo de columnas seguras (`app/workshops/services/report_ai_service.py`), denegando cualquier comando SQL inyectado maliciosamente.

---

## Por qué control de accesos a nivel de atributos y no de endpoints simple

| Tipo de Control | Permite ocultar campos sensibles | Flexibilidad por Rol | Complejidad de API |
|---|---|---|---|
| **Control por Endpoint (`/taller/{id}`)** | No (Retorna todo el objeto o nada) | Baja | Baja |
| **Control a nivel de Atributo (ARS)** | **Sí** (Oculta precios, calificaciones, ingresos) | **Alta** (Granularidad según permisos) | Media (Constructor SQL dinámico) |

---

## Documentación Técnica

- [`docs/ai_reports_implementation.md`](docs/ai_reports_implementation.md) — Análisis arquitectónico del asistente de voz, Speech-to-Text y procesamiento con Gemini 2.5 Flash.

---

## Equipo

| Integrante | Rol |
|---|---|
| **Evert Rodríguez Araúz** | Backend Developer / Arquitecto de Software |
| *[Integrante 2]* | *[Rol]* |
| *[Integrante 3]* | *[Rol]* |

---

*Proyecto desarrollado para la materia de Sistemas de Información II — UAGRM*
