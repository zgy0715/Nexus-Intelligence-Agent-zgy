"""自主爬取 Agent — 原生 tool-calling 循环（async generator，逐步 yield 事件）。

v3 变更：
- **上下文工程**：工具结果经 `truncate_tool_result` 结构化截断；历史超过
  token 预算时由 ContextManager 滚动压缩（emit `compaction` 事件），
  摘要块过大时用辅助模型（本地 Ollama）二次合并。
- **并行工具执行**：同一响应里的多个工具调用并发派发（`dispatch_many`），
  finish/取消仍走串行特殊路径。
- **模型路由**：主模型（DeepSeek）只做推理/报告；后台杂事路由到辅助模型。
- **领域记忆**：启动时注入同站点历史经验，收尾时写回（Redis）。
- **usage 透出**：progress 事件携带累计 token 与估算上下文占用。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from nia.ai.llm_client import LLMClient, loads_json_loose
from nia.crawler.extractor import StructuredExtractor
from nia.crawler.fetcher import AsyncFetcher
from nia.crawler.models import CrawlConfig
from nia.agent.context import (
    ContextManager,
    estimate_messages_tokens,
    summarize_args,
    summarize_result,
    truncate_tool_result,
)
from nia.agent.events import AgentEvent
from nia.agent.memory import AgentMemory, domains_of
from nia.agent.prompts import summary_prompt, system_prompt
from nia.agent.state import AgentState
from nia.agent.tools import TOOL_REGISTRY, ToolExecutor
from nia.utils.config import Config

logger = logging.getLogger(__name__)

_REASON_TEXT = {
    "finished": "目标已达成",
    "budget_exhausted": "预算（页面/步数）已用尽",
    "cancelled": "用户取消",
    "no_progress": "连续多步无新发现",
    "error": "运行出错",
}

_TOOL_RESULT_LIMIT = 6000

# 给 LLM 的 tools schema（由 Pydantic 参数模型自动生成，见 tools.py）
AGENT_TOOLS = [TOOL_REGISTRY[n].openai_schema() for n in
               ("fetch_page", "crawl_links", "extract_data", "record_finding", "finish")]


class AutonomousCrawlAgent:
    def __init__(self, state: AgentState, config: CrawlConfig | None = None):
        self.state = state
        self.config = config or CrawlConfig()
        self.llm = LLMClient()
        self.ctx = ContextManager()
        self.memory = AgentMemory()

    async def run(self) -> AsyncGenerator[AgentEvent, None]:
        st = self.state
        try:
            async for event in self._run_inner():
                yield event
        finally:
            # 无论正常结束、异常还是消费方提前断开，都要释放 HTTP 连接池
            try:
                await self.llm.aclose()
            except Exception as e:  # pragma: no cover - 关闭失败不应掩盖真实错误
                logger.debug(f"llm close failed: {e}")

    async def _run_inner(self) -> AsyncGenerator[AgentEvent, None]:
        st = self.state

        # 领域记忆：注入同站点历史经验（Redis 不可用时为空串，无副作用）
        seed_domains = domains_of(st.seeds)
        memory_hints = await self.memory.load_hints(seed_domains)
        if memory_hints:
            logger.info(f"agent memory hints injected for {seed_domains}")

        yield AgentEvent("start", {"goal": st.goal, "seeds": st.seeds,
                                   "budget_pages": st.budget_pages, "budget_steps": st.budget_steps})

        messages: list = [
            {"role": "system", "content": system_prompt(st.goal, st.budget_pages, st.budget_steps, memory_hints)},
            {"role": "user", "content": (
                f"目标：{st.goal}\n\n种子 URL：\n" + "\n".join(f"- {u}" for u in st.seeds)
                + "\n\n请从种子页面开始探索。"
            )},
        ]

        no_tool_streak = 0
        agent_summary = ""
        llm_timeout = max(30.0, Config.LLM_TIMEOUT + 30.0)

        try:
            async with AsyncFetcher(self.config) as fetcher:
                # 复用本 Agent 的 LLM 客户端（extractor 不再各自新建一个）
                extractor = StructuredExtractor(self.config, llm=self.llm)
                executor = ToolExecutor(st, self.config, fetcher, extractor, self.llm)

                try:
                    while st.budget_left() and not st.cancelled:
                        st.steps_used += 1
                        findings_before = len(st.findings)
                        pages_before = st.pages_used

                        # ── 上下文滚动压缩：估算 token 超预算时压缩最旧步骤 ──
                        if self.ctx.should_compact(messages):
                            messages, saved = self.ctx.compact(messages)
                            if saved > 0:
                                logger.info(f"context compacted: ~{saved} tokens freed (total {self.ctx.compactions}x)")
                                yield AgentEvent("compaction", {
                                    "saved_tokens": saved,
                                    "est_tokens": estimate_messages_tokens(messages),
                                    "count": self.ctx.compactions,
                                })

                        try:
                            msg = await asyncio.wait_for(
                                self.llm.achat_tools(messages, tools=AGENT_TOOLS, tool_choice="auto"),
                                timeout=llm_timeout,
                            )
                        except asyncio.TimeoutError:
                            logger.error("agent LLM call timed out after %.0fs", llm_timeout)
                            yield AgentEvent("error", {"message": "LLM 调用超时"})
                            st.status = "error"
                            st.error = "LLM 调用超时"
                            break
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
                                st.status = "no_progress"
                                break
                            messages.append({"role": "user",
                                             "content": "请调用一个工具继续（fetch_page/crawl_links/extract_data/record_finding），目标达成时调用 finish。"})
                            continue
                        no_tool_streak = 0

                        # 解析全部 tool_calls（畸形参数归一化）
                        parsed_calls: list[dict] = []
                        for tc in tool_calls:
                            fn = tc.get("function") or {}
                            raw_args = fn.get("arguments", "") or "{}"
                            args = loads_json_loose(raw_args) if isinstance(raw_args, str) else raw_args
                            if not isinstance(args, dict):
                                args = {}
                            parsed_calls.append({
                                "id": tc.get("id", ""),
                                "name": fn.get("name") or "",
                                "args": args,
                            })

                        finished = False
                        aborted = False

                        # ── finish：串行特殊路径（保持消息序列合法性） ──
                        finish_call = next((c for c in parsed_calls if c["name"] == "finish"), None)
                        if finish_call is not None:
                            st.status = "finished"
                            agent_summary = str(finish_call["args"].get("summary") or "").strip()[:2000]
                            finished = True
                            # 必须为本次响应的**所有** tool_calls 回填 role:tool，
                            # 否则下一轮请求会被 API 判为消息序列非法。
                            for call in parsed_calls:
                                reply = agent_summary if (call["name"] == "finish" and agent_summary) else "任务已结束。"
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": call["id"],
                                    "content": reply,
                                })
                            self.ctx.record_batch([
                                f"{c['name']}({summarize_args(c['args'])}) → {'结束: ' + agent_summary[:120] if c['name'] == 'finish' else '任务已结束'}"
                                for c in parsed_calls
                            ])
                            for call in parsed_calls:
                                if call is not finish_call:
                                    yield AgentEvent("action", {"tool": call["name"], "args": {}})
                        elif st.cancelled:
                            # 取消后不再抓取，但同样要回填 tool 消息
                            for call in parsed_calls:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": call["id"],
                                    "content": "任务已被取消。",
                                })
                            self.ctx.record_batch([
                                f"{c['name']}({summarize_args(c['args'])}) → 已取消" for c in parsed_calls
                            ])
                            aborted = True
                        else:
                            # ── 并行执行一批工具调用（保持事件与结果按调用顺序产出） ──
                            for call in parsed_calls:
                                yield AgentEvent("action", {"tool": call["name"], "args": call["args"]})
                            results = await executor.dispatch_many(
                                [(c["name"], c["args"]) for c in parsed_calls]
                            )
                            batch_digests: list[str] = []
                            for call, result in zip(parsed_calls, results):
                                truncated = truncate_tool_result(result, limit=_TOOL_RESULT_LIMIT)
                                try:
                                    content = json.dumps(truncated, ensure_ascii=False)
                                    if len(content) > _TOOL_RESULT_LIMIT:  # 键极多的退化情况兜底
                                        content = content[:_TOOL_RESULT_LIMIT] + "…(截断)"
                                except (TypeError, ValueError):
                                    content = str(result)[:_TOOL_RESULT_LIMIT]
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": call["id"],
                                    "content": content,
                                })
                                batch_digests.append(
                                    f"{call['name']}({summarize_args(call['args'])}) → {summarize_result(result)}"
                                )
                                # 把新发现透出给前端
                                if isinstance(result, dict) and call["name"] in ("extract_data", "record_finding") and result.get("is_new"):
                                    f = st.findings[-1] if st.findings else {}
                                    yield AgentEvent("finding", {
                                        "title": f.get("title", ""), "url": f.get("url", ""),
                                        "data": f.get("data"), "content": f.get("content", ""),
                                    })
                                yield AgentEvent("observation", {
                                    "tool": call["name"],
                                    "result": _compact(result) if isinstance(result, dict) else {"raw": str(result)[:300]},
                                })
                            self.ctx.record_batch(batch_digests)

                        yield AgentEvent("progress", {
                            "pages_used": st.pages_used, "budget_pages": st.budget_pages,
                            "steps_used": st.steps_used, "budget_steps": st.budget_steps,
                            "findings": len(st.findings), "visited": len(st.visited),
                            "usage": self.llm.usage,
                            "est_context_tokens": estimate_messages_tokens(messages),
                        })

                        if finished or aborted:
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
                finally:
                    await executor.aclose()

        except Exception as e:
            logger.exception("agent run crashed")
            st.status = "error"
            st.error = str(e)[:300]
            yield AgentEvent("error", {"message": str(e)[:200]})

        # 收尾：确定状态 + 生成报告
        if st.cancelled and st.status in ("running", "finished"):
            st.status = "cancelled"
        elif st.status == "running":
            st.status = "budget_exhausted" if not st.budget_left() else "finished"

        reason = _REASON_TEXT.get(st.status, st.status)
        yield AgentEvent("progress", {
            "pages_used": st.pages_used, "budget_pages": st.budget_pages,
            "steps_used": st.steps_used, "budget_steps": st.budget_steps,
            "findings": len(st.findings), "visited": len(st.visited),
            "usage": self.llm.usage,
            "est_context_tokens": estimate_messages_tokens(messages),
        })

        report = await self._generate_report(reason, agent_summary)
        st.report = report
        st.usage = self.llm.usage  # 随 run 落库（agent_runs.extra）

        # 写领域记忆（尽力而为，绝不阻塞收尾）
        note = ""
        if st.findings:
            top = [f.get("url") for f in st.findings[:3] if f.get("url")]
            if top:
                note = f"有效入口: {'; '.join(top)}"
        await self.memory.record_outcome(
            seed_domains + domains_of([f.get("url", "") for f in st.findings[:10]]),
            st.status, len(st.findings), note,
        )

        yield AgentEvent("finish", {
            "status": st.status, "reason": reason, "report": report,
            "findings": st.findings, "finding_count": len(st.findings),
            "pages_used": st.pages_used, "steps_used": st.steps_used,
            "usage": self.llm.usage,
        })

    async def _generate_report(self, reason: str, agent_summary: str = "") -> str:
        try:
            return await self.llm.achat(
                [{"role": "user", "content": summary_prompt(
                    self.state.goal, self.state.findings, reason, agent_summary)}],
                temperature=0.3, max_tokens=2000,
            )
        except Exception as e:
            logger.warning(f"report generation failed: {e}")
            # 兜底：列出发现
            fallback = agent_summary or ""
            lines = [f"## 收集到 {len(self.state.findings)} 条发现（报告生成失败：{e}）"]
            if fallback:
                lines = [f"## Agent 总结\n{fallback}", ""] + lines
            for i, f in enumerate(self.state.findings, 1):
                lines.append(f"{i}. {f.get('title','')} — {f.get('url','')}")
            return "\n".join(lines)


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
