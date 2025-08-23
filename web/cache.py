from __future__ import annotations

"""Redis caching helpers."""

import json
from typing import Any

import redis.asyncio as redis

from config import settings

# Redis client shared across modules
redis_client = redis.from_url(
    settings.redis_url, encoding="utf-8", decode_responses=True
)


async def cache_get(key: str) -> Any | None:
    """Retrieve a JSON-serialised value from Redis."""
    try:
        data = await redis_client.get(key)
    except Exception:  # pragma: no cover - connection issues ignored
        return None
    if data is None:
        return None
    try:
        return json.loads(data)
    except Exception:  # pragma: no cover - invalid JSON
        return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Store a JSON-serialisable value in Redis with a TTL."""
    try:
        await redis_client.setex(key, ttl, json.dumps(value))
    except Exception:  # pragma: no cover - connection issues ignored
        pass


async def cache_invalidate(prefix: str) -> None:
    """Invalidate cached entries with the given prefix."""
    try:
        async for key in redis_client.scan_iter(match=f"{prefix}*"):
            await redis_client.delete(key)
    except Exception:  # pragma: no cover - connection issues ignored
        pass
