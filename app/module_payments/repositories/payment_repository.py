import uuid
from sqlalchemy.orm import Session
from app.module_incidents.models import Payment


def create_payment(db: Session, payment: Payment) -> Payment:
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def get_by_id(db: Session, payment_id: uuid.UUID) -> Payment | None:
    return db.query(Payment).filter(Payment.id == payment_id).first()


def get_by_order_id(db: Session, order_id: str) -> Payment | None:
    return db.query(Payment).filter(Payment.gateway_transaction_id == order_id).first()


def get_by_incident(db: Session, incident_id: uuid.UUID) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.incident_id == incident_id)
        .order_by(Payment.created_at.desc())
        .first()
    )


def save_payment(db: Session, payment: Payment) -> Payment:
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment
