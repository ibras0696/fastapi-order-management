"""Сессия БД и зависимости для FastAPI."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def get_engine():
    """Создать SQLAlchemy engine.

    Returns
    -------
    sqlalchemy.engine.Engine
        Engine для подключения к БД.
    """

    settings = get_settings()
    return create_engine(settings.sqlalchemy_url, pool_pre_ping=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: открыть сессию БД на запрос.

    Yields
    ------
    sqlalchemy.orm.Session
        Сессия БД.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
