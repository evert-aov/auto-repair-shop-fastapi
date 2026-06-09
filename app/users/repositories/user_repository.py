import uuid
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.users.models.user import User


class UserRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all(self) -> list[User]:
        return self.db.query(User).options(selectinload(User.roles)).all()

    def update(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def exists_by_username(self, username: str) -> bool:
        return self.db.query(User).filter(User.username == username).first() is not None

    def get_by_email(self, email):
        return self.db.query(User).filter(User.email == email).first()
