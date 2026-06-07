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

        # 自动创建 collection（如果不存在）
        collections = [c.name for c in self._client.get_collections().collections]
        if self._collection not in collections:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=1024,  # bge-m3 默认 1024 维
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {self._collection}")

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
        self._index_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "_data",
            "faiss",
        )
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
                self._metadata = []
                self._index = faiss.IndexFlatIP(self._embedding_dim)
                return False
            if self._index.ntotal != len(self._metadata):
                logger.warning(
                    f"Vector store index count ({self._index.ntotal}) "
                    f"does not match metadata count ({len(self._metadata)}), reinitializing"
                )
                self._metadata = []
                self._index = faiss.IndexFlatIP(self._embedding_dim)
                return False
            return True
        except Exception as e:
            logger.warning(f"Failed to load vector store index: {e}")
            return False


# ── 工厂函数 ─────────────────────────────────────────────────────


def get_vector_store() -> BaseVectorStore:
    """根据配置返回对应的向量存储实例。"""
    store_type = Config.VECTOR_STORE
    if store_type == "qdrant":
        return QdrantVectorStore()
    elif store_type == "faiss":
        return FAISSVectorStore(embedding_dim=Config.EMBED_DIM)
    else:
        raise ValueError(f"Unknown vector store: {store_type}")


# ── 兼容旧代码 ───────────────────────────────────────────────────


class VectorStore:
    """兼容旧代码的包装类，自动根据配置选择后端。"""

    def __init__(self, embedding_dim: int = 1024):
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
