import random
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app.users.models.user import User
from app.clients.models import Client, Vehicle
from app.workshops.models import Workshop, Technician, Specialty
from app.incidents.models import (
    Incident, IncidentStatus, IncidentPriority,
    WorkshopOffer, OfferStatus, Rating, RejectionReason
)
from app.incidents.models.incident_status_history import IncidentStatusHistory
from app.payments.models import Payment, PaymentStatus, PaymentMethod


# Coordenadas de Santa Cruz de la Sierra, Bolivia
SCZ_CENTER_LAT = -17.783
SCZ_CENTER_LNG = -63.180

CATEGORIES = ["battery", "tire", "engine", "towing", "ac", "general", "transmission", "locksmith"]
PRIORITIES = [IncidentPriority.LOW, IncidentPriority.MEDIUM, IncidentPriority.HIGH, IncidentPriority.CRITICAL]

def generate_random_coords(zone: str) -> tuple[float, float]:
    # Genera coordenadas en Santa Cruz dependiendo de la zona
    lat_offset = random.uniform(0.005, 0.035)
    lng_offset = random.uniform(0.005, 0.035)
    
    if zone == "Norte":
        return SCZ_CENTER_LAT + lat_offset, SCZ_CENTER_LNG + random.uniform(-0.015, 0.015)
    elif zone == "Sur":
        return SCZ_CENTER_LAT - lat_offset, SCZ_CENTER_LNG + random.uniform(-0.015, 0.015)
    elif zone == "Este":
        return SCZ_CENTER_LAT + random.uniform(-0.015, 0.015), SCZ_CENTER_LNG + lng_offset
    elif zone == "Oeste":
        return SCZ_CENTER_LAT + random.uniform(-0.015, 0.015), SCZ_CENTER_LNG - lng_offset
    else: # Centro
        return SCZ_CENTER_LAT + random.uniform(-0.01, 0.01), SCZ_CENTER_LNG + random.uniform(-0.01, 0.01)

