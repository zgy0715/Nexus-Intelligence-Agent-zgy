"""Agent 领域记忆 — Redis 记录同站点历史运行经验，注入 system prompt。

动机：同一个站点往往被反复爬取（课程演示/定期收集）。把上一次运行的
「状态 + 发现数 + 有效入口」存进 Redis（TTL 7 天），下次运行同域时注入
提示词，Agent 不必从零摸索（例如知道列表页在 /news 而首页是全屏动画）。

设计约束：
- Redis 不可用时静默降级为空提示（功能不降级，只是没有先验）；
- 每个域名的经验文本封顶（防止单条无限增长）；
- 记录由 run 收尾时异步写入，绝不阻塞主流程。
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from nia.utils.config import Config
from nia.utils.timeutil import utcnow

logger = logging.getLogger(__name__)

_MEMORY_TTL = 7 * 86400
_MAX_HINT_CHARS = 600
_MAX_LINES_PER_HINT = 5


def domains_of(urls: list[str]) -> list[str]:
    """从 URL 列表提取域名（去重、保序、容忍畸形输入）。"""
    out: list[str] = []
    for u in urls or []:
        try:
            host = urlparse(u if "://" in u else f"https://{u}").netloc.lower()
        except ValueError:
            continue
        if host and host not in out:
            out.append(host)
    return out


class AgentMemory:
    """基于 Redis hash 的域名级经验存储。所有方法尽力而为，失败返回空。"""

    def __init__(self):
        self._redis = None
        self._disabled = False

    async def _get_redis(self):
        if self._disabled:
            return None
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(Config.REDIS_URL, decode_responses=True)
            except Exception as e:  # pragma: no cover - redis 缺失等环境问题
                logger.debug(f"agent memory disabled: {e}")
                self._disabled = True
                return None
        return self._redis

    @staticmethod
    def _key(domain: str) -> str:
        return f"nia:agent:memory:{domain}"

    async def load_hints(self, domains: list[str]) -> str:
        """读取若干域名的经验，拼成可注入 system prompt 的文本块（无经验返回空串）。"""
        client = await self._get_redis()
        if not client or not domains:
            return ""
        try:
            lines: list[str] = []
            for domain in domains[:5]:
                raw = await client.get(self._key(domain))
                if raw:
                    lines.append(f"- {domain}: {raw}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"load agent memory hints failed: {e}")
            return ""

    async def record_outcome(self, domains: list[str], status: str, finding_count: int, note: str = "") -> None:
        """run 收尾时写入经验。追加式，超长裁剪旧行。"""
        client = await self._get_redis()
        if not client or not domains:
            return
        stamp = utcnow().strftime("%m-%d")
        entry = f"[{stamp}] {status}，发现 {finding_count} 条"
        if note:
            entry += f"。{note[:200]}"
        try:
            for domain in domains[:5]:
                key = self._key(domain)
                old = await client.get(key) or ""
                lines = [ln for ln in old.split("\n") if ln.strip()]
                # 同日覆盖：避免一天多次运行堆出重复行
                lines = [ln for ln in lines if not ln.startswith(f"[{stamp}]")]
                lines.append(entry)
                lines = lines[-_MAX_LINES_PER_HINT:]
                text = "\n".join(lines)[-_MAX_HINT_CHARS:]
                await client.set(key, text, ex=_MEMORY_TTL)
        except Exception as e:
            logger.debug(f"record agent memory failed: {e}")
