"""Shared async Redis client + a tiny token-bucket rate limiter."""

from __future__ import annotations

import time

from redis.asyncio import Redis

from postpilot.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def acquire_token(key: str, *, rate_per_min: int, burst: int | None = None) -> bool:
    """Best-effort token-bucket. Returns True if a token was granted.

    Used for per-X-account and app-wide X API throttling. Fail-open on Redis error
    so a cache outage never blocks posting outright (the X API still enforces its own caps).
    """
    burst = burst or rate_per_min
    refill = rate_per_min / 60.0
    now = time.time()
    redis = get_redis()
    bucket = f"rl:{key}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            data = await redis.hgetall(bucket)
            tokens = float(data.get("tokens", burst))
            ts = float(data.get("ts", now))
            tokens = min(burst, tokens + (now - ts) * refill)
            granted = tokens >= 1
            if granted:
                tokens -= 1
            pipe.hset(bucket, mapping={"tokens": tokens, "ts": now})
            pipe.expire(bucket, 3600)
            await pipe.execute()
        return granted
    except Exception:  # noqa: BLE001 - fail open
        return True


async def with_lock(key: str, *, ttl_seconds: int = 30) -> bool:
    """Acquire a non-blocking distributed lock (e.g., scheduler materializer leader)."""
    redis = get_redis()
    return bool(await redis.set(f"lock:{key}", "1", nx=True, ex=ttl_seconds))
