import json
import logging

import redis
from fastapi import APIRouter
from pydantic import BaseModel

from nia.rag.rag_engine import RAGEngine
from nia.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

rag_engine = RAGEngine()
redis_conn = redis.from_url(Config.REDIS_URL, decode_responses=True)


class QueryRequest(BaseModel):
    question: str


@router.post("")
async def query_rag(req: QueryRequest):
    try:
        result = rag_engine.query(req.question)
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        result = {
            "answer": f"查询失败: {str(e)[:200]}. 请检查 Ollama 服务是否运行，以及所需模型 (nomic-embed-text, qwen2:7b-instruct) 是否已安装。",
            "sources": [],
        }
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    history_entry = {
        "role": "assistant",
        "content": answer,
        "sources": sources,
    }
    user_entry = {
        "role": "user",
        "content": req.question,
    }
    try:
        existing = redis_conn.get("chat_history")
        history = json.loads(existing) if existing else []
        if not isinstance(history, list):
            history = []
    except (redis.RedisError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to read chat history from Redis: {e}")
        history = []
    history.append(user_entry)
    history.append(history_entry)
    try:
        redis_conn.set("chat_history", json.dumps(history, ensure_ascii=False))
    except redis.RedisError as e:
        logger.error(f"Failed to persist chat history to Redis: {e}")
    return {"answer": answer, "sources": sources}


@router.get("/history")
async def get_chat_history():
    try:
        existing = redis_conn.get("chat_history")
        history = json.loads(existing) if existing else []
        if not isinstance(history, list):
            return {"history": []}
        return {"history": history}
    except (redis.RedisError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to read chat history from Redis: {e}")
        return {"history": []}
