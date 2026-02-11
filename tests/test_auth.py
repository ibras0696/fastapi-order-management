"""Тесты аутентификации (register/token)."""

from __future__ import annotations

from pathlib import Path

from app.models import user as _user  # noqa: F401  # ensure model import for metadata
from tests.helpers import make_client


def test_register_and_token_happy_path(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

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
    client, _ = make_client(tmp_path)

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
    client, _ = make_client(tmp_path)

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
