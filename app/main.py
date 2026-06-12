import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from app.audit.middleware.audit_middleware import AuditMiddleware

# Import models to ensure they are registered with SQLAlchemy

from app.users.controller.user_controller import router as users_router
from app.scheduler import start_scheduler, stop_scheduler
from app.security.controller.auth_controller import router as auth_router
from app.users.controller.role_controller import router as role_route
from app.users.controller.permission_controller import router as permission_route
from app.clients.controller.client_controller import router as client_route
from app.clients.controller.vehicle_controller import router as vehicle_route
from app.incidents.controller.incident_controller import router as incidents_router
from app.incidents.controller.offer_controller import router as offers_router
from app.payments.controller.payment_controller import router as payments_router
from app.workshops.controller.workshop_controller import router as workshop_router
from app.workshops.controller.technician_controller import router as technician_router
from app.workshops.controller.specialty_controller import router as specialty_router
from app.notifications.controller.notification_controller import router as notification_router

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    start_scheduler()
    _ensure_specialties()
    from app.audit.database import ensure_audit_table
    ensure_audit_table()
    logger.info("App iniciada con scheduler y auditoria")
    yield
    # Shutdown logic
    stop_scheduler()
    logger.info("App apagada, scheduler detenido")

app = FastAPI(
    title="Plataforma de Auxilio Mecánico",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


def _ensure_specialties():
    from app.database import SessionLocal
    from app.workshops.models import Specialty as SpecialtyModel

    DEFAULT_SPECIALTIES = [
        "general", "battery", "tire", "engine",
        "ac", "transmission", "towing", "locksmith",
    ]
    db = SessionLocal()
    try:
        for name in DEFAULT_SPECIALTIES:
            if not db.query(SpecialtyModel).filter(SpecialtyModel.name == name).first():
                db.add(SpecialtyModel(name=name))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Could not ensure specialties: {e}")
    finally:
        db.close()

# Configurar CORS
origins_raw = os.getenv("ALLOWED_ORIGINS", "")
if origins_raw:
    allowed_origins = [origin.strip() for origin in origins_raw.split(",")]
    allow_all_origins = False
else:
    allowed_origins = ["*"]
    allow_all_origins = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=not allow_all_origins, # No se puede usar credentials con "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(role_route)
app.include_router(permission_route)
app.include_router(client_route)
app.include_router(vehicle_route)
app.include_router(incidents_router)
app.include_router(offers_router)
app.include_router(payments_router)
app.include_router(workshop_router)
app.include_router(technician_router)
app.include_router(specialty_router)
app.include_router(notification_router)

from app.users.controller.dashboard_controller import router as dashboard_router
app.include_router(dashboard_router)

from app.workshops.controller.report_controller import router as reports_router
app.include_router(reports_router)

from app.incidents.ws.location_router import router as location_ws_router
app.include_router(location_ws_router)

from app.incidents.controller.rating_controller import router as ratings_router
app.include_router(ratings_router)

from app.audit.controller.audit_controller import router as audit_router
app.include_router(audit_router)

app.add_middleware(AuditMiddleware)