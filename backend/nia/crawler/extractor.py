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

# 提示词版本：改动 _SYSTEM / 用户模板时要 +1，让旧缓存自动失效
PROMPT_VERSION = "v2"

# 送入 LLM 的正文上限
_MAX_CONTENT = 8000


class StructuredExtractor:
    def __init__(
        self,
        config: CrawlConfig,
        llm: LLMClient | None = None,
        cache: ExtractCache | None = None,
    ):
        self._config = config
        self._llm = llm or LLMClient()
        self._cache = cache or ExtractCache(ttl=config.cache_ttl, version=PROMPT_VERSION)
        self._sem = asyncio.Semaphore(max(1, config.llm_concurrency))
        self._owns_llm = llm is None

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
                content = page.text[:_MAX_CONTENT]
                data = await self._llm.achat_json([
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": (
                        # 用显式分隔符包裹页面内容，降低提示词注入的影响
                        f"Instruction: {instruction}\n\n"
                        f"Page title: {page.title}\nURL: {page.url}\n\n"
                        "<<<PAGE_TEXT_START>>>\n"
                        f"{content}\n"
                        "<<<PAGE_TEXT_END>>>\n\n"
                        "Return the extracted data as a JSON object."
                    )},
                ], temperature=0.1)
            except Exception as e:
                logger.warning("extract failed for %s: %s", page.url, e)
                return Finding(url=page.url, title=page.title, data={}, summary=f"提取失败: {e}"[:200])

        # achat_json 解析失败时返回 {}，旧实现把这个空结果当成功写进缓存，
        # 于是一次坏响应会污染该 URL 长达 cache_ttl（默认 7 天）。这里不缓存空结果。
        if not data:
            logger.info("extract returned empty result for %s (not cached)", page.url)
            return Finding(url=page.url, title=page.title, data={}, summary="模型未返回可解析的 JSON")

        finding = Finding(url=page.url, title=page.title, data=data, summary="")
        await self._cache.set(page.url, instruction, {"data": data, "summary": ""})
        return finding

    async def extract_many(self, pages: list[PageContent], instruction: str) -> list[Finding]:
        if not pages:
            return []
        results = await asyncio.gather(
            *(self.extract(p, instruction) for p in pages), return_exceptions=True
        )
        findings: list[Finding] = []
        for page, item in zip(pages, results):
            if isinstance(item, BaseException):
                logger.warning("extract raised for %s: %s", page.url, item)
                findings.append(
                    Finding(url=page.url, title=page.title, data={}, summary=f"提取异常: {item}"[:200])
                )
            else:
                findings.append(item)
        return findings

    async def aclose(self) -> None:
        """释放缓存连接；LLM 客户端若是自建的也一并关闭。"""
        try:
            await self._cache.close()
        except Exception as e:
            logger.debug("extractor cache close error: %s", e)
        if self._owns_llm:
            try:
                await self._llm.aclose()
            except Exception as e:
                logger.debug("extractor llm close error: %s", e)
