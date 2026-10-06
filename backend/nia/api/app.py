import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 确保 .env 在读取任何环境变量之前加载（config.py 虽也调用了 load_dotenv，
# 但 app.py 在 route 模块导入前就需要 CORS_ORIGINS，所以这里显式加载）
load_dotenv()

from nia.api.agent import router as agent_router
from nia.api.crawl import router as crawl_router
from nia.api.data import router as data_router
from nia.api.monitor import router as monitor_router
from nia.api.query import router as query_router
from nia.api.settings import router as settings_router
from nia.utils.config import Config

logging.basicConfig(
    level=getattr(logging, str(Config.LOG_LEVEL).upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _init_storage() -> None:
    """启动时确保 MongoDB 索引存在；失败只告警，不阻断启动。"""
    try:
        from nia.storage.database import get_db

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, get_db().init_db)
        logger.info("MongoDB 索引初始化完成")
    except Exception as e:
        logger.warning(f"MongoDB 初始化失败（服务仍会启动，但部分接口不可用）: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_storage()
    try:
        yield
    finally:
        # ── 优雅关闭：释放异步浏览器、HttpClient 与共享 LLM 连接池 ──
        try:
            from nia.crawler.browser_pool import AsyncBrowserPool

            await AsyncBrowserPool.close()
        except Exception as e:
            logger.warning(f"browser pool close failed: {e}")

        try:
            from nia.rag.rag_engine import reset_rag_engine

            reset_rag_engine()
        except Exception as e:
            logger.warning(f"rag engine close failed: {e}")

        try:
            from nia.api.query import close_ai_client

            close_ai_client()
        except Exception as e:
            logger.debug(f"ai client close skipped: {e}")

        try:
            from nia.storage.database import reset_instance

            reset_instance()
        except Exception as e:
            logger.debug(f"db close skipped: {e}")


app = FastAPI(title="Nexus Intelligence Agent API", version="2.1.0", lifespan=lifespan)

# CORS — 从环境变量读取允许的 origin 列表，生产环境必须配置
# 注意：allow_credentials=True 时 allow_origins 不能为 ["*"]，详见 CORS 规范
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000")
allow_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
if not allow_origins:
    # 空值以前会静默放宽为 ["*"]，这里保持可用但明确告警
    logger.warning("CORS_ORIGINS 为空，已回退为 ['*']（仅建议在本地开发时使用）")
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    # 通配符时不能 allow_credentials，显式列出的 origin 可以
    allow_credentials=allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_token_guard(request: Request, call_next):
    """可选的简单鉴权：设置 API_AUTH_TOKEN 后，/api/* 需要 X-API-Token 头。

    默认空值 = 关闭（保持本地开箱即用）。
    """
    token = (Config.API_AUTH_TOKEN or "").strip()
    if token and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        provided = request.headers.get("x-api-token") or ""
        if provided != token:
            return JSONResponse({"detail": "未授权：缺少或错误的 X-API-Token"}, status_code=401)
    return await call_next(request)


app.include_router(agent_router)
app.include_router(crawl_router)
app.include_router(query_router)
app.include_router(data_router)
app.include_router(monitor_router)
app.include_router(settings_router)


@app.get("/api/health")
async def health_check():
    """存活探针：进程能响应即 ok（不探测外部依赖）。"""
    return {"status": "ok", "version": app.version}


@app.get("/api/ready")
async def readiness_check():
    """就绪探针：真正探测 MongoDB 与 Redis。"""
    result = {"status": "ok", "mongodb": False, "redis": False}

    def _ping_mongo() -> bool:
        from nia.storage.database import get_db

        db = get_db()
        db.ping()  # 失败会抛异常
        return True

    try:
        result["mongodb"] = await asyncio.get_running_loop().run_in_executor(None, _ping_mongo)
    except Exception as e:
        logger.warning(f"readiness: mongodb ping failed: {e}")

    def _ping_redis() -> bool:
        import redis as redis_lib

        client = redis_lib.from_url(Config.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        try:
            return bool(client.ping())
        finally:
            client.close()

    try:
        result["redis"] = await asyncio.get_running_loop().run_in_executor(None, _ping_redis)
    except Exception as e:
        logger.warning(f"readiness: redis ping failed: {e}")

    if not (result["mongodb"] and result["redis"]):
        result["status"] = "degraded"
    return result


# ── 前端静态文件（生产部署：Docker 镜像内由本服务同端口提供 SPA） ──────────
# 未设置 STATIC_DIR 或目录不存在时完全跳过，本地开发仍走 Vite 的 5173。
_static_dir = os.getenv("STATIC_DIR", "")
if _static_dir and os.path.isdir(_static_dir):
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _index_file = os.path.join(_static_dir, "index.html")
    _assets_dir = os.path.join(_static_dir, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def _spa_root():
        return FileResponse(_index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str):
        """静态文件优先；其余路径回落到 index.html（前端路由由 React Router 接管）。"""
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        root = os.path.abspath(_static_dir)
        candidate = os.path.abspath(os.path.join(root, full_path))
        # 防目录穿越：必须仍在静态目录内
        if candidate.startswith(root + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(_index_file)

    logger.info(f"前端静态文件已挂载: {_static_dir}")
