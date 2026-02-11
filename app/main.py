"""Точка входа FastAPI приложения."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.migrations import run_migrations_once
from app.core.rate_limit_middleware import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Lifespan приложения.

    Здесь запускаем миграции один раз при старте процесса (если включено).
    """

    await asyncio.to_thread(run_migrations_once)
    yield


def create_app() -> FastAPI:
    """Создать и сконфигурировать экземпляр FastAPI.

    Returns
    -------
    fastapi.FastAPI
        Сконфигурированное приложение.
    """

    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_methods_list,
        allow_headers=settings.cors_headers_list,
    )
    app.add_middleware(RateLimitMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
