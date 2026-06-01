import hashlib
import json
import time

import redis

from nia.utils.config import Config


class RetryHandler:
    def __init__(self):
        self.redis = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.max_retries = 3

    def record_failure(self, url: str, spider_name: str, error: str):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        key = f"nia:retry:{url_hash}"
        self.redis.incr(key)
        self.redis.expire(key, 86400)
        item = json.dumps({
            "url": url,
            "spider": spider_name,
            "error": error,
            "timestamp": time.time(),
        }, ensure_ascii=False)
        self.redis.rpush(f"nia:retry_queue:{spider_name}", item)

    def should_retry(self, url: str) -> bool:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        key = f"nia:retry:{url_hash}"
        count = self.redis.get(key)
        if count is None:
            return True
        return int(count) < self.max_retries

    def get_retry_url(self, spider_name: str = "smart") -> str | None:
        item_json = self.redis.lpop(f"nia:retry_queue:{spider_name}")
        if item_json:
            item = json.loads(item_json)
            url = item.get("url")
            if url and self.should_retry(url):
                return url
            else:
                self.move_to_dead_letter(
                    url, spider_name, item.get("error", "重试次数超限")
                )
        return None

    def move_to_dead_letter(self, url: str, spider_name: str, error: str):
        item = json.dumps({
            "url": url,
            "spider": spider_name,
            "error": error,
            "timestamp": time.time(),
        }, ensure_ascii=False)
        self.redis.rpush(f"nia:dead_letter:{spider_name}", item)

    def get_dead_letter_count(self, spider_name: str = "smart") -> int:
        return self.redis.llen(f"nia:dead_letter:{spider_name}")

    def get_dead_letter_items(self, spider_name: str = "smart", limit: int = 10) -> list:
        items = self.redis.lrange(f"nia:dead_letter:{spider_name}", 0, limit - 1)
        return [json.loads(item) for item in items]
