"""提取结果缓存 — redis.asyncio，键 = sha256(归一化URL + 指令)。Redis 不可用时静默降级。"""

from __future__ import annotations

import hashlib
import json
import logging

from nia.utils.config import Config
from nia.utils.url_safety import normalize_url

logger = logging.getLogger(__name__)


def _cache_key(url: str, instruction: str) -> str:
    norm = normalize_url(url) or url
    digest = hashlib.sha256(f"{norm}||{instruction}".encode("utf-8")).hexdigest()
    return f"nia:cache:extract:{digest}"


class ExtractCache:
    """异步提取缓存。失败一律返回 miss / 静默，不影响主流程。"""

    def __init__(self, ttl: int | None = None):
        self._ttl = ttl if ttl is not None else Config.AI_CACHE_DAYS * 86400
        self._redis = None
        self._disabled = False

    async def _get_redis(self):
        if self._disabled:
            return None
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(Config.REDIS_URL, decode_responses=True)
            except Exception as e:
                logger.warning(f"ExtractCache disabled (redis unavailable): {e}")
                self._disabled = True
                return None
        return self._redis

    async def get(self, url: str, instruction: str) -> dict | None:
        r = await self._get_redis()
        if r is None:
            return None
        try:
            raw = await r.get(_cache_key(url, instruction))
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.debug(f"cache get error: {e}")
            return None

    async def set(self, url: str, instruction: str, value: dict) -> None:
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.set(_cache_key(url, instruction), json.dumps(value, ensure_ascii=False), ex=self._ttl)
        except Exception as e:
            logger.debug(f"cache set error: {e}")

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
