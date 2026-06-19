import random
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app.users.models.user import User
from app.clients.models import Client, Vehicle
from app.workshops.models import Workshop
from app.incidents.models import (
    Incident, IncidentStatus, IncidentPriority,
    WorkshopOffer, OfferStatus, RejectionReason
)
from app.incidents.models.incident_status_history import IncidentStatusHistory
from app.seed_kpi import generate_random_coords, CATEGORIES, PRIORITIES

def run_extras_seed():
    db: Session = SessionLocal()
    try:
        print("🌱 Iniciando semilla adicional para incidentes no exitosos (cancelados y sin oferta)...")
        
        # Obtener clientes y vehículos existentes
        clients = db.query(Client).all()
        workshops = db.query(Workshop).all()
        
        if not clients:
            print("❌ No hay clientes registrados en la base de datos para asociar. Ejecuta seed_kpi.py primero.")
            return

        # Calcular dinámicamente las confianzas de IA para alcanzar una Tasa de Éxito de exactamente 90%
        # Éxito = Confianza >= 0.7
        total_existentes = db.query(Incident).filter(Incident.ai_category.isnot(None)).count()
        confident_existentes = db.query(Incident).filter(
            Incident.ai_category.isnot(None), Incident.ai_confidence >= 0.7
        ).count()
        
        total_objetivo = total_completed = total_existentes + 70
        confident_objetivo = int(round(0.90 * total_objetivo))
        
        nuevos_confident_necesarios = max(0, confident_objetivo - confident_existentes)
        # Asegurarse de no requerir más de los 70 que vamos a crear
        nuevos_confident_necesarios = min(70, nuevos_confident_necesarios)
        nuevos_no_confident = 70 - nuevos_confident_necesarios
        
        print(f"📊 Estadísticas actuales:")
        print(f"   - Incidentes con IA analizados actualmente: {total_existentes}")
        print(f"   - Incidentes exitosos (confianza >= 0.70): {confident_existentes} ({(confident_existentes/total_existentes*100) if total_existentes > 0 else 0:.1f}%)")
        print(f"   - Incidentes totales objetivos tras siembra: {total_objetivo}")
        print(f"   - Incidentes exitosos objetivos tras siembra: {confident_objetivo}")
        print(f"   - Nuevos incidentes con confianza >= 0.70 necesarios: {nuevos_confident_necesarios}")
        print(f"   - Nuevos incidentes con confianza < 0.70 necesarios: {nuevos_no_confident}")

        # Crear lista de 70 confianzas
        confidences = []
        for _ in range(nuevos_confident_necesarios):
            confidences.append(round(random.uniform(0.70, 0.95), 2))
        for _ in range(nuevos_no_confident):
            confidences.append(round(random.uniform(0.35, 0.68), 2))
        random.shuffle(confidences)

        now = datetime.now(timezone.utc)
        
        # Crear 70 incidentes: 35 cancelados por el cliente, 35 sin ofertas/talleres
        for i in range(70):
            client = random.choice(clients)
            vehicles = db.query(Vehicle).filter(Vehicle.client_id == client.id).all()
            vehicle = random.choice(vehicles) if vehicles else None
            
            category = random.choice(CATEGORIES)
            priority = random.choice(PRIORITIES)
            zone = random.choice(["Centro", "Norte", "Sur", "Este", "Oeste"])
            lat, lng = generate_random_coords(zone)
            
            # Coherent date: must be after client registration
            client_created = client.created_at
            if client_created.tzinfo is None:
                client_created = client_created.replace(tzinfo=timezone.utc)
            
            time_window_seconds = (now - client_created).total_seconds()
            if time_window_seconds > 0:
                created_at = client_created + timedelta(seconds=random.uniform(0, time_window_seconds))
            else:
                created_at = now
            
            # 35 cancelados, 35 sin oferta
            status = IncidentStatus.CANCELLED if i < 35 else IncidentStatus.NO_OFFERS
            
            incident_id = uuid.uuid7()
            ai_confidence = confidences[i]
            
            incident = Incident(
                id=incident_id,
                client_id=client.id,
                vehicle_id=vehicle.id if vehicle else None,
                description=f"Auxilio mecánico por falla de {category} en zona {zone}",
                incident_lat=lat,
                incident_lng=lng,
                status=status,
                ai_category=category,
                ai_priority=priority,
                ai_summary=f"El cliente solicita asistencia debido a un problema con {category}.",
                ai_confidence=ai_confidence,
                created_at=created_at,
                updated_at=created_at + timedelta(minutes=random.uniform(5, 15))
            )
            db.add(incident)
            db.flush()
            
            # Historial base
            t_pending = created_at
            t_analyzing = t_pending + timedelta(seconds=10)
            t_matched = t_analyzing + timedelta(seconds=20)
            
            h1 = IncidentStatusHistory(incident_id=incident_id, previous_status=None, new_status=IncidentStatus.PENDING.value, reason="Incidente reportado", created_at=t_pending)
            h2 = IncidentStatusHistory(incident_id=incident_id, previous_status=IncidentStatus.PENDING.value, new_status=IncidentStatus.ANALYZING.value, reason="IA analizando el incidente", created_at=t_analyzing)
            h3 = IncidentStatusHistory(incident_id=incident_id, previous_status=IncidentStatus.ANALYZING.value, new_status=IncidentStatus.MATCHED.value, reason="Algoritmo buscando talleres", created_at=t_matched)
            db.add(h1)
            db.add(h2)
            db.add(h3)
            
            if status == IncidentStatus.CANCELLED:
                # Cancelado por solicitud del cliente
                t_cancelled = t_matched + timedelta(seconds=random.uniform(30, 300))
                h4 = IncidentStatusHistory(
                    incident_id=incident_id,
                    previous_status=IncidentStatus.MATCHED.value,
                    new_status=IncidentStatus.CANCELLED.value,
                    reason="Cancelado por solicitud del cliente",
                    created_at=t_cancelled
                )
                db.add(h4)
            else:
                # No ofertas (los talleres rechazaron o expiró el tiempo de respuesta)
                t_no_offers = t_matched + timedelta(minutes=3)
                
                # Simular ofertas enviadas a talleres que fueron rechazadas o expiraron
                if workshops:
                    num_offers = random.randint(1, 3)
                    selected_workshops = random.sample(workshops, min(num_offers, len(workshops)))
                    for w in selected_workshops:
                        is_timeout = random.random() < 0.4
                        off_status = OfferStatus.TIMEOUT if is_timeout else OfferStatus.REJECTED
                        rej_reason = RejectionReason.TIMEOUT_NO_RESPONSE if is_timeout else random.choice([
                            RejectionReason.BUSY, RejectionReason.FAR_FROM_ZONE, RejectionReason.NO_TECHNICIAN
                        ])
                        
                        offer = WorkshopOffer(
                            id=uuid.uuid4(),
                            incident_id=incident_id,
                            workshop_id=w.id,
                            status=off_status,
                            rejection_reason=rej_reason.value,
                            distance_km=round(random.uniform(2.0, 12.0), 2),
                            ai_score=round(random.uniform(0.35, 0.78), 2),
                            notified_at=t_matched,
                            rejected_at=t_matched + timedelta(seconds=random.uniform(20, 60)) if not is_timeout else None,
                            created_at=t_matched,
                            expires_at=t_matched + timedelta(minutes=3)
                        )
                        db.add(offer)
                
                h4 = IncidentStatusHistory(
                    incident_id=incident_id,
                    previous_status=IncidentStatus.MATCHED.value,
                    new_status=IncidentStatus.NO_OFFERS.value,
                    reason="Ningún taller disponible aceptó la solicitud en el tiempo límite",
                    created_at=t_no_offers
                )
                db.add(h4)
                
        db.commit()
        
        # Validar tasa final
        final_total = db.query(Incident).filter(Incident.ai_category.isnot(None)).count()
        final_confident = db.query(Incident).filter(
            Incident.ai_category.isnot(None), Incident.ai_confidence >= 0.7
        ).count()
        final_rate = final_confident / final_total * 100 if final_total > 0 else 0.0
        
        print("\n🎉 Siembra de incidentes no exitosos completada!")
        print(f"📊 Estadísticas finales de IA en Base de Datos:")
        print(f"   - Total incidentes analizados: {final_total}")
        print(f"   - Total incidentes exitosos (confianza >= 0.7): {final_confident}")
        print(f"   - Tasa de éxito IA final: {final_rate:.1f}%")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error al sembrar incidentes no exitosos: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_extras_seed()
