"""URL frontier — 带优先级的 BFS 队列，含深度/同域限制、归一化去重、预算控制。

与旧实现的区别：
- 用最小堆做**优先级**出队：浅层优先、路径短的优先、查询参数少的优先。
  这样一个「链接很多」的页面不会把后面更有价值的 URL 饿死。
- 预算只对**已抓取**数量生效（`max_pages`），队列另有独立上限（`max_queue`），
  入队时不再因为「已访问+待抓取」达到 max_pages 而把后续链接全部拒掉。
- 每页最多入队 `max_links_per_page` 个链接，防止目录页一次灌入上千 URL。
"""

from __future__ import annotations

import heapq
import itertools
import logging

from nia.crawler.models import CrawlConfig
from nia.utils.url_safety import get_domain, normalize_url

logger = logging.getLogger(__name__)

_SEED_BIAS = 1000  # 越接近种子路径，分数越低（越优先）


class URLFrontier:
    """广度优先 + 优先级排序的 URL 队列。

    - visited：已出队（即已抓取或正在抓取）的归一化 URL
    - pending：已入队待抓取的归一化 URL（与 visited 一起防重复入队）
    - 入队即做归一化、安全、深度、同域校验
    """

    def __init__(self, config: CrawlConfig, seeds: list[str]):
        self._config = config
        self._seq = itertools.count()
        self._queue: list[tuple[int, int, int, str, str]] = []  # (score, seq, depth, url, parent)
        self.visited: set[str] = set()
        self.pending: set[str] = set()
        self.skipped: int = 0          # 因预算/队列上限被拒的数量
        self.deduped: int = 0          # 因重复被拒的数量

        # 同域限制：以种子域名为白名单基准
        self._allowed = set(config.allowed_domains)
        for seed in seeds:
            norm = normalize_url(seed)
            if norm:
                self._allowed.add(get_domain(norm))
        for seed in seeds:
            self.add(seed, depth=0, parent="")

    @property
    def max_queue(self) -> int:
        return max(self._config.max_pages * 4, 100)

    def _score(self, url: str, depth: int) -> int:
        """越小越优先：浅层 > 路径短 > 查询参数少。"""
        path = url.split("://", 1)[-1]
        path_len = path.count("/")
        query_params = url.count("&") + (1 if "?" in url else 0)
        return depth * 10000 + path_len * 10 + query_params

    def add(self, url: str, depth: int, parent: str = "") -> bool:
        """尝试入队一个 URL。被去重/越界/越权/队列满时返回 False。"""
        if depth > self._config.max_depth:
            return False
        norm = normalize_url(url, base=parent or None)
        if not norm or norm in self.visited or norm in self.pending:
            self.deduped += 1
            return False
        if self._config.same_domain_only and get_domain(norm) not in self._allowed:
            return False
        if len(self._queue) >= self.max_queue:
            self.skipped += 1
            return False
        heapq.heappush(self._queue, (self._score(norm, depth), next(self._seq), depth, norm, parent))
        self.pending.add(norm)
        return True

    def add_many(self, urls: list[str], depth: int, parent: str = "", limit: int | None = None) -> int:
        """批量入队，最多尝试 limit 个（默认 80）以避免目录页灌爆队列。"""
        cap = limit if limit is not None else 80
        added = 0
        for u in urls[:cap]:
            if self.add(u, depth, parent):
                added += 1
        if len(urls) > cap:
            self.skipped += len(urls) - cap
        return added

    def pop_batch(self, n: int) -> list[tuple[str, int]]:
        """取出至多 n 个优先级最高的待抓取项，移入 visited。"""
        batch: list[tuple[str, int]] = []
        while self._queue and len(batch) < n:
            _score, _seq, depth, url, _parent = heapq.heappop(self._queue)
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

    @property
    def queued_count(self) -> int:
        return len(self._queue)
