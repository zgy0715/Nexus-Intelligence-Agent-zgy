"""
Embedding 管理器 — 默认 fastembed（本地 ONNX, CPU 即可, 无需 Ollama）。
可选 bge-m3(Ollama) / openai。
"""

from __future__ import annotations

import logging

from nia.utils.config import Config

logger = logging.getLogger(__name__)


class _FastEmbedAdapter:
    """把 fastembed.TextEmbedding 适配成 embed_query / embed_documents 接口。"""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        logger.info(f"Embedding provider: fastembed (local ONNX, {model_name})")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        # query_embed 在部分版本不存在，统一用 embed 兜底
        try:
            return next(iter(self._model.query_embed(text))).tolist()
        except AttributeError:
            return next(iter(self._model.embed([text]))).tolist()


class EmbeddingManager:
    """统一的 Embedding 接口，根据 EMBED_PROVIDER 自动切换后端。"""

    def __init__(self):
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is not None:
            return self._embeddings

        provider = Config.EMBED_PROVIDER
        model = Config.EMBED_MODEL

        if provider == "fastembed":
            self._embeddings = _FastEmbedAdapter(model)
        elif provider == "bge-m3":
            # 本地 bge-m3 via Ollama（保留兼容）
            from langchain_ollama import OllamaEmbeddings

            self._embeddings = OllamaEmbeddings(base_url=Config.OLLAMA_BASE_URL, model=model)
            logger.info("Embedding provider: bge-m3 (local via Ollama)")
        elif provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            self._embeddings = OpenAIEmbeddings(
                api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL, model=model
            )
            logger.info(f"Embedding provider: OpenAI ({model})")
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")

        return self._embeddings

    def embed_text(self, text: str) -> list[float]:
        return self._get_embeddings().embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._get_embeddings().embed_documents(texts)

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """将长文本切分为重叠 chunks。保证 start 严格前进，杜绝死循环。"""
        if not text:
            return []
        text = text.strip()
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + chunk_size, n)
            # 在窗口后半段寻找句子边界，让切分更自然
            if end < n:
                window = text[start:end]
                split = max(
                    window.rfind("。"),
                    window.rfind("！"),
                    window.rfind("？"),
                    window.rfind("\n"),
                    window.rfind(". "),
                    window.rfind(" "),
                )
                if split > chunk_size // 2:
                    end = start + split + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= n:
                break
            start = max(end - overlap, start + 1)  # 关键：严格前进
        return chunks
