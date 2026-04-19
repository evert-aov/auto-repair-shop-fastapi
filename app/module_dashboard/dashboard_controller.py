from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, extract
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.module_incidents.models import (
    Incident, IncidentStatus, Payment, PaymentStatus,
    WorkshopOffer, OfferStatus, Rating,
)
from app.module_workshops.models import Workshop, Technician
from app.module_users.models import User
from app.security.models import Client, Vehicle
from app.security.config.security import require_role

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

_DAYS_ES = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}


# ─── DTOs ─────────────────────────────────────────────────────────────────────

class AdminStats(BaseModel):
    total_revenue: float
    platform_profit: float
    active_users: int
    active_workshops: int
    ai_success_rate: float
    incident_distribution: dict[str, int]
    monthly_growth: list[dict[str, Any]]
    pending_workshops: list[dict[str, Any]]
    cancelled_services: list[dict[str, Any]]


class WorkshopStats(BaseModel):
    completed_services: int
    gross_revenue: float
    commission_due: float
    avg_rating: float
    avg_response_min: float
    technician_performance: list[dict[str, Any]]
    daily_revenue: list[dict[str, Any]]
    emergency_inbox: list[dict[str, Any]]
    technician_locations: list[dict[str, Any]]


class ClientStats(BaseModel):
    total_spent: float
    service_count: int
    vehicle_count: int
    spending_by_vehicle: list[dict[str, Any]]
    spending_by_category: list[dict[str, Any]]
    service_history: list[dict[str, Any]]


# ─── Admin Dashboard ──────────────────────────────────────────────────────────

@router.get("/admin", response_model=AdminStats)
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
) -> AdminStats:
    now = datetime.now(timezone.utc)

    # Revenue & profit
    rev_row = db.query(
        func.coalesce(func.sum(Payment.gross_amount), 0.0),
        func.coalesce(func.sum(Payment.commission_amount), 0.0),
    ).filter(Payment.status == PaymentStatus.COMPLETED).first()
    total_revenue = float(rev_row[0])
    platform_profit = float(rev_row[1])

    # Users & workshops
    active_users = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    active_workshops = db.query(func.count(Workshop.id)).filter(
        Workshop.is_active.is_(True), Workshop.is_verified.is_(True)
    ).scalar() or 0

    # AI success rate: pct of analyzed incidents with confidence >= 0.7
    analyzed = db.query(func.count(Incident.id)).filter(Incident.ai_category.isnot(None)).scalar() or 0
    confident = db.query(func.count(Incident.id)).filter(
        Incident.ai_category.isnot(None), Incident.ai_confidence >= 0.7
    ).scalar() or 0
    ai_success_rate = round((confident / analyzed * 100) if analyzed > 0 else 0.0, 1)

    # Incident distribution by ai_category
    dist_rows = db.query(Incident.ai_category, func.count(Incident.id)).filter(
        Incident.ai_category.isnot(None)
    ).group_by(Incident.ai_category).all()
    incident_distribution = {row[0]: row[1] for row in dist_rows}

    # Monthly growth (last 6 months)
    monthly_growth = []
    for i in range(5, -1, -1):
        ref = now - timedelta(days=30 * i)
        year, month = ref.year, ref.month
        label = f"{year}-{month:02d}"
        ws_count = db.query(func.count(Workshop.id)).filter(
            extract("year", Workshop.created_at) == year,
            extract("month", Workshop.created_at) == month,
        ).scalar() or 0
        cl_count = db.query(func.count(Client.id)).filter(
            extract("year", Client.created_at) == year,
            extract("month", Client.created_at) == month,
        ).scalar() or 0
        monthly_growth.append({"month": label, "workshops": ws_count, "clients": cl_count})

    # Pending workshops (not verified)
    pending_ws = db.query(Workshop).filter(Workshop.is_verified.is_(False)).order_by(
        Workshop.created_at.desc()
    ).limit(10).all()
    pending_workshops = [
        {
            "id": str(w.id),
            "name": w.name,
            "owner_name": _get_user_name(db, w.owner_user_id),
            "city": w.address[:40] if w.address else "",
            "created_at": w.created_at.isoformat(),
        }
        for w in pending_ws
    ]

    # Cancelled services audit
    cancelled_rows = (
        db.query(Incident)
        .filter(Incident.status == IncidentStatus.CANCELLED)
        .order_by(Incident.created_at.desc())
        .limit(10)
        .all()
    )
    cancelled_services = [
        {
            "client_name": _get_client_name(db, inc.client_id),
            "workshop_name": _get_workshop_name(db, inc.assigned_workshop_id),
            "ai_category": inc.ai_category,
            "created_at": inc.created_at.isoformat(),
        }
        for inc in cancelled_rows
    ]

    return AdminStats(
        total_revenue=total_revenue,
        platform_profit=platform_profit,
        active_users=active_users,
        active_workshops=active_workshops,
        ai_success_rate=ai_success_rate,
        incident_distribution=incident_distribution,
        monthly_growth=monthly_growth,
        pending_workshops=pending_workshops,
        cancelled_services=cancelled_services,
    )


