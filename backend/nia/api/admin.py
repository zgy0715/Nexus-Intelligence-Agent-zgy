"""管理 API — 索引重建等运维操作（本机使用，无鉴权时注意不要暴露公网）。"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reindex")
async def reindex():
    """从 MySQL crawled_data 全量重建向量索引（FAISS IDMap2）与 BM25 索引。

    适用：升级索引格式（如旧版平面索引）、更换 EMBED_MODEL 后、索引损坏时。
    阻塞操作，放线程池执行；数据量大时耗时较长。
    """
    def _rebuild():
        from nia.rag.bm25 import reset_bm25_index
        from nia.rag.rag_engine import get_rag_engine
        from nia.rag.vector_store import get_vector_store
        from nia.storage.database import get_db

        store = get_vector_store()
        store.clear()
        reset_bm25_index()
        engine = get_rag_engine()

        rows = get_db().list(
            "crawled_data",
            order_by="created_at",
            descending=False,
            limit=5000,
            columns=("id", "url", "title", "content"),
        )
        docs = 0
        chunks = 0
        for row in rows:
            content = row.get("content") or ""
            if not content:
                continue
            n = engine.index_data(
                url=row.get("url", ""),
                title=row.get("title", ""),
                content=content,
                crawled_data_id=str(row["id"]),
            )
            docs += 1
            chunks += n
        return {"documents": docs, "chunks": chunks}

    try:
        # shield：重建是重活，客户端断开（如请求超时）不应取消执行中的重建
        result = await asyncio.shield(
            asyncio.get_running_loop().run_in_executor(None, _rebuild)
        )
        return {"message": "索引重建完成", **result}
    except Exception as e:
        logger.exception("reindex failed")
        raise HTTPException(500, f"重建失败: {e}") from e
