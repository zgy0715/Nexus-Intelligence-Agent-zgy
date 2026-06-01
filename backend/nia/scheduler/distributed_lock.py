import uuid

import redis

from nia.utils.config import Config


class DistributedLock:
    def __init__(self, redis_conn: redis.Redis = None, lock_timeout: int = 300):
        if redis_conn is not None:
            self.redis = redis_conn
        else:
            self.redis = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.lock_timeout = lock_timeout
        self._owner_ids = {}

    def acquire(self, resource_key: str) -> bool:
        key = self._lock_key(resource_key)
        owner_id = str(uuid.uuid4())
        acquired = self.redis.set(key, owner_id, nx=True, ex=self.lock_timeout)
        if acquired:
            self._owner_ids[resource_key] = owner_id
            return True
        return False

    def release(self, resource_key: str) -> bool:
        key = self._lock_key(resource_key)
        owner_id = self._owner_ids.get(resource_key)
        if not owner_id:
            return False

        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = self.redis.eval(lua_script, 1, key, owner_id)
        if result:
            self._owner_ids.pop(resource_key, None)
            return True
        return False

    def is_locked(self, resource_key: str) -> bool:
        key = self._lock_key(resource_key)
        return self.redis.exists(key) == 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for resource_key in list(self._owner_ids.keys()):
            self.release(resource_key)
        return False

    def _lock_key(self, resource_key: str) -> str:
        return f"nia:lock:{resource_key}"
