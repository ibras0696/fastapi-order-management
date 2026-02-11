"""Модель outbox событий для надёжной публикации в event-bus.

Назначение
----------
Outbox позволяет не терять события, когда брокер (RabbitMQ/Kafka) временно недоступен.
Событие записывается в БД в одной транзакции с бизнес-операцией (например,
созданием заказа),
а отдельный publisher процесс доставляет события в брокер с ретраями.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class OutboxStatus(str, Enum):
    """Статус outbox события."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"


class OutboxEvent(Base):
    """Outbox событие.

    Attributes
    ----------
    id : int
        Идентификатор события.
    event_type : str
        Тип события (например, `new_order`).
    aggregate_id : str
        Идентификатор агрегата (например, `order_id`).
    payload : dict
        Полезная нагрузка события (JSON).
    status : str
        Статус публикации.
    attempts : int
        Количество попыток доставки.
    next_attempt_at : datetime
        Когда можно пробовать доставить снова.
    last_error : str | None
        Последняя ошибка доставки.
    created_at : datetime
        Дата создания записи.
    published_at : datetime | None
        Дата успешной публикации.
    """

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'PENDING'"),
        index=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
