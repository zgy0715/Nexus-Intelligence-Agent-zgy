"""自主爬取 Agent — 原生 tool-calling 循环（async generator，逐步 yield 事件）。"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from nia.ai.llm_client import LLMClient, loads_json_loose
from nia.crawler.extractor import StructuredExtractor
from nia.crawler.fetcher import AsyncFetcher
from nia.crawler.models import CrawlConfig
from nia.agent.events import AgentEvent
from nia.agent.prompts import summary_prompt, system_prompt
from nia.agent.state import AgentState
from nia.agent.tools import TOOLS, ToolExecutor

logger = logging.getLogger(__name__)

_REASON_TEXT = {
    "finished": "目标已达成",
    "budget_exhausted": "预算（页面/步数）已用尽",
    "cancelled": "用户取消",
    "no_progress": "连续多步无新发现",
    "error": "运行出错",
}


class AutonomousCrawlAgent:
    def __init__(self, state: AgentState, config: CrawlConfig | None = None):
        self.state = state
        self.config = config or CrawlConfig()
        self.llm = LLMClient()

    async def run(self) -> AsyncGenerator[AgentEvent, None]:
        st = self.state
        yield AgentEvent("start", {"goal": st.goal, "seeds": st.seeds,
                                   "budget_pages": st.budget_pages, "budget_steps": st.budget_steps})

        messages: list = [
            {"role": "system", "content": system_prompt(st.goal, st.budget_pages, st.budget_steps)},
            {"role": "user", "content": (
                f"目标：{st.goal}\n\n种子 URL：\n" + "\n".join(f"- {u}" for u in st.seeds)
                + "\n\n请从种子页面开始探索。"
            )},
        ]

        no_tool_streak = 0
        try:
            async with AsyncFetcher(self.config) as fetcher:
                extractor = StructuredExtractor(self.config)
                executor = ToolExecutor(st, self.config, fetcher, extractor, self.llm)

                while st.budget_left() and not st.cancel_flag.is_set():
                    st.steps_used += 1
                    findings_before = len(st.findings)
                    pages_before = st.pages_used

                    try:
                        msg = await self.llm.achat_tools(messages, tools=TOOLS, tool_choice="auto")
                    except Exception as e:
                        logger.error(f"agent LLM call failed: {e}")
                        yield AgentEvent("error", {"message": f"LLM 调用失败: {str(e)[:200]}"})
                        st.status = "error"
                        st.error = str(e)[:300]
                        break

                    messages.append(msg)
                    if msg.get("content"):
                        yield AgentEvent("thought", {"text": msg["content"]})

                    tool_calls = msg.get("tool_calls") or []
                    if not tool_calls:
                        no_tool_streak += 1
                        if no_tool_streak >= 2:
                            # 模型不肯调用工具 → 强制收尾
                            break
                        messages.append({"role": "user",
                                         "content": "请调用一个工具继续（fetch_page/crawl_links/extract_data/record_finding），目标达成时调用 finish。"})
                        continue
                    no_tool_streak = 0

                    finished = False
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        name = fn.get("name", "")
                        args = loads_json_loose(fn.get("arguments", "") or "{}") or {}
                        yield AgentEvent("action", {"tool": name, "args": args})

                        if name == "finish":
                            st.status = "finished"
                            finished = True
                            break

                        result = await executor.dispatch(name, args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": _truncate_json(result),
                        })
                        # 把新发现透出给前端
                        if name in ("extract_data", "record_finding") and result.get("is_new"):
                            f = st.findings[-1] if st.findings else {}
                            yield AgentEvent("finding", {
                                "title": f.get("title", ""), "url": f.get("url", ""),
                                "data": f.get("data"), "content": f.get("content", ""),
                            })
                        yield AgentEvent("observation", {"tool": name, "result": _compact(result)})

                    yield AgentEvent("progress", {
                        "pages_used": st.pages_used, "budget_pages": st.budget_pages,
                        "steps_used": st.steps_used, "budget_steps": st.budget_steps,
                        "findings": len(st.findings), "visited": len(st.visited),
                    })

                    if finished:
                        break

                    # 无进展计数
                    if len(st.findings) == findings_before and st.pages_used == pages_before:
                        st.no_progress_streak += 1
                    else:
                        st.no_progress_streak = 0
                    if st.no_progress_streak >= st.no_progress_limit:
                        st.status = "no_progress"
                        break

                    if not st.budget_left():
                        messages.append({"role": "user", "content": "预算即将耗尽，请立即调用 finish 汇总成果。"})

        except Exception as e:
            logger.exception("agent run crashed")
            st.status = "error"
            st.error = str(e)[:300]
            yield AgentEvent("error", {"message": str(e)[:200]})

        # 收尾：确定状态 + 生成报告
        if st.cancel_flag.is_set() and st.status == "running":
            st.status = "cancelled"
        elif st.status == "running":
            st.status = "budget_exhausted" if not st.budget_left() else "finished"

        reason = _REASON_TEXT.get(st.status, st.status)
        yield AgentEvent("progress", {
            "pages_used": st.pages_used, "budget_pages": st.budget_pages,
            "steps_used": st.steps_used, "budget_steps": st.budget_steps,
            "findings": len(st.findings), "visited": len(st.visited),
        })

        report = await self._generate_report(reason)
        st.report = report
        yield AgentEvent("finish", {
            "status": st.status, "reason": reason, "report": report,
            "findings": st.findings, "pages_used": st.pages_used, "steps_used": st.steps_used,
        })

    async def _generate_report(self, reason: str) -> str:
        try:
            return await self.llm.achat(
                [{"role": "user", "content": summary_prompt(self.state.goal, self.state.findings, reason)}],
                temperature=0.3, max_tokens=2000,
            )
        except Exception as e:
            logger.warning(f"report generation failed: {e}")
            # 兜底：列出发现
            lines = [f"## 收集到 {len(self.state.findings)} 条发现（报告生成失败：{e}）"]
            for i, f in enumerate(self.state.findings, 1):
                lines.append(f"{i}. {f.get('title','')} — {f.get('url','')}")
            return "\n".join(lines)


def _truncate_json(obj: dict, limit: int = 6000) -> str:
    import json
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"


def _compact(result: dict) -> dict:
    """给前端的观察结果做瘦身（去掉长列表/大字段）。"""
    out = {}
    for k, v in result.items():
        if isinstance(v, list):
            out[k] = f"[{len(v)} 项]"
        elif isinstance(v, str) and len(v) > 300:
            out[k] = v[:300] + "..."
        else:
            out[k] = v
    return out
