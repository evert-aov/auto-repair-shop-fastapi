from pydantic import BaseModel, EmailStr


class LoginRequestDto(BaseModel):
    username: str
    password: str


class ForgotPasswordRequestDto(BaseModel):
    email: EmailStr


class VerifyRecoveryCodeRequestDto(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class SendCodeRequestDto(BaseModel):
    email: EmailStr


class VerifyCodeRequestDto(BaseModel):
    email: EmailStr
    code: str


class SendCodeResponseDto(BaseModel):
    message: str
    code: str | None = None

class PermissionDto(BaseModel):
    id: int
    name: str
    action: str

    class Config:
        from_attributes = True

class RoleDto(BaseModel):
    id: int
    name: str
    permissions: list[PermissionDto] = []

    class Config:
        from_attributes = True

class LoginResponseDto(BaseModel):
    access_token: str
    token_type: str = "bearer"
    redirect_to: str
    user_id: str
    user_name: str
    roles: list[RoleDto]


class ProfileUpdateDto(BaseModel):
    """Actualización del perfil propio. Campos de cliente solo se aplican si el usuario es cliente."""
    name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    password: str | None = None
    # Solo para clientes
    address: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None