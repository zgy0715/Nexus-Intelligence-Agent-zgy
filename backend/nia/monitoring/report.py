"""Daily monitoring reports backed by MySQL and UTC date windows."""

import logging

import redis
from sqlalchemy import text

from nia.storage.database import DatabaseManager
from nia.utils.config import Config
from nia.utils.timeutil import utc_date, utc_today_range

logger = logging.getLogger(__name__)


class DailyReport:
    def __init__(self, db: DatabaseManager, redis_conn: redis.Redis | None = None):
        self.db = db
        self.redis = redis_conn

    def generate_report(self) -> dict:
        stats = self.get_task_stats()
        return {
            "date": utc_date().isoformat(),
            "total_tasks": stats.get("total", 0),
            "success_rate": stats.get("success_rate", 0),
            "avg_llm_calls": stats.get("avg_llm_calls", 0),
            "avg_llm_time_ms": stats.get("avg_llm_time_ms", 0),
            "avg_crawl_time_ms": stats.get("avg_crawl_time_ms", 0),
            "top_domains": self.get_domain_stats(),
            "error_summary": stats.get("error_summary", {}),
        }

    def check_alert(self) -> str | None:
        stats = self.get_task_stats()
        if stats.get("degraded"):
            return "监控数据不可用：无法连接 MySQL，统计结果不可信"
        threshold = float(Config.ALERT_SUCCESS_RATE)
        total = stats.get("total", 0)
        success_rate = stats.get("success_rate", 0.0)
        if total > 0 and success_rate < threshold:
            return f"成功率告警: 当前成功率 {success_rate:.1f}%，低于 {threshold:.0f}% 阈值"
        return None

    def get_task_stats(self) -> dict:
        empty = {
            "total": 0, "success_count": 0, "success_rate": 0.0,
            "avg_llm_calls": 0.0, "avg_llm_time_ms": 0.0,
            "avg_crawl_time_ms": 0.0, "llm_calls": 0,
            "error_summary": {}, "degraded": False,
        }
        start, end = utc_today_range()
        try:
            stmt = text("""
                SELECT COUNT(*) AS total,
                       SUM(status IN ('completed', 'failed')) AS finished,
                       SUM(status = 'completed') AS success_count,
                       AVG(llm_calls) AS avg_llm_calls,
                       AVG(llm_time_ms) AS avg_llm_time_ms,
                       AVG(crawl_time_ms) AS avg_crawl_time_ms,
                       SUM(llm_calls) AS llm_calls
                  FROM crawl_tasks WHERE created_at >= :start AND created_at < :end
            """)
            errors_stmt = text("""
                SELECT COALESCE(error_type, 'unknown') AS error_type,
                       COUNT(*) AS cnt
                  FROM crawl_tasks
                 WHERE created_at >= :start AND created_at < :end AND status = 'failed'
                 GROUP BY error_type ORDER BY cnt DESC LIMIT 5
            """)
            with self.db.engine.connect() as conn:
                row = conn.execute(stmt, {"start": start, "end": end}).mappings().one()
                error_rows = conn.execute(errors_stmt, {"start": start, "end": end}).mappings().all()
            errors = {item["error_type"] or "unknown": int(item["cnt"]) for item in error_rows}
            total = int(row["total"] or 0)
            finished = int(row["finished"] or 0)
            success_count = int(row["success_count"] or 0)
            return {
                "total": total,
                "finished": finished,
                "success_count": success_count,
                "success_rate": success_count / finished * 100 if finished else 0.0,
                "avg_llm_calls": float(row["avg_llm_calls"] or 0),
                "avg_llm_time_ms": float(row["avg_llm_time_ms"] or 0),
                "avg_crawl_time_ms": float(row["avg_crawl_time_ms"] or 0),
                "llm_calls": int(row["llm_calls"] or 0),
                "error_summary": errors,
                "degraded": False,
            }
        except Exception as e:
            logger.warning("get_task_stats failed: %s", e)
            return {**empty, "degraded": True}

    def get_domain_stats(self, days_ago: int = 0) -> list:
        start, end = utc_today_range(days_ago)
        try:
            stmt = text("""
                SELECT domain, COUNT(*) AS count FROM crawled_data
                 WHERE created_at >= :start AND created_at < :end
                 GROUP BY domain ORDER BY count DESC LIMIT 10
            """)
            with self.db.engine.connect() as conn:
                rows = conn.execute(stmt, {"start": start, "end": end}).mappings().all()
            return [{"domain": row["domain"] or "(unknown)", "count": int(row["count"])} for row in rows]
        except Exception as e:
            logger.warning("get_domain_stats failed: %s", e)
            return []
