"""
向量存储 — 支持 FAISS（默认，纯本地）/ Qdrant（可选）
FAISS:  零依赖本地索引，适合单机场景；序列化读写规避 Windows 非 ASCII 路径问题
Qdrant: 内置过滤、持久化，适合多实例部署
"""

import json
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod

import numpy as np

from nia.utils.config import Config

logger = logging.getLogger(__name__)

_RAG_DIR = os.path.dirname(os.path.abspath(__file__))      # backend/nia/rag
_PKG_DIR = os.path.dirname(_RAG_DIR)                        # backend/nia
_BACKEND_DIR = os.path.dirname(_PKG_DIR)                    # backend


class BaseVectorStore(ABC):
    """向量存储抽象基类。"""

    @abstractmethod
    def add_vectors(
        self,
        crawled_data_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        url: str = "",
        title: str = "",
    ) -> None:
        ...

    @abstractmethod
    def similarity_search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        ...

    @abstractmethod
    def delete_vectors(self, crawled_data_id: str) -> None:
        ...


# ── Qdrant 实现 ──────────────────────────────────────────────────


class QdrantVectorStore(BaseVectorStore):
    """基于 Qdrant 的向量存储，支持过滤、持久化。"""

    def __init__(self):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._client = QdrantClient(url=Config.QDRANT_URL)
        self._collection = Config.QDRANT_COLLECTION
        self._embedding_dim = Config.EMBED_DIM

        # 自动创建 collection（如果不存在）
        existing = {c.name: c for c in self._client.get_collections().collections}
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                f"Created Qdrant collection: {self._collection} (dim={self._embedding_dim})"
            )
        else:
            self._validate_collection_dim()

    def _validate_collection_dim(self) -> None:
        """已有 collection 的维度必须与当前 Embedding 模型一致，否则写入必然失败。"""
        try:
            info = self._client.get_collection(self._collection)
            size = info.config.params.vectors.size
        except Exception as e:  # Qdrant 版本差异 / 网络问题，不阻塞启动
            logger.warning(f"Cannot inspect Qdrant collection dim: {e}")
            return
        if size != self._embedding_dim:
            raise RuntimeError(
                f"Qdrant collection '{self._collection}' 维度为 {size}，"
                f"但当前 EMBED_DIM={self._embedding_dim}（EMBED_MODEL={Config.EMBED_MODEL}）。"
                f"请改回匹配的 EMBED_DIM，或删除该 collection 后重新索引。"
            )

    def add_vectors(
        self,
        crawled_data_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        url: str = "",
        title: str = "",
    ) -> None:
        from qdrant_client.models import PointStruct

        points = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "crawled_data_id": crawled_data_id,
                        "content_chunk": chunk,
                        "chunk_index": idx,
                        "url": url,
                        "title": title,
                    },
                )
            )

        if points:
            self._client.upsert(collection_name=self._collection, points=points)

    def similarity_search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        results = self._client.search(
            collection_name=self._collection,
            query_vector=query_embedding,
            limit=top_k,
        )
        return [
            {
                "id": hit.id,
                "crawled_data_id": hit.payload.get("crawled_data_id", ""),
                "content_chunk": hit.payload.get("content_chunk", ""),
                "similarity_score": hit.score,
                "url": hit.payload.get("url", ""),
                "title": hit.payload.get("title", ""),
            }
            for hit in results
        ]

    def delete_vectors(self, crawled_data_id: str) -> None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="crawled_data_id",
                        match=MatchValue(value=crawled_data_id),
                    )
                ]
            ),
        )


# ── FAISS 实现 ──────────────────────────────────────────────────


