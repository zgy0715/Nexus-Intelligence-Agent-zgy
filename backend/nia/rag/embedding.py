"""
Embedding 管理器 — 默认 fastembed（本地 ONNX, CPU 即可, 无需 Ollama）。
可选 bge-m3(Ollama) / openai。
"""

from __future__ import annotations

import logging
import threading

from nia.utils.config import Config

logger = logging.getLogger(__name__)


class _FastEmbedAdapter:
    """把 fastembed.TextEmbedding 适配成 embed_query / embed_documents 接口。"""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        import os

        from fastembed import TextEmbedding

        # 支持直接指向已下载好的本地模型目录（离线 / 内网环境）
        local_path = model_name if os.path.isdir(model_name) else None
        if local_path is None:
            supported = {m["model"] for m in TextEmbedding.list_supported_models()}
            if model_name not in supported:
                sample = ", ".join(sorted(supported)[:6])
                raise ValueError(
                    f"fastembed 不支持模型 '{model_name}'。请改用内置模型之一，例如: {sample} …"
                    f"（完整列表: python -c \"from fastembed import TextEmbedding; "
                    f"print([m['model'] for m in TextEmbedding.list_supported_models()])\"）"
                    f"，或把 EMBED_MODEL 指向本地模型目录。"
                )

        # cache_dir 必须显式指定：否则 fastembed 下载到临时目录，进程退出即被删除，
        # 每次启动都要重新下载模型。
        resolved_cache = None
        if cache_dir:
            resolved_cache = os.path.abspath(cache_dir)
            os.makedirs(resolved_cache, exist_ok=True)

        kwargs: dict = {"model_name": model_name}
        if resolved_cache:
            kwargs["cache_dir"] = resolved_cache
        if local_path:
            kwargs["specific_model_path"] = os.path.abspath(local_path)

        try:
            self._model = TextEmbedding(**kwargs)
        except Exception as e:
            raise RuntimeError(
                f"加载 fastembed 模型 '{model_name}' 失败: {e}。"
                "首次使用需要联网下载 ONNX 模型；国内网络可设置 "
                "HF_ENDPOINT=https://hf-mirror.com 后重试，"
                "或手动下载模型并设置 EMBED_MODEL=<本地模型目录>。"
            ) from e

        # 部分模型（e5 系列）要求查询/文档使用不同前缀
        self._query_prefix = "query: " if "e5" in model_name.lower() else ""
        self._doc_prefix = "passage: " if "e5" in model_name.lower() else ""
        logger.info(f"Embedding provider: fastembed (local ONNX, {model_name}, cache={resolved_cache})")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        payload = [self._doc_prefix + t for t in texts]
        return [vec.tolist() for vec in self._model.embed(payload)]

    def embed_query(self, text: str) -> list[float]:
        # query_embed 在部分版本不存在，统一用 embed 兜底
        try:
            return next(iter(self._model.query_embed(self._query_prefix + text))).tolist()
        except AttributeError:
            return next(iter(self._model.embed([self._query_prefix + text]))).tolist()


class EmbeddingManager:
    """统一的 Embedding 接口，根据 EMBED_PROVIDER 自动切换后端。"""

    def __init__(self):
        self._embeddings = None
        self._lock = threading.Lock()

    def _get_embeddings(self):
        # 双检锁: 爬取线程池可能并发首次调用，避免重复加载 ONNX 模型
        if self._embeddings is not None:
            return self._embeddings
        with self._lock:
            if self._embeddings is not None:
                return self._embeddings
            self._embeddings = self._build()
        return self._embeddings

    def _build(self):
        provider = Config.EMBED_PROVIDER
        model = Config.EMBED_MODEL

        if provider == "fastembed":
            return _FastEmbedAdapter(model, getattr(Config, "FASTEMBED_CACHE_DIR", None))
        if provider == "bge-m3":
            # 本地 bge-m3 via Ollama（可选，需要额外安装 langchain-ollama）
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError as e:
                raise RuntimeError(
                    "EMBED_PROVIDER=bge-m3 需要 Ollama 与 langchain-ollama："
                    "pip install langchain-ollama。若想零依赖本地推理，请使用 EMBED_PROVIDER=fastembed。"
                ) from e
            logger.info("Embedding provider: bge-m3 (local via Ollama)")
            return OllamaEmbeddings(base_url=Config.OLLAMA_BASE_URL, model=model)
        if provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            logger.info(f"Embedding provider: OpenAI ({model})")
            return OpenAIEmbeddings(
                api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL, model=model
            )
        raise ValueError(
            f"Unknown embedding provider: {provider!r} (可选: fastembed | bge-m3 | openai)"
        )

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
        # overlap 必须严格小于 chunk_size，否则会退化成逐字符滑窗
        chunk_size = max(int(chunk_size), 32)
        overlap = min(max(int(overlap), 0), chunk_size // 2)
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
