"""异步抓取器 — 共享 httpx.AsyncClient + 信号量限流 + 退避重试 + 可选 JS 渲染。

安全与稳健性要点：
- 手动跟随重定向，**每一跳**都重新做 SSRF 校验（防 302 跳内网）；
- 发请求前做 DNS 解析校验（防 localtest.me / nip.io 之类）；
- Content-Type 白名单 + 流式读取字节上限（防 PDF/图片/解压炸弹撑爆内存）；
- 429 尊重 Retry-After，退避带抖动；
- 遵从 robots.txt，并按 crawl-delay / 单域名并发做礼貌限速。
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import httpx

from nia.crawler.models import CrawlConfig, FetchResult
from nia.crawler.robots import RobotsCache, origin_of
from nia.utils.url_safety import resolve_and_check

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
_REDIRECT_STATUS = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5

# 只处理文本类内容；其余（pdf/image/zip/octet-stream…）直接判定为不支持
_TEXT_CONTENT_TYPES = {
    "",
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "text/xml",
    "application/xml",
    "application/json",
}

# 进程级 robots 缓存（跨任务复用，减少重复请求）
_robots = RobotsCache()


class _RetryableStatus(Exception):
    def __init__(self, status: int, retry_after: float | None = None):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.retry_after = retry_after


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    return max(0.0, dt.timestamp() - time.time())


async def _read_capped(resp: httpx.Response, max_bytes: int) -> tuple[bytes, bool]:
    """流式读取响应体，超过 max_bytes 立即停止（返回 truncated=True）。"""
    buf = bytearray()
    truncated = False
    async for chunk in resp.aiter_bytes():
        if not chunk:
            continue
        remaining = max_bytes - len(buf)
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            buf.extend(chunk[:remaining])
            truncated = True
            break
        buf.extend(chunk)
    return bytes(buf), truncated


def _decode(body: bytes, resp: httpx.Response) -> str:
    encoding = resp.encoding or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")


class AsyncFetcher:
    """整个爬取任务共享一个连接池；用 async with 管理生命周期。"""

    def __init__(self, config: CrawlConfig):
        self._config = config
        self._sem = asyncio.Semaphore(config.concurrency)
        self._js_sem = asyncio.Semaphore(config.js_concurrency)
        self._domain_sems: dict[str, asyncio.Semaphore] = {}
        self._domain_last: dict[str, float] = {}
        self._domain_delay: dict[str, float] = {}
        self._domain_lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncFetcher":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.request_timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=max(self._config.concurrency * 2, 8),
                max_keepalive_connections=max(self._config.concurrency, 4),
            ),
            follow_redirects=False,  # 手动跟随，逐跳校验
            headers={
                "User-Agent": _UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── 礼貌限速 ──────────────────────────────────────────────────

    async def _domain_gate(self, url: str) -> asyncio.Semaphore:
        origin = origin_of(url) or url
        async with self._domain_lock:
            sem = self._domain_sems.get(origin)
            if sem is None:
                sem = asyncio.Semaphore(max(1, self._config.per_domain_concurrency))
                self._domain_sems[origin] = sem
            return sem

    async def _wait_domain_delay(self, url: str) -> None:
        origin = origin_of(url)
        if not origin:
            return
        delay = self._domain_delay.get(origin, 0.0)
        if delay <= 0:
            return
        last = self._domain_last.get(origin)
        if last is not None:
            wait = delay - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
        self._domain_last[origin] = time.monotonic()

    async def _robots_text(self, url: str) -> str | None:
        """抓取 robots.txt 原文（不复用 robots 检查，避免递归）。"""
        assert self._client is not None
        try:
            async with self._sem:
                resp = await self._client.get(url)
            if resp.status_code >= 400:
                return None
            return resp.text
        except Exception:
            return None

    async def _check_robots(self, url: str) -> tuple[bool, float]:
        if not self._config.respect_robots:
            return True, 0.0
        # 传 "*" 表示只应用 robots.txt 里的通配规则（标准做法）
        return await _robots.allowed(url, "*", self._robots_text)

    # ── 抓取 ──────────────────────────────────────────────────────

    async def fetch(self, url: str) -> FetchResult:
        """抓取单页（信号量限流 + 重试）。use_js 时走浏览器池。"""
        start = time.monotonic()
        result = await self._fetch_with_policy(url)
        result.elapsed = time.monotonic() - start
        return result

    async def _fetch_with_policy(self, url: str) -> FetchResult:
        try:
            allowed, delay = await self._check_robots(url)
        except Exception as e:  # robots 检查本身失败不应阻断抓取
            logger.debug("robots 检查异常 %s: %s", url, e)
            allowed, delay = True, 0.0

        origin = origin_of(url)
        if origin and delay:
            self._domain_delay[origin] = float(delay)

        if not allowed:
            return FetchResult(
                url=url,
                success=False,
                blocked_by_robots=True,
                error="robots.txt 禁止抓取该路径",
            )

        if self._config.use_js:
            return await self._fetch_js(url)

        result = await self._fetch_http(url)

        # 启发式：httpx 正文过短 → 回退 JS 渲染
        if (
            self._config.js_fallback
            and not result.blocked_by_robots
            and (not result.success or len(result.html) < self._config.js_fallback_min_chars)
        ):
            logger.info("JS fallback for %s (html=%d chars)", url, len(result.html))
            js_result = await self._fetch_js(url)
            if js_result.success and len(js_result.html) >= len(result.html):
                return js_result
        return result

    async def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        """并发抓取；单个 URL 崩溃不会拖垮整批。"""
        if not urls:
            return []
        raw = await asyncio.gather(*(self.fetch(u) for u in urls), return_exceptions=True)
        results: list[FetchResult] = []
        for url, item in zip(urls, raw):
            if isinstance(item, BaseException):
                logger.warning("fetch %s raised %s: %s", url, type(item).__name__, item)
                results.append(FetchResult(url=url, success=False, error=f"{type(item).__name__}: {item}"[:300]))
            else:
                results.append(item)
        return results

    async def _fetch_http(self, url: str) -> FetchResult:
        assert self._client is not None
        sem = await self._domain_gate(url)
        async with sem:
            async with self._sem:
                last_err = ""
                for attempt in range(self._config.max_retries + 1):
                    try:
                        await self._wait_domain_delay(url)
                        return await self._request_once(url)
                    except _RetryableStatus as e:
                        last_err = f"HTTP {e.status}"
                        if attempt < self._config.max_retries:
                            backoff = 0.5 * (2**attempt)
                            if e.retry_after:
                                backoff = max(backoff, min(e.retry_after, 30.0))
                            await asyncio.sleep(backoff + random.uniform(0, 0.3))
                    except (httpx.TimeoutException, httpx.TransportError) as e:
                        last_err = f"{type(e).__name__}: {e}"
                        if attempt < self._config.max_retries:
                            await asyncio.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                return FetchResult(url=url, success=False, error=last_err or "fetch failed")

    async def _request_once(self, url: str) -> FetchResult:
        """单次请求，手动跟随重定向并逐跳校验。"""
        assert self._client is not None
        current = url
        max_bytes = max(1024, int(self._config.max_content_bytes))

        for _hop in range(_MAX_REDIRECTS + 1):
            ok, reason = resolve_and_check(current)
            if not ok:
                return FetchResult(url=url, final_url=current, success=False, error=f"URL 被安全策略拦截: {reason}")

            async with self._client.stream("GET", current) as resp:
                if resp.status_code in _REDIRECT_STATUS:
                    location = resp.headers.get("location")
                    if not location:
                        return FetchResult(
                            url=url,
                            final_url=str(resp.url),
                            status_code=resp.status_code,
                            success=False,
                            error=f"重定向缺少 Location (HTTP {resp.status_code})",
                        )
                    nxt = urljoin(str(resp.url), location)
                    if nxt == current:
                        return FetchResult(url=url, final_url=current, success=False, error="重定向死循环")
                    current = nxt
                    continue

                if resp.status_code in _RETRY_STATUS:
                    raise _RetryableStatus(resp.status_code, _parse_retry_after(resp.headers.get("retry-after")))

                content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                if content_type not in _TEXT_CONTENT_TYPES:
                    return FetchResult(
                        url=url,
                        final_url=str(resp.url),
                        status_code=resp.status_code,
                        success=False,
                        content_type=content_type,
                        error=f"不支持的内容类型: {content_type}",
                    )

                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    return FetchResult(
                        url=url,
                        final_url=str(resp.url),
                        status_code=resp.status_code,
                        success=False,
                        content_type=content_type,
                        error=f"响应体过大: {declared} 字节（上限 {max_bytes}）",
                    )

                body, truncated = await _read_capped(resp, max_bytes)
                html = _decode(body, resp)
                if truncated:
                    logger.info("响应体超过上限已截断: %s (%d 字节)", current, max_bytes)
                return FetchResult(
                    url=url,
                    final_url=str(resp.url),
                    html=html,
                    status_code=resp.status_code,
                    success=resp.status_code < 400 and bool(html),
                    error="" if resp.status_code < 400 else f"HTTP {resp.status_code}",
                    content_type=content_type,
                    truncated=truncated,
                )

        return FetchResult(url=url, final_url=current, success=False, error=f"重定向次数超过 {_MAX_REDIRECTS}")

    async def _fetch_js(self, url: str) -> FetchResult:
        from nia.crawler.browser_pool import AsyncBrowserPool

        timeout = max(30.0, self._config.request_timeout * 2)
        async with self._js_sem:
            try:
                data = await asyncio.wait_for(AsyncBrowserPool.fetch(url), timeout=timeout)
            except asyncio.TimeoutError:
                return FetchResult(url=url, success=False, error=f"JS 渲染超时（{timeout:.0f}s）", rendered_js=True)
        return FetchResult(
            url=url,
            final_url=data.get("final_url") or url,
            html=data.get("html", ""),
            status_code=data.get("status_code") or 0,
            success=bool(data.get("success")),
            error=data.get("error", ""),
            rendered_js=True,
        )
