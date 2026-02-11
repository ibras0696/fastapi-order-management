"""Rate limiting в Redis (Token Bucket через Lua).

Notes
-----
Подходит для нескольких процессов/реплик, так как состояние хранится в Redis.
Если Redis недоступен, middleware должен fallback'иться на in-memory limiter.
"""

from __future__ import annotations

import time

from redis.asyncio import Redis


_LUA_TOKEN_BUCKET = r"""
-- KEYS[1] = bucket key
-- ARGV[1] = capacity
-- ARGV[2] = refill_rate (tokens per second)
-- ARGV[3] = now_ts (seconds, float)
-- ARGV[4] = cost

local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now_ts = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call("HMGET", key, "tokens", "ts")
local tokens = tonumber(data[1])
local ts = tonumber(data[2])

if tokens == nil or ts == nil then
  tokens = capacity
  ts = now_ts
end

local elapsed = now_ts - ts
if elapsed < 0 then
  elapsed = 0
end

tokens = math.min(capacity, tokens + elapsed * refill_rate)
ts = now_ts

local allowed = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
end

redis.call("HSET", key, "tokens", tokens, "ts", ts)
-- set TTL so buckets expire; keep 2x refill window minimum 60s
local ttl = math.max(60, math.floor((capacity / refill_rate) * 2))
redis.call("EXPIRE", key, ttl)

return allowed
"""


class RedisRateLimiter:
    """Redis-backed token bucket limiter."""

    def __init__(self, client: Redis, *, capacity: int, refill_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")

        self.client = client
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._script = client.register_script(_LUA_TOKEN_BUCKET)

    async def allow(self, key: str, cost: int = 1) -> bool:
        """Проверить, разрешён ли запрос."""

        if cost <= 0:
            raise ValueError("cost must be positive")

        now_ts = time.time()
        allowed = await self._script(
            keys=[key],
            args=[self.capacity, self.refill_rate, now_ts, cost],
        )
        return bool(int(allowed))
