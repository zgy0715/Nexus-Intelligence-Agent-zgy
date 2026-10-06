"""自主 Agent 的运行状态。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field

from nia.utils.config import Config
from nia.utils.timeutil import utcnow


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
    created_at: str = field(default_factory=lambda: utcnow().isoformat())

    cancel_flag: asyncio.Event = field(default_factory=asyncio.Event)

    def budget_left(self) -> bool:
        return self.pages_used < self.budget_pages and self.steps_used < self.budget_steps

    def cancel(self) -> None:
        """请求取消（幂等）。真正的取消检查发生在每一步与每个工具调用之前。"""
        self.cancel_flag.set()

    @staticmethod
    def _finding_key(finding: dict) -> tuple[str, str, str]:
        """去重键。

        旧实现只用 (url, title)，于是两条标题/URL 都为空的 record_finding
        会被静默丢掉；这里在二者皆空时退化为内容摘要哈希。
        """
        url = (finding.get("url") or "").strip()
        title = (finding.get("title") or "").strip()
        content = (finding.get("content") or "").strip()
        if not content and finding.get("data") is not None:
            try:
                content = json.dumps(finding["data"], ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError):
                content = str(finding["data"])
        digest = hashlib.sha1(content.encode("utf-8", "ignore")).hexdigest()[:16] if content else ""
        return (url, title, digest)

    def add_finding(self, finding: dict) -> bool:
        """去重添加 finding。返回是否为新发现。

        同一 (url, title) 会合并：新内容更丰富时覆盖旧条目。
        """
        key = self._finding_key(finding)
        for i, f in enumerate(self.findings):
            if self._finding_key(f) == key:
                new_len = len((finding.get("content") or "") + str(finding.get("data") or ""))
                old_len = len((f.get("content") or "") + str(f.get("data") or ""))
                if new_len > old_len:
                    self.findings[i] = finding
                return False
        self.findings.append(finding)
        return True

    @property
    def cancelled(self) -> bool:
        return self.cancel_flag.is_set()

    def to_dict(self, max_findings: int | None = None) -> dict:
        findings = self.findings
        if max_findings is not None and len(findings) > max_findings:
            findings = findings[:max_findings]
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "seeds": self.seeds,
            "status": self.status,
            "pages_used": self.pages_used,
            "steps_used": self.steps_used,
            "findings": findings,
            "finding_count": len(self.findings),
            "report": self.report,
            "error": self.error,
            "created_at": self.created_at,
        }
