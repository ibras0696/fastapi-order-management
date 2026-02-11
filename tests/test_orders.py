"""Тесты заказов (orders endpoints)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.models import order as _order  # noqa: F401  # ensure model import for metadata
from app.models import user as _user  # noqa: F401  # ensure model import for metadata
from tests.helpers import make_client


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


def test_create_order_unauthorized(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    response = client.post(
        "/orders/",
        json={"items": [{"product_id": 1, "quantity": 1, "price": 10.0}]},
    )
    assert response.status_code == 401


def test_orders_crud_happy_path(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token = register_and_login(client, email="user@example.com", password="password123")

    response = client.post(
        "/orders/",
        headers=auth_headers(token),
        json={
            "items": [
                {"product_id": 1, "quantity": 2, "price": 10.0},
                {"product_id": 2, "quantity": 1, "price": 5.5},
            ]
        },
    )
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "PENDING"
    assert order["total_price"] == 25.5
    assert order["items"][0]["product_id"] == 1

    order_id = order["id"]
    user_id = order["user_id"]

    response = client.get(f"/orders/{order_id}/", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["id"] == order_id

    response = client.patch(
        f"/orders/{order_id}/",
        headers=auth_headers(token),
        json={"status": "PAID"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PAID"

    response = client.get(f"/orders/user/{user_id}/", headers=auth_headers(token))
    assert response.status_code == 200
    orders = response.json()
    assert isinstance(orders, list)
    assert len(orders) == 1
    assert orders[0]["id"] == order_id


def test_orders_forbidden_other_user(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token1 = register_and_login(
        client,
        email="user1@example.com",
        password="password123",
    )
    token2 = register_and_login(
        client,
        email="user2@example.com",
        password="password123",
    )

    response = client.post(
        "/orders/",
        headers=auth_headers(token1),
        json={"items": [{"product_id": 1, "quantity": 1, "price": 10.0}]},
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    user_id = response.json()["user_id"]

    response = client.get(f"/orders/{order_id}/", headers=auth_headers(token2))
    assert response.status_code == 403

    response = client.get(f"/orders/user/{user_id}/", headers=auth_headers(token2))
    assert response.status_code == 403
