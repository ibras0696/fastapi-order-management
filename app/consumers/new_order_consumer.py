"""Консюмер события `new_order` из RabbitMQ.

Поведение
---------
- Читает сообщения из очереди `new_order`.
- Запускает фоновую задачу Celery `process_order`.
- Ack только после успешного запуска задачи.
"""

from __future__ import annotations

import time

from loguru import logger
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

from app.core.config import get_settings
from app.db.redis import loads_json
from app.messaging.rabbitmq import RabbitMQConfig, consume
from app.tasks import process_order


def _get_retry_count(props: BasicProperties) -> int:
    headers = getattr(props, "headers", None) or {}
    try:
        return int(headers.get("x-retry-count", 0))
    except Exception:  # noqa: BLE001
        return 0


def _publish_retry(
    *,
    ch: BlockingChannel,
    queue_name: str,
    body: bytes,
    retry_count: int,
    delay_seconds: float,
) -> None:
    props = BasicProperties(
        content_type="application/json",
        delivery_mode=2,
        headers={"x-retry-count": retry_count},
        expiration=str(int(delay_seconds * 1000)),
    )
    ch.basic_publish(
        exchange="",
        routing_key=f"{queue_name}.retry",
        body=body,
        properties=props,
        mandatory=False,
    )


def handle_message(
    *,
    ch: BlockingChannel,
    method: Basic.Deliver,
    props: BasicProperties,
    body: bytes,
) -> None:
    """Обработать сообщение очереди."""

    settings = get_settings()
    retry_count = _get_retry_count(props)
    try:
        payload = loads_json(body.decode("utf-8"))
        order_id = payload.get("order_id")
        if not isinstance(order_id, str) or not order_id:
            raise ValueError("order_id is required")

        logger.info("new_order received order_id={id}", id=order_id)
        process_order.delay(order_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("new_order dispatched to celery order_id={id}", id=order_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Consumer failed: {err}", err=str(exc))
        if retry_count >= settings.rabbitmq_consumer_max_retries:
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return

        delay = float(settings.rabbitmq_consumer_retry_base_seconds) * (2**retry_count)
        _publish_retry(
            ch=ch,
            queue_name=settings.rabbitmq_new_order_queue,
            body=body,
            retry_count=retry_count + 1,
            delay_seconds=delay,
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)


def run_forever() -> None:
    """Запустить консюмера в бесконечном цикле с переподключением."""

    settings = get_settings()
    cfg = RabbitMQConfig(
        amqp_url=settings.rabbitmq_dsn,
        new_order_queue=settings.rabbitmq_new_order_queue,
    )
    queue = settings.rabbitmq_new_order_queue

    logger.info("new_order consumer started queue={q}", q=queue)
    while True:
        try:
            consume(
                config=cfg,
                queue_name=queue,
                on_message=handle_message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Consumer connection failed: {err}", err=str(exc))
            time.sleep(2)


if __name__ == "__main__":
    run_forever()
