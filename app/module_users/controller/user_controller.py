from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.module_users.dtos.user_dtos import UserResponseDto, UserCreateDto, UserUpdateDto
from app.module_users.services import user_service
from app.security.config.security import require_role
router = APIRouter(prefix="/api/users", tags=["Users"])

# Solo admin y workshop_owner pueden acceder al CRUD de usuarios
_allowed = Depends(require_role("admin", "workshop_owner"))


@router.post("/", response_model=UserResponseDto, status_code=status.HTTP_201_CREATED, dependencies=[_allowed])
def create_user(user_data: UserCreateDto, db: Session = Depends(get_db)):
    return user_service.create_user(db, user_data)


@router.get("/", response_model=list[UserResponseDto], status_code=status.HTTP_200_OK, dependencies=[_allowed])
def get_all_users(db: Session = Depends(get_db)):
    return user_service.get_all_users(db)


@router.get("/{user_id}", response_model=UserResponseDto, status_code=status.HTTP_200_OK, dependencies=[_allowed])
def get_user_by_id(user_id: UUID, db: Session = Depends(get_db)):
    return user_service.get_user_by_id(db, user_id)


@router.put("/{user_id}", response_model=UserResponseDto, status_code=status.HTTP_200_OK, dependencies=[_allowed])
def update_user(user_id: UUID, user_data: UserUpdateDto, db: Session = Depends(get_db)):
    return user_service.update_user(db, user_id, user_data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_allowed])
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    user_service.delete_user(db, user_id)
