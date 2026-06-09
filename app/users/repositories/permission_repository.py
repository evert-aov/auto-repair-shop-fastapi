from sqlalchemy.orm import Session
from app.users.models.permission import Permission


class PermissionRepository:
    db: Session

    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Permission]:
        return self.db.query(Permission).all()

    def get_by_id(self, permission_id: int) -> Permission | None:
        return self.db.query(Permission).filter(Permission.id == permission_id).first()

    def get_by_name(self, name: str) -> Permission | None:
        return self.db.query(Permission).filter(Permission.name == name).first()

    def get_by_action(self, action: str) -> Permission | None:
        return self.db.query(Permission).filter(Permission.action == action).first()

    def save(self, permission: Permission) -> Permission:
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def delete(self, permission: Permission) -> None:
        self.db.delete(permission)
        self.db.commit()
