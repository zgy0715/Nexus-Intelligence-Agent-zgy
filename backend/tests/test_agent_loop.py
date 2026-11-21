"""agent 主循环离线集成测试 — FakeLLM 驱动完整 tool-calling 循环。

不依赖任何网络 / Redis / MySQL / DeepSeek：
- LLMClient 与 AgentMemory 被 monkeypatch 替换；
- 脚本化的 FakeLLM 依次返回 tool_calls（只用 record_finding / finish，不触发真实抓取）。

覆盖四条主路径：并行工具 + finish / 无进展收尾 / 拒调工具收尾 / 启动前取消。
"""

from __future__ import annotations

import asyncio
import json

import nia.agent.agent as agent_mod
from nia.agent.agent import AutonomousCrawlAgent
from nia.agent.events import AgentEvent
from nia.agent.state import AgentState


# ── 测试替身 ─────────────────────────────────────────────────────

class FakeLLM:
    """脚本化 LLM：依次吐出预设响应；usage 与 achat/aclose 可被断言。"""

    def __init__(self, script: list[dict], report: str = "## 模拟报告\n\n正文。"):
        self._script = list(script)
        self._report = report
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _bump(self) -> None:
        self.usage["calls"] += 1
        self.usage["prompt_tokens"] += 100
        self.usage["completion_tokens"] += 20
        self.usage["total_tokens"] += 120

    async def achat_tools(self, messages, tools=None, tool_choice=None, **kw) -> dict:
        self._bump()
        if not self._script:
            return {"role": "assistant", "content": "脚本耗尽"}
        return self._script.pop(0)

    async def achat(self, messages, temperature=None, max_tokens=None, **kw) -> str:
        self._bump()
        return self._report

    async def astream(self, messages, **kw):
        yield self._report

    async def aclose(self) -> None:
        return None


class FakeMemory:
    def __init__(self) -> None:
        self.recorded: list[tuple] = []

    async def load_hints(self, domains) -> str:
        return ""

    async def record_outcome(self, domains, status, findings, note="") -> None:
        self.recorded.append((tuple(domains), status, findings, note))


def _tool_call(idx: int, name: str, args: dict) -> dict:
    return {
        "id": f"call_{idx}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
    }


def _mk_agent(monkeypatch, script: list[dict], report: str = "## 模拟报告") -> AutonomousCrawlAgent:
    monkeypatch.setattr(agent_mod, "LLMClient", lambda: FakeLLM(script, report))
    fake_mem = FakeMemory()
    monkeypatch.setattr(agent_mod, "AgentMemory", lambda: fake_mem)
    st = AgentState(run_id="t", goal="收集测试数据", seeds=["https://example.org/"])
    return AutonomousCrawlAgent(st)


def _collect(agent: AutonomousCrawlAgent) -> list[AgentEvent]:
    async def run() -> list[AgentEvent]:
        return [e async for e in agent.run()]

    return asyncio.run(run())


# ── 场景 1：并行工具 + 正常 finish ───────────────────────────────

def test_parallel_tools_then_finish(monkeypatch):
    script = [
        # 同一响应里两个 record_finding —— 走 dispatch_many 并行路径
        {"role": "assistant", "content": "记录两条发现", "tool_calls": [
            _tool_call(1, "record_finding", {"title": "发现A", "content": "内容A", "url": "https://a.org/1"}),
            _tool_call(2, "record_finding", {"title": "发现B", "content": "内容B", "url": "https://a.org/2"}),
        ]},
        {"role": "assistant", "content": "完成", "tool_calls": [
            _tool_call(3, "finish", {"summary": "两条发现已记录"}),
        ]},
    ]
    agent = _mk_agent(monkeypatch, script)
    events = _collect(agent)

    types = [e.type.value for e in events]
    assert types[0] == "start"
    assert types.count("action") == 2        # 两个工具各发一次 action
    assert types.count("observation") == 2
    assert types.count("finding") == 2       # is_new=True 各透出一条
    assert types.count("progress") >= 1
    assert types[-1] == "finish"

    finish = events[-1].data
    assert finish["status"] == "finished"
    assert finish["finding_count"] == 2
    assert finish["report"].startswith("## 模拟报告")
    assert finish["usage"]["calls"] == 3     # 2 次 achat_tools + 1 次 achat(报告)

    st = agent.state
    assert st.status == "finished"
    assert len(st.findings) == 2
    assert st.report == finish["report"]
    assert st.usage["total_tokens"] == 360


