import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.incidents.models import IncidentStatus, Payment, PaymentMethod, PaymentStatus
from app.incidents.repositories.incident_repository import IncidentRepository
from app.incidents.repositories.payment_repository import PaymentRepository
from app.incidents.dtos.payment_dtos import CreateOrderDTO, OrderCreatedDTO, PaymentResponseDTO
from app.incidents.services.paypal_service import PaypalService
from app.workshops.models import Workshop
from app.workshops.repositories.workshop_repository import WorkshopRepository
from app.security.config.security import get_current_user, require_permission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])

_client_only = Depends(require_permission("incidents:create"))


@router.post(
    "/create-order",
    response_model=OrderCreatedDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    dto: CreateOrderDTO,
    current_user=_client_only,
    db: Session = Depends(get_db),
):
    """Cliente: inicia un pago PayPal para un incidente completado."""
    incident = IncidentRepository(db).get_by_id(dto.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    if incident.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado para este incidente")

    if incident.status != IncidentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="El incidente aún no está completado")

    if not incident.total_cost or incident.total_cost <= 0:
        raise HTTPException(status_code=400, detail="El taller no ha registrado el costo del servicio")

    existing = PaymentRepository(db).get_by_incident(dto.incident_id)
    if existing and existing.status == PaymentStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Este incidente ya fue pagado")

    workshop = WorkshopRepository(db).get_by_id(incident.assigned_workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    commission_rate = float(workshop.commission_rate or 10) / 100
    gross = float(incident.total_cost)
    commission = round(gross * commission_rate, 2)
    net = round(gross - commission, 2)

    try:
        paypal_result = await PaypalService.create_order(
            amount_usd=gross,
            incident_id=str(incident.id),
        )
    except Exception as exc:
        logger.error(f"[PayPal] Error creando orden: {exc}")
        raise HTTPException(status_code=502, detail=f"Error al conectar con PayPal: {exc}")

    payment = Payment(
        incident_id=incident.id,
        client_id=current_user.id,
        workshop_id=incident.assigned_workshop_id,
        gross_amount=gross,
        commission_amount=commission,
        net_amount=net,
        currency="USD",
        payment_method=PaymentMethod.PAYPAL,
        status=PaymentStatus.PENDING,
        gateway_transaction_id=paypal_result["order_id"],
    )
    payment = PaymentRepository(db).create(payment)

    logger.info(f"[Pago] Orden PayPal creada para incidente {incident.id}: {paypal_result['order_id']}")

    return OrderCreatedDTO(
        payment_id=payment.id,
        order_id=paypal_result["order_id"],
        approve_url=paypal_result["approve_url"],
        amount=gross,
        currency="USD",
    )


@router.post(
    "/capture/{order_id}",
    response_model=PaymentResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def capture_order(
    order_id: str,
    current_user=_client_only,
    db: Session = Depends(get_db),
):
    """Cliente: captura el pago después de que PayPal lo aprueba."""
    payment_repo = PaymentRepository(db)
    payment = payment_repo.get_by_order_id(order_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if payment.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    if payment.status == PaymentStatus.COMPLETED:
        return PaymentResponseDTO.model_validate(payment)

    try:
        capture = await PaypalService.capture_order(order_id)
    except Exception as exc:
        logger.error(f"[PayPal] Error capturando orden {order_id}: {exc}")
        payment.status = PaymentStatus.FAILED
        payment_repo.save(payment)
        raise HTTPException(status_code=502, detail=f"Error al capturar el pago: {exc}")

    payment.status = PaymentStatus.COMPLETED
    payment.paid_at = datetime.now(timezone.utc)
    payment.gateway_transaction_id = capture["capture_id"]
    payment_repo.save(payment)

    logger.info(f"[Pago] Captura exitosa para incidente {payment.incident_id}: {capture['capture_id']}")

    # Payout automático al taller si tiene email PayPal configurado
    workshop = db.query(Workshop).filter(Workshop.id == payment.workshop_id).first()
    if workshop and workshop.paypal_email:
        try:
            payout = await PaypalService.send_payout(
                workshop_email=workshop.paypal_email,
                net_amount=payment.net_amount,
                currency=payment.currency,
                payment_id=str(payment.id),
                incident_id=str(payment.incident_id),
            )
            payment.payout_id = payout["payout_id"]
            payment.payout_status = payout["payout_status"]
            payment_repo.save(payment)
            logger.info(
                f"[Pago] Payout enviado al taller '{workshop.name}' "
                f"({workshop.paypal_email}): {payout['payout_id']}"
            )
        except Exception as payout_exc:
            payment.payout_status = "FAILED"
            payment_repo.save(payment)
            logger.error(
                f"[Pago] Error enviando payout al taller '{workshop.name}': {payout_exc}"
            )
    else:
        logger.info(
            f"[Pago] Taller '{workshop.name if workshop else payment.workshop_id}' "
            f"sin PayPal configurado — payout omitido"
        )

    return PaymentResponseDTO.model_validate(payment)


@router.get(
    "/incident/{incident_id}",
    response_model=PaymentResponseDTO | None,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("incidents:read"))],
)
def get_payment_by_incident(
    incident_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene el estado de pago de un incidente."""
    return PaymentRepository(db).get_by_incident(incident_id)
