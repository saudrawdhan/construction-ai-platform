from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.security.roles import Role


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class UserAdminCreate(BaseModel):
    """Payload for an administrator creating a user. ``role`` is validated against the Role enum
    and the password has a minimum length."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: Role
    password: str = Field(min_length=8, max_length=128)


class UserAdminUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: Role | None = None
    is_active: bool | None = None
