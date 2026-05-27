import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.incidents.dtos.notification_dtos import NotificationDto
from app.incidents.models import Notification
from app.incidents.repositories.notification_repository import NotificationRepository
from app.users.models import User
from app.security.config.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=List[NotificationDto])
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50
):
    """
    Obtiene el historial de notificaciones del usuario actual.
    """
    notifications = NotificationRepository(db).get_all_by_user(current_user.id, limit=limit)
    
    result = []
    from app.incidents.models import Payment, PaymentStatus
    for n in notifications:
        pay_status = "pending"
        if n.incident_id:
            payment = db.query(Payment).filter(
                Payment.incident_id == n.incident_id, 
                Payment.status == PaymentStatus.COMPLETED
            ).first()
            if payment:
                pay_status = "completed"
        
        n_dict = {
            "id": n.id,
            "user_id": n.user_id,
            "incident_id": n.incident_id,
            "type": n.type.value,
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "sent_at": n.sent_at,
            "read_at": n.read_at,
            "payment_status": pay_status
        }
        result.append(n_dict)
    return result

@router.patch("/{notification_id}/read", response_model=NotificationDto)
def mark_notification_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marca una notificación específica como leída.
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or not owned by user"
        )

    return NotificationRepository(db).mark_as_read(notification_id)

@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el conteo de notificaciones no leídas.
    """
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    return {"unread_count": count}