def test_finish_backfills_all_tool_messages(monkeypatch):
    """回归：finish 与其它 tool_calls 同批出现时，必须全部回填 role:tool，
    否则下一轮 API 判消息序列非法（本项目踩过的坑）。"""
    script = [
        {"role": "assistant", "content": None, "tool_calls": [
            _tool_call(1, "record_finding", {"title": "X", "content": "Y"}),
            _tool_call(2, "finish", {"summary": "完事"}),
        ]},
    ]
    agent = _mk_agent(monkeypatch, script)
    events = _collect(agent)
    assert events[-1].type.value == "finish"
    assert agent.state.status == "finished"


# ── 场景 2：连续无进展 → 强制收尾 ────────────────────────────────

def test_no_progress_forces_finish(monkeypatch):
    """每轮重复记录同一 finding：跨步累积 no_progress_streak 到阈值即收尾。

    注意先在状态里预置该 finding —— 否则第一次记录是新发现，会把 streak 清零。
    """
    dup = {"title": "重复", "content": "相同内容"}
    script = [
        {"role": "assistant", "content": None, "tool_calls": [_tool_call(1, "record_finding", dict(dup))]},
        {"role": "assistant", "content": None, "tool_calls": [_tool_call(2, "record_finding", dict(dup))]},
        {"role": "assistant", "content": None, "tool_calls": [_tool_call(3, "record_finding", dict(dup))]},
    ]
    agent = _mk_agent(monkeypatch, script)
    agent.state.add_finding(dict(dup))  # 预置：之后的三次记录全部是重复
    events = _collect(agent)

    finish = events[-1].data
    assert finish["status"] == "no_progress"
    assert finish["reason"] == "连续多步无新发现"
    assert agent.state.steps_used == 3


# ── 场景 3：模型拒调工具 → 两步后强制收尾 ────────────────────────

def test_no_tool_calls_forces_finish(monkeypatch):
    script = [
        {"role": "assistant", "content": "我只是说说，不调工具"},
        {"role": "assistant", "content": "还是不调"},
    ]
    agent = _mk_agent(monkeypatch, script)
    events = _collect(agent)

    types = [e.type.value for e in events]
    assert types.count("thought") == 2
    assert "action" not in types
    assert events[-1].data["status"] == "no_progress"
    assert agent.state.steps_used == 2


# ── 场景 4：启动前取消 ──────────────────────────────────────────

def test_cancel_before_run(monkeypatch):
    script = [
        {"role": "assistant", "content": None, "tool_calls": [
            _tool_call(1, "record_finding", {"title": "不该出现", "content": "x"}),
        ]},
    ]
    agent = _mk_agent(monkeypatch, script)
    agent.state.cancel()  # 运行前就取消

    events = _collect(agent)
    types = [e.type.value for e in events]
    assert "action" not in types          # 没有任何工具被执行
    assert events[-1].type.value == "finish"
    assert events[-1].data["status"] == "cancelled"
    assert events[-1].data["reason"] == "用户取消"
    assert agent.state.steps_used == 0


# ── 场景 5：LLM 异常 → error 事件且不崩溃 ───────────────────────

def test_llm_failure_yields_error_event(monkeypatch):
    class ExplodingLLM(FakeLLM):
        async def achat_tools(self, messages, tools=None, tool_choice=None, **kw):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(agent_mod, "LLMClient", lambda: ExplodingLLM([]))
    monkeypatch.setattr(agent_mod, "AgentMemory", lambda: FakeMemory())
    st = AgentState(run_id="t", goal="g", seeds=["https://example.org/"])
    agent = AutonomousCrawlAgent(st)

    events = _collect(agent)
    types = [e.type.value for e in events]
    assert "error" in types
    assert events[-1].type.value == "finish"
    assert agent.state.status == "error"
    # 报告生成失败有兜底：列出发现而不是空字符串
    assert "报告生成失败" in agent.state.report or agent.state.report
