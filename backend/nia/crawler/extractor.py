"""结构化提取器 — 并发 LLM 提取 + 缓存。"""

from __future__ import annotations

import asyncio
import logging

from nia.ai.llm_client import LLMClient
from nia.crawler.cache import ExtractCache
from nia.crawler.models import CrawlConfig, Finding, PageContent

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a precise web data extraction assistant. "
    "Extract data from the page text according to the user's instruction. "
    "Return ONLY a valid JSON object with the extracted fields. "
    "If a field is absent, use null. Respond in the same language as the content."
)


class StructuredExtractor:
    def __init__(
        self,
        config: CrawlConfig,
        llm: LLMClient | None = None,
        cache: ExtractCache | None = None,
    ):
        self._config = config
        self._llm = llm or LLMClient()
        self._cache = cache or ExtractCache(ttl=config.cache_ttl)
        self._sem = asyncio.Semaphore(config.llm_concurrency)

    async def extract(self, page: PageContent, instruction: str) -> Finding:
        if not instruction or not page.text:
            return Finding(url=page.url, title=page.title, data={}, summary="")

        cached = await self._cache.get(page.url, instruction)
        if cached is not None:
            return Finding(
                url=page.url,
                title=page.title,
                data=cached.get("data", {}),
                summary=cached.get("summary", ""),
            )

        async with self._sem:
            try:
                content = page.text[:8000]
                data = await self._llm.achat_json([
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": (
                        f"Instruction: {instruction}\n\n"
                        f"Page title: {page.title}\nURL: {page.url}\n\n"
                        f"Page text:\n{content}\n\n"
                        "Return the extracted data as a JSON object."
                    )},
                ], temperature=0.1)
            except Exception as e:
                logger.warning(f"extract failed for {page.url}: {e}")
                return Finding(url=page.url, title=page.title, data={}, summary=f"提取失败: {e}")

        finding = Finding(url=page.url, title=page.title, data=data, summary="")
        await self._cache.set(page.url, instruction, {"data": data, "summary": ""})
        return finding

    async def extract_many(self, pages: list[PageContent], instruction: str) -> list[Finding]:
        return await asyncio.gather(*(self.extract(p, instruction) for p in pages))
