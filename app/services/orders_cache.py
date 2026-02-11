"""Кеширование заказов в Redis (best-effort).

Правило
-------
Ошибки Redis никогда не должны "ронять" API. Все операции кеша выполняются
best-effort: при исключениях возвращаем None/False и логируем.
"""

from __future__ import annotations

from loguru import logger
from redis import Redis

from app.core.config import get_settings
from app.db.redis import dumps_json, loads_json
from app.schemas.orders import OrderOut


def make_order_cache_key(order_id: str) -> str:
    """Собрать ключ кеша для заказа."""

    return f"orders:{order_id}"


def get_order_from_cache(client: Redis, order_id: str) -> OrderOut | None:
    """Получить заказ из Redis.

    Parameters
    ----------
    client : redis.Redis
        Redis клиент.
    order_id : str
        UUID заказа.

    Returns
    -------
    OrderOut | None
        Заказ из кеша или None.
    """

    key = make_order_cache_key(order_id)
    try:
        value = client.get(key)
        if value is None:
            return None
        data = loads_json(value)
        return OrderOut.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Redis cache get failed for key={key}: {err}",
            key=key,
            err=str(exc),
        )
        return None


def set_order_cache(client: Redis, order: OrderOut) -> bool:
    """Сохранить заказ в Redis с TTL.

    Returns
    -------
    bool
        True если запись успешна, иначе False.
    """

    settings = get_settings()
    key = make_order_cache_key(order.id)
    try:
        payload = dumps_json(order.model_dump())
        client.setex(key, settings.redis_orders_ttl_seconds, payload)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Redis cache set failed for key={key}: {err}",
            key=key,
            err=str(exc),
        )
        return False


def delete_order_cache(client: Redis, order_id: str) -> bool:
    """Удалить кеш заказа.

    Returns
    -------
    bool
        True если удалось выполнить операцию, иначе False.
    """

    key = make_order_cache_key(order_id)
    try:
        client.delete(key)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Redis cache delete failed for key={key}: {err}",
            key=key,
            err=str(exc),
        )
        return False
