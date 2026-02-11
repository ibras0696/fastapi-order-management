"""Утилиты безопасности (пароли, JWT).

Пароли
------
Используется PBKDF2-HMAC-SHA256 (stdlib), чтобы не тянуть `passlib` и избежать
dep-warning'ов. Формат хранения:

`pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`

JWT
---
Используется `PyJWT` (HS256 по умолчанию).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

_SCHEME = "pbkdf2_sha256"
_SALT_BYTES = 16
_DK_LEN = 32


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def hash_password(password: str) -> str:
    """Захэшировать пароль.

    Parameters
    ----------
    password : str
        Пароль в открытом виде.

    Returns
    -------
    str
        Строка хэша в формате `<scheme>$<iterations>$<salt>$<hash>`.
    """

    iterations = 200_000
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=_DK_LEN,
    )
    return f"{_SCHEME}${iterations}${_b64encode(salt)}${_b64encode(dk)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Проверить пароль по сохранённому хэшу.

    Returns
    -------
    bool
        True, если пароль совпал.
    """

    try:
        scheme, iterations_s, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if scheme != _SCHEME:
            return False
        iterations = int(iterations_s)
        salt = _b64decode(salt_b64)
        expected = _b64decode(digest_b64)
    except Exception:  # noqa: BLE001
        return False

    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected),
    )
    return hmac.compare_digest(dk, expected)


def create_access_token(subject: str) -> str:
    """Создать JWT access token.

    Parameters
    ----------
    subject : str
        Subject токена (например, email пользователя).

    Returns
    -------
    str
        JWT токен.
    """

    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Декодировать JWT токен и вернуть payload.

    Raises
    ------
    jwt.PyJWTError
        Если токен невалиден.
    """

    settings = get_settings()
    return jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.algorithm],
    )
