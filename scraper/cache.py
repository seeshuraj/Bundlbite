"""
Redis Cache Layer
Upstash Redis via HTTP (no persistent connection needed).
Falls back to in-memory dict if Redis is unavailable.
"""

import os
import json
import time
from typing import Optional

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisCache:
    def __init__(self):
        self._mem: dict = {}  # fallback in-memory store
        self._client = None
        url = os.getenv("REDIS_URL")
        if url and REDIS_AVAILABLE:
            try:
                self._client = aioredis.from_url(url, decode_responses=True)
            except Exception:
                self._client = None

    async def get(self, key: str) -> Optional[dict]:
        if self._client:
            try:
                val = await self._client.get(key)
                return json.loads(val) if val else None
            except Exception:
                pass
        # In-memory fallback
        entry = self._mem.get(key)
        if entry and entry["expires"] > time.time():
            return entry["value"]
        return None

    async def set(self, key: str, value: dict, ttl: int = 900):
        if self._client:
            try:
                await self._client.setex(key, ttl, json.dumps(value))
                return
            except Exception:
                pass
        # In-memory fallback
        self._mem[key] = {"value": value, "expires": time.time() + ttl}

    async def delete(self, key: str):
        if self._client:
            try:
                await self._client.delete(key)
            except Exception:
                pass
        self._mem.pop(key, None)
