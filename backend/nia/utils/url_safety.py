"""URL 安全校验与归一化 — 防 SSRF，供爬取引擎与 API 复用。"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "vbscript"}
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
}
# 常见跟踪参数，归一化时剔除以提升去重命中率
_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|spm$|ref$|ref_src$|from$)")


def is_safe_url(url: str) -> tuple[bool, str]:
    """返回 (是否安全, 原因)。仅允许 http/https 且非内网/私有地址。"""
    if not url:
        return False, "空 URL"
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return False, "仅支持 http/https 协议"
    parts = urlsplit(url)
    if parts.scheme.lower() in BLOCKED_SCHEMES:
        return False, f"禁止协议: {parts.scheme}"
    host = (parts.hostname or "").lower()
    if not host:
        return False, "缺少主机名"
    if host in BLOCKED_HOSTS:
        return False, "禁止访问内网地址"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, "禁止访问私有网络地址"
    except ValueError:
        pass  # 域名而非 IP，放行
    return True, ""


def validate_url(url: str) -> str:
    """校验并返回清理后的 URL，不安全则抛 ValueError。"""
    url = (url or "").strip()
    ok, reason = is_safe_url(url)
    if not ok:
        raise ValueError(reason)
    return url


def normalize_url(url: str, base: str | None = None) -> str | None:
    """归一化 URL 用于去重；非法/不安全返回 None。

    处理：相对→绝对、去 fragment、小写 scheme/host、去默认端口、剔除跟踪参数。
    """
    if not url:
        return None
    url = url.strip()
    if base:
        url = urljoin(base, url)
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https"):
        return None

    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not host:
        return None
    # 去默认端口
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    # 过滤跟踪参数
    query = parts.query
    if query:
        kept = []
        for pair in query.split("&"):
            key = pair.split("=", 1)[0]
            if not _TRACKING_PARAMS.match(key):
                kept.append(pair)
        query = "&".join(kept)

    path = parts.path or "/"
    normalized = urlunsplit((scheme, netloc, path, query, ""))  # 去 fragment

    ok, _ = is_safe_url(normalized)
    return normalized if ok else None


def get_domain(url: str) -> str:
    """提取归一化域名（小写 host）。"""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
