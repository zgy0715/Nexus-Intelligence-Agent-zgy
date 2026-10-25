"""Agent 事件 — 类型化定义，经 SSE 实时推送给前端。

v3 变更：
- 事件类型从裸字符串改为 StrEnum（拼写错误在定义处即暴露，而非前端渲染时）；
- AgentEvent 改为 Pydantic 模型，seq 由事件总线（API 层）分配，
  作为 SSE 的 `id:` 行 → 浏览器断线重连时通过 Last-Event-ID 头回报，
  服务端据此续传，不再重复推送。

前端据此渲染不同样式的事件：
start | thought | action | observation | finding | progress | compaction | finish | error
"""

from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, Field


class AgentEventType(StrEnum):
    START = "start"
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    FINDING = "finding"
    PROGRESS = "progress"
    COMPACTION = "compaction"  # v3：上下文滚动压缩发生
    FINISH = "finish"
    ERROR = "error"
    EOF = "_eof"  # 内部哨兵：标记事件流终结，不透传给前端


class AgentEvent(BaseModel):
    type: AgentEventType
    data: dict = Field(default_factory=dict)
    # 全局递增序号（由 API 层 _emit 分配），0 表示尚未入总线
    seq: int = 0

    def __init__(self, type: AgentEventType | str, data: dict | None = None, **kwargs) -> None:
        # 保留位置参数用法（旧代码大量 AgentEvent("start", {...})）
        super().__init__(type=AgentEventType(type), data=data or {}, **kwargs)

    def to_payload(self) -> dict:
        return {"type": self.type.value, "seq": self.seq, **self.data}

    def to_sse(self) -> str:
        payload = json.dumps(self.to_payload(), ensure_ascii=False)
        return f"id: {self.seq}\ndata: {payload}\n\n"
