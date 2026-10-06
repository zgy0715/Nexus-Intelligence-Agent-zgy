import logging
import threading

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from nia.utils.config import Config

logger = logging.getLogger(__name__)

# (collection, keys, kwargs) —— 启动时统一创建，见 README 的集合说明
_INDEXES: list[tuple[str, list[tuple[str, int]], dict]] = [
    ("websites", [("domain", 1)], {}),
    ("extraction_rules", [("website_id", 1)], {}),
    ("crawled_data", [("url", 1)], {}),
    ("crawled_data", [("domain", 1)], {}),
    ("crawled_data", [("created_at", -1)], {}),
    ("crawl_tasks", [("task_id", 1)], {"unique": True}),
    ("crawl_tasks", [("status", 1)], {}),
    ("crawl_tasks", [("created_at", -1)], {}),
    ("chat_history", [("created_at", -1)], {}),
    ("task_logs", [("url", 1)], {}),
    ("task_logs", [("domain", 1)], {}),
    ("task_logs", [("created_at", -1)], {}),
    ("vector_data", [("crawled_data_id", 1)], {}),
    ("agent_runs", [("run_id", 1)], {"unique": True}),
    ("agent_runs", [("created_at", -1)], {}),
]


class DatabaseManager:
    """进程内共享的 MongoDB 连接。

    MongoClient 自带连接池，每个请求 new 一个实例会不断新建连接池且永不关闭，
    因此这里用单例把连接收敛到一份；`close()` 由应用 lifespan 调用。
    """

    _instance: "DatabaseManager | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._client = None
                    obj._db = None
                    cls._instance = obj
        return cls._instance

    # ── 连接管理 ──────────────────────────────────────────────────

    def connect(self) -> "DatabaseManager":
        if self._client is None:
            self._client = MongoClient(
                Config.MONGO_URL,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=50,
            )
            self._db = self._client[Config.MONGO_DB]
        return self

    def get_database(self) -> Database:
        if self._db is None:
            self.connect()
        return self._db

    def get_collection(self, name: str) -> Collection:
        return self.get_database()[name]

    def ping(self) -> None:
        """主动探活，失败时抛异常（PyMongo 连接是惰性的）。"""
        if self._client is None:
            self.connect()
        self._client.admin.command("ping")

    # ── 初始化 ────────────────────────────────────────────────────

    def init_db(self) -> None:
        """创建集合索引。幂等，可在每次启动时调用。

        MongoDB 不可用时只探活一次就放弃：否则 15 条 create_index 会各等一次
        serverSelectionTimeout，把启动时间拖到几十秒。
        """
        self.get_database()
        try:
            self.ping()
        except Exception as e:
            logger.warning(f"MongoDB 不可用，跳过索引初始化（启动后写入会再报错）: {e}")
            return
        created = 0
        for name, keys, kwargs in _INDEXES:
            try:
                self._db[name].create_index(keys, **kwargs)
                created += 1
            except Exception as e:
                logger.warning(f"create_index failed for {name}{keys}: {e}")
        logger.info(f"MongoDB indexes ensured ({created}/{len(_INDEXES)})")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._db = None

    @classmethod
    def reset_instance(cls) -> None:
        """丢弃单例（测试用）。"""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None


def get_db() -> DatabaseManager:
    """共享的 DatabaseManager（已连接）。"""
    return DatabaseManager().connect()


def reset_instance() -> None:
    """丢弃共享连接（应用关闭 / 测试用）。"""
    DatabaseManager.reset_instance()
