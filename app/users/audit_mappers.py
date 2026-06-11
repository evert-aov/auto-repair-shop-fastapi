from collections import OrderedDict
from typing import Any

from app.users.models.user import User
from app.users.models.role import Role
from app.users.models.permission import Permission


def user_to_audit_map(entity: User) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(entity.id)
    m["username"] = entity.username
    m["name"] = entity.name
    m["last_name"] = entity.last_name
    m["email"] = entity.email
    m["password"] = entity.password
    m["phone"] = entity.phone
    m["is_active"] = entity.is_active
    m["type"] = entity.type
    m["fcm_token"] = entity.fcm_token
    m["roles"] = [r.name for r in entity.roles] if entity.roles else []
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    m["updated_at"] = entity.updated_at.isoformat() if entity.updated_at else None
    return m


def user_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = str(dto.id) if hasattr(dto, "id") else None
    m["username"] = getattr(dto, "username", None)
    m["name"] = getattr(dto, "name", None)
    m["last_name"] = getattr(dto, "last_name", None)
    m["email"] = getattr(dto, "email", None)
    m["phone"] = getattr(dto, "phone", None)
    m["is_active"] = getattr(dto, "is_active", None)
    m["type"] = getattr(dto, "type", None)
    return m


def role_to_audit_map(entity: Role) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = entity.id
    m["name"] = entity.name
    m["description"] = entity.description
    m["permissions"] = [p.action for p in entity.permissions] if entity.permissions else []
    m["created_at"] = entity.create_at.isoformat() if entity.create_at else None
    m["updated_at"] = entity.updated_at.isoformat() if entity.updated_at else None
    return m


def role_from_dto(dto: Any) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = getattr(dto, "id", None)
    m["name"] = getattr(dto, "name", None)
    m["description"] = getattr(dto, "description", None)
    m["permissions_ids"] = getattr(dto, "permissions_ids", None)
    return m


def permission_to_audit_map(entity: Permission) -> dict[str, Any]:
    m: dict[str, Any] = OrderedDict()
    m["id"] = entity.id
    m["name"] = entity.name
    m["description"] = entity.description
    m["action"] = entity.action
    m["created_at"] = entity.created_at.isoformat() if entity.created_at else None
    return m
