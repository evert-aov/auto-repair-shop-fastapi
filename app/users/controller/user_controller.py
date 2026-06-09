from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.users.dtos.user_dtos import UserResponseDto, UserCreateDto, UserUpdateDto
from app.users.services.user_service import UserService
from app.security.config.security import require_permission

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("/", response_model=UserResponseDto, status_code=status.HTTP_201_CREATED)
def create_user(
        user_data: UserCreateDto,
        db: Session = Depends(get_db),
        _auth=Depends(require_permission("users:create"))
):
    return UserService(db).create_user(user_data)


@router.get("/", response_model=list[UserResponseDto], status_code=status.HTTP_200_OK)
def get_all_users(
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("users:read"))
):
    return UserService(db).get_all_users()


@router.get("/{user_id}", response_model=UserResponseDto, status_code=status.HTTP_200_OK)
def get_user_by_id(
    user_id: UUID,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("users:read"))
):
    return UserService(db).get_user_by_id(user_id)


@router.put("/{user_id}", response_model=UserResponseDto, status_code=status.HTTP_200_OK)
def update_user(
    user_id: UUID,
    user_data: UserUpdateDto,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("users:update"))
):
    return UserService(db).update_user(user_id, user_data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _auth=Depends(require_permission("users:delete"))
):
    UserService(db).delete_user(user_id)
