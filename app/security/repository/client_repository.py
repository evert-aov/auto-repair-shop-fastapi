from uuid import UUID

from sqlalchemy.orm import Session

from app.security.models import Client


def get_all_clients(db: Session) -> list[Client]:
    return db.query(Client).all()


def get_client_by_id(db: Session, client_id: UUID) -> Client | None:
    return db.query(Client).filter(Client.id == client_id).first()


def save_client(db: Session, client: Client) -> Client:
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client: Client) -> None:
    db.delete(client)
    db.commit()