def run_kpi_seed():
    db: Session = SessionLocal()
    try:
        # Obtener clientes, vehículos, talleres y técnicos existentes
        clients = db.query(Client).all()
        workshops = db.query(Workshop).filter(Workshop.is_verified.is_(True)).all()
        
        if not clients:
            print("❌ No hay clientes en la base de datos. Ejecuta primero 'python -m app.seed'")
            return
        if not workshops:
            print("❌ No hay talleres verificados en la base de datos. Ejecuta primero 'python -m app.seed'")
            return

        print(f"Seeding KPI data with {len(clients)} clients and {len(workshops)} workshops...")

        # Generar 120 incidentes en los últimos 30 días
        now = datetime.now(timezone.utc)
        
        for i in range(120):
            # 1. Determinar datos aleatorios del incidente
            client = random.choice(clients)
            # Buscar vehículos del cliente o crear uno
            vehicles = db.query(Vehicle).filter(Vehicle.client_id == client.id).all()
            vehicle = random.choice(vehicles) if vehicles else None
            
            category = random.choice(CATEGORIES)
            priority = random.choice(PRIORITIES)
            zone = random.choice(["Centro", "Norte", "Sur", "Este", "Oeste"])
            lat, lng = generate_random_coords(zone)
            
            # Antigüedad aleatoria: entre 0 y 30 días
            days_ago = random.uniform(0, 30)
            created_at = now - timedelta(days=days_ago)
            
            # Status distribution: 70% Completed, 15% Cancelled, 10% No Offers, 5% In Progress
            rand_val = random.random()
            if rand_val < 0.70:
                status = IncidentStatus.COMPLETED
            elif rand_val < 0.85:
                status = IncidentStatus.CANCELLED
            elif rand_val < 0.95:
                status = IncidentStatus.NO_OFFERS
            else:
                status = IncidentStatus.IN_PROGRESS
                
            incident = Incident(
                id=uuid.uuid7(),
                client_id=client.id,
                vehicle_id=vehicle.id if vehicle else None,
                description=f"Auxilio mecánico por falla de {category} en {zone}",
                incident_lat=lat,
                incident_lng=lng,
                status=status,
                ai_category=category,
                ai_priority=priority,
                ai_summary=f"El cliente solicita asistencia inmediata debido a un problema con {category}.",
                ai_confidence=round(random.uniform(0.75, 0.99), 2),
                created_at=created_at,
                updated_at=created_at + timedelta(minutes=random.uniform(30, 90)) if status in [IncidentStatus.COMPLETED, IncidentStatus.CANCELLED] else created_at
            )
            
            db.add(incident)
            db.flush()

            # 2. Historial de estados (SLA)
            # PENDING
            h1 = IncidentStatusHistory(
                incident_id=incident.id,
                previous_status=None,
                new_status=IncidentStatus.PENDING.value,
                reason="Incidente reportado por el cliente",
                created_at=created_at
            )
            db.add(h1)
            
            # ANALYZING (10s después)
            t_analyzing = created_at + timedelta(seconds=10)
            h2 = IncidentStatusHistory(
                incident_id=incident.id,
                previous_status=IncidentStatus.PENDING.value,
                new_status=IncidentStatus.ANALYZING.value,
                reason="IA analizando el incidente",
                created_at=t_analyzing
            )
            db.add(h2)
            
            # MATCHED (30s después)
            t_matched = t_analyzing + timedelta(seconds=20)
            h3 = IncidentStatusHistory(
                incident_id=incident.id,
                previous_status=IncidentStatus.ANALYZING.value,
                new_status=IncidentStatus.MATCHED.value,
                reason="Taller óptimo encontrado por el algoritmo",
                created_at=t_matched
            )
            db.add(h3)
            
            # 3. Flujo según estado final
            if status in [IncidentStatus.COMPLETED, IncidentStatus.IN_PROGRESS]:
                workshop = random.choice(workshops)
                technicians = db.query(Technician).filter(Technician.workshop_id == workshop.id).all()
                technician = random.choice(technicians) if technicians else None
                
                # Tiempo de asignación (entre 30s y 3 min)
                assign_sec = random.uniform(30, 180)
                t_assigned = t_matched + timedelta(seconds=assign_sec)
                
                incident.assigned_workshop_id = workshop.id
                if technician:
                    incident.assigned_technician_id = technician.id
                
                # Tiempo estimado de llegada (ej: 15 minutos)
                est_arrival = random.randint(10, 25)
                incident.estimated_arrival_min = est_arrival
                
                # Registrar ASSIGNED
                h4 = IncidentStatusHistory(
                    incident_id=incident.id,
                    previous_status=IncidentStatus.MATCHED.value,
                    new_status=IncidentStatus.ASSIGNED.value,
                    reason=f"Taller {workshop.name} aceptó el servicio",
                    created_at=t_assigned
                )
                db.add(h4)
                
                # Oferta del Taller
                offer = WorkshopOffer(
                    incident_id=incident.id,
                    workshop_id=workshop.id,
                    status=OfferStatus.ACCEPTED,
                    distance_km=round(random.uniform(1.5, 12.0), 2),
                    ai_score=round(random.uniform(0.65, 0.98), 2),
                    notified_at=t_matched,
                    accepted_at=t_assigned,
                    created_at=t_matched,
                    expires_at=t_matched + timedelta(minutes=3)
                )
                db.add(offer)
                
                # Llegada del técnico: IN_PROGRESS (SLA de llegada)
                # 80% llega a tiempo (dentro del est_arrival), 20% retrasado
                if random.random() < 0.80:
                    arrival_min = random.uniform(5, est_arrival - 1)
                else:
                    arrival_min = random.uniform(est_arrival + 2, est_arrival + 10)
                    
                t_arrival = t_assigned + timedelta(minutes=arrival_min)
                
                h5 = IncidentStatusHistory(
                    incident_id=incident.id,
                    previous_status=IncidentStatus.ASSIGNED.value,
                    new_status=IncidentStatus.IN_PROGRESS.value,
                    reason="Técnico llegó al lugar del incidente",
                    created_at=t_arrival
                )
                db.add(h5)
                
                if status == IncidentStatus.COMPLETED:
                    # Finalización (20 a 45 min después)
                    t_completed = t_arrival + timedelta(minutes=random.uniform(20, 45))
                    h6 = IncidentStatusHistory(
                        incident_id=incident.id,
                        previous_status=IncidentStatus.IN_PROGRESS.value,
                        new_status=IncidentStatus.COMPLETED.value,
                        reason="Servicio concluido exitosamente",
                        created_at=t_completed
                    )
                    db.add(h6)
                    
                    # Pago
                    gross = round(random.uniform(80, 450), 2)
                    comm = round(gross * 0.10, 2)
                    payment = Payment(
                        id=uuid.uuid7(),
                        incident_id=incident.id,
                        client_id=client.id,
                        workshop_id=workshop.id,
                        gross_amount=gross,
                        commission_amount=comm,
                        net_amount=round(gross - comm, 2),
                        currency="BOB",
                        payment_method=random.choice([PaymentMethod.QR, PaymentMethod.CARD, PaymentMethod.CASH]),
                        status=PaymentStatus.COMPLETED,
                        paid_at=t_completed,
                        created_at=t_completed
                    )
                    db.add(payment)
                    incident.total_cost = gross
                    
                    # Rating (calificación)
                    rating = Rating(
                        incident_id=incident.id,
                        client_id=client.id,
                        workshop_id=workshop.id,
                        score=random.choice([4, 5, 5, 5, 3]),  # mayormente altas
                        response_time_score=random.choice([4, 5, 5]),
                        quality_score=random.choice([4, 5, 5, 5]),
                        comment="Excelente atención y servicio rápido.",
                        created_at=t_completed + timedelta(minutes=10)
                    )
                    db.add(rating)
                    
            elif status == IncidentStatus.CANCELLED:
                # Cancelado por el cliente o taller
                workshop = random.choice(workshops)
                
                # Ofertas rechazadas antes del descarte
                offer = WorkshopOffer(
                    incident_id=incident.id,
                    workshop_id=workshop.id,
                    status=OfferStatus.REJECTED,
                    rejection_reason=random.choice([RejectionReason.BUSY.value, RejectionReason.FAR_FROM_ZONE.value]),
                    distance_km=round(random.uniform(5.0, 15.0), 2),
                    ai_score=round(random.uniform(0.40, 0.70), 2),
                    notified_at=t_matched,
                    rejected_at=t_matched + timedelta(seconds=random.uniform(20, 60)),
                    created_at=t_matched,
                    expires_at=t_matched + timedelta(minutes=3)
                )
                db.add(offer)
                
                # CANCELLED
                t_cancelled = t_matched + timedelta(minutes=random.uniform(1, 10))
                h4 = IncidentStatusHistory(
                    incident_id=incident.id,
                    previous_status=IncidentStatus.MATCHED.value,
                    new_status=IncidentStatus.CANCELLED.value,
                    reason="Cancelado por solicitud del cliente",
                    created_at=t_cancelled
                )
                db.add(h4)
                
            elif status == IncidentStatus.NO_OFFERS:
                # Expiración: timeout de ofertas
                workshop = random.choice(workshops)
                offer = WorkshopOffer(
                    incident_id=incident.id,
                    workshop_id=workshop.id,
                    status=OfferStatus.TIMEOUT,
                    rejection_reason=RejectionReason.TIMEOUT_NO_RESPONSE.value,
                    distance_km=round(random.uniform(3.0, 10.0), 2),
                    ai_score=round(random.uniform(0.50, 0.75), 2),
                    notified_at=t_matched,
                    rejected_at=t_matched + timedelta(minutes=3),
                    created_at=t_matched,
                    expires_at=t_matched + timedelta(minutes=3)
                )
                db.add(offer)
                
                # NO_OFFERS
                h4 = IncidentStatusHistory(
                    incident_id=incident.id,
                    previous_status=IncidentStatus.MATCHED.value,
                    new_status=IncidentStatus.NO_OFFERS.value,
                    reason="Ningún taller disponible aceptó la solicitud",
                    created_at=t_matched + timedelta(minutes=3)
                )
                db.add(h4)

        db.commit()
        print("\n🎉 Seeding de KPI con alto volumen completado exitosamente!")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error al sembrar datos de KPI: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_kpi_seed()
