"""交叉编码重排（可选）— fastembed TextCrossEncoder。

对 RRF 融合后的候选做精排：cross-encoder 把 (query, doc) 一起过模型，
相关性判断质量显著高于双塔向量，但代价是每对都要推理 —— 只对
top RAG_CANDIDATE_K 候选使用。

配置：``RERANK_MODEL``（如 BAAI/bge-reranker-base，约 1GB，走 HF 镜像）。
留空 = 完全禁用（默认），此时融合结果直接按 RRF 排序返回 —— 混合检索
的主体收益来自召回融合，重排是锦上添花，所以默认关闭。
"""

from __future__ import annotations

import logging
import threading

from nia.utils.config import Config

logger = logging.getLogger(__name__)

_encoder = None
_encoder_lock = threading.Lock()
_load_failed = False


def _get_encoder():
    """懒加载 TextCrossEncoder；加载失败永久禁用（进程生命周期内）。"""
    global _encoder, _load_failed
    if not Config.RERANK_MODEL:
        return None
    if _load_failed:
        return None
    if _encoder is None:
        with _encoder_lock:
            if _encoder is not None:
                return _encoder
            try:
                from fastembed import TextCrossEncoder

                _encoder = TextCrossEncoder(model_name=Config.RERANK_MODEL)
                logger.info(f"reranker loaded: {Config.RERANK_MODEL}")
            except Exception as e:
                logger.warning(f"reranker load failed (disabled): {e}")
                _load_failed = True
                return None
    return _encoder


def rerank(query: str, docs: list[tuple[str, str]], top_k: int) -> list[tuple[str, float]]:
    """重排候选。docs = [(doc_id, text)]；返回 [(doc_id, score)] 降序。

    任何失败返回 []（调用方回退 RRF 排序）。
    """
    encoder = _get_encoder()
    if encoder is None or not docs:
        return []
    try:
        query_text = query
        doc_texts = [t for _id, t in docs]
        scores = list(encoder.rerank(query_text, doc_texts))
        pairs = [(docs[i][0], float(s)) for i, s in enumerate(scores)]
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:top_k]
    except Exception as e:
        logger.debug(f"rerank failed: {e}")
        return []
