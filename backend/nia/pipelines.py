import logging
import uuid
from datetime import datetime
from urllib.parse import urlparse

import redis

from nia.ai.dom_detector import DOMChangeDetector
from nia.ai.extraction_pipeline import AIExtractionPipeline
from nia.ai.rule_learner import RuleLearner
from nia.rag.rag_engine import RAGEngine
from nia.scheduler.distributed_lock import DistributedLock
from nia.storage.data_version import DataVersionControl
from nia.storage.database import DatabaseManager
from nia.utils.config import Config

logger = logging.getLogger(__name__)

__all__ = ["AIExtractionPipeline", "DataStoragePipeline"]


class DataStoragePipeline:
    def __init__(self):
        self.db: DatabaseManager | None = None
        self.rag: RAGEngine | None = None
        self.dom_detector: DOMChangeDetector | None = None
        self.rule_learner: RuleLearner | None = None
        self.version_control: DataVersionControl | None = None
        self.distributed_lock: DistributedLock | None = None
        self.redis_conn: redis.Redis | None = None

    def open_spider(self, spider):
        self.db = DatabaseManager()
        self.db.init_db()
        self.rag = RAGEngine()
        self.redis_conn = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.dom_detector = DOMChangeDetector(self.redis_conn)
        self.rule_learner = RuleLearner(self.redis_conn)
        self.version_control = DataVersionControl(self.db)
        self.distributed_lock = DistributedLock(self.redis_conn)

    def close_spider(self, spider):
        if self.redis_conn:
            self.redis_conn.close()
        if self.db:
            self.db.close()
        self.db = None
        self.rag = None
        self.dom_detector = None
        self.rule_learner = None
        self.version_control = None
        self.distributed_lock = None
        self.redis_conn = None

    def process_item(self, item, spider):
        url = item.get("url", "")
        domain = urlparse(url).netloc
        raw_html = item.get("raw_html", "")
        data_id = str(uuid.uuid4())

        if self.distributed_lock is not None:
            lock_key = f"url:{url}"
            if not self.distributed_lock.acquire(lock_key):
                logger.debug(f"URL is being processed by another node: {url}")
                return item

        try:
            self._store_data(item, url, domain, raw_html, data_id)
            self._index_rag(item, url, data_id)
            self._detect_dom_change(domain, raw_html)
            self._record_extraction_result(item, domain)
            self._track_version(url, item, data_id)
        finally:
            if self.distributed_lock is not None:
                self.distributed_lock.release(lock_key)

        return item

    def _store_data(self, item, url, domain, raw_html, data_id):
        try:
            collection = self.db.get_collection("crawled_data")
            doc = {
                "id": data_id,
                "url": url,
                "domain": domain,
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "raw_html": raw_html,
                "extracted_data": item.get("extracted_data", {}),
                "extraction_method": item.get("extraction_method", ""),
                "dom_hash": item.get("dom_hash", ""),
                "metadata": item.get("metadata", {}),
                "created_at": datetime.utcnow(),
            }
            collection.insert_one(doc)
        except Exception as e:
            logger.error(
                f"Failed to store item for {url}: {e}. "
                f"Item keys: {list(item.keys())[:10] if isinstance(item, dict) else type(item)}"
            )

    def _index_rag(self, item, url, data_id):
        try:
            content_text = item.get("content", "") or ""
            extracted = item.get("extracted_data", {})
            if isinstance(extracted, dict):
                for v in extracted.values():
                    if isinstance(v, str):
                        content_text += "\n" + v
            self.rag.index_data(
                url=url,
                title=item.get("title", ""),
                content=content_text,
                crawled_data_id=data_id,
            )
        except Exception as e:
            logger.error(f"Failed to index data for RAG {url}: {e}")

    def _detect_dom_change(self, domain, raw_html):
        try:
            if raw_html:
                if self.dom_detector.is_page_changed(domain, raw_html):
                    self.dom_detector.update_signature(domain, raw_html)
        except Exception as e:
            logger.error(f"DOM change detection failed for {domain}: {e}")

    def _record_extraction_result(self, item, domain):
        try:
            extraction_method = item.get("extraction_method", "")
            success = bool(extraction_method) and extraction_method != "failed"
            self.rule_learner.record_extraction(domain, success)
        except Exception as e:
            logger.error(f"Rule learner recording failed for {domain}: {e}")

    def _track_version(self, url, item, data_id):
        try:
            collection = self.db.get_collection("crawled_data")
            existing = collection.find_one(
                {"url": url, "id": {"$ne": data_id}},
                sort=[("created_at", -1)],
            )

            if existing and existing.get("extracted_data"):
                old_data = existing["extracted_data"] if isinstance(existing["extracted_data"], dict) else {}
                new_data = item.get("extracted_data", {})
                if isinstance(new_data, dict) and old_data:
                    self.version_control.compare_and_record(old_data, new_data, data_id)
        except Exception as e:
            logger.error(f"Version tracking failed for {url}: {e}")
