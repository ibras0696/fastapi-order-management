"""Схемы для аутентификации."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Схема регистрации пользователя.

    Attributes
    ----------
    email : EmailStr
        Email пользователя.
    password : str
        Пароль (в открытом виде, будет захэширован).
    """

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    """Публичная схема пользователя."""

    id: int
    email: EmailStr


class Token(BaseModel):
    """Ответ на получение токена."""

    access_token: str
    token_type: str = "bearer"
