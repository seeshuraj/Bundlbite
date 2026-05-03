# scraper/cache.py
# Redis cache with in-memory fallback
# Zero crash risk — if Redis is unavailable, falls back to RAM dict

import os
import asyncio
from typing import Optional

# In-memory fallback store
_memory_cache: dict = {}

# Redis client (lazy init)
_redis = None


async def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis = aioredis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        await _redis.ping()
        print("[Cache] Connected to Redis")
        return _redis
    except Exception as e:
        print(f"[Cache] Redis unavailable ({e}), using in-memory fallback")
        _redis = None
        return None


async def get_cache(key: str) -> Optional[str]:
    """Get a value from cache. Returns None if not found or expired."""
    r = await _get_redis()
    if r:
        try:
            return await r.get(key)
        except Exception:
            pass
    # In-memory fallback
    entry = _memory_cache.get(key)
    if entry:
        value, expires_at = entry
        if expires_at is None or asyncio.get_event_loop().time() < expires_at:
            return value
        else:
            del _memory_cache[key]
    return None


async def set_cache(key: str, value: str, ttl: int = 900) -> None:
    """Set a cache value with TTL in seconds (default 15 min)."""
    r = await _get_redis()
    if r:
        try:
            await r.setex(key, ttl, value)
            return
        except Exception:
            pass
    # In-memory fallback
    expires_at = asyncio.get_event_loop().time() + ttl
    _memory_cache[key] = (value, expires_at)


async def delete_cache(key: str) -> None:
    """Delete a cache entry."""
    r = await _get_redis()
    if r:
        try:
            await r.delete(key)
            return
        except Exception:
            pass
    _memory_cache.pop(key, None)


async def flush_cache() -> None:
    """Clear all cache entries."""
    r = await _get_redis()
    if r:
        try:
            await r.flushdb()
        except Exception:
            pass
    _memory_cache.clear()
