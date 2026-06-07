import redis
import requests as req
from fastapi import APIRouter
from pymongo import MongoClient

from nia.storage.database import DatabaseManager
from nia.utils.config import Config

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/config")
async def get_config():
    return {
        "config": {
            "LLM_PROVIDER": Config.LLM_PROVIDER.value,
            "DEEPSEEK_LLM_MODEL": Config.DEEPSEEK_LLM_MODEL,
            "OPENAI_LLM_MODEL": Config.OPENAI_LLM_MODEL,
            "QWEN_LLM_MODEL": Config.QWEN_LLM_MODEL,
            "OLLAMA_LLM_MODEL": Config.OLLAMA_LLM_MODEL,
            "EMBED_PROVIDER": Config.EMBED_PROVIDER,
            "EMBED_MODEL": Config.EMBED_MODEL,
            "VECTOR_STORE": Config.VECTOR_STORE,
            "QDRANT_URL": Config.QDRANT_URL,
            "QDRANT_COLLECTION": Config.QDRANT_COLLECTION,
            "REDIS_URL": Config.REDIS_URL,
            "MONGO_URL": Config.MONGO_URL,
            "MONGO_DB": Config.MONGO_DB,
            "LOG_LEVEL": Config.LOG_LEVEL,
            "AI_CACHE_DAYS": Config.AI_CACHE_DAYS,
            "EXTRACTION_FAILURE_THRESHOLD": Config.EXTRACTION_FAILURE_THRESHOLD,
            "DOM_SIMILARITY_THRESHOLD": Config.DOM_SIMILARITY_THRESHOLD,
            "RAG_THRESHOLD": Config.RAG_THRESHOLD,
        }
    }


@router.get("/status")
async def get_service_status():
    redis_status = {"connected": False}
    try:
        r = redis.from_url(Config.REDIS_URL, decode_responses=True)
        r.ping()
        info = r.info("server")
        redis_status = {"connected": True, "version": info.get("redis_version")}
    except Exception:
        pass

    mongodb_status = {"connected": False}
    try:
        db_manager = DatabaseManager()
        database = db_manager.get_database()
        database.command("ping")
        server_info = db_manager._client.server_info()
        mongodb_status = {"connected": True, "version": server_info.get("version")}
    except Exception:
        pass

    llm_status = {"connected": False, "provider": Config.LLM_PROVIDER.value, "model": Config.DEEPSEEK_LLM_MODEL}
    try:
        if Config.LLM_PROVIDER.value == "deepseek":
            # 测试 DeepSeek API 连接
            resp = req.get(
                f"{Config.DEEPSEEK_BASE_URL}/models",
                headers={"Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}"},
                timeout=5,
            )
            if resp.status_code == 200:
                llm_status["connected"] = True
        elif Config.LLM_PROVIDER.value == "ollama":
            resp = req.get(f"{Config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                llm_status["connected"] = True
                llm_status["models"] = [m.get("name") for m in models]
    except Exception:
        pass

    return {
        "redis": redis_status,
        "mongodb": mongodb_status,
        "llm_provider": llm_status,
    }