class FAISSVectorStore(BaseVectorStore):
    """基于 FAISS IndexIDMap2 的向量存储。

    v3：从「向量列表位置即 id」改为 IndexIDMap2 显式 int id ——
    删除文档变成 ``remove_ids``（O(删除数)），替代旧版
    reconstruct 全量向量 + 重建整个索引的 O(n) 放大。
    旧版平面索引文件不再兼容（加载时丢弃，用 /api/admin/reindex 重建）。
    """

    def __init__(self, embedding_dim: int = 1024):
        import faiss

        self._embedding_dim = embedding_dim
        # FAISS_INDEX_PATH 若已配置则按它解析（相对路径以 backend/ 为基准），否则用默认目录
        configured = Config.FAISS_INDEX_PATH
        if configured and configured != "./data/faiss_index":
            base = configured
            if not os.path.isabs(base):
                base = os.path.join(_BACKEND_DIR, base)
            self._index_dir = base
        else:
            self._index_dir = os.path.join(_PKG_DIR, "_data", "faiss")
        self._index_path = os.path.join(self._index_dir, "index.faiss")
        self._metadata_path = os.path.join(self._index_dir, "metadata.json")
        self._lock = threading.Lock()
        self._metadata: list[dict] = []  # 每项含 faiss_id（int）
        self._by_id: dict[int, dict] = {}
        self._next_id = 1

        self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(self._embedding_dim))
        if not self._load_index():
            self._reset()

    # ── 写入 ─────────────────────────────────────────────────────

    def add_vectors(
        self,
        crawled_data_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        url: str = "",
        title: str = "",
    ) -> None:
        import faiss

        with self._lock:
            embeddings_np = np.array(embeddings, dtype=np.float32)
            # 元数据必须与写入的向量一一对应，否则索引与元数据永久错位
            if embeddings_np.size == 0 or embeddings_np.shape[0] != len(chunks):
                logger.warning(
                    f"add_vectors skipped: {len(chunks)} chunks vs "
                    f"{embeddings_np.shape[0] if embeddings_np.ndim == 2 else 0} embeddings"
                )
                return
            if embeddings_np.shape[1] != self._embedding_dim:
                raise ValueError(
                    f"向量维度 {embeddings_np.shape[1]} 与索引维度 {self._embedding_dim} 不一致，"
                    f"请检查 EMBED_MODEL / EMBED_DIM 配置并重建索引。"
                )
            norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embeddings_np = embeddings_np / norms

            ids = np.arange(self._next_id, self._next_id + len(chunks), dtype=np.int64)
            self._index.add_with_ids(embeddings_np, ids)

            for faiss_id, idx, chunk in zip(ids, range(len(chunks)), chunks):
                meta = {
                    "faiss_id": int(faiss_id),
                    "id": str(uuid.uuid4()),
                    "crawled_data_id": crawled_data_id,
                    "content_chunk": chunk,
                    "chunk_index": idx,
                    "url": url,
                    "title": title,
                }
                self._metadata.append(meta)
                self._by_id[int(faiss_id)] = meta
            self._next_id += len(chunks)

            self._save_index()

    # ── 检索 ─────────────────────────────────────────────────────

    def similarity_search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        with self._lock:
            if self._index.ntotal == 0:
                return []

            query_np = np.array([query_embedding], dtype=np.float32)
            norm = np.linalg.norm(query_np)
            if norm > 0:
                query_np = query_np / norm

            k = min(top_k, self._index.ntotal)
            distances, ids = self._index.search(query_np, k)

            results = []
            for i in range(k):
                faiss_id = int(ids[0][i])
                meta = self._by_id.get(faiss_id)
                if meta is None:
                    continue
                results.append(
                    {
                        "id": meta["id"],
                        "crawled_data_id": meta["crawled_data_id"],
                        "content_chunk": meta["content_chunk"],
                        "similarity_score": float(distances[0][i]),
                        "url": meta.get("url", ""),
                        "title": meta.get("title", ""),
                    }
                )
            return results

    def delete_vectors(self, crawled_data_id: str) -> None:
        import faiss

        with self._lock:
            remove_ids = [
                m["faiss_id"] for m in self._metadata if m["crawled_data_id"] == crawled_data_id
            ]
            if not remove_ids:
                return
            # IDMap2 支持 remove_ids：O(删除数)，替代旧版全量 reconstruct + 重建
            self._index.remove_ids(np.array(remove_ids, dtype=np.int64))
            removed = set(remove_ids)
            self._metadata = [m for m in self._metadata if m["faiss_id"] not in removed]
            for fid in removed:
                self._by_id.pop(fid, None)
            self._save_index()

    def clear(self) -> None:
        """清空索引（reindex 前调用）。"""
        with self._lock:
            self._reset()
            self._save_index()

    def _save_index(self) -> None:
        os.makedirs(self._index_dir, exist_ok=True)
        import faiss

        # faiss.write_index 走 C 层 fopen，在 Windows 上无法处理含非 ASCII 字符的
        # 路径（如中文项目目录）。serialize 成字节流后用 Python open() 写盘绕开。
        data = faiss.serialize_index(self._index)
        with open(self._index_path, "wb") as f:
            f.write(np.asarray(data).tobytes())
        with open(self._metadata_path, "w", encoding="utf-8") as f:
            json.dump({"next_id": self._next_id, "items": self._metadata}, f, ensure_ascii=False)

    def _load_index(self) -> bool:
        import faiss

        if not os.path.exists(self._index_path) or not os.path.exists(
            self._metadata_path
        ):
            return False
        try:
            # 对应 _save_index 的 serialize 写盘格式（绕开 faiss C 层 fopen 的
            # Windows 非 ASCII 路径问题）
            with open(self._index_path, "rb") as f:
                index = faiss.deserialize_index(np.frombuffer(f.read(), dtype=np.uint8))
            if not isinstance(index, faiss.IndexIDMap2):
                logger.warning(
                    "检测到旧版平面索引格式（v3 前），已丢弃；请调用 /api/admin/reindex 重建"
                )
                return False
            with open(self._metadata_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if not isinstance(doc, dict) or "items" not in doc:
                logger.warning("Vector store metadata format unexpected, reinitializing")
                return False
            self._index = index
            self._metadata = doc["items"]
            self._next_id = int(doc.get("next_id", 1))
            self._by_id = {m["faiss_id"]: m for m in self._metadata}
            if self._index.d != self._embedding_dim:
                logger.warning(
                    f"索引维度 ({self._index.d}) 与当前 EMBED_DIM ({self._embedding_dim}) "
                    f"不一致（EMBED_MODEL={Config.EMBED_MODEL}），丢弃旧索引并重建"
                )
                self._reset()
                return False
            if self._index.ntotal != len(self._metadata):
                logger.warning(
                    f"Vector store index count ({self._index.ntotal}) "
                    f"does not match metadata count ({len(self._metadata)}), reinitializing"
                )
                self._reset()
                return False
            logger.info(f"FAISS index loaded: {self._index.ntotal} vectors (dim={self._index.d}, IDMap2)")
            return True
        except Exception as e:
            logger.warning(f"Failed to load vector store index: {e}")
            return False

    def _reset(self) -> None:
        import faiss

        self._metadata = []
        self._by_id = {}
        self._next_id = 1
        self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(self._embedding_dim))


