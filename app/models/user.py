"""Модель пользователя."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """Пользователь системы.

    Attributes
    ----------
    id : int
        Идентификатор пользователя.
    email : str
        Email (уникальный).
    hashed_password : str
        Хэш пароля.
    created_at : datetime
        Дата создания.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
