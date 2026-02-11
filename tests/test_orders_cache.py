"""Тесты Redis-кеша заказов (best-effort + fallback)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.models import order as _order  # noqa: F401  # ensure model import for metadata
from app.models import user as _user  # noqa: F401  # ensure model import for metadata
from tests_helpers import make_client


class FakeRedis:
    """Простой in-memory Redis для тестов."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def setex(
        self,
        key: str,
        ttl_seconds: int,
        value: str,
    ) -> None:  # noqa: ARG002
        self.data[key] = value

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)


class BrokenRedis:
    """Redis-клиент, который всегда падает (симуляция Redis down)."""

    async def get(self, key: str) -> str | None:  # noqa: ARG002
        raise RuntimeError("redis is down")

    async def setex(
        self,
        key: str,
        ttl_seconds: int,
        value: str,
    ) -> None:  # noqa: ARG002
        raise RuntimeError("redis is down")

    async def delete(self, key: str) -> None:  # noqa: ARG002
        raise RuntimeError("redis is down")


def register_and_login(client: TestClient, email: str, password: str) -> str:
    """Зарегистрироваться и получить JWT токен."""

    response = client.post("/register/", json={"email": email, "password": password})
    assert response.status_code == 201

    response = client.post("/token/", data={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    """Собрать заголовки авторизации."""

    return {"Authorization": f"Bearer {token}"}


def test_get_order_uses_cache_when_present(tmp_path: Path, monkeypatch) -> None:
    """GET /orders/{id} отдаёт из кеша (без обращения к БД), если кеш есть."""

    client, _ = make_client(tmp_path)
    token = register_and_login(client, email="user@example.com", password="password123")

    response = client.post(
        "/orders/",
        headers=auth_headers(token),
        json={"items": [{"product_id": 1, "quantity": 1, "price": 10.0}]},
    )
    assert response.status_code == 201
    order_id = response.json()["id"]

    fake_redis = FakeRedis()

    # Подкладываем кеш вручную тем же форматом, который ожидает orders_cache.
    cached_value = (
        '{"id":"%s","user_id":1,"items":[{"product_id":1,"quantity":1,"price":10.0}],'
        '"total_price":10.0,"status":"PENDING"}'
    ) % order_id
    fake_redis.data[f"orders:{order_id}"] = (
        cached_value
    )

    monkeypatch.setattr("app.api.routes.orders.get_redis_client", lambda: fake_redis)

    async def boom(*args, **kwargs):  # noqa: ANN001,ARG001
        raise AssertionError("DB must not be used when cache hit")

    monkeypatch.setattr("app.api.routes.orders.get_order", boom)

    response = client.get(f"/orders/{order_id}/", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["id"] == order_id


def test_get_order_fallbacks_to_db_when_redis_down(tmp_path: Path, monkeypatch) -> None:
    """Если Redis недоступен, эндпоинт должен работать (fallback на БД)."""

    client, _ = make_client(tmp_path)
    token = register_and_login(client, email="user@example.com", password="password123")

    response = client.post(
        "/orders/",
        headers=auth_headers(token),
        json={"items": [{"product_id": 1, "quantity": 1, "price": 10.0}]},
    )
    assert response.status_code == 201
    order_id = response.json()["id"]

    monkeypatch.setattr("app.api.routes.orders.get_redis_client", lambda: BrokenRedis())

    response = client.get(f"/orders/{order_id}/", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["id"] == order_id
