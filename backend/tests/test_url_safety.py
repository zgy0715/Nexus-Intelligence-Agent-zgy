"""url_safety：SSRF 五层防御的单测（DNS 部分用 monkeypatch，全程离线）。"""

from __future__ import annotations

import nia.utils.url_safety as us


# ── 协议白名单 ──────────────────────────────────────────────────

def test_blocked_schemes():
    for url in ("file:///etc/passwd", "ftp://x.com", "data:text/html,x", "javascript:alert(1)"):
        ok, reason = us.is_safe_url(url)
        assert not ok
        assert reason


def test_non_http_rejected():
    ok, _ = us.is_safe_url("gopher://x.com")
    assert not ok
    ok, _ = us.is_safe_url("")
    assert not ok


# ── 字面 IP / 主机黑名单 ─────────────────────────────────────────

def test_literal_private_ips_blocked():
    for url in (
        "http://127.0.0.1:6379/",
        "http://10.1.2.3/x",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data",  # 云元数据
        "http://0.0.0.0/",
        "http://[::1]/",
    ):
        ok, reason = us.is_safe_url(url)
        assert not ok, url
        assert "禁止" in reason or "私有" in reason


def test_localhost_host_blocked():
    ok, reason = us.is_safe_url("http://localhost:8500/")
    assert not ok
    assert "内网" in reason


def test_public_ip_allowed():
    ok, reason = us.is_safe_url("http://8.8.8.8/")
    assert ok, reason


def test_invalid_port_blocked():
    ok, _ = us.is_safe_url("http://8.8.8.8:99999/")
    assert not ok
    ok, _ = us.is_safe_url("http://8.8.8.8:0/")
    assert not ok


# ── DNS 解析校验（防 localtest.me / nip.io 类绕过） ───────────────

def test_resolve_detects_dns_to_internal(monkeypatch):
    """域名解析到内网地址必须被拒 —— nip.io 类绕过的核心防线。"""
    monkeypatch.setattr(us, "_resolve_host", lambda host: ("127.0.0.1",))
    ok, reason = us.is_safe_url("http://evil.example.com/", resolve=True)
    assert not ok
    assert "内网" in reason


def test_resolve_public_ok(monkeypatch):
    monkeypatch.setattr(us, "_resolve_host", lambda host: ("93.184.216.34",))
    ok, reason = us.is_safe_url("http://example.com/", resolve=True)
    assert ok, reason


def test_resolve_unresolvable_blocked(monkeypatch):
    monkeypatch.setattr(us, "_resolve_host", lambda host: ())
    ok, reason = us.is_safe_url("http://nonexistent.example/", resolve=True)
    assert not ok
    assert "无法解析" in reason


def test_resolve_and_check_delegates(monkeypatch):
    monkeypatch.setattr(us, "_resolve_host", lambda host: ("10.0.0.1",))
    ok, _ = us.resolve_and_check("http://sneaky.example.com/")
    assert not ok


def test_literal_ip_skips_dns(monkeypatch):
    """字面 IP 走 ip_address 分支，resolve=True 不应触发 DNS。"""
    called = []

    def _spy(host):
        called.append(host)
        return ()

    monkeypatch.setattr(us, "_resolve_host", _spy)
    ok, _ = us.is_safe_url("http://8.8.8.8/", resolve=True)
    assert ok
    assert not called


# ── normalize_url ────────────────────────────────────────────────

def test_normalize_strips_tracking_and_fragment():
    out = us.normalize_url("https://a.com/p?utm_source=x&id=3&fbclid=y#frag")
    assert out == "https://a.com/p?id=3"


def test_normalize_relative_to_absolute():
    out = us.normalize_url("/news?page=2", base="https://a.com/list/")
    assert out == "https://a.com/news?page=2"


def test_normalize_default_port_removed():
    assert us.normalize_url("https://a.com:443/x") == "https://a.com/x"
    assert us.normalize_url("http://a.com:8080/x") == "http://a.com:8080/x"


def test_normalize_rejects_unsafe():
    assert us.normalize_url("javascript:void(0)") is None
    assert us.normalize_url("") is None
    assert us.normalize_url("http://127.0.0.1/") is None


def test_get_domain():
    assert us.get_domain("https://WWW.Example.com/a") == "www.example.com"
    assert us.get_domain("not a url") == ""
