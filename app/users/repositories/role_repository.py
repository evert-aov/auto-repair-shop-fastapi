from sqlalchemy.orm import Session
from app.users.models.role import Role


class RoleRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Role]:
        return self.db.query(Role).all()

    def get_by_id(self, role_id: int) -> Role | None:
        return self.db.query(Role).filter(Role.id == role_id).first()

    def get_by_name(self, role_name: str) -> Role | None:
        return self.db.query(Role).filter(Role.name == role_name).first()

    def exists_by_name(self, role_name: str) -> bool:
        return self.db.query(Role).filter(Role.name == role_name).first() is not None

    def save(self, role: Role) -> Role:
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def delete(self, role: Role) -> None:
        self.db.delete(role)
        self.db.commit()