from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.users.dtos.dashboard_dtos import TechnicianStats, ClientStats, WorkshopStats, AdminStats
from app.users.services.dashboard_service import DashboardService
from app.security.config.security import require_permission

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/admin", response_model=AdminStats)
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("roles:read")),
) -> AdminStats:
    service = DashboardService(db)
    return service.get_admin_stats()


@router.get("/workshop", response_model=WorkshopStats)
def workshop_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("workshops:update")),
) -> WorkshopStats:
    service = DashboardService(db)
    return service.get_workshop_stats(current_user.id)


@router.get("/technician", response_model=TechnicianStats)
def technician_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("technicians:read")),
) -> TechnicianStats:
    service = DashboardService(db)
    return service.get_technician_stats(current_user.id)


@router.get("/client", response_model=ClientStats)
def client_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("vehicles:create")),
) -> ClientStats:
    service = DashboardService(db)
    return service.get_client_stats(current_user.id)