# ── 工厂函数 ─────────────────────────────────────────────────────

_store_lock = threading.Lock()
_store: "BaseVectorStore | None" = None


def get_vector_store() -> BaseVectorStore:
    """返回**进程内唯一**的向量存储实例。

    FAISS 后端每次写盘都是"整索引覆盖"，多个实例并存会导致最后一个写者
    覆盖其它实例的写入，而且后创建的实例看不到此前索引的数据 —— 因此必须
    全进程共用一个实例（读写都在同一份内存索引上）。
    """
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        store_type = Config.VECTOR_STORE
        if store_type == "qdrant":
            _store = QdrantVectorStore()
        elif store_type == "faiss":
            _store = FAISSVectorStore(embedding_dim=Config.EMBED_DIM)
        else:
            raise ValueError(
                f"Unknown vector store: {store_type!r} (可选: faiss | qdrant)"
            )
        return _store


def reset_vector_store() -> None:
    """丢弃缓存的实例（测试或配置变更后使用）。"""
    global _store
    with _store_lock:
        _store = None


# ── 兼容旧代码 ───────────────────────────────────────────────────


class VectorStore:
    """兼容旧代码的包装类，委托给进程内共享的后端实例。"""

    def __init__(self, embedding_dim: int | None = None):
        self._store = get_vector_store()

    def add_vectors(
        self,
        crawled_data_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        url: str = "",
        title: str = "",
    ) -> None:
        self._store.add_vectors(crawled_data_id, chunks, embeddings, url, title)

    def similarity_search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        return self._store.similarity_search(query_embedding, top_k)

    def delete_vectors(self, crawled_data_id: str) -> None:
        self._store.delete_vectors(crawled_data_id)
