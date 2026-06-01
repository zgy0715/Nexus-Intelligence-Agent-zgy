import json
import logging
import os
import threading
import uuid

import faiss
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, embedding_dim: int = 768):
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
        faiss.write_index(self._index, self._index_path)
        with open(self._metadata_path, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)

    def _load_index(self) -> bool:
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
