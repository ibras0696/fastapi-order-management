"""Утилиты для тестов (TestClient + async SQLite)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


def make_client(tmp_path: Path) -> tuple[TestClient, async_sessionmaker[AsyncSession]]:
    """Собрать TestClient с тестовой SQLite БД (async).

    Parameters
    ----------
    tmp_path : pathlib.Path
        Временная директория pytest.

    Returns
    -------
    tuple[fastapi.testclient.TestClient, sqlalchemy.ext.asyncio.async_sessionmaker]
        (клиент приложения, фабрика async сессий).
    """

    db_path = tmp_path / "test.db"
    engine: AsyncEngine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    testing_session_local: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    async def _init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_schema())

    app = create_app()

    async def override_get_db():  # noqa: ANN001
        async with testing_session_local() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local
