"""自主 Agent 的运行状态。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from nia.utils.config import Config


@dataclass
class AgentState:
    run_id: str
    goal: str
    seeds: list[str]

    visited: set[str] = field(default_factory=set)
    findings: list[dict] = field(default_factory=list)

    budget_pages: int = field(default_factory=lambda: Config.AGENT_MAX_PAGES)
    budget_steps: int = field(default_factory=lambda: Config.AGENT_MAX_STEPS)
    no_progress_limit: int = field(default_factory=lambda: Config.AGENT_NO_PROGRESS_LIMIT)

    pages_used: int = 0
    steps_used: int = 0
    no_progress_streak: int = 0

    status: str = "running"  # running | finished | budget_exhausted | cancelled | error
    report: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    cancel_flag: asyncio.Event = field(default_factory=asyncio.Event)

    def budget_left(self) -> bool:
        return self.pages_used < self.budget_pages and self.steps_used < self.budget_steps

    def add_finding(self, finding: dict) -> bool:
        """去重添加 finding（按 url+title）。返回是否为新发现。"""
        key = (finding.get("url", ""), finding.get("title", ""))
        for f in self.findings:
            if (f.get("url", ""), f.get("title", "")) == key:
                return False
        self.findings.append(finding)
        return True

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "seeds": self.seeds,
            "status": self.status,
            "pages_used": self.pages_used,
            "steps_used": self.steps_used,
            "findings": self.findings,
            "report": self.report,
            "error": self.error,
            "created_at": self.created_at,
        }
