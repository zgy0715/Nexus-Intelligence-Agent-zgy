import os
from enum import Enum

from dotenv import load_dotenv

load_dotenv()

# ── fastembed 内置模型 → 向量维度 ────────────────────────────────────
# 来源: fastembed.TextEmbedding.list_supported_models()
# 重要: fastembed 只认自己内置的模型 id（其中并没有 BAAI/bge-m3），
#       写错会直接抛异常。新增模型请先跑上面的 list_supported_models() 核对。
FASTEMBED_MODEL_DIMS: dict[str, int] = {
    "BAAI/bge-small-zh-v1.5": 512,
    "BAAI/bge-small-en": 384,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en": 768,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
    "intfloat/multilingual-e5-large": 1024,
    "jinaai/jina-embeddings-v2-base-zh": 768,
    "jinaai/jina-embeddings-v3": 1024,
    "nomic-ai/nomic-embed-text-v1.5": 768,
    "mixedbread-ai/mxbai-embed-large-v1": 1024,
    "thenlper/gte-large": 1024,
    "thenlper/gte-base": 768,
}

# 默认模型: 中文语料友好、体积小（约 90MB）、CPU 推理快
DEFAULT_EMBED_MODEL = "BAAI/bge-small-zh-v1.5"


class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    QWEN = "qwen"
    OLLAMA = "ollama"


