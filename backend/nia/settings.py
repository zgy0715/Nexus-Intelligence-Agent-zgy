import os

BOT_NAME = "nia"

SPIDER_MODULES = ["nia.spiders"]
NEWSPIDER_MODULE = "nia.spiders"

ROBOTSTXT_OBEY = False

DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 8

SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

DOWNLOADER_MIDDLEWARES = {
    "nia.middlewares.NiaAntiBlockMiddleware": 400,
    "nia.captcha.captcha_middleware.CaptchaMiddleware": 500,
}

ITEM_PIPELINES = {
    "nia.pipelines.AIExtractionPipeline": 100,
    "nia.pipelines.DataStoragePipeline": 200,
}

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.environ.get("OLLAMA_LLM_MODEL", "qwen2:7b-instruct")
OLLAMA_VL_MODEL = os.environ.get("OLLAMA_VL_MODEL", "qwen2.5-vl:3b")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "nia")

AI_CACHE_DAYS = int(os.environ.get("AI_CACHE_DAYS", "7"))
EXTRACTION_FAILURE_THRESHOLD = float(os.environ.get("EXTRACTION_FAILURE_THRESHOLD", "0.3"))
DOM_SIMILARITY_THRESHOLD = float(os.environ.get("DOM_SIMILARITY_THRESHOLD", "0.7"))

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
}

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

AWS_ENABLED = False

HTTPCACHE_ENABLED = False

FEEDS = {}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
