"""User-related business logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Найти пользователя по email.

    Parameters
    ----------
    db : sqlalchemy.ext.asyncio.AsyncSession
        Async сессия БД.
    email : str
        Email пользователя.

    Returns
    -------
    User | None
        Пользователь или None.
    """

    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str) -> User:
    """Создать пользователя.

    Parameters
    ----------
    db : sqlalchemy.ext.asyncio.AsyncSession
        Async сессия БД.
    email : str
        Email пользователя.
    password : str
        Пароль в открытом виде.

    Returns
    -------
    User
        Созданный пользователь.
    """

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Проверить логин/пароль.

    Parameters
    ----------
    db : sqlalchemy.ext.asyncio.AsyncSession
        Async сессия БД.
    email : str
        Email пользователя.
    password : str
        Пароль в открытом виде.

    Returns
    -------
    User | None
        Пользователь при успехе, иначе None.
    """

    user = await get_user_by_email(db, email=email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
