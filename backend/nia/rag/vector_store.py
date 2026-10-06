"""
向量存储 — 支持 Qdrant (推荐) / FAISS
Qdrant: 内置过滤、持久化、Docker 一行启动
FAISS:  纯本地索引，适合小规模场景
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


# ── FAISS 实现（兼容旧版） ──────────────────────────────────────


class FAISSVectorStore(BaseVectorStore):
    """基于 FAISS 的向量存储（兼容旧版，适合小规模场景）。"""

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
        self._metadata: list[dict] = []

        if not self._load_index():
            self._index = faiss.IndexFlatIP(self._embedding_dim)

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

            self._index.add(embeddings_np)

            for idx, chunk in enumerate(chunks):
                self._metadata.append(
                    {
                        "id": str(uuid.uuid4()),
                        "crawled_data_id": crawled_data_id,
                        "content_chunk": chunk,
                        "chunk_index": idx,
                        "url": url,
                        "title": title,
                    }
                )

            self._save_index()

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
            distances, indices = self._index.search(query_np, k)

            results = []
            for i in range(k):
                idx = int(indices[0][i])
                if idx < 0 or idx >= len(self._metadata):
                    continue
                meta = self._metadata[idx]
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
            keep_indices = [
                i
                for i, meta in enumerate(self._metadata)
                if meta["crawled_data_id"] != crawled_data_id
            ]
            keep_metadata = [self._metadata[i] for i in keep_indices]

            if not keep_indices:
                self._index = faiss.IndexFlatIP(self._embedding_dim)
                self._metadata = []
            else:
                kept_vectors = np.zeros(
                    (len(keep_indices), self._embedding_dim), dtype=np.float32
                )
                for new_idx, old_idx in enumerate(keep_indices):
                    kept_vectors[new_idx] = self._index.reconstruct(int(old_idx))
                self._index = faiss.IndexFlatIP(self._embedding_dim)
                self._index.add(kept_vectors)
                self._metadata = keep_metadata

            self._save_index()

    def _save_index(self) -> None:
        os.makedirs(self._index_dir, exist_ok=True)
        import faiss

        faiss.write_index(self._index, self._index_path)
        with open(self._metadata_path, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)

    def _load_index(self) -> bool:
        import faiss

        if not os.path.exists(self._index_path) or not os.path.exists(
            self._metadata_path
        ):
            return False
        try:
            self._index = faiss.read_index(self._index_path)
            with open(self._metadata_path, "r", encoding="utf-8") as f:
                self._metadata = json.load(f)
            if not isinstance(self._metadata, list):
                logger.warning("Vector store metadata is not a list, reinitializing")
                self._reset()
                return False
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
            logger.info(f"FAISS index loaded: {self._index.ntotal} vectors (dim={self._index.d})")
            return True
        except Exception as e:
            logger.warning(f"Failed to load vector store index: {e}")
            return False

    def _reset(self) -> None:
        import faiss

        self._metadata = []
        self._index = faiss.IndexFlatIP(self._embedding_dim)


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
