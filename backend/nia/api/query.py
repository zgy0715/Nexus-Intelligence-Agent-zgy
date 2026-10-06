"""
智能问答 API — RAG 检索 + 普通聊天 自动切换
"""

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from pymongo.errors import PyMongoError

from nia.utils.config import Config
from nia.utils.timeutil import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

# ── 聊天历史配置 ─────────────────────────────────────────────────
CHAT_HISTORY_MAX = 100


def _get_db():
    from nia.storage.database import get_db

    return get_db()


class QueryRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("问题不能为空")
        if len(v) > 2000:
            raise ValueError("问题过长，最多 2000 字符")
        return v


async def _run_sync(fn, *args):
    """把阻塞调用（Mongo/pymongo、向量检索）挪出事件循环。"""
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


async def _save_history(question: str, answer: str, sources: list) -> None:
    def _write():
        collection = _get_db().get_collection("chat_history")
        now = utcnow().isoformat()
        collection.insert_many([
            {"role": "user", "content": question, "created_at": now},
            {"role": "assistant", "content": answer, "sources": sources, "created_at": now},
        ])
        total = collection.count_documents({})
        if total > CHAT_HISTORY_MAX * 2:
            excess = total - CHAT_HISTORY_MAX * 2
            oldest = collection.find({}, {"_id": 1}).sort("created_at", 1).limit(excess)
            ids = [doc["_id"] for doc in oldest]
            if ids:
                collection.delete_many({"_id": {"$in": ids}})

    try:
        await _run_sync(_write)
    except PyMongoError as e:
        logger.warning(f"Failed to save chat history: {e}")
    except Exception as e:
        logger.warning(f"Failed to save chat history: {e}")


_rag_backoff_until = 0.0
# RAG 检索超时/失败后的退避时长（秒）：退避期内直接走普通聊天，避免每次请求都干等
RAG_BACKOFF_SECONDS = 300.0


async def _try_rag(question: str) -> dict | None:
    """尝试 RAG 检索。超时/失败/退避期内返回 None（调用方降级为普通聊天）。"""
    global _rag_backoff_until
    if time.monotonic() < _rag_backoff_until:
        logger.debug("RAG 处于退避期，跳过检索")
        return None
    try:
        from nia.rag.rag_engine import aget_rag_engine

        async def _rag_answer(q: str) -> dict:
            # 引擎构造（ONNX 模型加载）与检索都是阻塞调用，放进线程池执行
            engine = await aget_rag_engine()
            return await engine.aquery(q)

        result = await asyncio.wait_for(
            _rag_answer(question), timeout=max(5.0, Config.RAG_TIMEOUT)
        )
        _rag_backoff_until = 0.0
        return result
    except asyncio.TimeoutError:
        _rag_backoff_until = time.monotonic() + RAG_BACKOFF_SECONDS
        logger.warning(
            f"RAG 检索超时（>{Config.RAG_TIMEOUT}s），{int(RAG_BACKOFF_SECONDS)}s 内跳过 RAG 直接聊天"
        )
        return None
    except Exception as e:
        # 检索管线本身出错（模型未下载/FAISS 损坏等）——记录下来，别静默吞掉
        _rag_backoff_until = time.monotonic() + RAG_BACKOFF_SECONDS
        logger.warning(f"RAG 检索失败，降级为普通聊天: {e}")
        return None


@router.post("")
async def query_smart(req: QueryRequest):
    """智能问答：先尝试 RAG 检索，相关性不足或检索不可用时降级为普通聊天。"""
    question = req.question
    answer = ""
    sources: list = []
    mode = "chat"
    rag_ok = False

    # 第一步：尝试 RAG 检索
    rag_result = await _try_rag(question)
    if rag_result:
        relevance = float(rag_result.get("relevance") or 0.0)
        rag_sources = rag_result.get("sources") or []
        if rag_sources and relevance >= Config.RAG_THRESHOLD:
            answer = rag_result.get("answer") or ""
            sources = rag_sources
            rag_ok = bool(answer.strip())
            mode = "rag"
        else:
            logger.debug(
                "RAG 相关性不足（relevance=%.3f < %.3f, sources=%d），降级为普通聊天",
                relevance, Config.RAG_THRESHOLD, len(rag_sources),
            )

    # 第二步：降级为普通聊天
    if not rag_ok:
        try:
            llm = _get_ai_client()
            answer = await llm.achat(
                [
                    {"role": "system", "content": "你是一个智能助手。用中文回答用户的问题，回答要简洁准确。"},
                    {"role": "user", "content": question},
                ],
                temperature=0.7,
            )
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            answer = "抱歉，暂时无法回答你的问题（LLM 服务不可用）。"
            mode = "error"

    await _save_history(question, answer, sources)
    return {"answer": answer, "sources": sources, "mode": mode}


_ai_client = None


def _get_ai_client():
    """进程内共享的 LLM 客户端（连接池复用）。"""
    global _ai_client
    if _ai_client is None:
        from nia.ai.llm_client import LLMClient

        _ai_client = LLMClient()
    return _ai_client


def close_ai_client() -> None:
    global _ai_client
    if _ai_client is not None:
        try:
            _ai_client.close()
        finally:
            _ai_client = None


@router.get("/history")
async def get_chat_history(limit: int = Query(50, ge=1, le=200)):
    """获取聊天历史（最新的 N 轮；每轮包含 user + assistant 两条）。"""
    def _read():
        cursor = (
            _get_db().get_collection("chat_history")
            .find({}, {"_id": 0})
            .sort("created_at", -1)
            .limit(limit * 2)
        )
        messages = list(cursor)
        messages.reverse()  # 按时间正序
        return messages

    try:
        messages = await _run_sync(_read)
        return {"history": messages, "count": len(messages)}
    except PyMongoError as e:
        logger.warning(f"Failed to read chat history: {e}")
        return {"history": [], "count": 0}


@router.delete("/history")
async def clear_chat_history():
    """清空聊天历史"""
    def _clear():
        return _get_db().get_collection("chat_history").delete_many({}).deleted_count

    try:
        deleted = await _run_sync(_clear)
        return {"message": "聊天记录已清空", "deleted": deleted}
    except PyMongoError as e:
        raise HTTPException(500, f"清空失败: {e}")
