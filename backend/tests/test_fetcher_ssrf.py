"""crawler.fetcher：SSRF 总闸 —— httpx 路径与 JS 渲染路径都必须在入口被拦截。

关键回归：旧版 use_js=True 时 URL 直接进浏览器池、完全绕过 resolve_and_check。
修复后总闸在 _fetch_with_policy 入口（robots 检查之前），所有路径共用。
"""

from __future__ import annotations

import asyncio

from nia.crawler.fetcher import AsyncFetcher
from nia.crawler.models import CrawlConfig


def _cfg(**kw) -> CrawlConfig:
    return CrawlConfig(request_timeout=3.0, max_retries=0, respect_robots=False, **kw)


def test_http_path_blocks_internal():
    async def run():
        async with AsyncFetcher(_cfg()) as f:
            return await f.fetch("http://127.0.0.1:6379/")

    r = asyncio.run(run())
    assert r.success is False
    assert "安全策略拦截" in r.error


def test_js_path_blocks_internal_before_browser():
    """use_js=True：内网地址必须在进入浏览器池之前被拒（旧版完全绕过校验）。"""
    async def run():
        async with AsyncFetcher(_cfg(use_js=True)) as f:
            return await f.fetch("http://127.0.0.1:8500/")

    r = asyncio.run(run())
    assert r.success is False
    assert "安全策略拦截" in r.error
    # 浏览器路径被拦下后 rendered_js 不应为真（根本没有发起渲染）
    assert r.rendered_js is False


def test_localhost_blocked_by_blacklist():
    async def run():
        async with AsyncFetcher(_cfg()) as f:
            return await f.fetch("http://localhost:8000/api/health")

    r = asyncio.run(run())
    assert r.success is False
    assert "安全策略拦截" in r.error


def test_metadata_endpoint_blocked():
    async def run():
        async with AsyncFetcher(_cfg()) as f:
            return await f.fetch("http://169.254.169.254/latest/meta-data/")

    r = asyncio.run(run())
    assert r.success is False
    assert "安全策略拦截" in r.error
