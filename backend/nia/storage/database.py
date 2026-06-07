from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure

from nia.utils.config import Config


class DatabaseManager:
    def __init__(self):
        self._client: MongoClient | None = None
        self._db: Database | None = None

    def connect(self) -> None:
        if self._client is not None:
            return
        mongo_url = getattr(Config, "MONGO_URL", "mongodb://localhost:27017")
        mongo_db = getattr(Config, "MONGO_DB", "nia")
        self._client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        self._db = self._client[mongo_db]

    def get_database(self) -> Database:
        if self._db is None:
            self.connect()
        return self._db

    def get_collection(self, name: str) -> Collection:
        if self._db is None:
            self.connect()
        return self._db[name]

    def init_db(self) -> None:
        if self._db is None:
            self.connect()

        try:
            self._db["websites"].create_index("domain")
            self._db["extraction_rules"].create_index("website_id")
            self._db["crawled_data"].create_index("url")
            self._db["crawled_data"].create_index("domain")
            self._db["crawled_data"].create_index("created_at")
            self._db["crawl_tasks"].create_index("task_id", unique=True)
            self._db["crawl_tasks"].create_index("status")
            self._db["crawl_tasks"].create_index("created_at")
            self._db["chat_history"].create_index("created_at")
            self._db["chat_history"].create_index("role")
            self._db["vector_data"].create_index("crawled_data_id")
            self._db["task_logs"].create_index("url")
            self._db["task_logs"].create_index("domain")
            self._db["task_logs"].create_index("created_at")
            self._db["agent_runs"].create_index("run_id", unique=True)
            self._db["agent_runs"].create_index("created_at")
        except ConnectionFailure:
            pass

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._db = None
