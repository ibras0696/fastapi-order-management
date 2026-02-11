"""Сервис outbox событий (создание и обработка ретраев)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxEvent, OutboxStatus


def add_outbox_event(
    db: AsyncSession,
    *,
    event_type: str,
    aggregate_id: str,
    payload: dict,
) -> OutboxEvent:
    """Добавить outbox событие в БД.

    Parameters
    ----------
    db : sqlalchemy.ext.asyncio.AsyncSession
        Async сессия БД.
    event_type : str
        Тип события.
    aggregate_id : str
        Идентификатор агрегата.
    payload : dict
        Полезная нагрузка.

    Returns
    -------
    OutboxEvent
        Созданная запись outbox.
    """

    event = OutboxEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        payload=payload,
        status=OutboxStatus.PENDING.value,
        attempts=0,
        next_attempt_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event


def calculate_next_attempt_at(attempts: int) -> datetime:
    """Посчитать время следующей попытки.

    Backoff
    -------
    Экспоненциальный backoff с верхней границей 60 секунд.
    """

    delay_seconds = min(60, 2**attempts)
    return datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
