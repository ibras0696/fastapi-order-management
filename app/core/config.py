"""Конфигурация приложения.

Все настройки должны приходить из переменных окружения (опционально через `.env`).
Секреты нельзя хранить в репозитории/коде — используйте `.env` локально и
секрет-менеджер в проде.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
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

    app_name: str = Field("order-management")
    app_env: str = Field("local")
    log_level: str = Field("INFO")

    api_host: str = Field("0.0.0.0")
    api_port: int = Field(8000)

    run_migrations_on_startup: bool = Field(False)
    migrations_wait_tries: int = Field(60, ge=1)
    migrations_wait_sleep_seconds: float = Field(1.0, gt=0)

    secret_key: SecretStr = Field(..., min_length=32)
    algorithm: str = Field("HS256")
    access_token_expire_minutes: int = Field(30, ge=1)

    cors_allow_origins: str = Field("*")
    cors_allow_methods: str = Field("*")
    cors_allow_headers: str = Field("*")
    cors_allow_credentials: bool = Field(False)

    rate_limit_enabled: bool = Field(True)
    rate_limit_backend: str = Field("memory")
    rate_limit_capacity: int = Field(100, ge=1)
    rate_limit_refill_rate: float = Field(50.0, gt=0)

    # DB settings
    postgres_host: str = "db"
    postgres_port: int = Field(5432, ge=1, le=65535)
    postgres_db: str = "order_management"
    postgres_user: str = "postgres"
    postgres_password: SecretStr | None = None

    # Redis settings
    redis_host: str = "redis"
    redis_port: int = Field(6379, ge=1, le=65535)
    redis_db: int = Field(0, ge=0)
    redis_orders_ttl_seconds: int = Field(300, ge=1)

    # RabbitMQ settings
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = Field(5672, ge=1, le=65535)
    rabbitmq_user: str = "guest"
    rabbitmq_password: SecretStr = Field(...)
    rabbitmq_vhost: str = Field("/")
    rabbitmq_new_order_queue: str = Field("new_order")
    rabbitmq_consumer_max_retries: int = Field(5, ge=0)
    rabbitmq_consumer_retry_base_seconds: float = Field(2.0, gt=0)

    outbox_poll_seconds: float = Field(1.0, gt=0)
    outbox_batch_size: int = Field(50, ge=1)
    outbox_lease_seconds: int = Field(30, ge=1)

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    database_url: str | None = None
    database_async_url: str | None = None

    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL DSN from component settings."""

        if self.postgres_password is None:
            raise ValueError(
                "POSTGRES_PASSWORD is required when DATABASE_URL is not set",
            )
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret.strip()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return value

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
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password.get_secret_value()}"
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
        """Вернуть sync URL подключения к БД для SQLAlchemy.

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

    @property
    def sqlalchemy_async_url(self) -> str:
        """Вернуть async URL подключения к БД для SQLAlchemy AsyncEngine.

        Priority
        --------
        1) `DATABASE_ASYNC_URL`, если задан.
        2) Иначе строится из `DATABASE_URL`/Postgres DSN:
           - `postgresql://...` -> `postgresql+asyncpg://...`
           - `sqlite+pysqlite://...` -> `sqlite+aiosqlite://...`
        """

        url = self.database_async_url or self.sqlalchemy_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("sqlite+pysqlite://"):
            return url.replace("sqlite+pysqlite://", "sqlite+aiosqlite://", 1)
        return url

    @field_validator("rabbitmq_password")
    @classmethod
    def _validate_non_empty_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("secret value must not be empty")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Вернуть кэшированный экземпляр настроек.

    Returns
    -------
    Settings
        Настройки приложения.
    """

    return Settings()
