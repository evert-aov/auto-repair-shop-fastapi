import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.module_incidents.models import Notification


def save_notification(db: Session, notification: Notification) -> Notification:
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_unread_by_user(db: Session, user_id: uuid.UUID) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .order_by(Notification.sent_at.desc())
        .all()
    )


def mark_as_read(db: Session, notification_id: uuid.UUID) -> Notification | None:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if notification:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification
