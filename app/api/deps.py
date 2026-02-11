"""Общие зависимости для роутов FastAPI (auth, user context)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.users import get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token/")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Получить текущего пользователя по JWT токену.

    Parameters
    ----------
    token : str
        JWT access token.
    db : sqlalchemy.ext.asyncio.AsyncSession
        Async сессия БД.

    Returns
    -------
    User
        Текущий пользователь.

    Raises
    ------
    HTTPException
        Если токен неверный или пользователь не найден.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentials",
    )
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise credentials_exception
    except Exception as exc:  # noqa: BLE001
        raise credentials_exception from exc

    user = await get_user_by_email(db, email=subject)
    if user is None:
        raise credentials_exception
    return user
