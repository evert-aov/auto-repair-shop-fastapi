from fastapi import Depends, HTTPException, status

from app.security.config.security import get_current_user


def require_admin(current_user=Depends(get_current_user)):
    user_roles = {r.name for r in current_user.roles}
    if "admin" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol ADMIN.",
        )
    return current_user
