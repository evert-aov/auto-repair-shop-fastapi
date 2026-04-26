import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.module_incidents.models import Incident, IncidentStatus, Payment, PaymentMethod, PaymentStatus
from app.module_incidents.repositories import incident_repository
from app.module_payments.dtos.payment_dtos import CreateOrderDTO, OrderCreatedDTO, PaymentResponseDTO
from app.module_payments.repositories import payment_repository
from app.module_payments.services import paypal_service
from app.module_workshops.repositories import workshop_repository
from app.security.config.security import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])

_client_only = Depends(require_role("client"))


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
    incident = incident_repository.get_incident_by_id(db, dto.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    if incident.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado para este incidente")

    if incident.status != IncidentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="El incidente aún no está completado")

    if not incident.total_cost or incident.total_cost <= 0:
        raise HTTPException(status_code=400, detail="El taller no ha registrado el costo del servicio")

    existing = payment_repository.get_by_incident(db, dto.incident_id)
    if existing and existing.status == PaymentStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Este incidente ya fue pagado")

    workshop = workshop_repository.get_workshop_by_id(db, incident.assigned_workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    commission_rate = float(workshop.commission_rate or 10) / 100
    gross = float(incident.total_cost)
    commission = round(gross * commission_rate, 2)
    net = round(gross - commission, 2)

    try:
        paypal_result = await paypal_service.create_order(
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
    payment = payment_repository.create_payment(db, payment)

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
    payment = payment_repository.get_by_order_id(db, order_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if payment.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    if payment.status == PaymentStatus.COMPLETED:
        return PaymentResponseDTO.model_validate(payment)

    try:
        capture = await paypal_service.capture_order(order_id)
    except Exception as exc:
        logger.error(f"[PayPal] Error capturando orden {order_id}: {exc}")
        payment.status = PaymentStatus.FAILED
        payment_repository.save_payment(db, payment)
        raise HTTPException(status_code=502, detail=f"Error al capturar el pago: {exc}")

    payment.status = PaymentStatus.COMPLETED
    payment.paid_at = datetime.now(timezone.utc)
    payment.gateway_transaction_id = capture["capture_id"]
    payment_repository.save_payment(db, payment)

    logger.info(f"[Pago] Captura exitosa para incidente {payment.incident_id}: {capture['capture_id']}")

    return PaymentResponseDTO.model_validate(payment)


@router.get(
    "/incident/{incident_id}",
    response_model=PaymentResponseDTO | None,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("client", "workshop_owner", "admin"))],
)
def get_payment_by_incident(
    incident_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene el estado de pago de un incidente."""
    return payment_repository.get_by_incident(db, incident_id)
