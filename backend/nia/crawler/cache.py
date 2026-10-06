"""提取结果缓存 — redis.asyncio，键含 URL/指令/模型/提示词版本。Redis 不可用时静默降级。

键里带上 provider + model + prompt 版本，这样换模型或改提示词之后旧缓存自动失效，
不会命中 7 天前用另一套提示词/模型生成的脏数据。
"""

from __future__ import annotations

import hashlib
import json
import logging

from nia.utils.config import Config
from nia.utils.url_safety import normalize_url

logger = logging.getLogger(__name__)


def _model_fingerprint() -> str:
    try:
        info = Config.get_llm_config()
        return f"{Config.LLM_PROVIDER}:{info.get('model', '')}"
    except Exception:
        return str(getattr(Config, "LLM_PROVIDER", "unknown"))


def _cache_key(url: str, instruction: str, version: str = "") -> str:
    norm = normalize_url(url) or url
    raw = f"{norm}||{instruction}||{_model_fingerprint()}||{version}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"nia:cache:extract:{digest}"


class ExtractCache:
    """异步提取缓存。失败一律返回 miss / 静默，不影响主流程。"""

    def __init__(self, ttl: int | None = None, version: str = ""):
        self._ttl = ttl if ttl is not None else Config.AI_CACHE_DAYS * 86400
        self._version = version
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
            raw = await r.get(_cache_key(url, instruction, self._version))
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.debug(f"cache get error: {e}")
            return None

    async def set(self, url: str, instruction: str, value: dict) -> None:
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.set(
                _cache_key(url, instruction, self._version),
                json.dumps(value, ensure_ascii=False),
                ex=self._ttl,
            )
        except Exception as e:
            logger.debug(f"cache set error: {e}")

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            finally:
                self._redis = None
