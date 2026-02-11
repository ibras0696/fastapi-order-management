"""Redis клиент и хелперы.

Важно
-----
Redis должен быть *опциональной* зависимостью для API: при ошибках Redis эндпоинты
не должны падать — должен быть fallback на БД.
"""

from __future__ import annotations

import json

import redis
from redis import Redis

from app.core.config import get_settings


_pool: redis.ConnectionPool | None = None
_client: Redis | None = None


def get_redis_client() -> Redis:
    """Получить singleton Redis клиент (через pool).

    Returns
    -------
    redis.Redis
        Клиент Redis.
    """

    global _pool, _client  # noqa: PLW0603
    settings = get_settings()
    if _client is not None:
        return _client

    _pool = redis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
        max_connections=20,
    )
    _client = redis.Redis(connection_pool=_pool)
    return _client


def dumps_json(value: object) -> str:
    """Сериализовать объект в JSON строку."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads_json(value: str) -> object:
    """Десериализовать JSON строку."""

    return json.loads(value)
