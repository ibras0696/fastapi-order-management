"""Тесты аутентификации (register/token)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import user as _user  # noqa: F401  # ensure model import for metadata


def make_client(tmp_path: Path) -> TestClient:
    """Собрать TestClient с тестовой SQLite БД.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Временная директория pytest.

    Returns
    -------
    fastapi.testclient.TestClient
        Клиент для запросов к приложению.
    """

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
    return TestClient(app)


def test_register_and_token_happy_path(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/register/",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert isinstance(body["id"], int)

    response = client.post(
        "/token/",
        data={"username": "user@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    token_body = response.json()
    assert token_body["token_type"] == "bearer"
    assert isinstance(token_body["access_token"], str)
    assert token_body["access_token"]


def test_register_duplicate_email(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/register/",
        json={"email": "dup@example.com", "password": "password123"},
    )
    assert response.status_code == 201

    response = client.post(
        "/register/",
        json={"email": "dup@example.com", "password": "password123"},
    )
    assert response.status_code == 400


def test_token_wrong_password(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/register/",
        json={"email": "user2@example.com", "password": "password123"},
    )
    assert response.status_code == 201

    response = client.post(
        "/token/",
        data={"username": "user2@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
