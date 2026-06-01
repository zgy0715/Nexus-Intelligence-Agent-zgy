import json
import logging
import uuid
import time

import redis
from fastapi import APIRouter
from pydantic import BaseModel

from nia.scheduler.priority_queue import PrioritySpiderScheduler
from nia.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", tags=["crawl"])

scheduler = PrioritySpiderScheduler()
redis_conn = redis.from_url(Config.REDIS_URL, decode_responses=True)


class CrawlRequest(BaseModel):
    url: str
    instruction: str
    use_js: bool = False


@router.post("")
async def create_crawl_task(req: CrawlRequest):
    task_id = str(uuid.uuid4())
    scheduler.add_url(req.url, priority=10)
    result = {
        "task_id": task_id,
        "url": req.url,
        "instruction": req.instruction,
        "use_js": req.use_js,
        "status": "queued",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        existing = redis_conn.get("crawl_results")
        results = json.loads(existing) if existing else []
        if not isinstance(results, list):
            results = []
    except (redis.RedisError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to read crawl results from Redis: {e}")
        results = []
    results.append(result)
    try:
        redis_conn.set("crawl_results", json.dumps(results, ensure_ascii=False))
    except redis.RedisError as e:
        logger.error(f"Failed to persist crawl results to Redis: {e}")
    return {"task_id": task_id, "status": "queued"}


@router.get("/results")
async def get_crawl_results():
    try:
        existing = redis_conn.get("crawl_results")
        results = json.loads(existing) if existing else []
        if not isinstance(results, list):
            return {"results": []}
        return {"results": results}
    except (redis.RedisError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to read crawl results from Redis: {e}")
        return {"results": []}
