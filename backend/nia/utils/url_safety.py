"""URL 安全校验与归一化 — 防 SSRF，供爬取引擎与 API 复用。

安全模型（纵深防御）：
1. 协议白名单：仅 http/https；
2. 主机黑名单（localhost / 云元数据域名等）；
3. 字面 IP 检查：私有 / 回环 / 链路本地 / 保留 / 组播 / 未指定 一律拒绝；
4. **DNS 解析检查**：域名解析出的所有 A/AAAA 记录只要有一个是内网地址就拒绝，
   这样 `localtest.me`、`127.0.0.1.nip.io` 之类的绕过手段失效；
5. 端口检查：拒绝 0 与 >65535 的非法端口，并可选限制非标准端口。

`normalize_url` 为了性能不做 DNS 解析（它会被每页的每个链接调用），
真正的解析校验由 `resolve_and_check()` 在发请求前执行。
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from functools import lru_cache
from urllib.parse import urljoin, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "vbscript"}
BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
    "::1",
    "metadata.google.internal",
    "metadata.goog",
    "169.254.169.254",
}

# 常见跟踪参数，归一化时剔除以提升去重命中率。
# 注意：刻意不剔除 ref / from / spm 之外的语义化参数，避免把不同页面折叠成同一个 key。
_TRACKING_PARAMS = re.compile(
    r"^(utm_|fbclid$|gclid$|msclkid$|yclid$|dclid$|_ga$|mc_eid$|mc_cid$|igshid$|hmsr$|hmpl$|hmcu$|hmkw$|hmci$)"
)

# 可选：非空时只允许这些端口（None = 不限制，仅校验 1-65535）
ALLOWED_PORTS: frozenset[int] | None = None


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


@lru_cache(maxsize=2048)
def _resolve_host(host: str) -> tuple[str, ...]:
    """解析主机名为 IP 列表；失败返回空元组。带 LRU 缓存避免重复 DNS 查询。"""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError, UnicodeError) as exc:
        logger.debug("DNS 解析失败 %s: %s", host, exc)
        return ()
    return tuple({info[4][0] for info in infos})


def is_safe_url(url: str, resolve: bool = False) -> tuple[bool, str]:
    """返回 (是否安全, 原因)。仅允许 http/https 且非内网/私有地址。

    Args:
        resolve: 是否做 DNS 解析校验（会在解析结果里查找内网地址）。
    """
    if not url:
        return False, "空 URL"
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return False, "仅支持 http/https 协议"
    try:
        parts = urlsplit(url)
    except ValueError:
        return False, "URL 格式非法"
    if parts.scheme.lower() in BLOCKED_SCHEMES:
        return False, f"禁止协议: {parts.scheme}"
    host = (parts.hostname or "").lower()
    if not host:
        return False, "缺少主机名"

    # 端口非法（如 :99999）会在这里抛 ValueError，必须放进 try
    try:
        port = parts.port
    except ValueError:
        return False, "端口非法（必须在 0-65535 之间）"
    if port is not None and not (0 < port <= 65535):
        return False, "端口非法（必须在 0-65535 之间）"
    if ALLOWED_PORTS is not None and port not in ALLOWED_PORTS:
        return False, f"禁止访问端口: {port}"

    if host in BLOCKED_HOSTS:
        return False, "禁止访问内网地址"

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # 域名而非字面 IP：可选择性做 DNS 解析校验
        if resolve:
            addrs = _resolve_host(host)
            if not addrs:
                return False, f"域名无法解析: {host}"
            for addr in addrs:
                try:
                    if _ip_is_blocked(ipaddress.ip_address(addr)):
                        return False, f"域名 {host} 解析到内网地址 {addr}"
                except ValueError:
                    continue
        return True, ""
    if _ip_is_blocked(ip):
        return False, "禁止访问私有网络地址"
    return True, ""


def validate_url(url: str, resolve: bool = False) -> str:
    """校验并返回清理后的 URL，不安全则抛 ValueError。"""
    url = (url or "").strip()
    ok, reason = is_safe_url(url, resolve=resolve)
    if not ok:
        raise ValueError(reason)
    return url


def resolve_and_check(url: str) -> tuple[bool, str]:
    """发请求前的最后一道闸：做 DNS 解析校验。

    这样 `localtest.me`、`127.0.0.1.nip.io` 之类「域名指向内网」的绕过手段会失效。
    """
    return is_safe_url(url, resolve=True)


def normalize_url(url: str, base: str | None = None) -> str | None:
    """归一化 URL 用于去重；非法/不安全返回 None。

    处理：相对→绝对、去 fragment、小写 scheme/host、去默认端口、剔除跟踪参数。
    不做 DNS 解析（性能考虑），安全性的最终确认由 resolve_and_check 完成。
    """
    if not url:
        return None
    url = url.strip()
    if base:
        try:
            url = urljoin(base, url)
        except ValueError:
            return None
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
    # 去默认端口（parts.port 对非法端口会抛 ValueError，必须捕获）
    try:
        port = parts.port
    except ValueError:
        return None
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    # 过滤跟踪参数
    query = parts.query
    if query:
        kept = [p for p in query.split("&") if not _TRACKING_PARAMS.match(p.split("=", 1)[0])]
        query = "&".join(kept)

    path = parts.path or "/"
    try:
        normalized = urlunsplit((scheme, netloc, path, query, ""))  # 去 fragment
    except ValueError:
        return None

    ok, _ = is_safe_url(normalized)
    return normalized if ok else None


def get_domain(url: str) -> str:
    """提取归一化域名（小写 host）。"""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
