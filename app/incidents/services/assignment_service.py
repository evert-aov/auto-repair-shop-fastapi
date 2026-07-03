import logging
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.incidents.models import Incident, WorkshopOffer, IncidentStatus, OfferStatus
from app.incidents.repositories.incident_repository import IncidentRepository
from app.incidents.repositories.offer_repository import OfferRepository
from app.incidents.repositories.status_history_repository import StatusHistoryRepository
from app.workshops.repositories.workshop_repository import WorkshopRepository
from app.workshops.repositories.technician_repository import TechnicianRepository

logger = logging.getLogger(__name__)

_CATEGORY_TO_SPECIALTY: dict[str, str | None] = {
    "battery": "battery",
    "tire": "tire",
    "engine": "engine",
    "ac": "ac",
    "transmission": "transmission",
    "towing": "towing",
    "locksmith": "locksmith",
    "general": "general",
    "collision": "general",  # Mapeado a mecánica general por ahora
    "incierto": None,
    "uncertain": None,
}

_COOLDOWN_DURATIONS: dict[str, timedelta] = {
    "no_reason": timedelta(hours=1),
    "busy": timedelta(hours=2),
    "far_from_zone": timedelta(hours=6),
    "no_parts": timedelta(minutes=30),
    "no_technician": timedelta(hours=1),
    "timeout_no_response": timedelta(hours=3),
}


