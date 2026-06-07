import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保 .env 在读取任何环境变量之前加载（config.py 虽也调用了 load_dotenv，
# 但 app.py 在 route 模块导入前就需要 CORS_ORIGINS，所以这里显式加载）
load_dotenv()

from nia.api.agent import router as agent_router
from nia.api.crawl import router as crawl_router
from nia.api.data import router as data_router
from nia.api.monitor import router as monitor_router
from nia.api.query import router as query_router
from nia.api.settings import router as settings_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # ── 优雅关闭：释放异步浏览器与 LLM 连接池，避免 Windows 上 "Event loop is closed" ──
    try:
        from nia.crawler.browser_pool import AsyncBrowserPool

        await AsyncBrowserPool.close()
    except Exception as e:
        logger.warning(f"browser pool close failed: {e}")


app = FastAPI(title="Nexus Intelligence Agent API", version="2.0.0", lifespan=lifespan)

# CORS — 从环境变量读取允许的 origin 列表，生产环境必须配置
# 注意：allow_credentials=True 时 allow_origins 不能为 ["*"]，详见 CORS 规范
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000")
allow_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
if not allow_origins:
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    # 通配符时不能 allow_credentials，显式列出的 origin 可以
    allow_credentials=allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(crawl_router)
app.include_router(query_router)
app.include_router(data_router)
app.include_router(monitor_router)
app.include_router(settings_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
