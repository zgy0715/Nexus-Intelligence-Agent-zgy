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
            "OLLAMA_BASE_URL": Config.OLLAMA_BASE_URL,
            "OLLAMA_LLM_MODEL": Config.OLLAMA_LLM_MODEL,
            "OLLAMA_VL_MODEL": Config.OLLAMA_VL_MODEL,
            "OLLAMA_EMBED_MODEL": Config.OLLAMA_EMBED_MODEL,
            "REDIS_URL": Config.REDIS_URL,
            "MONGO_URL": Config.MONGO_URL,
            "MONGO_DB": Config.MONGO_DB,
            "LOG_LEVEL": Config.LOG_LEVEL,
            "AI_CACHE_DAYS": Config.AI_CACHE_DAYS,
            "EXTRACTION_FAILURE_THRESHOLD": Config.EXTRACTION_FAILURE_THRESHOLD,
            "DOM_SIMILARITY_THRESHOLD": Config.DOM_SIMILARITY_THRESHOLD,
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

    ollama_status = {"connected": False}
    try:
        resp = req.get(f"{Config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m.get("name") for m in models]
            ollama_status = {"connected": True, "models": model_names}
    except Exception:
        pass

    return {
        "redis": redis_status,
        "mongodb": mongodb_status,
        "ollama": ollama_status,
    }
