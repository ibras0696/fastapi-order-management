"""Тесты outbox (создание события при создании заказа)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import order as _order  # noqa: F401
from app.models import outbox as _outbox  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.models.outbox import OutboxEvent


def make_client(tmp_path: Path) -> tuple[TestClient, sessionmaker]:
    """Собрать TestClient и фабрику сессий для проверки БД."""

    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    app = create_app()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


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

    db = session_factory()
    try:
        events = db.query(OutboxEvent).filter(
            OutboxEvent.aggregate_id == order_id,
        ).all()
        assert len(events) == 1
        assert events[0].event_type == "new_order"
        assert events[0].payload == {"order_id": order_id}
        assert events[0].status == "PENDING"
    finally:
        db.close()
