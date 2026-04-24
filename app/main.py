import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware

# Import models to ensure they are registered with SQLAlchemy
from app.module_workshops.models import Workshop, Technician, Specialty, WorkshopSpecialty
from app.module_incidents.models import Incident, Rating, WorkshopOffer

from app.module_users.controller.user_controller import router as users_router
from app.scheduler import start_scheduler, stop_scheduler
from app.security.controller.auth_controller import router as auth_router
from app.module_users.controller.role_controller import router as role_route
from app.module_users.controller.permission_controller import router as permission_route
from app.security.controller.client_controller import router as client_route
from app.module_users.controller.vehicle_controller import router as vehicle_route
from app.module_incidents.controller.incident_controller import router as incidents_router
from app.module_incidents.controller.offer_controller import router as offers_router
from app.module_workshops.controller.workshop_controller import router as workshop_router
from app.module_workshops.controller.technician_controller import router as technician_router
from app.module_workshops.controller.specialty_controller import router as specialty_router

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI(
    title="Plataforma de Auxilio Mecánico",
    version="1.0.0",
)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

@app.on_event("startup")
async def startup_event():
    start_scheduler()
    _ensure_specialties()
    logger.info("App iniciada con scheduler")


def _ensure_specialties():
    from app.database import SessionLocal
    from app.module_workshops.models.models import Specialty as SpecialtyModel

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

@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()
    logger.info("App apagada, scheduler detenido")

# Configurar CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
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
app.include_router(workshop_router)
app.include_router(technician_router)
app.include_router(specialty_router)

from app.module_dashboard.dashboard_controller import router as dashboard_router
app.include_router(dashboard_router)