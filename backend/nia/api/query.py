"""
智能问答 API — RAG 检索 + 普通聊天 自动切换
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from pymongo.errors import PyMongoError

from nia.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

# 延迟初始化
_rag_engine = None
_llm_client = None


def _get_rag_engine():
    global _rag_engine
    if _rag_engine is None:
        from nia.rag.rag_engine import RAGEngine
        _rag_engine = RAGEngine()
    return _rag_engine


def _get_llm_client():
    global _llm_client
    if _llm_client is None:
        from nia.ai.llm_client import LLMClient
        _llm_client = LLMClient()
    return _llm_client


# ── 聊天历史配置 ─────────────────────────────────────────────────
CHAT_HISTORY_MAX = 100


def _get_db():
    from nia.storage.database import DatabaseManager
    db = DatabaseManager()
    db.connect()
    return db


class QueryRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        if len(v) > 2000:
            raise ValueError("问题过长，最多 2000 字符")
        return v


@router.post("")
async def query_smart(req: QueryRequest):
    """智能问答：先尝试 RAG 检索，无结果则直接和 LLM 聊天"""
    question = req.question
    answer = ""
    sources = []

    # 第一步：尝试 RAG 检索
    RAG_THRESHOLD = Config.RAG_THRESHOLD  # 相似度阈值，低于此值用普通聊天
    try:
        rag_result = _get_rag_engine().query(question)
        rag_answer = rag_result.get("answer", "")
        rag_sources = rag_result.get("sources", [])
        relevance = rag_result.get("relevance", 0.0)

        # 如果 RAG 搜到高相关内容，使用 RAG 回答
        if rag_sources and relevance >= RAG_THRESHOLD:
            answer = rag_answer
            sources = rag_sources
        else:
            # 相关性不够，降级到普通聊天
            raise Exception("low relevance")
    except Exception:
        # RAG 失败或无数据，使用普通 LLM 聊天
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            llm = _get_llm_client()
            messages = [
                SystemMessage(content=(
                    "你是一个智能助手。用中文回答用户的问题，回答要简洁准确。"
                )),
                HumanMessage(content=question),
            ]
            answer = llm.chat(messages, temperature=0.7)
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            answer = f"抱歉，暂时无法回答你的问题。错误信息：{str(e)[:200]}"

    # 保存聊天记录到 MongoDB
    try:
        db = _get_db()
        collection = db.get_collection("chat_history")

        collection.insert_one({
            "role": "user",
            "content": question,
            "created_at": datetime.utcnow().isoformat(),
        })
        collection.insert_one({
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "created_at": datetime.utcnow().isoformat(),
        })

        # 限制总条数
        total = collection.count_documents({})
        if total > CHAT_HISTORY_MAX * 2:
            excess = total - CHAT_HISTORY_MAX * 2
            oldest = collection.find().sort("created_at", 1).limit(excess)
            oldest_ids = [doc["_id"] for doc in oldest]
            collection.delete_many({"_id": {"$in": oldest_ids}})

    except PyMongoError as e:
        logger.warning(f"Failed to save chat history: {e}")

    return {"answer": answer, "sources": sources}


@router.get("/history")
async def get_chat_history(limit: int = Query(50, ge=1, le=200)):
    """获取聊天历史（最新的 N 条）"""
    try:
        db = _get_db()
        collection = db.get_collection("chat_history")
        cursor = collection.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).limit(limit * 2)  # *2 因为每轮有 user + assistant
        messages = list(cursor)
        messages.reverse()  # 按时间正序
        return {"history": messages}
    except PyMongoError as e:
        logger.warning(f"Failed to read chat history: {e}")
        return {"history": []}


@router.delete("/history")
async def clear_chat_history():
    """清空聊天历史"""
    try:
        db = _get_db()
        collection = db.get_collection("chat_history")
        collection.delete_many({})
        return {"message": "聊天记录已清空"}
    except PyMongoError as e:
        raise HTTPException(500, f"清空失败: {e}")
