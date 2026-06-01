import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen2:7b-instruct")
    OLLAMA_VL_MODEL = os.getenv("OLLAMA_VL_MODEL", "qwen2.5-vl:3b")
    OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "nia")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    AI_CACHE_DAYS = int(os.getenv("AI_CACHE_DAYS", "7"))
    EXTRACTION_FAILURE_THRESHOLD = float(os.getenv("EXTRACTION_FAILURE_THRESHOLD", "0.3"))
    DOM_SIMILARITY_THRESHOLD = float(os.getenv("DOM_SIMILARITY_THRESHOLD", "0.7"))
