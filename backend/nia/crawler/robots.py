"""robots.txt 遵从与爬取延迟 — 按域名缓存，避免重复请求。

礼貌爬取的兜底：即使目标站点没有 robots.txt，也会通过
`crawl_delay`（若声明）与单域名并发上限来限制压力。
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

# robots.txt 缓存有效期（秒）
_CACHE_TTL = 3600.0
# 未声明 crawl-delay 时的默认同域名最小间隔（秒）
DEFAULT_DOMAIN_DELAY = 0.0
# 抓取 robots.txt 的最大等待时间
_ROBOTS_TIMEOUT = 10.0


def origin_of(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    if not parts.scheme or not parts.hostname:
        return ""
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


class RobotsCache:
    """进程级 robots.txt 缓存：域名 → (RobotFileParser | None, crawl_delay)。"""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[RobotFileParser | None, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _lock_for(self, origin: str) -> asyncio.Lock:
        async with self._global_lock:
            lock = self._locks.get(origin)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[origin] = lock
            return lock

    async def rules(self, url: str, fetch_text) -> tuple[RobotFileParser | None, float]:
        """返回 (解析器, crawl_delay)。解析器为 None 表示「允许全部」。

        fetch_text 是一个 async 可调用：`await fetch_text(url) -> str | None`。
        """
        origin = origin_of(url)
        if not origin:
            return None, DEFAULT_DOMAIN_DELAY

        entry = self._cache.get(origin)
        now = asyncio.get_running_loop().time()
        if entry is not None and now - entry[1] < _CACHE_TTL:
            parser = entry[0]
            return parser, (parser.crawl_delay("*") or DEFAULT_DOMAIN_DELAY) if parser else DEFAULT_DOMAIN_DELAY

        lock = await self._lock_for(origin)
        async with lock:
            entry = self._cache.get(origin)
            now = asyncio.get_running_loop().time()
            if entry is not None and now - entry[1] < _CACHE_TTL:
                parser = entry[0]
                return parser, (parser.crawl_delay("*") or DEFAULT_DOMAIN_DELAY) if parser else DEFAULT_DOMAIN_DELAY

            text = None
            try:
                text = await asyncio.wait_for(fetch_text(f"{origin}/robots.txt"), timeout=_ROBOTS_TIMEOUT)
            except Exception as e:  # 网络失败/超时都视为允许全部
                logger.debug("robots.txt 获取失败 %s: %s", origin, e)

            parser: RobotFileParser | None = None
            if text and text.strip():
                try:
                    parser = RobotFileParser()
                    parser.set_url(f"{origin}/robots.txt")
                    parser.parse(text.splitlines())
                except Exception as e:
                    logger.debug("robots.txt 解析失败 %s: %s", origin, e)
                    parser = None

            self._cache[origin] = (parser, now)
            delay = (parser.crawl_delay("*") or DEFAULT_DOMAIN_DELAY) if parser else DEFAULT_DOMAIN_DELAY
            return parser, float(delay)

    async def allowed(self, url: str, user_agent: str, fetch_text) -> tuple[bool, float]:
        parser, delay = await self.rules(url, fetch_text)
        if parser is None:
            return True, delay
        try:
            return bool(parser.can_fetch(user_agent, url)), delay
        except Exception:
            return True, delay

    def clear(self) -> None:
        self._cache.clear()
        self._locks.clear()
