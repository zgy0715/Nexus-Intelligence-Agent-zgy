"""BM25 关键词检索（jieba 分词 + rank-bm25）— 混合检索的关键词路。

动机：纯向量召回对**中文短查询 + 专有名词**（产品名、人名、错误码）召回质量
明显受限——这类词在向量空间里不够显著，但 BM25 精确命中。

设计约束：
- 索引在进程内存中，启动后首次查询时从 MySQL crawled_data 全量构建
  （阻塞调用，必须经 asyncio.to_thread）；之后随 index_data 增量插入；
- jieba 懒加载（首次分词初始化词典，约 1s）；
- 文档量级（本项目的爬取页面数）下 rank-bm25 足够；到十万级应换 tantivy；
- 任何失败静默返回空，不影响向量路检索。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """jieba 分词 + 小写归一 + 去空白（懒加载 jieba，失败退回按空格切分）。"""
    text = (text or "").lower()
    try:
        import jieba

        return [t for t in jieba.lcut(text) if t.strip()]
    except Exception as e:  # pragma: no cover
        logger.debug(f"jieba unavailable, fallback split: {e}")
        return text.split()


@dataclass
class BM25Doc:
    doc_id: str
    text: str


@dataclass
class BM25Index:
    """进程内 BM25 索引。线程安全（RAG 在线程池中调用）。"""

    corpus: list[BM25Doc] = field(default_factory=list)
    _bm25: object | None = None
    _ids: list[str] = field(default_factory=list)
    _id_set: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _built: bool = False

    def __post_init__(self) -> None:
        pass

    @property
    def size(self) -> int:
        return len(self.corpus)

    def build(self, docs: list[BM25Doc]) -> None:
        """全量构建（重复 doc_id 以新文档为准）。"""
        with self._lock:
            merged: dict[str, str] = {}
            for d in docs:
                merged[d.doc_id] = d.text
            self.corpus = [BM25Doc(k, v) for k, v in merged.items()]
            self._rebuild()

    def add(self, doc_id: str, text: str) -> None:
        """增量插入/更新单文档。索引量小时直接重建（rank-bm25 无增量 API）。"""
        if not text:
            return
        with self._lock:
            if doc_id in self._id_set:
                self.corpus = [d for d in self.corpus if d.doc_id != doc_id]
            self.corpus.append(BM25Doc(doc_id, text))
            self._rebuild()

    def remove(self, doc_id: str) -> None:
        with self._lock:
            if doc_id in self._id_set:
                self.corpus = [d for d in self.corpus if d.doc_id != doc_id]
                self._rebuild()

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """返回 [(doc_id, score)]，按分数降序。空索引/未构建返回 []。"""
        with self._lock:
            if self._bm25 is None or not self.corpus:
                return []
            try:
                scores = self._bm25.get_scores(_tokenize(query))
            except Exception as e:
                logger.debug(f"bm25 search failed: {e}")
                return []
            pairs = sorted(zip(self._ids, scores), key=lambda x: x[1], reverse=True)
            return [(doc_id, float(s)) for doc_id, s in pairs[:top_k] if s > 0]

    def _rebuild(self) -> None:
        try:
            # BM25Plus 而非 BM25Okapi：Okapi 的原始 IDF 在「词出现在所有文档」时
            # 会变负（小语料必现），全查询得负分被过滤后永远 0 命中；
            # BM25Plus 保证 IDF 恒正，小语料下排序才有意义。
            from rank_bm25 import BM25Plus

            self._ids = [d.doc_id for d in self.corpus]
            self._id_set = set(self._ids)
            tokenized = [_tokenize(d.text) for d in self.corpus]
            self._bm25 = BM25Plus(tokenized) if tokenized else None
            self._built = True
        except Exception as e:
            logger.warning(f"bm25 rebuild failed: {e}")
            self._bm25 = None


_index: BM25Index | None = None
_index_lock = threading.Lock()


def get_bm25_index() -> BM25Index:
    global _index
    if _index is not None:
        return _index
    with _index_lock:
        if _index is None:
            _index = BM25Index()
        return _index


def reset_bm25_index() -> None:
    global _index
    with _index_lock:
        _index = None


def ensure_bm25_loaded() -> int:
    """确保索引已从 MySQL 构建（阻塞，供线程池调用）。返回索引文档数。"""
    idx = get_bm25_index()
    if idx.size > 0:
        return idx.size
    try:
        from nia.storage.database import get_db

        db = get_db()
        rows = db.list(
            "crawled_data",
            order_by="created_at",
            limit=2000,
            columns=("id", "title", "content"),
        )
        docs = [
            BM25Doc(doc_id=str(r.get("id")), text=f"{r.get('title') or ''}\n{(r.get('content') or '')[:3000]}")
            for r in rows
            if r.get("content")
        ]
        idx.build(docs)
        logger.info(f"BM25 index built: {idx.size} docs")
        return idx.size
    except Exception as e:
        logger.warning(f"bm25 index build failed: {e}")
        return 0
