"""爬取引擎 — 编排 并发批量 / BFS 整站 抓取 + 提取。"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import time
from typing import Awaitable, Callable

from nia.crawler.extractor import StructuredExtractor
from nia.crawler.fetcher import AsyncFetcher
from nia.crawler.frontier import URLFrontier
from nia.crawler.models import CrawlConfig, Finding, PageContent
from nia.crawler.parser import parse_html

logger = logging.getLogger(__name__)

ProgressCb = Callable[[dict], Awaitable[None]]


class CrawlEngine:
    """无状态编排器；每次 crawl() 自管连接池生命周期。"""

    def __init__(self, config: CrawlConfig | None = None):
        self._config = config or CrawlConfig()

    async def crawl(
        self,
        seeds: list[str],
        instruction: str = "",
        progress_cb: ProgressCb | None = None,
        on_page: Callable[[PageContent], Awaitable[None]] | None = None,
    ) -> dict:
        """BFS 整站/批量抓取。instruction 非空时对每页做结构化提取。

        on_page: 每抓到一个成功页面时回调（传完整 PageContent，用于持久化/索引）。
        返回 {pages: [...], findings: [...], stats: {...}}。
        """
        cfg = self._config
        start = time.monotonic()
        frontier = URLFrontier(cfg, seeds)
        # 只保留轻量摘要（不持有整页 HTML），返回值和 stats 都只需要这些字段
        pages: list[dict] = []
        findings: list[Finding] = []
        seen_content: set[str] = set()
        page_errors = 0

        async def emit(event: str, **data):
            if progress_cb:
                await progress_cb({"event": event, **data})

        await emit("start", seeds=seeds, max_pages=cfg.max_pages, max_depth=cfg.max_depth)

        async with AsyncFetcher(cfg) as fetcher:
            extractor = StructuredExtractor(cfg) if instruction else None
            try:
                while frontier.has_next() and len(pages) < cfg.max_pages:
                    batch = frontier.pop_batch(cfg.concurrency)
                    if not batch:
                        break
                    fetch_results = await fetcher.fetch_many([u for u, _ in batch])

                    batch_pages: list[PageContent] = []
                    for (url, depth), fr in zip(batch, fetch_results):
                        if not fr.success:
                            page_errors += 1
                            await emit(
                                "page_error",
                                url=url,
                                error=fr.error,
                                blocked_by_robots=fr.blocked_by_robots,
                            )
                            continue

                        page = parse_html(fr.html, fr.final_url or url)

                        # 正文去重：镜像页/分页参数变体不再重复提取与存储
                        digest = hashlib.sha1(page.text.encode("utf-8", "ignore")).hexdigest()
                        if digest in seen_content:
                            await emit("page_duplicate", url=page.url, title=page.title)
                            continue
                        seen_content.add(digest)

                        pages.append(
                            {
                                "url": page.url,
                                "title": page.title,
                                "chars": len(page.text),
                                "links": len(page.links),
                                "depth": depth,
                                "rendered_js": fr.rendered_js,
                            }
                        )
                        batch_pages.append(page)

                        if on_page is not None:
                            try:
                                await on_page(page)
                            except Exception as e:
                                logger.warning("on_page sink failed for %s: %s", page.url, e)

                        if depth < cfg.max_depth:
                            frontier.add_many(page.links, depth + 1, parent=page.url)

                        await emit(
                            "page",
                            url=page.url,
                            title=page.title,
                            depth=depth,
                            links=len(page.links),
                            chars=len(page.text),
                            truncated=fr.truncated,
                            rendered_js=fr.rendered_js,
                            elapsed=round(fr.elapsed, 2),
                            visited=frontier.visited_count,
                            queued=frontier.queued_count,
                        )

                        if len(pages) >= cfg.max_pages:
                            break

                    if extractor and batch_pages:
                        batch_findings = await extractor.extract_many(batch_pages, instruction)
                        for f in batch_findings:
                            if f.data:
                                findings.append(f)
                                await emit(
                                    "finding",
                                    url=f.url,
                                    title=f.title,
                                    fields=len(f.data),
                                    data=f.data,
                                )
            finally:
                if extractor:
                    await extractor.aclose()

        stats = {
            "pages_crawled": len(pages),
            "findings": len(findings),
            "page_errors": page_errors,
            "duplicates": len(seen_content) - len(pages),
            "skipped": frontier.skipped,
            "elapsed": round(time.monotonic() - start, 2),
        }
        await emit("done", **stats)
        return {
            "pages": pages,
            "findings": [f.to_dict() for f in findings],
            "stats": stats,
        }

    async def crawl_urls(
        self,
        urls: list[str],
        instruction: str = "",
        progress_cb: ProgressCb | None = None,
        on_page: Callable[[PageContent], Awaitable[None]] | None = None,
    ) -> dict:
        """批量并发抓取一组 URL（不跟随链接）。

        旧实现会重新构造一个 CrawlConfig，把 request_timeout / max_retries /
        cache_ttl / js_fallback 等字段全部丢掉；这里用 dataclasses.replace 复制，
        只覆盖真正需要改的三个字段。
        """
        cfg = dataclasses.replace(
            self._config,
            max_depth=0,
            max_pages=len(urls),
            same_domain_only=False,
        )
        engine = CrawlEngine(cfg)
        return await engine.crawl(urls, instruction, progress_cb, on_page)
