import uuid
from datetime import datetime
from sqlalchemy import func, extract, text
from sqlalchemy.orm import Session, aliased
from app.users.models.user import User
from app.workshops.models import Workshop, Technician
from app.clients.models import Client, Vehicle
from app.incidents.models import Incident, IncidentStatus, WorkshopOffer, OfferStatus, Rating
from app.incidents.models.incident_status_history import IncidentStatusHistory
from app.payments.models import Payment, PaymentStatus


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_revenue_and_profit(self) -> tuple[float, float]:
        rev_row = self.db.query(
            func.coalesce(func.sum(Payment.gross_amount), 0.0),
            func.coalesce(func.sum(Payment.commission_amount), 0.0),
        ).filter(Payment.status == PaymentStatus.COMPLETED).first()
        return float(rev_row[0]), float(rev_row[1])

    def get_active_users_count(self) -> int:
        return self.db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0

    def get_active_workshops_count(self) -> int:
        return self.db.query(func.count(Workshop.id)).filter(
            Workshop.is_active.is_(True), Workshop.is_verified.is_(True)
        ).scalar() or 0

    def get_ai_incident_counts(self) -> tuple[int, int]:
        analyzed = self.db.query(func.count(Incident.id)).filter(Incident.ai_category.isnot(None)).scalar() or 0
        confident = self.db.query(func.count(Incident.id)).filter(
            Incident.ai_category.isnot(None), Incident.ai_confidence >= 0.7
        ).scalar() or 0
        return analyzed, confident

    def get_incident_distribution_by_category(self) -> dict[str, int]:
        dist_rows = self.db.query(Incident.ai_category, func.count(Incident.id)).filter(
            Incident.ai_category.isnot(None)
        ).group_by(Incident.ai_category).all()
        return {row[0]: row[1] for row in dist_rows}

    def get_pending_workshops(self, limit: int = 10) -> list[Workshop]:
        return self.db.query(Workshop).filter(Workshop.is_verified.is_(False)).order_by(
            Workshop.created_at.desc()
        ).limit(limit).all()

    def get_month_revenue(self, start: datetime, end: datetime) -> float:
        row = self.db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0)).filter(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.created_at >= start, Payment.created_at < end,
        ).first()
        return float(row[0])

    def get_month_profit(self, start: datetime, end: datetime) -> float:
        row = self.db.query(func.coalesce(func.sum(Payment.commission_amount), 0.0)).filter(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.created_at >= start, Payment.created_at < end,
        ).first()
        return float(row[0])

    def get_month_users(self, start: datetime, end: datetime) -> int:
        return self.db.query(func.count(User.id)).filter(
            User.created_at >= start, User.created_at < end,
        ).scalar() or 0

    def get_month_ai_rate(self, start: datetime, end: datetime) -> float:
        ana = self.db.query(func.count(Incident.id)).filter(
            Incident.ai_category.isnot(None), Incident.created_at >= start, Incident.created_at < end,
        ).scalar() or 0
        conf = self.db.query(func.count(Incident.id)).filter(
            Incident.ai_category.isnot(None), Incident.ai_confidence >= 0.7,
            Incident.created_at >= start, Incident.created_at < end,
        ).scalar() or 0
        return round((conf / ana * 100) if ana > 0 else 0.0, 1)

    def get_cancelled_incidents(self, limit: int = 10) -> list[Incident]:
        return (
            self.db.query(Incident)
            .filter(Incident.status == IncidentStatus.CANCELLED)
            .order_by(Incident.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_avg_assignment_time(self) -> float:
        avg_assign_row = self.db.query(
            func.avg(func.extract('epoch', WorkshopOffer.accepted_at - Incident.created_at))
        ).join(Incident, WorkshopOffer.incident_id == Incident.id)\
         .filter(WorkshopOffer.status == OfferStatus.ACCEPTED).first()
        return float(avg_assign_row[0] or 0.0)

    def get_avg_arrival_time(self) -> float:
        h_assigned = aliased(IncidentStatusHistory)
        h_in_progress = aliased(IncidentStatusHistory)
        avg_arrival_row = self.db.query(
            func.avg(func.extract('epoch', h_in_progress.created_at - h_assigned.created_at))
        ).filter(
            h_assigned.incident_id == h_in_progress.incident_id,
            h_assigned.new_status == 'assigned',
            h_in_progress.new_status == 'in_progress'
        ).first()
        return float(avg_arrival_row[0] or 0.0)

    def get_estimated_arrival_time(self) -> float:
        est_row = self.db.query(func.avg(Incident.estimated_arrival_min)).filter(
            Incident.status.in_([IncidentStatus.IN_PROGRESS, IncidentStatus.COMPLETED]),
            Incident.estimated_arrival_min.isnot(None)
        ).first()
        return float(est_row[0] or 15.0)

    def get_user_name(self, user_id) -> str:
        if not user_id:
            return "Desconocido"
        u = self.db.query(User.name, User.last_name).filter(User.id == user_id).first()
        return f"{u.name} {u.last_name}" if u else "Desconocido"

    def get_workshop_name(self, workshop_id) -> str:
        if not workshop_id:
            return "Sin taller"
        w = self.db.query(Workshop.name).filter(Workshop.id == workshop_id).first()
        return w.name if w else "Sin taller"

    def get_workshop_by_owner(self, owner_user_id) -> Workshop | None:
        return self.db.query(Workshop).filter(Workshop.owner_user_id == owner_user_id).first()

    def get_workshop_total_revenue(self, workshop_id) -> float:
        row = self.db.query(func.coalesce(func.sum(Payment.net_amount), 0.0)).filter(
            Payment.workshop_id == workshop_id,
            Payment.status == PaymentStatus.COMPLETED
        ).first()
        return float(row[0])

    def get_workshop_incident_counts(self, workshop_id) -> tuple[int, int, int]:
        total = self.db.query(func.count(Incident.id)).filter(Incident.assigned_workshop_id == workshop_id).scalar() or 0
        completed = self.db.query(func.count(Incident.id)).filter(
            Incident.assigned_workshop_id == workshop_id,
            Incident.status == IncidentStatus.COMPLETED
        ).scalar() or 0
        active = self.db.query(func.count(Incident.id)).filter(
            Incident.assigned_workshop_id == workshop_id,
            Incident.status.in_([IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS])
        ).scalar() or 0
        return total, completed, active

    def get_workshop_avg_rating(self, workshop_id) -> float:
        row = self.db.query(func.avg(Rating.score)).filter(Rating.workshop_id == workshop_id).first()
        return float(row[0] or 0.0)

    def get_workshop_ratings_count(self, workshop_id) -> int:
        return self.db.query(func.count(Rating.id)).filter(Rating.workshop_id == workshop_id).scalar() or 0

    def get_workshop_recent_ratings(self, workshop_id, limit=5) -> list[Rating]:
        return self.db.query(Rating).filter(Rating.workshop_id == workshop_id).order_by(
            Rating.created_at.desc()
        ).limit(limit).all()

    def get_workshop_active_technicians_count(self, workshop_id) -> int:
        return self.db.query(func.count(Technician.id)).filter(
            Technician.workshop_id == workshop_id,
            Technician.is_active.is_(True)
        ).scalar() or 0

    def get_workshop_growth(self, workshop_id, year, month) -> tuple[int, float]:
        comp_count = self.db.query(func.count(Incident.id)).filter(
            Incident.assigned_workshop_id == workshop_id,
            Incident.status == IncidentStatus.COMPLETED,
            extract("year", Incident.created_at) == year,
            extract("month", Incident.created_at) == month
        ).scalar() or 0
        rev_row = self.db.query(func.coalesce(func.sum(Payment.net_amount), 0.0)).filter(
            Payment.workshop_id == workshop_id,
            Payment.status == PaymentStatus.COMPLETED,
            extract("year", Payment.created_at) == year,
            extract("month", Payment.created_at) == month
        ).first()
        return comp_count, float(rev_row[0])

    def get_technician_by_user(self, user_id) -> Technician | None:
        # Technician usa joined-table inheritance: Technician.id == User.id (la PK es la misma)
        return self.db.query(Technician).filter(Technician.id == user_id).first()

    def get_technician_incident_counts(self, technician_id) -> tuple[int, int, int]:
        total = self.db.query(func.count(Incident.id)).filter(Incident.assigned_technician_id == technician_id).scalar() or 0
        completed = self.db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == technician_id,
            Incident.status == IncidentStatus.COMPLETED
        ).scalar() or 0
        active = self.db.query(func.count(Incident.id)).filter(
            Incident.assigned_technician_id == technician_id,
            Incident.status.in_([IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS])
        ).scalar() or 0
        return total, completed, active

    def get_technician_avg_rating(self, technician_id) -> float:
        row = self.db.query(func.avg(Rating.score)).join(Incident, Rating.incident_id == Incident.id).filter(
            Incident.assigned_technician_id == technician_id
        ).first()
        return float(row[0] or 0.0)

    def get_technician_assigned_incidents(self, technician_id, limit=10) -> list[Incident]:
        return self.db.query(Incident).filter(
            Incident.assigned_technician_id == technician_id,
            Incident.status.in_([IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS])
        ).order_by(Incident.created_at.desc()).limit(limit).all()

    def get_client_by_user(self, user_id) -> Client | None:
        # Client usa joined-table inheritance: Client.id == User.id (la PK es la misma)
        return self.db.query(Client).filter(Client.id == user_id).first()

    def get_client_total_spent(self, client_id) -> float:
        row = self.db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0)).filter(
            Payment.client_id == client_id,
            Payment.status == PaymentStatus.COMPLETED
        ).first()
        return float(row[0])

    def get_client_service_count(self, client_id) -> int:
        return self.db.query(func.count(Incident.id)).filter(
            Incident.client_id == client_id,
            Incident.status == IncidentStatus.COMPLETED
        ).scalar() or 0

    def get_client_vehicle_count(self, client_id) -> int:
        return self.db.query(func.count(Vehicle.id)).filter(Vehicle.client_id == client_id).scalar() or 0

    def get_client_spending_by_vehicle(self, client_id) -> list[tuple]:
        rows = self.db.query(
            Vehicle.id,
            Vehicle.make,
            Vehicle.model,
            Vehicle.license_plate,
            func.coalesce(func.sum(Payment.gross_amount), 0.0)
        ).join(Incident, Incident.vehicle_id == Vehicle.id)\
         .join(Payment, Payment.incident_id == Incident.id)\
         .filter(Vehicle.client_id == client_id, Payment.status == PaymentStatus.COMPLETED)\
         .group_by(Vehicle.id, Vehicle.make, Vehicle.model, Vehicle.license_plate).all()
        return rows

    def get_client_spending_by_category(self, client_id) -> list[tuple[str, float]]:
        rows = self.db.query(
            Incident.ai_category,
            func.coalesce(func.sum(Payment.gross_amount), 0.0),
        ).join(Payment, Payment.incident_id == Incident.id).filter(
            Payment.client_id == client_id,
            Payment.status == PaymentStatus.COMPLETED,
            Incident.ai_category.isnot(None),
        ).group_by(Incident.ai_category).all()
        return [(r[0], float(r[1])) for r in rows]

    def get_client_service_history(self, client_id, limit=10) -> list[Incident]:
        return (
            self.db.query(Incident)
            .filter(
                Incident.client_id == client_id,
                Incident.status == IncidentStatus.COMPLETED,
            )
            .order_by(Incident.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_incident_gross_payment(self, incident_id) -> float:
        return float(
            self.db.query(func.coalesce(func.sum(Payment.gross_amount), 0.0))
            .filter(
                Payment.incident_id == incident_id,
                Payment.status == PaymentStatus.COMPLETED,
            ).scalar() or 0.0
        )

    def get_incident_rating(self, incident_id, client_id) -> Rating | None:
        return self.db.query(Rating).filter(
            Rating.incident_id == incident_id, Rating.client_id == client_id
        ).first()

    def get_sla_compliance_rate(self, workshop_id: uuid.UUID = None) -> float:
        from sqlalchemy import and_
        h_assigned = aliased(IncidentStatusHistory, name="h_assigned")
        h_in_progress = aliased(IncidentStatusHistory, name="h_in_progress")
        
        query = self.db.query(
            Incident.id,
            Incident.estimated_arrival_min,
            h_assigned.created_at.label("assigned_at"),
            h_in_progress.created_at.label("arrived_at")
        ).join(h_assigned, and_(h_assigned.incident_id == Incident.id, h_assigned.new_status == 'assigned'))\
         .join(h_in_progress, and_(h_in_progress.incident_id == Incident.id, h_in_progress.new_status == 'in_progress'))\
         .filter(Incident.status == IncidentStatus.COMPLETED)
         
        if workshop_id:
            query = query.filter(Incident.assigned_workshop_id == workshop_id)
            
        rows = query.all()
        if not rows:
            return 100.0
            
        on_time_count = 0
        for r in rows:
            est = r.estimated_arrival_min or 15
            actual = (r.arrived_at - r.assigned_at).total_seconds() / 60.0
            if actual <= est:
                on_time_count += 1
                
        return round((on_time_count / len(rows)) * 100.0, 1)

    def get_workshop_rank(self, workshop_id: uuid.UUID) -> int:
        all_workshops = self.db.query(Workshop.id, Workshop.rating_avg, Workshop.total_services)\
            .filter(Workshop.is_verified.is_(True))\
            .order_by(Workshop.rating_avg.desc(), Workshop.total_services.desc())\
            .all()
            
        for index, w in enumerate(all_workshops):
            if w.id == workshop_id:
                return index + 1
        return 1
