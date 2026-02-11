"""Конфигурация pytest."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core import config as config_module  # noqa: E402

# В тестах не запускаем миграции на старте приложения (они требуют внешнего Postgres).
os.environ.setdefault("RUN_MIGRATIONS_ON_STARTUP", "false")
config_module.get_settings.cache_clear()