class AssignmentService:
    db: Session

    def __init__(self, db: Session):
        self.db = db
        self.incident_repository = IncidentRepository(db)
        self.offer_repository = OfferRepository(db)
        self.status_history_repository = StatusHistoryRepository(db)
        self.workshop_repository = WorkshopRepository(db)
        self.technician_repository = TechnicianRepository(db)

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _calculate_ai_score(distance_km: float, workshop_rating: float, incident_priority: str) -> float:
        distance_score = max(0.0, 1.0 - distance_km / 50.0)
        rating_score = workshop_rating / 5.0
        priority_weights = {"LOW": 0.3, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}
        priority_weight = priority_weights.get(incident_priority, 0.5)
        return round(distance_score * 0.4 + rating_score * 0.4 + priority_weight * 0.2, 3)

    @staticmethod
    def _calculate_activity_penalty(activity_points: int) -> float:
        """
        Returns penalty fraction (0.0 = no penalty, 1.0 = fully blocked).
        - >= 50 pts: 0% penalty (normal)
        - 0 pts: 100% penalty (blocked)
        - Linear below 50
        """
        if activity_points <= 0:
            return 1.0
        if activity_points >= 50:
            return 0.0
        return (50 - activity_points) / 50.0

    def _is_in_cooldown(self, workshop_id: uuid.UUID) -> bool:
        last_rejection = (
            self.db.query(WorkshopOffer)
            .filter(
                WorkshopOffer.workshop_id == workshop_id,
                WorkshopOffer.status.in_([OfferStatus.REJECTED, OfferStatus.TIMEOUT]),
                WorkshopOffer.rejected_at.isnot(None),
            )
            .order_by(WorkshopOffer.rejected_at.desc())
            .first()
        )

        if not last_rejection:
            return False

        reason = last_rejection.rejection_reason or "no_reason"
        duration = _COOLDOWN_DURATIONS.get(reason, timedelta(hours=1))
        expires_at = last_rejection.rejected_at + duration

        if datetime.now(timezone.utc) >= expires_at:
            return False

        # Si el taller aceptó exitosamente una oferta DESPUÉS del último rechazo,
        # el cooldown se cancela (el taller demostró disponibilidad)
        last_accepted = (
            self.db.query(WorkshopOffer)
            .filter(
                WorkshopOffer.workshop_id == workshop_id,
                WorkshopOffer.status == OfferStatus.ACCEPTED,
                WorkshopOffer.accepted_at.isnot(None),
                WorkshopOffer.accepted_at > last_rejection.rejected_at,
            )
            .first()
        )
        if last_accepted:
            return False

        return True

    async def find_and_create_offer(self, incident: Incident) -> WorkshopOffer | None:
        """
        YANGO REAL N=1: find the best workshop, create a single exclusive offer.
        Returns the created offer, or None if no candidates found.
        """
        from app.notifications.services.notification_service import NotificationService

        # Support multiple categories separated by comma
        categories = [c.strip() for c in (incident.ai_category or "").split(",") if c.strip()]
        if not categories:
            logger.warning(f"No categories found for incident {incident.id}")
            await self._mark_no_offers(incident)
            return None

        specialties = []
        specialty_names = []
        for cat in categories:
            s_name = _CATEGORY_TO_SPECIALTY.get(cat)
            if not s_name:
                logger.warning(f"No specialty mapping for ai_category={cat!r}")
                continue
            spec = self.workshop_repository.get_specialty_by_name(s_name)
            if not spec:
                logger.warning(f"Specialty '{s_name}' not in database")
                continue
            specialties.append(spec)
            specialty_names.append(s_name)

        if not specialties:
            logger.warning(f"No valid specialties found in database for categories {categories}")
            await self._mark_no_offers(incident)
            return None

        specialty_names_str = ", ".join(specialty_names)

        from sqlalchemy.orm import selectinload
        from app.workshops.models import Workshop

        all_workshops = (
            self.db.query(Workshop)
            .options(selectinload(Workshop.workshop_specialties))
            .all()
        )

        logger.warning(f"🔎 Iniciando evaluación de talleres para el incidente {incident.id} (Especialidades requeridas: '{specialty_names_str}'). Total registrados: {len(all_workshops)}")

        scored: list[tuple] = []
        for workshop in all_workshops:
            # 1. Filtro de Especialidad (El taller debe cubrir al menos una de las especialidades requeridas)
            workshop_specialty_ids = {ws.specialty_id for ws in workshop.workshop_specialties}
            required_specialty_ids = {sp.id for sp in specialties}
            has_specialty = bool(workshop_specialty_ids & required_specialty_ids)
            if not has_specialty:
                logger.warning(f"❌ Taller {workshop.name} descartado: No cubre ninguna de las especialidades requeridas '{specialty_names_str}'")
                continue

            # 2. Filtro de Activo
            if not workshop.is_active:
                logger.warning(f"❌ Taller {workshop.name} descartado: No está activo")
                continue

            # 3. Filtro de Verificado
            if not workshop.is_verified:
                logger.warning(f"❌ Taller {workshop.name} descartado: No está verificado")
                continue

            # 4. Filtro de Calificación Mínima
            rating_val = float(workshop.rating_avg)
            if rating_val < 1.0 and rating_val != 0.0:
                logger.warning(f"❌ Taller {workshop.name} descartado: Calificación promedio {rating_val} menor al mínimo de 1.0")
                continue

            # 5. Filtro de Rango Geográfico (Distancia <= 50.0 km)
            distance_km = self._haversine(
                incident.incident_lat,
                incident.incident_lng,
                float(workshop.latitude or 0),
                float(workshop.longitude or 0),
            )
            if distance_km > 50.0:
                logger.warning(f"❌ Taller {workshop.name} descartado: Distancia de {distance_km:.2f}km supera el límite de 50.0km")
                continue

            # 6. Filtro de Puntos de Actividad
            pts = workshop.activity_points if workshop.activity_points is not None else 50
            if pts <= 0:
                logger.warning(f"❌ Taller {workshop.name} descartado: Puntos de actividad insuficientes ({pts})")
                continue

            # 7. Filtro de Cooldown
            if self._is_in_cooldown(workshop.id):
                logger.warning(f"❌ Taller {workshop.name} descartado: Está en período de enfriamiento (cooldown)")
                continue

            # 8. Filtro de Técnicos Disponibles
            technician = self.technician_repository.get_available_technician(workshop.id)
            if not technician:
                logger.warning(f"❌ Taller {workshop.name} descartado: No tiene técnicos disponibles")
                continue

            # Si pasa todos los filtros, es APTO
            logger.warning(
                f"✅ Taller {workshop.name} APTO. "
                f"Especialidades: '{specialty_names_str}' | "
                f"Distancia: {distance_km:.2f}km | "
                f"Calificación: {rating_val:.2f} | "
                f"Puntos de actividad: {pts} | "
                f"Técnico disponible: {technician.name}"
            )

            priority_value = incident.ai_priority.value if incident.ai_priority else "MEDIUM"
            base_score = self._calculate_ai_score(distance_km, rating_val, priority_value)
            penalty = self._calculate_activity_penalty(pts)
            final_score = round(base_score * (1.0 - penalty), 3)
            scored.append((workshop, distance_km, final_score))

        if not scored:
            logger.warning(f"⚠️ No quedó ningún taller apto después de los filtros para el incidente {incident.id}")
            await self._mark_no_offers(incident)
            return None

        winner_workshop, winner_distance, winner_score = max(scored, key=lambda x: x[2])

        offer = WorkshopOffer(
            incident_id=incident.id,
            workshop_id=winner_workshop.id,
            status=OfferStatus.NOTIFIED,
            distance_km=winner_distance,
            ai_score=winner_score,
            notified_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
            timeout_minutes=3,
        )
        self.offer_repository.save(offer)

        incident.estimated_arrival_min = int(winner_distance * 1.2)
        incident.status = IncidentStatus.MATCHED
        self.incident_repository.save(incident)

        logger.info(
            f"[ASIGNACIÓN] Incidente {incident.id} → Taller '{winner_workshop.name}' (id={winner_workshop.id}) | "
            f"distancia={winner_distance:.1f}km score={winner_score:.3f} puntos_actividad={winner_workshop.activity_points}"
        )

        notification_service = NotificationService(self.db)
        await notification_service.notify_workshop_new_offer(
            workshop=winner_workshop,
            incident=incident,
            offer=offer,
        )

        return offer

    async def _mark_no_offers(self, incident: Incident) -> None:
        from app.notifications.services.notification_service import NotificationService

        prev = incident.status.value if incident.status else None
        incident.status = IncidentStatus.NO_OFFERS
        self.incident_repository.save(incident)

        self.status_history_repository.log_status_change(
            incident_id=incident.id,
            previous_status=prev,
            new_status=IncidentStatus.NO_OFFERS.value,
            reason="No compatible workshops found",
        )

        notification_service = NotificationService(self.db)
        await notification_service.notify_client_no_workshops(incident)
