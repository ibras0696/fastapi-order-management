"""Тесты outbox (создание события при создании заказа)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import order as _order  # noqa: F401
from app.models import outbox as _outbox  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.models.outbox import OutboxEvent
from tests_helpers import make_client


def _fetch_outbox_events(
    session_factory: async_sessionmaker[AsyncSession],
    order_id: str,
) -> list[OutboxEvent]:
    async def _run() -> list[OutboxEvent]:
        async with session_factory() as db:
            result = await db.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == order_id)
            )
            return list(result.scalars().all())

    return asyncio.run(_run())


def register_and_login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/register/", json={"email": email, "password": password})
    assert response.status_code == 201

    response = client.post("/token/", data={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_outbox_event_created_on_order_create(tmp_path: Path) -> None:
    client, session_factory = make_client(tmp_path)
    token = register_and_login(client, email="user@example.com", password="password123")

    response = client.post(
        "/orders/",
        headers=auth_headers(token),
        json={"items": [{"product_id": 1, "quantity": 1, "price": 10.0}]},
    )
    assert response.status_code == 201
    order_id = response.json()["id"]

    events = _fetch_outbox_events(session_factory, order_id=order_id)
    assert len(events) == 1
    assert events[0].event_type == "new_order"
    assert events[0].payload == {"order_id": order_id}
    assert events[0].status == "PENDING"
