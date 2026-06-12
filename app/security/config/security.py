import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db

SECRET_KEY = os.getenv('JWT_SECRET')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    from app.users.repositories.user_repository import UserRepository

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user = UserRepository(db).get_by_username(username)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo")

    _set_user_on_request(user)

    return user


def _set_user_on_request(user) -> None:
    try:
        from app.audit.middleware.audit_middleware import get_current_request
        request = get_current_request()
        if request is not None:
            request.state.current_user = user
    except Exception:
        pass



def require_role(*role_names: str):
    """
    Dependencia reutilizable para proteger endpoints por rol.
    Uso: Depends(require_role("client"))  o  Depends(require_role("workshop_owner", "technician"))
    """
    def checker(current_user=Depends(get_current_user)):
        user_roles = {r.name for r in current_user.roles}
        if not user_roles.intersection(role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Roles requeridos: {list(role_names)}",
            )
        return current_user
    return checker


def require_permission(*permission_actions: str):
    """
    Dependencia reutilizable para proteger endpoints por permisos específicos.
    Uso: Depends(require_permission("user:create")) o Depends(require_permission("incident:read", "incident:write"))
    """
    def checker(current_user=Depends(get_current_user)):
        # Obtener los nombres de acciones de permisos asignados al usuario a través de sus roles
        user_permissions = {p.action for r in current_user.roles for p in r.permissions}
        if not user_permissions.intersection(permission_actions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Permisos requeridos: {list(permission_actions)}",
            )
        return current_user
    return checker
