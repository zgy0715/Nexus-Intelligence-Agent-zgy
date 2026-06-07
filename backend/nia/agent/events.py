"""Agent 事件 — 经 SSE 实时推送给前端（思考/动作/观察/发现/报告）。"""

from __future__ import annotations

import json
from dataclasses import dataclass

# 事件类型约定（前端据此渲染不同样式）：
#   start | thought | action | observation | finding | progress | finish | error
EventType = str


@dataclass
class AgentEvent:
    type: EventType
    data: dict

    def to_payload(self) -> dict:
        return {"type": self.type, **self.data}

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_payload(), ensure_ascii=False)}\n\n"
