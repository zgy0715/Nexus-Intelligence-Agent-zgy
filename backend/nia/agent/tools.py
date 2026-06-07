"""Agent 工具集 — OpenAI tools schema + 异步实现 + 预算拦截。"""

from __future__ import annotations

import logging

from nia.ai.llm_client import LLMClient
from nia.crawler.extractor import StructuredExtractor
from nia.crawler.fetcher import AsyncFetcher
from nia.crawler.models import CrawlConfig, PageContent
from nia.crawler.parser import parse_html
from nia.agent.state import AgentState
from nia.utils.url_safety import normalize_url

logger = logging.getLogger(__name__)

# 给 LLM 的工具定义（finish 也声明，便于模型在该调用时调用）
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "抓取并快速理解一个网页，返回标题、内容摘要与候选链接。用于探索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要抓取的网页 URL"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crawl_links",
            "description": "并发抓取并摘要一组网页（最多 8 个），用于批量探索相关链接。",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要批量抓取的 URL 列表（最多 8 个）",
                    }
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_data",
            "description": "从某个网页按指令提取结构化数据，并自动记录为一条发现。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "instruction": {"type": "string", "description": "提取什么（如：标题、日期、作者、要点）"},
                },
                "required": ["url", "instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_finding",
            "description": "把你综合得到的有价值信息记录为一条发现。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "url": {"type": "string", "description": "来源 URL（可选）"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "目标已充分达成或无更多可探索内容时调用，结束任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "对成果的简短总结"}
                },
                "required": ["summary"],
            },
        },
    },
]

_MAX_BATCH = 8
_MAX_CANDIDATE_LINKS = 20


class ToolExecutor:
    """持有爬取资源，执行 Agent 工具调用。"""

    def __init__(
        self,
        state: AgentState,
        config: CrawlConfig,
        fetcher: AsyncFetcher,
        extractor: StructuredExtractor,
        llm: LLMClient,
    ):
        self.state = state
        self.config = config
        self.fetcher = fetcher
        self.extractor = extractor
        self.llm = llm
        self._pages: dict[str, PageContent] = {}  # 归一化 url -> 已抓取页面

    # ── 内部：抓取+解析（带缓存与预算登记） ──────────────────────

    async def _get_page(self, url: str) -> PageContent | None:
        norm = normalize_url(url)
        if not norm:
            return None
        if norm in self._pages:
            return self._pages[norm]
        fr = await self.fetcher.fetch(norm)
        self.state.visited.add(norm)
        self.state.pages_used += 1
        if not fr.success:
            return None
        page = parse_html(fr.html, fr.final_url or norm)
        self._pages[norm] = page
        return page

    async def _summarize(self, page: PageContent) -> str:
        if not page.text:
            return ""
        try:
            return await self.llm.achat([
                {"role": "system", "content": "用 2-3 句话概括网页的核心内容，使用与内容相同的语言。"},
                {"role": "user", "content": f"标题：{page.title}\n\n内容：\n{page.text[:4000]}"},
            ], temperature=0.2, max_tokens=300)
        except Exception as e:
            logger.debug(f"summarize failed: {e}")
            return ""

    # ── 工具实现 ──────────────────────────────────────────────────

    async def fetch_page(self, url: str) -> dict:
        page = await self._get_page(url)
        if page is None:
            return {"ok": False, "error": "抓取失败或 URL 无效", "url": url}
        summary = await self._summarize(page)
        return {
            "ok": True,
            "url": page.url,
            "title": page.title,
            "summary": summary,
            "num_links": len(page.links),
            "candidate_links": page.links[:_MAX_CANDIDATE_LINKS],
            "chars": len(page.text),
        }

    async def crawl_links(self, urls: list[str]) -> dict:
        urls = [u for u in (urls or []) if u][:_MAX_BATCH]
        # 过滤已访问
        fresh = [u for u in urls if (normalize_url(u) or u) not in self.state.visited]
        if not fresh:
            return {"ok": True, "pages": [], "note": "这些链接都已访问过"}
        pages = []
        for u in fresh:
            page = await self._get_page(u)
            if page is None:
                pages.append({"url": u, "ok": False})
                continue
            summary = await self._summarize(page)
            pages.append({
                "url": page.url,
                "title": page.title,
                "summary": summary,
                "num_links": len(page.links),
                "candidate_links": page.links[:10],
            })
        return {"ok": True, "pages": pages}

    async def extract_data(self, url: str, instruction: str) -> dict:
        page = await self._get_page(url)
        if page is None:
            return {"ok": False, "error": "抓取失败或 URL 无效", "url": url}
        finding = await self.extractor.extract(page, instruction)
        is_new = self.state.add_finding({
            "url": finding.url,
            "title": finding.title,
            "data": finding.data,
        })
        return {"ok": True, "url": finding.url, "title": finding.title, "data": finding.data, "is_new": is_new}

    async def record_finding(self, title: str, content: str, url: str = "") -> dict:
        is_new = self.state.add_finding({"url": url, "title": title, "content": content})
        return {"ok": True, "recorded": True, "is_new": is_new}

    # ── 派发 ──────────────────────────────────────────────────────

    async def dispatch(self, name: str, args: dict) -> dict:
        """执行工具调用。抓取类工具会先做预算检查。"""
        fetch_tools = {"fetch_page", "crawl_links", "extract_data"}
        if name in fetch_tools and not self.state.budget_left():
            return {"ok": False, "budget_exhausted": True,
                    "message": "页面/步数预算已用尽，请立即调用 finish 汇总。"}
        try:
            if name == "fetch_page":
                return await self.fetch_page(args.get("url", ""))
            if name == "crawl_links":
                return await self.crawl_links(args.get("urls", []))
            if name == "extract_data":
                return await self.extract_data(args.get("url", ""), args.get("instruction", ""))
            if name == "record_finding":
                return await self.record_finding(
                    args.get("title", ""), args.get("content", ""), args.get("url", "")
                )
            return {"ok": False, "error": f"未知工具: {name}"}
        except Exception as e:
            logger.warning(f"tool {name} error: {e}")
            return {"ok": False, "error": str(e)[:300]}
