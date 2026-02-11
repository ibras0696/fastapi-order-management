"""Тесты middleware безопасности (CORS и rate limiting)."""

from __future__ import annotations

from pathlib import Path

from app.core import config as config_module
from app.core import rate_limit_middleware as rate_limit_module
from app.models import order as _order  # noqa: F401
from app.models import user as _user  # noqa: F401
from tests.helpers import make_client


def test_rate_limit_returns_429(tmp_path: Path, monkeypatch) -> None:
    """При превышении лимита middleware должен вернуть 429."""

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("RATE_LIMIT_CAPACITY", "1")
    monkeypatch.setenv("RATE_LIMIT_REFILL_RATE", "0.0001")
    config_module.get_settings.cache_clear()
    rate_limit_module.get_rate_limiter.cache_clear()
    rate_limit_module.get_rate_limiter_redis.cache_clear()

    client, _ = make_client(tmp_path)

    response = client.post(
        "/register/",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 201

    response = client.post(
        "/register/",
        json={"email": "b@example.com", "password": "password123"},
    )
    assert response.status_code == 429


def test_cors_preflight_sets_headers(tmp_path: Path, monkeypatch) -> None:
    """CORS preflight должен возвращать CORS заголовки для разрешённого origin."""

    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://example.com")
    monkeypatch.setenv("CORS_ALLOW_METHODS", "POST,GET,PATCH,OPTIONS")
    monkeypatch.setenv("CORS_ALLOW_HEADERS", "authorization,content-type")
    config_module.get_settings.cache_clear()

    client, _ = make_client(tmp_path)

    response = client.options(
        "/orders/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://example.com"
