"""爬取引擎 — 编排 并发批量 / BFS 整站 抓取 + 提取。

v3 变更：
- **HTML 磁盘缓存**：命中（24h TTL）的 URL 不再打网络，演示/定期采集零请求；
- **流水线化**：批 N 的 LLM 结构化提取与批 N+1 的抓取**重叠执行**
  （旧实现等整批提取完才继续下一批抓取，抓取槽位在提取期间全部空转）。
  提取任务有并发上限（extractor 内部信号量），结束时统一 gather 兜底。
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
import time
from typing import Awaitable, Callable

from nia.crawler.extractor import StructuredExtractor
from nia.crawler.fetcher import AsyncFetcher
from nia.crawler.frontier import URLFrontier
from nia.crawler.html_cache import HtmlDiskCache
from nia.crawler.models import CrawlConfig, FetchResult, Finding, PageContent
from nia.crawler.parser import parse_html
from nia.utils.config import Config

logger = logging.getLogger(__name__)

ProgressCb = Callable[[dict], Awaitable[None]]


class CrawlEngine:
    """无状态编排器；每次 crawl() 自管连接池生命周期。"""

    def __init__(self, config: CrawlConfig | None = None):
        self._config = config or CrawlConfig()
        self._html_cache = HtmlDiskCache() if Config.CRAWL_HTML_CACHE_TTL > 0 else None

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
        dup_count = 0
        page_errors = 0
        cache_hits = 0
        extraction_tasks: list[asyncio.Task] = []

        async def emit(event: str, **data):
            if progress_cb:
                await progress_cb({"event": event, **data})

        async def extract_and_emit(batch_pages: list[PageContent]) -> None:
            nonlocal findings
            try:
                batch_findings = await extractor.extract_many(batch_pages, instruction)
                for f in batch_findings:
                    if f.data:
                        findings.append(f)
                        await emit("finding", url=f.url, title=f.title, fields=len(f.data), data=f.data)
            except Exception as e:
                logger.warning("batch extraction failed: %s", e)

        await emit("start", seeds=seeds, max_pages=cfg.max_pages, max_depth=cfg.max_depth)

        async with AsyncFetcher(cfg) as fetcher:
            extractor = StructuredExtractor(cfg) if instruction else None
            try:
                while frontier.has_next() and len(pages) < cfg.max_pages:
                    batch = frontier.pop_batch(cfg.concurrency)
                    if not batch:
                        break

                    # ── HTML 磁盘缓存：命中直接构造 FetchResult，未命中才联网 ──
                    to_fetch: list[tuple[str, int]] = []
                    results_by_url: dict[str, FetchResult] = {}
                    if self._html_cache:
                        for url, depth in batch:
                            cached = self._html_cache.get(url)
                            if cached:
                                cache_hits += 1
                                results_by_url[url] = FetchResult(
                                    url=url,
                                    final_url=cached.get("final_url") or url,
                                    html=cached.get("html", ""),
                                    status_code=200,
                                    success=True,
                                    from_cache=True,
                                )
                            else:
                                to_fetch.append((url, depth))
                    else:
                        to_fetch = list(batch)
                    if to_fetch:
                        fetch_results = await fetcher.fetch_many([u for u, _ in to_fetch])
                        for (url, _depth), fr in zip(to_fetch, fetch_results):
                            results_by_url[url] = fr
                            if fr.success and not fr.rendered_js and self._html_cache:
                                self._html_cache.put(url, fr.final_url or url, fr.html)

                    batch_pages: list[PageContent] = []
                    for (url, depth) in batch:
                        fr = results_by_url.get(url)
                        if fr is None or not fr.success:
                            page_errors += 1
                            await emit(
                                "page_error",
                                url=url,
                                error=fr.error if fr else "未获取到响应",
                                blocked_by_robots=fr.blocked_by_robots if fr else False,
                            )
                            continue

                        page = parse_html(fr.html, fr.final_url or url)

                        # 正文去重：镜像页/分页参数变体不再重复提取与存储
                        digest = hashlib.sha1(page.text.encode("utf-8", "ignore")).hexdigest()
                        if digest in seen_content:
                            dup_count += 1
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
                            frontier.add_many(page.links, depth + 1, parent=page.url, anchors=page.anchors)

                        await emit(
                            "page",
                            url=page.url,
                            title=page.title,
                            depth=depth,
                            links=len(page.links),
                            chars=len(page.text),
                            truncated=fr.truncated,
                            rendered_js=fr.rendered_js,
                            from_cache=fr.from_cache,
                            elapsed=round(fr.elapsed, 2),
                            visited=frontier.visited_count,
                            queued=frontier.queued_count,
                        )

                        if len(pages) >= cfg.max_pages:
                            break

                    # ── 流水线：提取投递为后台任务，与下一批抓取重叠 ──
                    if extractor and batch_pages:
                        extraction_tasks.append(asyncio.create_task(extract_and_emit(batch_pages)))
            finally:
                if extractor:
                    await extractor.aclose()
                if extraction_tasks:
                    await asyncio.gather(*extraction_tasks, return_exceptions=True)

        stats = {
            "pages_crawled": len(pages),
            "findings": len(findings),
            "page_errors": page_errors,
            "duplicates": dup_count,
            "skipped": frontier.skipped,
            "cache_hits": cache_hits,
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
