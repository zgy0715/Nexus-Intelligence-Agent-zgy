import os
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


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
    # fastembed | bge-m3(ollama) | deepseek | openai
    # 默认 fastembed：本地 ONNX，CPU 即可，无需 Ollama/torch；bge-m3 = 1024 维
    EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "fastembed")
    EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")

    # ── Vector Store ──────────────────────────────────────────────
    VECTOR_STORE = os.getenv("VECTOR_STORE", "faiss")  # faiss | qdrant
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "nia_vectors")
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index")
    EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))  # bge-m3=1024, bge-small=384

    # ── 基础设施 ──────────────────────────────────────────────────
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "nia")

    # ── AI 配置 ───────────────────────────────────────────────────
    AI_CACHE_DAYS = int(os.getenv("AI_CACHE_DAYS", "7"))
    EXTRACTION_FAILURE_THRESHOLD = float(os.getenv("EXTRACTION_FAILURE_THRESHOLD", "0.3"))
    DOM_SIMILARITY_THRESHOLD = float(os.getenv("DOM_SIMILARITY_THRESHOLD", "0.7"))
    RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.3"))

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

    # ── 自主爬取 Agent ────────────────────────────────────────────
    AGENT_MAX_PAGES = int(os.getenv("AGENT_MAX_PAGES", "30"))
    AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "20"))
    AGENT_NO_PROGRESS_LIMIT = int(os.getenv("AGENT_NO_PROGRESS_LIMIT", "3"))  # 连续无新发现上限

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
