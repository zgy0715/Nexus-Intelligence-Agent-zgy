"""爬取引擎 — 编排 并发批量 / BFS 整站 抓取 + 提取。"""

from __future__ import annotations

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
        pages: list[PageContent] = []
        findings: list[Finding] = []

        async def emit(event: str, **data):
            if progress_cb:
                await progress_cb({"event": event, **data})

        await emit("start", seeds=seeds, max_pages=cfg.max_pages, max_depth=cfg.max_depth)

        async with AsyncFetcher(cfg) as fetcher:
            extractor = StructuredExtractor(cfg) if instruction else None
            try:
                while frontier.has_next() and frontier.visited_count <= cfg.max_pages:
                    batch = frontier.pop_batch(cfg.concurrency)
                    if not batch:
                        break
                    fetch_results = await fetcher.fetch_many([u for u, _ in batch])

                    batch_pages: list[PageContent] = []
                    for (url, depth), fr in zip(batch, fetch_results):
                        if not fr.success:
                            await emit("page_error", url=url, error=fr.error)
                            continue
                        page = parse_html(fr.html, fr.final_url or url)
                        pages.append(page)
                        batch_pages.append(page)
                        if on_page is not None:
                            try:
                                await on_page(page)
                            except Exception as e:
                                logger.warning(f"on_page sink failed for {page.url}: {e}")
                        if depth < cfg.max_depth:
                            frontier.add_many(page.links, depth + 1, parent=page.url)
                        await emit(
                            "page",
                            url=page.url,
                            title=page.title,
                            depth=depth,
                            links=len(page.links),
                            chars=len(page.text),
                            elapsed=round(fr.elapsed, 2),
                            visited=frontier.visited_count,
                        )

                    if extractor and batch_pages:
                        batch_findings = await extractor.extract_many(batch_pages, instruction)
                        for f in batch_findings:
                            if f.data:
                                findings.append(f)
                                await emit("finding", url=f.url, title=f.title, fields=len(f.data))
            finally:
                if extractor:
                    await extractor._cache.close()

        stats = {
            "pages_crawled": len(pages),
            "findings": len(findings),
            "elapsed": round(time.monotonic() - start, 2),
        }
        await emit("done", **stats)
        return {
            "pages": [{"url": p.url, "title": p.title, "chars": len(p.text), "links": len(p.links)} for p in pages],
            "findings": [f.to_dict() for f in findings],
            "stats": stats,
        }

    async def crawl_urls(
        self, urls: list[str], instruction: str = "", progress_cb: ProgressCb | None = None
    ) -> dict:
        """批量并发抓取一组 URL（不跟随链接）。"""
        # 复制配置并禁用深度/同域，仅抓给定 URL
        cfg = CrawlConfig(
            max_depth=0,
            max_pages=max(len(urls), self._config.max_pages),
            same_domain_only=False,
            concurrency=self._config.concurrency,
            llm_concurrency=self._config.llm_concurrency,
            use_js=self._config.use_js,
        )
        engine = CrawlEngine(cfg)
        return await engine.crawl(urls, instruction, progress_cb)