class Config:
    # ── LLM Provider ──────────────────────────────────────────────
    LLM_PROVIDER = LLMProvider(os.getenv("LLM_PROVIDER", "deepseek"))

    # DeepSeek
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_LLM_MODEL = os.getenv("DEEPSEEK_LLM_MODEL", "deepseek-chat")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")

    # Qwen (阿里云通义)
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_LLM_MODEL = os.getenv("QWEN_LLM_MODEL", "qwen-plus")

    # Ollama (本地)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen2:7b-instruct")

    # ── Embedding ─────────────────────────────────────────────────
    # fastembed | bge-m3(Ollama) | openai
    # 默认 fastembed: 本地 ONNX, CPU 即可, 无需 Ollama/torch
    EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "fastembed")
    EMBED_MODEL = os.getenv("EMBED_MODEL", DEFAULT_EMBED_MODEL)
    # 模型缓存目录：默认落到 backend/data/fastembed（进程间复用，不必每次重新下载）。
    # 不设置时 fastembed 会用临时目录，进程退出即被清理，每次启动都重新下载。
    FASTEMBED_CACHE_DIR = os.getenv("FASTEMBED_CACHE_DIR", "./data/fastembed")

    # ── Vector Store ──────────────────────────────────────────────
    VECTOR_STORE = os.getenv("VECTOR_STORE", "faiss")  # faiss | qdrant
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "nia_vectors")
    # 相对路径按 backend/ 解析（见 nia/rag/vector_store.py）
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index")
    # 未显式设置时按 EMBED_MODEL 自动推导维度，避免换模型后维度错配
    EMBED_DIM = int(os.getenv("EMBED_DIM") or FASTEMBED_MODEL_DIMS.get(EMBED_MODEL, 512))

    # ── 基础设施 ──────────────────────────────────────────────────
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "nia")

    # ── AI 配置 ───────────────────────────────────────────────────
    AI_CACHE_DAYS = int(os.getenv("AI_CACHE_DAYS", "7"))
    EXTRACTION_FAILURE_THRESHOLD = float(os.getenv("EXTRACTION_FAILURE_THRESHOLD", "0.3"))
    DOM_SIMILARITY_THRESHOLD = float(os.getenv("DOM_SIMILARITY_THRESHOLD", "0.7"))
    RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.3"))
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
    # 单次 RAG 检索（含向量化+检索+LLM）超时秒数；超时降级为普通聊天，避免请求长时间挂住
    RAG_TIMEOUT = float(os.getenv("RAG_TIMEOUT", "60"))

    # LLM 请求（async 路径）
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

    # ── 并发爬取引擎 ──────────────────────────────────────────────
    CRAWL_CONCURRENCY = int(os.getenv("CRAWL_CONCURRENCY", "8"))        # 抓取并发
    CRAWL_LLM_CONCURRENCY = int(os.getenv("CRAWL_LLM_CONCURRENCY", "4"))  # LLM 提取并发
    CRAWL_MAX_PAGES = int(os.getenv("CRAWL_MAX_PAGES", "50"))
    CRAWL_MAX_DEPTH = int(os.getenv("CRAWL_MAX_DEPTH", "2"))
    CRAWL_REQUEST_TIMEOUT = float(os.getenv("CRAWL_REQUEST_TIMEOUT", "30"))
    CRAWL_MAX_RETRIES = int(os.getenv("CRAWL_MAX_RETRIES", "3"))
    CRAWL_JS_CONCURRENCY = int(os.getenv("CRAWL_JS_CONCURRENCY", "4"))  # 浏览器标签页并发
    # 单页响应体上限（字节），防止大文件/解压炸弹撑爆内存
    CRAWL_MAX_CONTENT_BYTES = int(os.getenv("CRAWL_MAX_CONTENT_BYTES", str(5 * 1024 * 1024)))
    # 单域名并发上限（礼貌抓取，避免打挂对方站点）
    CRAWL_PER_DOMAIN_CONCURRENCY = int(os.getenv("CRAWL_PER_DOMAIN_CONCURRENCY", "2"))
    # robots.txt 遵从开关
    CRAWL_RESPECT_ROBOTS = os.getenv("CRAWL_RESPECT_ROBOTS", "true").lower() in ("1", "true", "yes", "on")
    # 单个进程内同时执行的爬取任务上限（防止无上限排队）
    MAX_CONCURRENT_CRAWLS = int(os.getenv("MAX_CONCURRENT_CRAWLS", "4"))

    # ── 监控告警 ──────────────────────────────────────────────────
    ALERT_SUCCESS_RATE = float(os.getenv("ALERT_SUCCESS_RATE", "90"))  # 低于该成功率告警

    # ── 自主爬取 Agent ────────────────────────────────────────────
    AGENT_MAX_PAGES = int(os.getenv("AGENT_MAX_PAGES", "30"))
    AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "20"))
    AGENT_NO_PROGRESS_LIMIT = int(os.getenv("AGENT_NO_PROGRESS_LIMIT", "3"))  # 连续无新发现上限
    # 单次工具调用的超时（秒），保证「取消」能打断进行中的工具
    AGENT_TOOL_TIMEOUT = float(os.getenv("AGENT_TOOL_TIMEOUT", "180"))

    # ── API 访问控制 ──────────────────────────────────────────────
    # 留空 = 不鉴权（仅建议本机使用）；部署到公网请务必设置
    API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")

    # ── 日志 ──────────────────────────────────────────────────────
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def get_llm_config(cls) -> dict:
        """获取当前 LLM Provider 的配置"""
        provider = cls.LLM_PROVIDER
        if provider == LLMProvider.DEEPSEEK:
            return {
                "api_key": cls.DEEPSEEK_API_KEY,
                "base_url": cls.DEEPSEEK_BASE_URL,
                "model": cls.DEEPSEEK_LLM_MODEL,
            }
        elif provider == LLMProvider.OPENAI:
            return {
                "api_key": cls.OPENAI_API_KEY,
                "base_url": cls.OPENAI_BASE_URL,
                "model": cls.OPENAI_LLM_MODEL,
            }
        elif provider == LLMProvider.QWEN:
            return {
                "api_key": cls.QWEN_API_KEY,
                "base_url": cls.QWEN_BASE_URL,
                "model": cls.QWEN_LLM_MODEL,
            }
        elif provider == LLMProvider.OLLAMA:
            return {
                "api_key": "ollama",
                "base_url": cls.OLLAMA_BASE_URL,
                "model": cls.OLLAMA_LLM_MODEL,
            }
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
