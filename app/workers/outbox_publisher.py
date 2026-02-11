"""Publisher outbox событий в RabbitMQ.

Поведение
---------
- Читает из БД события со статусом PENDING и `next_attempt_at <= now()`.
- Пытается опубликовать в RabbitMQ.
- При успехе помечает как PUBLISHED.
- При ошибке увеличивает attempts, сохраняет last_error и ставит next_attempt_at
  по backoff.

Важно
-----
Этот процесс должен быть отдельным от web, чтобы падения RabbitMQ не ломали API.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.sql import or_

from app.core.config import get_settings
from app.db.redis import dumps_json
from app.db.session import SessionLocal
from app.messaging.rabbitmq import RabbitMQConfig, publish_json
from app.models.outbox import OutboxEvent, OutboxStatus
from app.services.outbox import calculate_next_attempt_at


def lease_events(db: Session, *, limit: int, lease_seconds: int) -> list[OutboxEvent]:
    """Атомарно “взять в работу” пачку событий.

    Notes
    -----
    Используем `FOR UPDATE SKIP LOCKED`, чтобы несколько publisher'ов не взяли
    одно и то же событие. Для восстановления после падения publisher'а
    допускаем переобработку событий в статусе PROCESSING после истечения lease.
    """

    now = datetime.now(timezone.utc)
    events = (
        db.query(OutboxEvent)
        .filter(
            or_(
                OutboxEvent.status == OutboxStatus.PENDING.value,
                OutboxEvent.status == OutboxStatus.PROCESSING.value,
            )
        )
        .filter(OutboxEvent.next_attempt_at <= now)
        .order_by(OutboxEvent.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )

    lease_until = now.replace(microsecond=0) + timedelta(seconds=lease_seconds)
    for event in events:
        event.status = OutboxStatus.PROCESSING.value
        event.next_attempt_at = lease_until
        db.add(event)
    db.commit()
    return events


def publish_one_event(db: Session, event: OutboxEvent) -> None:
    """Опубликовать одно событие и обновить состояние в БД."""

    settings = get_settings()
    config = RabbitMQConfig(
        amqp_url=settings.rabbitmq_dsn,
        new_order_queue=settings.rabbitmq_new_order_queue,
    )
    try:
        if event.event_type == "new_order":
            body = dumps_json(event.payload).encode("utf-8")
            publish_json(
                config=config,
                routing_key=config.new_order_queue,
                body=body,
            )
        else:
            logger.warning(
                "Unknown outbox event_type={t}, skipping",
                t=event.event_type,
            )
            event.status = OutboxStatus.PUBLISHED.value
            event.published_at = datetime.now(timezone.utc)
            db.add(event)
            db.commit()
            return

        event.status = OutboxStatus.PUBLISHED.value
        event.published_at = datetime.now(timezone.utc)
        event.last_error = None
        db.add(event)
        db.commit()
        logger.info(
            "Outbox published id={id} type={t} aggregate_id={a}",
            id=event.id,
            t=event.event_type,
            a=event.aggregate_id,
        )
    except Exception as exc:  # noqa: BLE001
        event.attempts = int(event.attempts) + 1
        event.next_attempt_at = calculate_next_attempt_at(event.attempts)
        event.last_error = str(exc)
        event.status = OutboxStatus.PENDING.value
        db.add(event)
        db.commit()
        logger.warning(
            "Outbox publish failed id={id} attempts={a}: {err}",
            id=event.id,
            a=event.attempts,
            err=str(exc),
        )


def run_forever() -> None:
    """Запустить publisher в бесконечном цикле."""

    settings = get_settings()
    logger.info(
        "Outbox publisher started poll={p}s batch={b}",
        p=settings.outbox_poll_seconds,
        b=settings.outbox_batch_size,
    )
    while True:
        db = SessionLocal()
        try:
            try:
                events = lease_events(
                    db,
                    limit=settings.outbox_batch_size,
                    lease_seconds=settings.outbox_lease_seconds,
                )
                for event in events:
                    publish_one_event(db, event)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Outbox loop failed: {err}", err=str(exc))
        finally:
            db.close()
        time.sleep(settings.outbox_poll_seconds)


if __name__ == "__main__":
    run_forever()
