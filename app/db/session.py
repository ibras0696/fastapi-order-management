"""Сессия БД и зависимости для FastAPI (async).

Notes
-----
FastAPI поддерживает как sync, так и async обработчики. В этом проекте
используется SQLAlchemy AsyncSession, чтобы не блокировать event loop
операциями ввода/вывода к БД.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Создать и закэшировать SQLAlchemy AsyncEngine.

    Returns
    -------
    sqlalchemy.ext.asyncio.AsyncEngine
        Async engine для подключения к БД.
    """

    settings = get_settings()
    return create_async_engine(settings.sqlalchemy_async_url, pool_pre_ping=True)


SessionLocal = async_sessionmaker(
    bind=get_async_engine(),
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: открыть async сессию БД на запрос.

    Yields
    ------
    sqlalchemy.ext.asyncio.AsyncSession
        Async сессия БД.
    """

    async with SessionLocal() as db:
        yield db
