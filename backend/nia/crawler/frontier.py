"""URL frontier — BFS 队列，带深度/同域限制、归一化去重、预算拦截。"""

from __future__ import annotations

import logging
from collections import deque

from nia.crawler.models import CrawlConfig
from nia.utils.url_safety import get_domain, normalize_url

logger = logging.getLogger(__name__)


class URLFrontier:
    """广度优先的 URL 队列。

    - visited：已抓取（或正在抓取）的归一化 URL
    - pending：已入队待抓取的归一化 URL（与 visited 一起防重复入队）
    - 入队即做归一化、安全、深度、同域、预算校验
    """

    def __init__(self, config: CrawlConfig, seeds: list[str]):
        self._config = config
        self._queue: deque[tuple[str, int, str]] = deque()  # (url, depth, parent)
        self.visited: set[str] = set()
        self.pending: set[str] = set()

        # 同域限制：以种子域名为白名单基准
        self._allowed = set(config.allowed_domains)
        for seed in seeds:
            norm = normalize_url(seed)
            if norm:
                self._allowed.add(get_domain(norm))
        for seed in seeds:
            self.add(seed, depth=0, parent="")

    def add(self, url: str, depth: int, parent: str = "") -> bool:
        """尝试入队一个 URL。被去重/越界/越权时返回 False。"""
        if depth > self._config.max_depth:
            return False
        if len(self.visited) + len(self.pending) >= self._config.max_pages:
            return False
        norm = normalize_url(url, base=parent or None)
        if not norm or norm in self.visited or norm in self.pending:
            return False
        if self._config.same_domain_only and get_domain(norm) not in self._allowed:
            return False
        self._queue.append((norm, depth, parent))
        self.pending.add(norm)
        return True

    def add_many(self, urls: list[str], depth: int, parent: str = "") -> int:
        return sum(1 for u in urls if self.add(u, depth, parent))

    def pop_batch(self, n: int) -> list[tuple[str, int]]:
        """取出至多 n 个待抓取项，移入 visited。"""
        batch: list[tuple[str, int]] = []
        while self._queue and len(batch) < n:
            url, depth, _parent = self._queue.popleft()
            self.pending.discard(url)
            if url in self.visited:
                continue
            self.visited.add(url)
            batch.append((url, depth))
        return batch

    def has_next(self) -> bool:
        return bool(self._queue)

    @property
    def visited_count(self) -> int:
        return len(self.visited)
