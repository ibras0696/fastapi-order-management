"""Модель заказа."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class OrderStatus(str, Enum):
    """Статус заказа."""

    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    CANCELED = "CANCELED"


def _default_uuid() -> str:
    """Сгенерировать UUID в строковом виде."""

    return str(uuid4())


class Order(Base):
    """Заказ пользователя.

    Attributes
    ----------
    id : str
        UUID заказа.
    user_id : int
        Идентификатор пользователя-владельца.
    items : list[dict]
        Список товаров (JSON).
    total_price : float
        Итоговая сумма заказа.
    status : str
        Статус заказа.
    created_at : datetime
        Дата создания.
    """

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_default_uuid,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )

    # JSONB для Postgres, JSON для остальных (например, SQLite в тестах).
    items: Mapped[list[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'PENDING'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
