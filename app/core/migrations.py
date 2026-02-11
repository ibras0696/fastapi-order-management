"""Запуск Alembic миграций при старте приложения (lifespan).

Важно
-----
В продакшене обычно миграции гоняются отдельным job/step.
Но если требуется "самодостаточный" запуск через `docker compose up`,
можно запускать миграции при старте приложения. Для Postgres используем
advisory lock, чтобы миграции выполнялись ровно одним процессом.
"""

from __future__ import annotations

import time
import zlib
from contextlib import contextmanager

import psycopg2
from alembic import command
from alembic.config import Config
from loguru import logger

from app.core.config import Settings, get_settings


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql://")


def _make_alembic_config(database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _wait_for_postgres(settings: Settings) -> None:
    """Подождать доступности Postgres перед миграциями."""

    tries = int(settings.migrations_wait_tries)
    sleep_seconds = float(settings.migrations_wait_sleep_seconds)

    for i in range(1, tries + 1):
        try:
            conn = psycopg2.connect(settings.sqlalchemy_url)
            conn.close()
            return
        except Exception:  # noqa: BLE001
            logger.info(
                "DB not ready yet ({i}/{n}), sleep {s}s",
                i=i,
                n=tries,
                s=sleep_seconds,
            )
            time.sleep(sleep_seconds)

    raise RuntimeError("database is not reachable for migrations")


@contextmanager
def _pg_advisory_lock(database_url: str, lock_key: int):
    """Взять advisory lock на Postgres и гарантированно отпустить."""

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
        yield
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
        finally:
            conn.close()


def run_migrations_once() -> None:
    """Запустить миграции до head (один раз на старт процесса).

    Notes
    -----
    Для Postgres используется `pg_advisory_lock`, чтобы при нескольких инстансах
    миграции выполнялись только одним процессом.
    """

    settings = get_settings()
    db_url = settings.sqlalchemy_url

    logger.info(
        "Migrations on startup enabled={v}",
        v=settings.run_migrations_on_startup,
    )

    if not settings.run_migrations_on_startup:
        return

    if _is_postgres(db_url):
        _wait_for_postgres(settings)
        lock_key = zlib.crc32(settings.app_name.encode("utf-8"))
        logger.info("Acquiring advisory lock key={k}", k=lock_key)
        with _pg_advisory_lock(db_url, lock_key):
            logger.info("Running alembic upgrade head (postgres)")
            cfg = _make_alembic_config(db_url)
            command.upgrade(cfg, "head")
        logger.info("Migrations completed")
        return

    logger.info("Running alembic upgrade head (non-postgres)")
    cfg = _make_alembic_config(db_url)
    command.upgrade(cfg, "head")
    logger.info("Migrations completed")
