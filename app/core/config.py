"""Конфигурация приложения.

Все настройки должны приходить из переменных окружения (опционально через `.env`).
Секреты нельзя хранить в репозитории/коде — используйте `.env` локально и
секрет-менеджер в проде.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str) -> list[str]:
    """Разбить строку CSV на список значений.

    Parameters
    ----------
    value : str
        CSV строка.

    Returns
    -------
    list[str]
        Список значений без пробелов.
    """

    if value.strip() == "*":
        return ["*"]
    return [part.strip() for part in value.split(",") if part.strip()]


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения.

    Notes
    -----
    В локальной разработке значения могут браться из файла `.env`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "order-management"
    app_env: str = "local"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    run_migrations_on_startup: bool = False
    migrations_wait_tries: int = 60
    migrations_wait_sleep_seconds: float = 1.0

    secret_key: str = "change-me-make-it-long-and-random"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_allow_origins: str = "*"
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"
    cors_allow_credentials: bool = False

    rate_limit_enabled: bool = True
    rate_limit_backend: str = "memory"
    rate_limit_capacity: int = 100
    rate_limit_refill_rate: float = 50.0

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "order_management"
    postgres_user: str = "postgres"
    postgres_password: str = "change-me"

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_orders_ttl_seconds: int = 300

    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    rabbitmq_new_order_queue: str = "new_order"
    rabbitmq_consumer_max_retries: int = 5
    rabbitmq_consumer_retry_base_seconds: float = 2.0

    outbox_poll_seconds: float = 1.0
    outbox_batch_size: int = 50
    outbox_lease_seconds: int = 30

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    database_url: str | None = None

    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL DSN from component settings."""

        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_dsn(self) -> str:
        """Build Redis DSN from component settings."""

        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def rabbitmq_dsn(self) -> str:
        """Собрать DSN RabbitMQ из компонентных настроек.

        Returns
        -------
        str
            DSN для подключения к RabbitMQ.
        """

        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/"
            f"{self.rabbitmq_vhost.lstrip('/')}"
        )

    @property
    def effective_celery_broker_url(self) -> str:
        """Вернуть broker URL для Celery.

        Notes
        -----
        По умолчанию используем Redis, а не RabbitMQ, чтобы не смешивать event-bus
        и tasks.
        """

        return self.celery_broker_url or self.redis_dsn

    @property
    def effective_celery_result_backend(self) -> str:
        """Вернуть result backend URL для Celery."""

        return self.celery_result_backend or self.redis_dsn

    @property
    def cors_origins_list(self) -> list[str]:
        """Список разрешённых origins для CORS."""

        return _split_csv(self.cors_allow_origins)

    @property
    def cors_methods_list(self) -> list[str]:
        """Список разрешённых методов для CORS."""

        return _split_csv(self.cors_allow_methods)

    @property
    def cors_headers_list(self) -> list[str]:
        """Список разрешённых заголовков для CORS."""

        return _split_csv(self.cors_allow_headers)

    @property
    def sqlalchemy_url(self) -> str:
        """Вернуть URL подключения к БД для SQLAlchemy.

        Priority
        --------
        1) `DATABASE_URL`, если задан.
        2) Иначе собирается DSN PostgreSQL из компонентных env-переменных.

        Returns
        -------
        str
            URL для SQLAlchemy.
        """

        return self.database_url or self.postgres_dsn


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Вернуть кэшированный экземпляр настроек.

    Returns
    -------
    Settings
        Настройки приложения.
    """

    return Settings()
