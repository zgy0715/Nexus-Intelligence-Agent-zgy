import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter

from nia.storage.database import get_db
from nia.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

_PROVIDER_MODEL_ATTR = {
    "deepseek": "DEEPSEEK_LLM_MODEL",
    "openai": "OPENAI_LLM_MODEL",
    "qwen": "QWEN_LLM_MODEL",
    "ollama": "OLLAMA_LLM_MODEL",
}


def _current_model() -> str:
    attr = _PROVIDER_MODEL_ATTR.get(Config.LLM_PROVIDER.value, "DEEPSEEK_LLM_MODEL")
    return getattr(Config, attr, "") or ""


def _redact_uri(uri: str) -> str:
    """去掉连接串里的密码，避免把凭据直接吐给前端。"""
    try:
        parts = urlsplit(uri or "")
        if not parts.password:
            return uri
        netloc = parts.netloc.replace(f":{parts.password}@", ":***@")
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return "***"


@router.get("/config")
async def get_config():
    return {
        "config": {
            "LLM_PROVIDER": Config.LLM_PROVIDER.value,
            "LLM_MODEL": _current_model(),
            "DEEPSEEK_LLM_MODEL": Config.DEEPSEEK_LLM_MODEL,
            "OPENAI_LLM_MODEL": Config.OPENAI_LLM_MODEL,
            "QWEN_LLM_MODEL": Config.QWEN_LLM_MODEL,
            "OLLAMA_LLM_MODEL": Config.OLLAMA_LLM_MODEL,
            # v3：辅助模型（角色：上下文摘要/查询改写），非敏感项
            "AUX_LLM_PROVIDER": Config.AUX_LLM_PROVIDER,
            "AUX_LLM_MODEL": Config.AUX_LLM_MODEL,
            "AUX_LLM_ENABLED": bool((Config.AUX_LLM_PROVIDER or "").strip()),
            "EMBED_PROVIDER": Config.EMBED_PROVIDER,
            "EMBED_MODEL": Config.EMBED_MODEL,
            "EMBED_DIM": Config.EMBED_DIM,
            "VECTOR_STORE": Config.VECTOR_STORE,
            "QDRANT_URL": _redact_uri(Config.QDRANT_URL),
            "QDRANT_COLLECTION": Config.QDRANT_COLLECTION,
            "REDIS_URL": _redact_uri(Config.REDIS_URL),
            "MYSQL_URL": _redact_uri(Config.MYSQL_URL),
            "LOG_LEVEL": Config.LOG_LEVEL,
            "AI_CACHE_DAYS": Config.AI_CACHE_DAYS,
            "EXTRACTION_FAILURE_THRESHOLD": Config.EXTRACTION_FAILURE_THRESHOLD,
            "DOM_SIMILARITY_THRESHOLD": Config.DOM_SIMILARITY_THRESHOLD,
            "RAG_THRESHOLD": Config.RAG_THRESHOLD,
            "RAG_TOP_K": Config.RAG_TOP_K,
            # v3：混合检索参数组
            "RAG_HYBRID": Config.RAG_HYBRID,
            "RAG_RRF_K": Config.RAG_RRF_K,
            "RAG_CANDIDATE_K": Config.RAG_CANDIDATE_K,
            "RAG_QUERY_REWRITE": Config.RAG_QUERY_REWRITE,
            "RERANK_MODEL": Config.RERANK_MODEL or "",
            "CRAWL_MAX_PAGES": Config.CRAWL_MAX_PAGES,
            "CRAWL_CONCURRENCY": Config.CRAWL_CONCURRENCY,
            "MAX_CONCURRENT_CRAWLS": Config.MAX_CONCURRENT_CRAWLS,
            "API_AUTH_ENABLED": bool((Config.API_AUTH_TOKEN or "").strip()),
        }
    }


# ── 依赖探测（全部阻塞调用，放到线程池里跑） ────────────────────


def _probe_redis() -> dict:
    try:
        import redis as redis_lib

        client = redis_lib.from_url(
            Config.REDIS_URL, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        try:
            client.ping()
            info = client.info("server")
            return {"connected": True, "version": info.get("redis_version")}
        finally:
            client.close()
    except Exception as e:
        logger.info(f"settings: redis probe failed: {e}")
        return {"connected": False, "error": str(e)[:200]}


def _probe_mysql() -> dict:
    try:
        db = get_db()
        db.ping()
        with db.engine.connect() as conn:
            version = conn.exec_driver_sql("SELECT VERSION()").scalar_one()
        return {"connected": True, "version": str(version)}
    except Exception as e:
        logger.info(f"settings: mysql probe failed: {e}")
        return {"connected": False, "error": str(e)[:200]}


def _probe_llm() -> dict:
    status: dict = {
        "connected": False,
        "provider": Config.LLM_PROVIDER.value,
        "model": _current_model(),
    }
    provider = Config.LLM_PROVIDER.value
    try:
        if provider == "ollama":
            base = (Config.OLLAMA_BASE_URL or "").rstrip("/")
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{base}/api/tags")
            if resp.status_code == 200:
                status["connected"] = True
                status["models"] = [m.get("name") for m in resp.json().get("models", [])]
        else:
            cfg = Config.get_llm_config()
            if not cfg.get("api_key"):
                status["error"] = "未配置 API Key"
                return status
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"{cfg['base_url'].rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {cfg['api_key']}"},
                )
            status["connected"] = resp.status_code == 200
            if resp.status_code != 200:
                status["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        logger.info(f"settings: llm probe failed: {e}")
        status["error"] = str(e)[:200]
    return status


def _probe_aux_llm() -> dict:
    """辅助模型健康探测（get_aux_client 内含 60s 缓存探测，不额外打请求）。"""
    provider = (Config.AUX_LLM_PROVIDER or "").strip().lower()
    status: dict = {
        "connected": False,
        "provider": provider or "(未配置)",
        "model": Config.AUX_LLM_MODEL or "",
        "enabled": bool(provider),
        "role": "摘要 / 查询改写（后台任务）",
    }
    if not provider:
        status["error"] = "未启用（AUX_LLM_PROVIDER 为空）"
        return status
    try:
        # 独立事件循环在线程里跑 async 探测（Ollama 走 /api/tags，不触发模型加载）
        import asyncio as _asyncio

        from nia.ai.llm_client import get_aux_client

        async def _probe():
            return await get_aux_client()

        loop = _asyncio.new_event_loop()
        try:
            client = loop.run_until_complete(_probe())
        finally:
            loop.close()
        status["connected"] = client is not None
        if client is None:
            status["error"] = "不可达或模型缺失（自动回退主模型）"
    except Exception as e:
        logger.info(f"settings: aux llm probe failed: {e}")
        status["error"] = str(e)[:200]
    return status


@router.get("/status")
async def get_service_status():
    loop = asyncio.get_running_loop()
    redis_status, mysql_status, llm_status, aux_status = await asyncio.gather(
        loop.run_in_executor(None, _probe_redis),
        loop.run_in_executor(None, _probe_mysql),
        loop.run_in_executor(None, _probe_llm),
        loop.run_in_executor(None, _probe_aux_llm),
    )
    return {
        "redis": redis_status,
        "mysql": mysql_status,
        "llm_provider": llm_status,
        "aux_llm": aux_status,
    }
