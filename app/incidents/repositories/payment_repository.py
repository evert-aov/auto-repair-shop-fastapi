import uuid
from sqlalchemy.orm import Session
from app.incidents.models import Payment


class PaymentRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def create(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_by_order_id(self, order_id: str) -> Payment | None:
        return self.db.query(Payment).filter(Payment.gateway_transaction_id == order_id).first()

    def get_by_incident(self, incident_id: uuid.UUID) -> Payment | None:
        return (
            self.db.query(Payment)
            .filter(Payment.incident_id == incident_id)
            .order_by(Payment.created_at.desc())
            .first()
        )

    def save(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment
