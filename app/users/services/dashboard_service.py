import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from app.users.repositories.dashboard_repository import DashboardRepository
from app.users.dtos.dashboard_dtos import AdminStats, WorkshopStats, TechnicianStats, ClientStats
from app.users.models.user import User
from app.workshops.models import Workshop
from app.incidents.models import IncidentStatus, Incident, WorkshopOffer, OfferStatus, Rating
from app.incidents.models.incident_status_history import IncidentStatusHistory
from app.payments.models import Payment, PaymentStatus
from app.clients.models import Client


class DashboardService:
    def __init__(self, db: Session):
        self.repo = DashboardRepository(db)

    def _pct_change(self, curr: float, prev: float) -> float:
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        return round((curr - prev) / prev * 100, 1)

    def get_admin_stats(self) -> AdminStats:
        now = datetime.now(timezone.utc)
        total_revenue, platform_profit = self.repo.get_revenue_and_profit()
        active_users = self.repo.get_active_users_count()
        active_workshops = self.repo.get_active_workshops_count()
        
        analyzed, confident = self.repo.get_ai_incident_counts()
        ai_success_rate = round((confident / analyzed * 100) if analyzed > 0 else 0.0, 1)
        incident_distribution = self.repo.get_incident_distribution_by_category()

        # Monthly growth (last 6 months)
        monthly_growth = []
        for i in range(5, -1, -1):
            ref = now - timedelta(days=30 * i)
            year, month = ref.year, ref.month
            label = f"{year}-{month:02d}"
            # Let's count workshops/clients created in that month
            ws_count = self.repo.db.query(Workshop).filter(
                self.repo.db.raw_connection().module.extract("year", Workshop.created_at) == year if hasattr(self.repo.db.raw_connection().module, 'extract') else extract_mock(Workshop.created_at, "year", year, self.repo.db),
                self.repo.db.raw_connection().module.extract("month", Workshop.created_at) == month if hasattr(self.repo.db.raw_connection().module, 'extract') else extract_mock(Workshop.created_at, "month", month, self.repo.db),
            ).count() if False else self._raw_month_counts(year, month)
            monthly_growth.append({"month": label, "workshops": ws_count["workshops"], "clients": ws_count["clients"]})

        pending = self.repo.get_pending_workshops()
        pending_workshops = [
            {
                "id": str(w.id),
                "name": w.name,
                "owner_name": self.repo.get_user_name(w.owner_user_id),
                "city": w.address[:40] if w.address else "",
                "created_at": w.created_at.isoformat(),
            }
            for w in pending
        ]

        # Month-over-month trends
        now_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = now_month_start
        last_month_start = (now_month_start - timedelta(days=1)).replace(day=1)

        revenue_trend_pct = self._pct_change(
            self.repo.get_month_revenue(now_month_start, now),
            self.repo.get_month_revenue(last_month_start, last_month_end)
        )
        profit_trend_pct = self._pct_change(
            self.repo.get_month_profit(now_month_start, now),
            self.repo.get_month_profit(last_month_start, last_month_end)
        )
        users_trend_pct = self._pct_change(
            self.repo.get_month_users(now_month_start, now),
            self.repo.get_month_users(last_month_start, last_month_end)
        )
        
        now_ai = self.repo.get_month_ai_rate(now_month_start, now)
        prev_ai = self.repo.get_month_ai_rate(last_month_start, last_month_end)
        ai_trend_pct = round(now_ai - prev_ai, 1)

        cancelled = self.repo.get_cancelled_incidents()
        cancelled_services = [
            {
                "client_name": self.repo.get_user_name(inc.client_id),
                "workshop_name": self.repo.get_workshop_name(inc.assigned_workshop_id),
                "ai_category": inc.ai_category,
                "created_at": inc.created_at.isoformat(),
            }
            for inc in cancelled
        ]

        # Assignment & Arrival
        avg_assignment_min = round(self.repo.get_avg_assignment_time() / 60.0, 1)
        avg_arrival_min = round(self.repo.get_avg_arrival_time() / 60.0, 1)
        if avg_arrival_min == 0:
            avg_arrival_min = round(self.repo.get_estimated_arrival_time(), 1)

        # Efficient workshops & Incidents zones
        efficient_workshops = self._get_efficient_workshops()
        incidents_by_zone = self._get_incident_zones()

        # New metrics
        total_incidents = self.repo.db.query(func.count(Incident.id)).scalar() or 0
        cancelled_count = self.repo.db.query(func.count(Incident.id)).filter(Incident.status == IncidentStatus.CANCELLED).scalar() or 0
        cancelled_pct = round((cancelled_count / total_incidents * 100.0) if total_incidents > 0 else 0.0, 1)
        on_time_completed_pct = 95.0

        return AdminStats(
            total_revenue=total_revenue,
            platform_profit=platform_profit,
            active_users=active_users,
            active_workshops=active_workshops,
            ai_success_rate=ai_success_rate,
            revenue_trend_pct=revenue_trend_pct,
            profit_trend_pct=profit_trend_pct,
            users_trend_pct=users_trend_pct,
            ai_trend_pct=ai_trend_pct,
            incident_distribution=incident_distribution,
            monthly_growth=monthly_growth,
            pending_workshops=pending_workshops,
            cancelled_services=cancelled_services,
            avg_assignment_min=avg_assignment_min,
            avg_arrival_min=avg_arrival_min,
            efficient_workshops=efficient_workshops,
            incidents_by_zone=incidents_by_zone,
            cancelled_count=cancelled_count,
            cancelled_pct=cancelled_pct,
            on_time_completed_pct=on_time_completed_pct,
        )

    def _raw_month_counts(self, year: int, month: int) -> dict:
        from sqlalchemy import extract
        ws_count = self.repo.db.query(Workshop).filter(
            extract("year", Workshop.created_at) == year,
            extract("month", Workshop.created_at) == month
        ).count()
        from app.clients.models import Client
        cl_count = self.repo.db.query(Client).filter(
            extract("year", Client.created_at) == year,
            extract("month", Client.created_at) == month
        ).count()
        return {"workshops": ws_count, "clients": cl_count}

    def _get_efficient_workshops(self) -> list[dict]:
        from sqlalchemy import func
        from app.workshops.models import Workshop
        from app.incidents.models import Rating, Incident, IncidentStatus
        efficient_rows = self.repo.db.query(Workshop, func.avg(Rating.score))\
            .join(Rating, Rating.workshop_id == Workshop.id)\
            .group_by(Workshop.id)\
            .order_by(func.avg(Rating.score).desc())\
            .limit(10).all()
        
        result = []
        for w, score in efficient_rows:
            completed_services = self.repo.db.query(func.count(Incident.id)).filter(
                Incident.assigned_workshop_id == w.id,
                Incident.status == IncidentStatus.COMPLETED
            ).scalar() or 0
            
            result.append({
                "id": str(w.id),
                "name": w.name,
                "rating_avg": round(float(score or 0.0), 1),
                "activity_points": w.activity_points or 0,
                "completed_services": completed_services,
                "is_active": w.is_active
            })
        return result

    def _get_incident_zones(self) -> list[dict]:
        zone_rows = self.repo.db.query(
            Client.address,
            func.count(Incident.id)
        ).join(Client, Incident.client_id == Client.id)\
         .filter(Client.address.isnot(None))\
         .group_by(Client.address)\
         .order_by(func.count(Incident.id).desc())\
         .limit(10).all()
        return [
            {"zone": row[0] or "General", "incidents_count": row[1]}
            for row in zone_rows
        ]

    def get_workshop_stats(self, owner_user_id: uuid.UUID) -> WorkshopStats:
        workshop = self.repo.get_workshop_by_owner(owner_user_id)
        if not workshop:
            raise HTTPException(status_code=404, detail="Taller no encontrado para este propietario")

        wid = workshop.id
        
        # 1. completed_services
        completed_services = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_workshop_id == wid,
            Incident.status == IncidentStatus.COMPLETED
        ).scalar() or 0
        
        # 2. gross_revenue
        gross_revenue = self.repo.db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0)).filter(
            Payment.workshop_id == wid,
            Payment.status == PaymentStatus.COMPLETED
        ).scalar() or 0.0

        # 3. commission_due
        commission_due = self.repo.db.query(func.coalesce(func.sum(Payment.commission_amount), 0.0)).filter(
            Payment.workshop_id == wid,
            Payment.status == PaymentStatus.COMPLETED
        ).scalar() or 0.0

        # 4. avg_rating
        avg_rating = round(self.repo.get_workshop_avg_rating(wid), 1)

        # 5. avg_response_min
        avg_assign_row = self.repo.db.query(
            func.avg(func.extract('epoch', WorkshopOffer.accepted_at - Incident.created_at))
        ).join(Incident, WorkshopOffer.incident_id == Incident.id)\
         .filter(WorkshopOffer.status == OfferStatus.ACCEPTED, Incident.assigned_workshop_id == wid).first()
        avg_assignment_min = round(float(avg_assign_row[0] or 0.0) / 60.0, 1)
        avg_response_min = avg_assignment_min

        # 6. technician_performance  (campos alineados con el frontend Angular)
        from app.workshops.models import Technician
        from app.incidents.models import Rating
        techs = self.repo.db.query(Technician).filter(Technician.workshop_id == wid).all()
        technician_performance = []
        for t in techs:
            t_completed = self.repo.db.query(func.count(Incident.id)).filter(
                Incident.assigned_technician_id == t.id,
                Incident.status == IncidentStatus.COMPLETED
            ).scalar() or 0
            t_revenue = self.repo.db.query(
                func.coalesce(func.sum(Payment.gross_amount), 0.0)
            ).filter(
                Payment.workshop_id == wid,
                Payment.status == PaymentStatus.COMPLETED,
                Payment.incident_id.in_(
                    self.repo.db.query(Incident.id).filter(
                        Incident.assigned_technician_id == t.id
                    ).subquery()
                )
            ).scalar() or 0.0
            technician_performance.append({
                "id": str(t.id),
                "name": f"{t.name} {t.last_name}",
                "incidents_completed": t_completed,
                "revenue": round(float(t_revenue), 2),
            })

        # 7. daily_revenue  (campo 'day' en lugar de 'date' para el frontend)
        revenue_rows = self.repo.db.query(
            func.date(Payment.created_at).label("date"),
            func.coalesce(func.sum(Payment.gross_amount), 0.0).label("amount")
        ).filter(
            Payment.workshop_id == wid,
            Payment.status == PaymentStatus.COMPLETED
        ).group_by(func.date(Payment.created_at)).all()

        daily_revenue = [
            {"day": str(row.date), "revenue": float(row.amount)}
            for row in revenue_rows
        ]

        # 8. emergency_inbox
        active_incidents = self.repo.db.query(Incident).filter(
            Incident.assigned_workshop_id == wid,
            Incident.status.in_([IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS])
        ).order_by(Incident.created_at.desc()).all()
        
        emergency_inbox = [
            {
                "id": str(inc.id),
                "client_name": self.repo.get_user_name(inc.client_id),
                "ai_category": inc.ai_category,
                "ai_priority": inc.ai_priority.value if inc.ai_priority else "MEDIUM",
                "status": inc.status.value,
                "created_at": inc.created_at.isoformat()
            }
            for inc in active_incidents
        ]

        # 9. technician_locations
        technician_locations = [
            {
                "technician_id": str(t.id),
                "name": f"{t.name} {t.last_name}",
                "lat": float(t.current_latitude) if t.current_latitude else 0.0,
                "lng": float(t.current_longitude) if t.current_longitude else 0.0
            }
            for t in techs if t.current_latitude is not None
        ]

        # 10. avg_arrival_min  (self-join correcto entre dos alias)
        from sqlalchemy import and_
        h_assigned   = aliased(IncidentStatusHistory, name="h_assigned")
        h_in_progress = aliased(IncidentStatusHistory, name="h_in_progress")
        avg_arrival_row = self.repo.db.query(
            func.avg(func.extract('epoch', h_in_progress.created_at - h_assigned.created_at))
        ).select_from(h_assigned)\
         .join(h_in_progress, h_in_progress.incident_id == h_assigned.incident_id)\
         .join(Incident, Incident.id == h_assigned.incident_id)\
         .filter(
            Incident.assigned_workshop_id == wid,
            h_assigned.new_status == 'assigned',
            h_in_progress.new_status == 'in_progress'
        ).first()
        avg_arrival_min = round(float(avg_arrival_row[0] or 0.0) / 60.0, 1)

        if avg_arrival_min == 0:
            est_row = self.repo.db.query(func.avg(Incident.estimated_arrival_min)).filter(
                Incident.assigned_workshop_id == wid,
                Incident.status.in_([IncidentStatus.IN_PROGRESS, IncidentStatus.COMPLETED]),
                Incident.estimated_arrival_min.isnot(None)
            ).first()
            avg_arrival_min = round(float(est_row[0] or 15.0), 1)

        # 11. incident_distribution
        dist_rows = self.repo.db.query(Incident.ai_category, func.count(Incident.id)).filter(
            Incident.assigned_workshop_id == wid,
            Incident.ai_category.isnot(None)
        ).group_by(Incident.ai_category).all()
        incident_distribution = {row[0]: row[1] for row in dist_rows}

        # 12. workshop_rank
        workshop_rank = 1  # default or mock ranking

        # 13. incidents_by_zone
        zone_rows = self.repo.db.query(
            Client.address,
            func.count(Incident.id)
        ).join(Client, Incident.client_id == Client.id)\
         .filter(Incident.assigned_workshop_id == wid, Client.address.isnot(None))\
         .group_by(Client.address)\
         .order_by(func.count(Incident.id).desc())\
         .limit(10).all()
        incidents_by_zone = [
            {"zone": row[0] or "General", "incidents_count": row[1]}
            for row in zone_rows
        ]

        # 14. cancelled_count
        cancelled_count = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_workshop_id == wid,
            Incident.status == IncidentStatus.CANCELLED
        ).scalar() or 0

        # 15. cancelled_pct
        total_workshop_incidents = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_workshop_id == wid
        ).scalar() or 0
        cancelled_pct = round((cancelled_count / total_workshop_incidents * 100.0) if total_workshop_incidents > 0 else 0.0, 1)

        # 16. on_time_completed_pct
        on_time_completed_pct = 95.0

        return WorkshopStats(
            completed_services=completed_services,
            gross_revenue=gross_revenue,
            commission_due=commission_due,
            avg_rating=avg_rating,
            avg_response_min=avg_response_min,
            technician_performance=technician_performance,
            daily_revenue=daily_revenue,
            emergency_inbox=emergency_inbox,
            technician_locations=technician_locations,
            avg_assignment_min=avg_assignment_min,
            avg_arrival_min=avg_arrival_min,
            incident_distribution=incident_distribution,
            workshop_rank=workshop_rank,
            incidents_by_zone=incidents_by_zone,
            cancelled_count=cancelled_count,
            cancelled_pct=cancelled_pct,
            on_time_completed_pct=on_time_completed_pct,
        )

    def get_technician_stats(self, user_id: uuid.UUID) -> TechnicianStats:
        tech = self.repo.get_technician_by_user(user_id)
        if not tech:
            raise HTTPException(status_code=404, detail="Técnico no encontrado")

        tid = tech.id
        
        assigned_count = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == tid,
            Incident.status == IncidentStatus.ASSIGNED
        ).scalar() or 0
        
        in_progress_count = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == tid,
            Incident.status == IncidentStatus.IN_PROGRESS
        ).scalar() or 0
        
        # completed today: status COMPLETED and updated today
        completed_today = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == tid,
            Incident.status == IncidentStatus.COMPLETED,
            func.date(Incident.updated_at) == func.current_date()
        ).scalar() or 0
        
        completed_total = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == tid,
            Incident.status == IncidentStatus.COMPLETED
        ).scalar() or 0

        avg_rating = round(self.repo.get_technician_avg_rating(tid), 1)
        
        total_count = self.repo.db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == tid
        ).scalar() or 0
        productivity = round((completed_total / total_count * 100.0) if total_count > 0 else 100.0, 1)
        
        workshop_name = self.repo.get_workshop_name(tech.workshop_id)
        
        active_rows = self.repo.db.query(Incident).filter(
            Incident.assigned_technician_id == tid,
            Incident.status.in_([IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS])
        ).order_by(Incident.created_at.desc()).all()
        
        active_incidents = []
        for inc in active_rows:
            accepted_offer = self.repo.db.query(WorkshopOffer).filter(
                WorkshopOffer.incident_id == inc.id,
                WorkshopOffer.status == OfferStatus.ACCEPTED
            ).first()
            active_incidents.append({
                "id": str(inc.id),
                "offer_id": str(accepted_offer.id) if accepted_offer else None,
                "client_name": self.repo.get_user_name(inc.client_id),
                "ai_category": inc.ai_category,
                "ai_priority": inc.ai_priority.value if inc.ai_priority else "MEDIUM",
                "status": inc.status.value,
                "created_at": inc.created_at.isoformat(),
                "latitude": float(inc.incident_lat) if inc.incident_lat else None,
                "longitude": float(inc.incident_lng) if inc.incident_lng else None,
            })

        recent_rows = self.repo.db.query(Incident).filter(
            Incident.assigned_technician_id == tid,
            Incident.status == IncidentStatus.COMPLETED
        ).order_by(Incident.updated_at.desc()).limit(5).all()

        recent_completed = []
        for inc in recent_rows:
            rating = self.repo.db.query(Rating.score).filter(Rating.incident_id == inc.id).scalar()
            recent_completed.append({
                "id": str(inc.id),
                "client_name": self.repo.get_user_name(inc.client_id),
                "ai_category": inc.ai_category,
                "amount": inc.total_cost or 0.0,
                "rating_score": rating,
                "completed_at": inc.updated_at.isoformat(),
            })

        return TechnicianStats(
            assigned_count=assigned_count,
            in_progress_count=in_progress_count,
            completed_today=completed_today,
            completed_total=completed_total,
            avg_rating=avg_rating,
            productivity=productivity,
            is_available=tech.is_available,
            workshop_name=workshop_name,
            active_incidents=active_incidents,
            recent_completed=recent_completed,
        )

    def get_client_stats(self, user_id: uuid.UUID) -> ClientStats:
        client = self.repo.get_client_by_user(user_id)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        cid = client.id
        total_spent = self.repo.get_client_total_spent(cid)
        service_count = self.repo.get_client_service_count(cid)
        vehicle_count = self.repo.get_client_vehicle_count(cid)

        # Spending by vehicle
        vehicle_spending = self.repo.get_client_spending_by_vehicle(cid)
        spending_by_vehicle = [
            {
                "vehicle_id": str(vid),
                "make": make,
                "model": model,
                "plate": plate,
                "amount": spent
            }
            for vid, make, model, plate, spent in vehicle_spending
        ]
        spending_by_vehicle.sort(key=lambda x: x["amount"], reverse=True)

        # Spending by category
        cat_spending = self.repo.get_client_spending_by_category(cid)
        spending_by_category = [
            {"category": cat, "amount": spent}
            for cat, spent in cat_spending
        ]
        spending_by_category.sort(key=lambda x: x["amount"], reverse=True)

        # Service history
        history = self.repo.get_client_service_history(cid)
        service_history = []
        for inc in history:
            amount = self.repo.get_incident_gross_payment(inc.id)
            rating = self.repo.get_incident_rating(inc.id, cid)
            service_history.append({
                "id": str(inc.id),
                "created_at": inc.created_at.isoformat(),
                "workshop_name": self.repo.get_workshop_name(inc.assigned_workshop_id),
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
