"""RabbitMQ публикация/консюмер для event-bus (best-effort).

Важно
-----
RabbitMQ используется только как event-bus (события домена).
Celery использует отдельный брокер (по умолчанию Redis), чтобы не смешивать обязанности.
"""

from __future__ import annotations

from dataclasses import dataclass

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties


@dataclass(frozen=True)
class RabbitMQConfig:
    """Конфигурация подключения к RabbitMQ."""

    amqp_url: str
    new_order_queue: str


def _ensure_queue(channel: BlockingChannel, queue_name: str) -> None:
    """Объявить очередь (idempotent)."""

    channel.queue_declare(queue=queue_name, durable=True)


def ensure_event_queue_topology(channel: BlockingChannel, queue_name: str) -> None:
    """Объявить основную очередь + retry + dlq.

    Topology
    --------
    - `<queue_name>`: основная очередь, dead-letter -> `<queue_name>.dlq`
    - `<queue_name>.retry`: очередь для задержанных ретраев,
      dead-letter -> `<queue_name>`
    - `<queue_name>.dlq`: dead-letter queue
    """

    dlq = f"{queue_name}.dlq"
    retry = f"{queue_name}.retry"

    channel.queue_declare(queue=dlq, durable=True)

    channel.queue_declare(
        queue=queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": dlq,
        },
    )

    channel.queue_declare(
        queue=retry,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": queue_name,
        },
    )


def publish_json(
    *,
    config: RabbitMQConfig,
    routing_key: str,
    body: bytes,
) -> None:
    """Опубликовать сообщение в RabbitMQ.

    Parameters
    ----------
    config : RabbitMQConfig
        Настройки подключения.
    routing_key : str
        Routing key (для очереди — имя очереди).
    body : bytes
        Тело сообщения (JSON bytes).
    """

    parameters = pika.URLParameters(config.amqp_url)
    connection = pika.BlockingConnection(parameters)
    try:
        channel = connection.channel()
        channel.confirm_delivery()
        ensure_event_queue_topology(channel, routing_key)
        props = BasicProperties(
            content_type="application/json",
            delivery_mode=2,
        )
        ok = channel.basic_publish(
            exchange="",
            routing_key=routing_key,
            body=body,
            properties=props,
            mandatory=False,
        )
        if ok is False:
            raise RuntimeError("rabbitmq publish not confirmed")
    finally:
        connection.close()


def consume(
    *,
    config: RabbitMQConfig,
    queue_name: str,
    on_message,
) -> None:
    """Запустить консюмера (блокирующий)."""

    parameters = pika.URLParameters(config.amqp_url)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    ensure_event_queue_topology(channel, queue_name)
    channel.basic_qos(prefetch_count=10)

    def _callback(
        ch: BlockingChannel,
        method: Basic.Deliver,
        props: BasicProperties,
        body: bytes,
    ) -> None:
        on_message(ch=ch, method=method, props=props, body=body)

    channel.basic_consume(
        queue=queue_name,
        on_message_callback=_callback,
        auto_ack=False,
    )
    try:
        channel.start_consuming()
    finally:
        try:
            channel.stop_consuming()
        finally:
            connection.close()
