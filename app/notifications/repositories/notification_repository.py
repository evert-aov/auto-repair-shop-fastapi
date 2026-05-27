import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.notifications.models import Notification


class NotificationRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def save(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_unread_by_user(self, user_id: uuid.UUID) -> list[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .order_by(Notification.sent_at.desc())
            .all()
        )

    def get_all_by_user(self, user_id: uuid.UUID, limit: int = 50) -> list[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.sent_at.desc())
            .limit(limit)
            .all()
        )

    def mark_as_read(self, notification_id: uuid.UUID) -> Notification | None:
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(notification)
        return notification
