"""Celery задачи (фоновые обработки).

Важно
-----
Celery использует отдельный брокер для задач (по умолчанию Redis), а RabbitMQ
используется как event-bus для доменных событий.
"""

from __future__ import annotations

import time

from celery import Celery
from loguru import logger

from app.core.config import get_settings


def make_celery() -> Celery:
    """Создать Celery приложение.

    Returns
    -------
    celery.Celery
        Celery app.
    """

    settings = get_settings()
    celery_app = Celery(
        "order_management",
        broker=settings.effective_celery_broker_url,
        backend=settings.effective_celery_result_backend,
    )
    celery_app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
    )
    return celery_app


celery_app = make_celery()


@celery_app.task(
    name="process_order",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_order(self, order_id: str) -> None:  # noqa: ANN001
    """Фоновая обработка заказа (пример из ТЗ).

    Parameters
    ----------
    order_id : str
        UUID заказа.
    """

    time.sleep(2)
    logger.info("Order processed order_id={id}", id=order_id)
