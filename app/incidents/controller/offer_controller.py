import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.incidents.dtos.offert_dtos import OfferResponseDto, AcceptOfferDto, RejectOfferDto, CompleteOfferDto
from app.incidents.models import RejectionReason, WorkshopOffer, OfferStatus
from app.incidents.services.offer_service import OfferService
from app.incidents.ai.services import storage_service
from app.users.models import User
from app.security.config.security import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/offers", tags=["Workshop Offers"])


# =====================================================================
# ENDPOINTS
# =====================================================================

@router.post(
    "/{offer_id}/accept",
    response_model=OfferResponseDto,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:update"))],
)
async def accept_offer(
    offer_id: uuid.UUID,
    data: AcceptOfferDto,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    CU12: Taller ACEPTA una oferta
    
    Flujo:
    1. Validar que la offer pertenece al taller del current_user
    2. Marcar offer como "accepted"
    3. Asignar incident al taller
    4. Expirar otras offers
    5. Notificar al cliente
    
    Requiere rol: workshop_owner
    """
    
    offer_service = OfferService(db)
    
    from app.incidents.repositories.offer_repository import OfferRepository
    from app.workshops.repositories.workshop_repository import WorkshopRepository
    
    offer = OfferRepository(db).get_by_id(offer_id)
    
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer {offer_id} not found"
        )
    
    workshop = WorkshopRepository(db).get_by_id(offer.workshop_id)

    if not workshop or workshop.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this workshop"
        )

    # Aceptar la oferta
    try:
        incident = await offer_service.accept_offer(
            offer_id=offer_id,
            technician_id=data.technician_id,
            estimated_arrival_min=data.estimated_arrival_min
        )
        
        return OfferResponseDto(
            offer_id=offer.id,
            incident_id=incident.id,
            workshop_id=workshop.id,
            status="accepted",
            message=f"Oferta aceptada. Cliente notificado. ETA: {incident.estimated_arrival_min} min"
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{offer_id}/reject",
    response_model=OfferResponseDto,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:update"))],
)
async def reject_offer(
    offer_id: uuid.UUID,
    data: RejectOfferDto,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Taller RECHAZA una oferta
    
    Flujo:
    1. Validar que la offer pertenece al taller del current_user
    2. Marcar offer como "rejected"
    3. Aplicar penalización al taller
    4. Buscar siguiente taller en ranking
    5. Notificar al siguiente taller
    
    Requiere rol: workshop_owner
    """
    
    offer_service = OfferService(db)
    
    from app.incidents.repositories.offer_repository import OfferRepository
    from app.workshops.repositories.workshop_repository import WorkshopRepository
    
    offer = OfferRepository(db).get_by_id(offer_id)
    
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer {offer_id} not found"
        )
    
    workshop = WorkshopRepository(db).get_by_id(offer.workshop_id)

    if not workshop or workshop.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this workshop"
        )
    
    # Parsear razón de rechazo
    rejection_reason = None
    if data.rejection_reason:
        try:
            rejection_reason = RejectionReason(data.rejection_reason)
        except ValueError:
            logger.warning(
                f"Invalid rejection_reason: {data.rejection_reason}, usando default"
            )
            rejection_reason = RejectionReason.NO_REASON
    
    # Rechazar la oferta
    try:
        next_offer = await offer_service.reject_offer(
            offer_id=offer_id,
            rejection_reason=rejection_reason
        )
        
        if next_offer:
            return OfferResponseDto(
                offer_id=offer.id,
                incident_id=offer.incident_id,
                workshop_id=workshop.id,
                status="rejected",
                message="Oferta rechazada. Buscando nuevo taller...",
            )
        else:
            return OfferResponseDto(
                offer_id=offer.id,
                incident_id=offer.incident_id,
                workshop_id=workshop.id,
                status="rejected",
                message="Oferta rechazada. No hay más talleres disponibles.",
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/my-offers",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:read"))],
)
async def get_my_offers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtener ofertas pendientes del taller del usuario actual
    
    Retorna solo las offers en estado "notified" (esperando respuesta)
    """
    
    from app.workshops.repositories.workshop_repository import WorkshopRepository

    # Obtener talleres del usuario
    workshops = WorkshopRepository(db).get_workshops_by_owner(current_user.id)
    
    if not workshops:
        return []
    
    workshop_ids = [w.id for w in workshops]
    workshop_dict = {w.id: w for w in workshops}
    
    # Obtener offers pendientes
    offers = db.query(WorkshopOffer).filter(
        WorkshopOffer.workshop_id.in_(workshop_ids),
        WorkshopOffer.status == OfferStatus.NOTIFIED
    ).order_by(WorkshopOffer.created_at.desc()).all()
    
    # Enriquecer con datos de incident
    result = []
    
    from app.incidents.repositories.incident_repository import IncidentRepository
    
    for offer in offers:
        incident = IncidentRepository(db).get_by_id(offer.incident_id)
        workshop = workshop_dict.get(offer.workshop_id)
        
        if incident and workshop:
            result.append({
                "offer_id": offer.id,
                "incident_id": incident.id,
                "workshop_id": offer.workshop_id,
                "status": offer.status.value,
                "distance_km": offer.distance_km,
                "ai_score": offer.ai_score,
                "created_at": offer.created_at,
                "expires_at": offer.expires_at,
                "expires_in_seconds": max(0, int((offer.expires_at - datetime.now(timezone.utc)).total_seconds())) if offer.expires_at else None,
                "incident": {
                    "description": incident.description,
                    "ai_category": incident.ai_category,
                    "ai_priority": incident.ai_priority.value if incident.ai_priority else None,
                    "ai_summary": incident.ai_summary,
                    "vertex_analysis": incident.vertex_analysis,
                    "latitude": incident.incident_lat,
                    "longitude": incident.incident_lng,
                    "evidence_urls": [
                        storage_service.generate_signed_url(e.file_url) 
                        for e in incident.evidences if e.evidence_type.value.lower() == "image"
                    ]
                },
                "workshop": {
                    "latitude": workshop.latitude,
                    "longitude": workshop.longitude,
                }
            })
    
    return result

@router.get(
    "/my-active",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:read"))],
)
async def get_my_active_offers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.workshops.repositories.workshop_repository import WorkshopRepository
    from app.incidents.repositories.offer_repository import OfferRepository
    from app.incidents.repositories.incident_repository import IncidentRepository

    workshops = WorkshopRepository(db).get_workshops_by_owner(current_user.id)
    if not workshops:
        return []

    workshop_ids = [w.id for w in workshops]
    workshop_dict = {w.id: w for w in workshops}

    result = []
    for w_id in workshop_ids:
        active_offers = OfferRepository(db).get_active_offers_by_workshop(w_id)
        for offer in active_offers:
            incident = IncidentRepository(db).get_by_id(offer.incident_id)
            workshop = workshop_dict.get(offer.workshop_id)
            
            if incident and workshop:
                result.append({
                    "offer_id": offer.id,
                    "incident_id": incident.id,
                    "workshop_id": offer.workshop_id,
                    "status": offer.status.value,
                    "distance_km": offer.distance_km,
                    "ai_score": offer.ai_score,
                    "created_at": offer.created_at,
                    "estimated_arrival_min": incident.estimated_arrival_min,
                    "incident": {
                        "description": incident.description,
                        "ai_category": incident.ai_category,
                        "ai_priority": incident.ai_priority.value if incident.ai_priority else None,
                        "ai_summary": incident.ai_summary,
                        "vertex_analysis": incident.vertex_analysis,
                        "latitude": incident.incident_lat,
                        "longitude": incident.incident_lng,
                        "evidence_urls": [
                            storage_service.generate_signed_url(e.file_url) 
                            for e in incident.evidences if e.evidence_type.value.lower() == "image"
                        ]
                    },
                    "workshop": {
                        "latitude": workshop.latitude,
                        "longitude": workshop.longitude,
                    }
                })
    return result

@router.post(
    "/{offer_id}/complete",
    response_model=OfferResponseDto,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:update"))],
)
async def complete_offer(
    offer_id: uuid.UUID,
    data: CompleteOfferDto,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.incidents.repositories.offer_repository import OfferRepository
    from app.workshops.repositories.workshop_repository import WorkshopRepository
    from app.incidents.repositories.incident_repository import IncidentRepository

    offer = OfferRepository(db).get_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    workshop = WorkshopRepository(db).get_by_id(offer.workshop_id)
    if not workshop or workshop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your workshop")
        
    incident = IncidentRepository(db).get_by_id(offer.incident_id)
    if incident:
        from app.incidents.repositories.status_history_repository import StatusHistoryRepository
        from app.incidents.models import IncidentStatus, NotificationType
        
        prev_status = incident.status.value if incident.status else None
        incident.status = IncidentStatus.COMPLETED
        if data.cost is not None:
            incident.total_cost = data.cost
        
        IncidentRepository(db).save(incident)
        
        # [1.2] Liberar al técnico asignado
        if incident.assigned_technician_id:
            from app.workshops.models import Technician
            assigned_tech = db.query(Technician).filter_by(id=incident.assigned_technician_id).first()
            if assigned_tech:
                assigned_tech.is_available = True
                db.commit()
                logger.info(f"🔓 Técnico {assigned_tech.name} liberado y DISPONIBLE nuevamente")
        
        # Bonificación por trabajo bien hecho (+10 pts)
        workshop.activity_points = min(100, (workshop.activity_points or 0) + 10)
        WorkshopRepository(db).save(workshop)
        
        # Log de historial
        StatusHistoryRepository(db).log_status_change(
            incident_id=incident.id,
            previous_status=prev_status,
            new_status=IncidentStatus.COMPLETED.value,
            reason="Servicio completado por el taller"
        )
        
        # Notificación al cliente
        from app.incidents.services.notification_service import NotificationService
        notifier = NotificationService(db)
        await notifier._send_notification(
            user_id=incident.client_id,
            notification_type=NotificationType.SERVICE_COMPLETED,
            title="✅ Servicio finalizado",
            body=f"El taller {workshop.name} ha completado tu servicio. ¡Gracias!",
            incident_id=incident.id,
            priority="high"
        )
        
    return OfferResponseDto(
        offer_id=offer.id,
        incident_id=offer.incident_id,
        workshop_id=workshop.id,
        status="completed",
        message="Servicio completado exitosamente",
    )
