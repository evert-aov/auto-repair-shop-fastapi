from uuid import UUID
from sqlalchemy.orm import Session
from app.clients.models import Client

class ClientRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Client]:
        return self.db.query(Client).all()

    def get_by_id(self, client_id: UUID) -> Client | None:
        return self.db.query(Client).filter(Client.id == client_id).first()

    def save(self, client: Client) -> Client:
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def delete(self, client: Client) -> None:
        self.db.delete(client)
        self.db.commit()