# ─── Workshop Dashboard ───────────────────────────────────────────────────────

@router.get("/workshop", response_model=WorkshopStats)
def workshop_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("workshop_owner")),
) -> WorkshopStats:
    workshop = db.query(Workshop).filter(Workshop.owner_user_id == current_user.id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    wid = workshop.id

    # KPIs
    completed_services = db.query(func.count(Incident.id)).filter(
        Incident.assigned_workshop_id == wid,
        Incident.status == IncidentStatus.COMPLETED,
    ).scalar() or 0

    rev_row = db.query(
        func.coalesce(func.sum(Payment.gross_amount), 0.0),
        func.coalesce(func.sum(Payment.commission_amount), 0.0),
    ).filter(Payment.workshop_id == wid).first()
    gross_revenue = float(rev_row[0])
    commission_due = float(rev_row[1])

    avg_rating = float(workshop.rating_avg or 0.0)

    # Avg response time: mean seconds from notified_at to accepted_at for ACCEPTED offers
    offers = db.query(WorkshopOffer).filter(
        WorkshopOffer.workshop_id == wid,
        WorkshopOffer.status == OfferStatus.ACCEPTED,
        WorkshopOffer.notified_at.isnot(None),
        WorkshopOffer.accepted_at.isnot(None),
    ).all()
    if offers:
        deltas = [
            (o.accepted_at - o.notified_at).total_seconds() / 60
            for o in offers
            if o.accepted_at and o.notified_at and o.accepted_at > o.notified_at
        ]
        avg_response_min = round(sum(deltas) / len(deltas), 1) if deltas else 0.0
    else:
        avg_response_min = 0.0

    # Technician performance
    technicians = db.query(Technician).filter(Technician.workshop_id == wid).all()
    tech_perf = []
    for tech in technicians:
        t_completed = db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == tech.id,
            Incident.status == IncidentStatus.COMPLETED,
        ).scalar() or 0
        t_revenue = db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0)).join(
            Incident, Payment.incident_id == Incident.id
        ).filter(Incident.assigned_technician_id == tech.id).scalar() or 0.0
        tech_perf.append({
            "id": str(tech.id),
            "name": f"{tech.name} {tech.last_name[0]}." if tech.last_name else tech.name,
            "incidents_completed": t_completed,
            "revenue": float(t_revenue),
        })
    tech_perf.sort(key=lambda x: x["incidents_completed"], reverse=True)

    # Daily revenue (last 7 days)
    now = datetime.now(timezone.utc)
    daily_revenue = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        amount = db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0)).filter(
            Payment.workshop_id == wid,
            Payment.created_at >= day_start,
            Payment.created_at < day_end,
        ).scalar() or 0.0
        daily_revenue.append({"day": _DAYS_ES[day.weekday()], "revenue": float(amount)})

    # Emergency inbox — pending offers
    inbox_offers = db.query(WorkshopOffer).options(joinedload(WorkshopOffer.incident)).filter(
        WorkshopOffer.workshop_id == wid,
        WorkshopOffer.status == OfferStatus.NOTIFIED,
    ).order_by(WorkshopOffer.created_at.desc()).limit(10).all()
    emergency_inbox = [
        {
            "id": str(o.id),
            "client_name": _get_client_name(db, o.incident.client_id) if o.incident else "",
            "ai_category": o.incident.ai_category if o.incident else None,
            "ai_priority": o.incident.ai_priority.value if o.incident and o.incident.ai_priority else None,
            "incident_lat": float(o.incident.incident_lat) if o.incident and o.incident.incident_lat else None,
            "incident_lng": float(o.incident.incident_lng) if o.incident and o.incident.incident_lng else None,
            "created_at": o.created_at.isoformat(),
        }
        for o in inbox_offers
    ]

    # Technician locations
    technician_locations = [
        {
            "id": str(t.id),
            "name": f"{t.name} {t.last_name[0]}." if t.last_name else t.name,
            "is_available": t.is_available,
            "latitude": float(t.current_latitude) if t.current_latitude else None,
            "longitude": float(t.current_longitude) if t.current_longitude else None,
        }
        for t in technicians
    ]

    return WorkshopStats(
        completed_services=completed_services,
        gross_revenue=gross_revenue,
        commission_due=commission_due,
        avg_rating=avg_rating,
        avg_response_min=avg_response_min,
        technician_performance=tech_perf,
        daily_revenue=daily_revenue,
        emergency_inbox=emergency_inbox,
        technician_locations=technician_locations,
    )


