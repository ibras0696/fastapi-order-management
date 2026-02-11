"""Middleware для rate limiting (best-effort, in-memory)."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limiter import RateLimiter
from app.core.rate_limiter_redis import RedisRateLimiter
from app.db.redis import get_redis_client


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    """Создать и закэшировать rate limiter по текущим настройкам."""

    settings = get_settings()
    return RateLimiter(
        capacity=settings.rate_limit_capacity,
        refill_rate=settings.rate_limit_refill_rate,
    )


@lru_cache(maxsize=1)
def get_rate_limiter_redis() -> RedisRateLimiter:
    """Создать и закэшировать Redis rate limiter."""

    settings = get_settings()
    return RedisRateLimiter(
        get_redis_client(),
        capacity=settings.rate_limit_capacity,
        refill_rate=settings.rate_limit_refill_rate,
    )


def _get_client_key(request: Request) -> str:
    """Получить ключ rate limiting для запроса."""

    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client is None:
        return "unknown"
    return request.client.host


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Ограничение частоты запросов на уровне middleware."""

    _skip_paths = {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in self._skip_paths:
            return await call_next(request)

        limiter_backend = settings.rate_limit_backend.lower().strip()
        key = _get_client_key(request)
        allowed = True
        if limiter_backend == "redis":
            try:
                allowed = await get_rate_limiter_redis().allow(
                    key=f"ratelimit:{key}",
                    cost=1,
                )
            except Exception:  # noqa: BLE001
                allowed = get_rate_limiter().allow(key=key, cost=1)
        else:
            allowed = get_rate_limiter().allow(key=key, cost=1)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
            )

        return await call_next(request)
