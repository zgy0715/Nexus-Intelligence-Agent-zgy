"""日报/监控统计 — 全部基于 UTC 日窗口。

历史数据里 `created_at` 曾用 `datetime.utcnow().isoformat()` 存成字符串，
新数据存 BSON datetime。MongoDB 不会跨 BSON 类型比较，所以两个窗口都查
（$or），否则统计永远是 0。
"""

import datetime
import logging

import redis

from nia.storage.database import DatabaseManager
from nia.utils.config import Config
from nia.utils.timeutil import utc_date, utc_today_range

logger = logging.getLogger(__name__)


def _window_filter(start: datetime.datetime, end: datetime.datetime) -> dict:
    """同时匹配 BSON datetime 与历史 ISO 字符串。"""
    return {
        "$or": [
            {"created_at": {"$gte": start, "$lt": end}},
            {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}},
        ]
    }


class DailyReport:
    def __init__(self, db: DatabaseManager, redis_conn: redis.Redis | None = None):
        self.db = db
        self.redis = redis_conn

    # ── 概览 ──────────────────────────────────────────────────────

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
            return "监控数据不可用：无法连接 MongoDB，统计结果不可信"
        threshold = float(Config.ALERT_SUCCESS_RATE)
        total = stats.get("total", 0)
        success_rate = stats.get("success_rate", 0.0)
        if total > 0 and success_rate < threshold:
            return f"成功率告警: 当前成功率 {success_rate:.1f}%，低于 {threshold:.0f}% 阈值"
        return None

    # ── 统计 ──────────────────────────────────────────────────────

    def get_task_stats(self) -> dict:
        empty = {
            "total": 0,
            "success_count": 0,
            "success_rate": 0.0,
            "avg_llm_calls": 0.0,
            "avg_llm_time_ms": 0.0,
            "avg_crawl_time_ms": 0.0,
            "llm_calls": 0,
            "error_summary": {},
            "degraded": False,
        }
        start, end = utc_today_range()
        col = self.db.get_collection("crawl_tasks")
        window = _window_filter(start, end)
        try:
            pipeline = [
                {"$match": window},
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "finished": {
                            "$sum": {
                                "$cond": [
                                    {"$in": ["$status", ["completed", "failed"]]}, 1, 0
                                ]
                            }
                        },
                        "success_count": {
                            "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                        },
                        "avg_llm_calls": {"$avg": "$llm_calls"},
                        "avg_llm_time_ms": {"$avg": "$llm_time_ms"},
                        "avg_crawl_time_ms": {"$avg": "$crawl_time_ms"},
                        "llm_calls": {"$sum": "$llm_calls"},
                    }
                },
            ]
            result = list(col.aggregate(pipeline))

            error_pipeline = [
                {"$match": {**window, "status": "failed"}},
                {"$group": {"_id": "$error_type", "cnt": {"$sum": 1}}},
                {"$sort": {"cnt": -1}},
                {"$limit": 5},
            ]
            error_summary = {
                (doc["_id"] or "unknown"): doc["cnt"]
                for doc in col.aggregate(error_pipeline)
            }

            if not result:
                return empty

            r = result[0]
            total = int(r.get("total") or 0)
            # 成功率的分母用“已结束”的任务：把 running/queued 也算进去会低估成功率
            finished = int(r.get("finished") or 0)
            success_count = int(r.get("success_count") or 0)
            success_rate = (success_count / finished * 100) if finished > 0 else 0.0
            return {
                "total": total,
                "finished": finished,
                "success_count": success_count,
                "success_rate": success_rate,
                "avg_llm_calls": float(r.get("avg_llm_calls") or 0),
                "avg_llm_time_ms": float(r.get("avg_llm_time_ms") or 0),
                "avg_crawl_time_ms": float(r.get("avg_crawl_time_ms") or 0),
                "llm_calls": int(r.get("llm_calls") or 0),
                "error_summary": error_summary,
                "degraded": False,
            }
        except Exception as e:
            # 不要把 Mongo 故障伪装成“今天没有流量”
            logger.warning(f"get_task_stats failed: {e}")
            return {**empty, "degraded": True}

    def get_domain_stats(self, days_ago: int = 0) -> list:
        """按域名统计抓取量。

        旧实现读的是 task_logs —— 这个集合在代码里从来没有人写入过，
        所以域名分布永远是空的。这里改为从 crawled_data 聚合。
        """
        start, end = utc_today_range(days_ago)
        try:
            pipeline = [
                {"$match": _window_filter(start, end)},
                {"$group": {"_id": "$domain", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
            rows = self.db.get_collection("crawled_data").aggregate(pipeline)
            return [
                {"domain": doc["_id"] or "(unknown)", "count": doc["count"]}
                for doc in rows
            ]
        except Exception as e:
            logger.warning(f"get_domain_stats failed: {e}")
            return []
