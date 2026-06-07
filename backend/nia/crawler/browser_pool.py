"""异步浏览器池 — 复用单个 crawl4ai AsyncWebCrawler（纯 async，无 nest_asyncio）。

与旧的 utils/crawl4ai_engine.py 不同：本模块全程在调用方事件循环里 await，
不做 run_until_complete，也不在导入时 nest_asyncio.apply()，避免 FastAPI 下的重入坑。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class AsyncBrowserPool:
    """进程级单例：懒启动一个 headless 浏览器，并发开标签页复用之。"""

    _crawler = None
    _lock = asyncio.Lock()

    @classmethod
    async def _ensure(cls):
        if cls._crawler is not None:
            return cls._crawler
        async with cls._lock:
            if cls._crawler is not None:
                return cls._crawler
            from crawl4ai import AsyncWebCrawler
            try:
                from crawl4ai import BrowserConfig
                crawler = AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False))
            except (ImportError, TypeError):
                crawler = AsyncWebCrawler(headless=True, verbose=False)
            await crawler.start()
            cls._crawler = crawler
            logger.info("AsyncBrowserPool: headless browser started")
            return cls._crawler

    @classmethod
    async def fetch(cls, url: str) -> dict:
        """渲染并返回 {html, status_code, success, error}。"""
        try:
            crawler = await cls._ensure()
            result = await crawler.arun(url=url)
            return {
                "html": result.html if result else "",
                "status_code": getattr(result, "status_code", None) if result else None,
                "success": bool(result and result.success),
                "error": "",
            }
        except Exception as e:
            logger.warning(f"AsyncBrowserPool.fetch failed for {url}: {e}")
            return {"html": "", "status_code": None, "success": False, "error": str(e)}

    @classmethod
    async def close(cls):
        if cls._crawler is not None:
            try:
                await cls._crawler.close()
            except Exception as e:
                logger.warning(f"AsyncBrowserPool.close error: {e}")
            finally:
                cls._crawler = None
                logger.info("AsyncBrowserPool: browser closed")
