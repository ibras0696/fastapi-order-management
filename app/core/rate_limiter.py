"""Rate limiting по алгоритму Token Bucket.

Notes
-----
Реализация безопасна в рамках одного процесса (worker).
В распределённой среде состояние нужно хранить в общем хранилище (например, Redis).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    last_refill_ts: float


class RateLimiter:
    """Ограничитель частоты запросов по алгоритму Token Bucket.

    Parameters
    ----------
    capacity : int
        Максимальное количество токенов в ведре.
    refill_rate : float
        Скорость пополнения токенов в секунду. Должна быть положительной.
    """

    def __init__(self, capacity: int, refill_rate: float) -> None:
        """Инициализировать ограничитель частоты.

        Raises
        ------
        ValueError
            Если capacity или refill_rate не являются положительными.
        """

        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")

        self.capacity = capacity
        self.refill_rate = refill_rate
        self._lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}

    def allow(self, key: str, cost: int = 1) -> bool:
        """Проверить, разрешён ли запрос.

        Parameters
        ----------
        key : str
            Ключ лимита (например, IP адрес).
        cost : int, default=1
            Стоимость запроса в токенах.

        Returns
        -------
        bool
            True, если запрос можно выполнить, иначе False.
        """

        if cost <= 0:
            raise ValueError("cost must be positive")

        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.capacity), last_refill_ts=now)
                self._buckets[key] = bucket

            elapsed = max(0.0, now - bucket.last_refill_ts)
            bucket.tokens = min(
                self.capacity,
                bucket.tokens + elapsed * self.refill_rate,
            )
            bucket.last_refill_ts = now

            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True
            return False
