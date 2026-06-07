"""异步抓取器 — 共享 httpx.AsyncClient + 信号量限流 + 退避重试 + 可选 JS 渲染。"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from nia.crawler.models import CrawlConfig, FetchResult

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class AsyncFetcher:
    """整个爬取任务共享一个连接池；用 async with 管理生命周期。"""

    def __init__(self, config: CrawlConfig):
        self._config = config
        self._sem = asyncio.Semaphore(config.concurrency)
        self._js_sem = asyncio.Semaphore(config.js_concurrency)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncFetcher":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.request_timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=self._config.concurrency * 2,
                max_keepalive_connections=self._config.concurrency,
            ),
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, url: str) -> FetchResult:
        """抓取单页（信号量限流 + 重试）。use_js 时走浏览器池。"""
        start = time.monotonic()
        if self._config.use_js:
            result = await self._fetch_js(url)
            result.elapsed = time.monotonic() - start
            return result

        result = await self._fetch_http(url)

        # 启发式：httpx 正文过短 → 回退 JS 渲染
        if (
            self._config.js_fallback
            and (not result.success or len(result.html) < self._config.js_fallback_min_chars)
        ):
            logger.info(f"JS fallback for {url} (html={len(result.html)} chars)")
            js_result = await self._fetch_js(url)
            if js_result.success and len(js_result.html) >= len(result.html):
                result = js_result

        result.elapsed = time.monotonic() - start
        return result

    async def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        return await asyncio.gather(*(self.fetch(u) for u in urls))

    async def _fetch_http(self, url: str) -> FetchResult:
        assert self._client is not None
        async with self._sem:
            last_err = ""
            for attempt in range(self._config.max_retries + 1):
                try:
                    resp = await self._client.get(url)
                    if resp.status_code in _RETRY_STATUS and attempt < self._config.max_retries:
                        raise httpx.HTTPStatusError(
                            f"status {resp.status_code}", request=resp.request, response=resp
                        )
                    return FetchResult(
                        url=url,
                        final_url=str(resp.url),
                        html=resp.text,
                        status_code=resp.status_code,
                        success=resp.status_code < 400 and bool(resp.text),
                        error="" if resp.status_code < 400 else f"HTTP {resp.status_code}",
                    )
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
                    last_err = str(e)
                    if attempt < self._config.max_retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
            return FetchResult(url=url, success=False, error=last_err or "fetch failed")

    async def _fetch_js(self, url: str) -> FetchResult:
        from nia.crawler.browser_pool import AsyncBrowserPool

        async with self._js_sem:
            data = await AsyncBrowserPool.fetch(url)
        return FetchResult(
            url=url,
            final_url=url,
            html=data.get("html", ""),
            status_code=data.get("status_code") or 0,
            success=bool(data.get("success")),
            error=data.get("error", ""),
            rendered_js=True,
        )