# ─── Client Dashboard ─────────────────────────────────────────────────────────

@router.get("/client", response_model=ClientStats)
def client_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("client")),
) -> ClientStats:
    cid = current_user.id

    total_spent = float(
        db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0))
        .filter(Payment.client_id == cid).scalar() or 0.0
    )
    service_count = db.query(func.count(Incident.id)).filter(Incident.client_id == cid).scalar() or 0

    vehicles = db.query(Vehicle).filter(Vehicle.client_id == cid, Vehicle.is_active.is_(True)).all()
    vehicle_count = len(vehicles)

    # Spending by vehicle
    spending_by_vehicle = []
    for v in vehicles:
        amount = float(
            db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0))
            .join(Incident, Payment.incident_id == Incident.id)
            .filter(Payment.client_id == cid, Incident.vehicle_id == v.id)
            .scalar() or 0.0
        )
        spending_by_vehicle.append({
            "vehicle_id": str(v.id),
            "make": v.make,
            "model": v.model,
            "plate": v.license_plate,
            "amount": amount,
        })
    spending_by_vehicle.sort(key=lambda x: x["amount"], reverse=True)

    # Spending by category
    cat_rows = db.query(
        Incident.ai_category,
        func.coalesce(func.sum(Payment.gross_amount), 0.0),
    ).join(Payment, Payment.incident_id == Incident.id).filter(
        Payment.client_id == cid,
        Incident.ai_category.isnot(None),
    ).group_by(Incident.ai_category).all()
    spending_by_category = [
        {"category": row[0], "amount": float(row[1])} for row in cat_rows
    ]
    spending_by_category.sort(key=lambda x: x["amount"], reverse=True)

    # Service history (last 10 completed)
    history_rows = (
        db.query(Incident)
        .filter(
            Incident.client_id == cid,
            Incident.status == IncidentStatus.COMPLETED,
        )
        .order_by(Incident.created_at.desc())
        .limit(10)
        .all()
    )
    service_history = []
    for inc in history_rows:
        amount = float(
            db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0))
            .filter(Payment.incident_id == inc.id).scalar() or 0.0
        )
        rating = db.query(Rating).filter(
            Rating.incident_id == inc.id, Rating.client_id == cid
        ).first()
        service_history.append({
            "id": str(inc.id),
            "created_at": inc.created_at.isoformat(),
            "workshop_name": _get_workshop_name(db, inc.assigned_workshop_id),
            "ai_category": inc.ai_category,
            "amount": amount,
            "rating_score": rating.score if rating else None,
        })

    return ClientStats(
        total_spent=total_spent,
        service_count=service_count,
        vehicle_count=vehicle_count,
        spending_by_vehicle=spending_by_vehicle,
        spending_by_category=spending_by_category,
        service_history=service_history,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_user_name(db: Session, user_id) -> str:
    if not user_id:
        return "Desconocido"
    u = db.query(User.name, User.last_name).filter(User.id == user_id).first()
    return f"{u.name} {u.last_name}" if u else "Desconocido"


def _get_client_name(db: Session, client_id) -> str:
    return _get_user_name(db, client_id)


def _get_workshop_name(db: Session, workshop_id) -> str:
    if not workshop_id:
        return "Sin taller"
    w = db.query(Workshop.name).filter(Workshop.id == workshop_id).first()
    return w.name if w else "Sin taller"
