"""api.agent 的 AgentRequest：种子 URL 必须连 DNS 解析一起校验（防 nip.io 类绕过）。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import nia.api.agent as api_agent
import nia.utils.url_safety as us
from nia.api.agent import AgentRequest


def test_seeds_literal_internal_ip_rejected():
    """字面内网 IP 无需 DNS 即拒绝（真实实现，不 patch）。"""
    with pytest.raises(ValidationError):
        AgentRequest(goal="收集新闻", seeds=["http://127.0.0.1:6379/"])


def test_seeds_dns_to_internal_rejected(monkeypatch):
    """回归：旧版 is_safe_url 不带 resolve，域名指向内网的种子可通过校验。"""
    monkeypatch.setattr(us, "_resolve_host", lambda host: ("127.0.0.1",))
    monkeypatch.setattr(api_agent, "is_safe_url", us.is_safe_url)  # 确保走真实实现
    with pytest.raises(ValidationError, match="内网"):
        AgentRequest(goal="g", seeds=["http://sneaky.example.com/"])


def test_seeds_literal_private_rejected(monkeypatch):
    monkeypatch.setattr(api_agent, "is_safe_url", us.is_safe_url)
    with pytest.raises(ValidationError):
        AgentRequest(goal="g", seeds=["http://10.0.0.1/"])


def test_seeds_sanitized_and_deduped(monkeypatch):
    monkeypatch.setattr(api_agent, "is_safe_url", _stub_ok)
    req = AgentRequest(goal=" g ", seeds=["  http://a.com  ", "", "http://a.com"])
    assert req.goal == "g"
    assert req.seeds == ["http://a.com"]


def test_seeds_empty_rejected(monkeypatch):
    monkeypatch.setattr(api_agent, "is_safe_url", _stub_ok)
    with pytest.raises(ValidationError):
        AgentRequest(goal="g", seeds=["", "   "])


def test_seeds_too_many_rejected(monkeypatch):
    monkeypatch.setattr(api_agent, "is_safe_url", _stub_ok)
    with pytest.raises(ValidationError, match="最多 10 个"):
        AgentRequest(goal="g", seeds=[f"http://a{i}.com" for i in range(11)])


def _stub_ok(url: str, resolve: bool = False):
    if url.startswith(("http://", "https://")):
        return True, ""
    return False, "stub 拒绝"
