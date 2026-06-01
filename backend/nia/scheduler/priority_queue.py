import json

import redis

from nia.utils.config import Config


class PrioritySpiderScheduler:
    def __init__(self):
        self.redis = redis.from_url(Config.REDIS_URL, decode_responses=True)

    def add_url(self, url: str, priority: int = 0, spider_name: str = "smart"):
        self.redis.zadd(
            f"nia:queue:{spider_name}",
            {json.dumps({"url": url, "priority": priority}): -priority},
        )

    def get_next_url(self, spider_name: str = "smart") -> dict | None:
        key = f"nia:queue:{spider_name}"
        results = self.redis.zpopmin(key, count=1)
        if not results:
            return None
        item_json, score = results[0]
        item = json.loads(item_json)
        item["priority"] = -score
        return item

    def get_queue_size(self, spider_name: str = "smart") -> int:
        return self.redis.zcard(f"nia:queue:{spider_name}")

    def add_urls(self, urls: list, priority: int = 0, spider_name: str = "smart"):
        pipe = self.redis.pipeline()
        key = f"nia:queue:{spider_name}"
        for url in urls:
            member = json.dumps({"url": url, "priority": priority})
            pipe.zadd(key, {member: -priority})
        pipe.execute()
