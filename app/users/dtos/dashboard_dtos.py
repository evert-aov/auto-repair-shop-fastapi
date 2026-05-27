from pydantic import BaseModel
from typing import Any

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
    revenue_trend_pct: float
    profit_trend_pct: float
    users_trend_pct: float
    ai_trend_pct: float


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


class TechnicianStats(BaseModel):
    assigned_count: int
    in_progress_count: int
    completed_today: int
    completed_total: int
    avg_rating: float
    productivity: float
    is_available: bool
    workshop_name: str
    active_incidents: list[dict[str, Any]]
    recent_completed: list[dict[str, Any]]