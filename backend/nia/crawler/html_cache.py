"""HTML 磁盘缓存 — 重复任务不打网络（TTL 控制，LRU-ish 清理）。

与提取缓存（cache.py，Redis，缓存 LLM 提取结果）互补：这里缓存的是
**原始 HTML**，命中后连抓取都省掉。适用场景：同一批 URL 反复演示/定期采集。

设计约束：
- 只缓存 http(s) 成功响应的**非 JS 渲染**结果（JS 渲染成本高且页面动态性强）；
- 键 = 归一化 URL 的 sha256，文件体 = JSON {url, final_url, html, cached_at}；
- 单文件上限（默认 5MB）防大页面塞满磁盘；
- 全部尽力而为：磁盘 IO 失败静默降级为未命中。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time

from nia.utils.config import Config

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 24 * 3600
_DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024
_MAX_FILES = 2000  # 缓存文件数量上限（超限时清理最旧文件）


class HtmlDiskCache:
    def __init__(self, base_dir: str | None = None, ttl: int | None = None):
        self._dir = base_dir or os.path.join("./data", "html_cache")
        self._ttl = ttl if ttl is not None else getattr(Config, "CRAWL_HTML_CACHE_TTL", _DEFAULT_TTL)

    @staticmethod
    def _key(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8", "ignore")).hexdigest()

    def _path(self, key: str) -> str:
        # 两级散列目录，避免单目录文件过多
        return os.path.join(self._dir, key[:2], f"{key}.json")

    def get(self, url: str) -> dict | None:
        path = self._path(self._key(url))
        try:
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if time.time() - doc.get("cached_at", 0) > self._ttl:
                return None
            return doc
        except Exception as e:
            logger.debug(f"html cache get failed: {e}")
            return None

    def put(self, url: str, final_url: str, html: str) -> None:
        if not html or len(html) > _DEFAULT_MAX_FILE_BYTES:
            return
        doc = {"url": url, "final_url": final_url, "html": html, "cached_at": time.time()}
        path = self._path(self._key(url))
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False)
            os.replace(tmp, path)  # 原子替换，避免读到半截文件
            self._maybe_cleanup()
        except Exception as e:
            logger.debug(f"html cache put failed: {e}")

    def _maybe_cleanup(self) -> None:
        """超过文件数上限时按 mtime 清理最旧的 10%。"""
        try:
            files: list[tuple[float, str]] = []
            for root, _dirs, names in os.walk(self._dir):
                for name in names:
                    if name.endswith(".json"):
                        p = os.path.join(root, name)
                        try:
                            files.append((os.path.getmtime(p), p))
                        except OSError:
                            continue
            if len(files) <= _MAX_FILES:
                return
            files.sort()
            for _mtime, p in files[: len(files) - _MAX_FILES + _MAX_FILES // 10]:
                os.remove(p)
        except Exception as e:
            logger.debug(f"html cache cleanup failed: {e}")

    def clear(self) -> int:
        """清空缓存，返回删除的文件数（reindex/诊断用）。"""
        removed = 0
        try:
            for root, _dirs, names in os.walk(self._dir):
                for name in names:
                    if name.endswith(".json"):
                        try:
                            os.remove(os.path.join(root, name))
                            removed += 1
                        except OSError:
                            continue
        except Exception as e:
            logger.debug(f"html cache clear failed: {e}")
        return removed
