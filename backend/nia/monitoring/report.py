import datetime

import redis

from nia.storage.database import DatabaseManager


class DailyReport:
    def __init__(self, db: DatabaseManager, redis_conn: redis.Redis):
        self.db = db
        self.redis = redis_conn

    def generate_report(self) -> dict:
        stats = self.get_task_stats()
        domain_stats = self.get_domain_stats()
        return {
            "date": datetime.date.today().isoformat(),
            "total_tasks": stats.get("total", 0),
            "success_rate": stats.get("success_rate", 0),
            "avg_llm_calls": stats.get("avg_llm_calls", 0),
            "avg_llm_time_ms": stats.get("avg_llm_time_ms", 0),
            "avg_crawl_time_ms": stats.get("avg_crawl_time_ms", 0),
            "top_domains": domain_stats,
            "error_summary": stats.get("error_summary", {}),
        }

    def check_alert(self) -> str | None:
        stats = self.get_task_stats()
        success_rate = stats.get("success_rate", 0)
        if success_rate < 90 and stats.get("total", 0) > 0:
            return f"成功率告警: 当前成功率 {success_rate:.1f}%，低于 90% 阈值"
        return None

    def get_task_stats(self) -> dict:
        today = datetime.date.today()
        start = datetime.datetime.combine(today, datetime.time.min)
        end = datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time.min)
        col = self.db.get_collection("crawl_tasks")
        try:
            pipeline = [
                {
                    "$match": {
                        "created_at": {"$gte": start, "$lt": end},
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "success_count": {
                            "$sum": {
                                "$cond": [{"$eq": ["$status", "completed"]}, 1, 0]
                            }
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
                {
                    "$match": {
                        "created_at": {"$gte": start, "$lt": end},
                        "status": "failed",
                    }
                },
                {
                    "$group": {
                        "_id": "$error_type",
                        "cnt": {"$sum": 1},
                    }
                },
                {"$sort": {"cnt": -1}},
                {"$limit": 5},
            ]
            error_result = list(col.aggregate(error_pipeline))
            error_summary = {doc["_id"]: doc["cnt"] for doc in error_result if doc["_id"]}

            if result:
                r = result[0]
                total = r["total"]
                success_count = r["success_count"]
                success_rate = (success_count / total * 100) if total > 0 else 0
                return {
                    "total": total,
                    "success_count": success_count,
                    "success_rate": success_rate,
                    "avg_llm_calls": float(r.get("avg_llm_calls") or 0),
                    "avg_llm_time_ms": float(r.get("avg_llm_time_ms") or 0),
                    "avg_crawl_time_ms": float(r.get("avg_crawl_time_ms") or 0),
                    "llm_calls": int(r.get("llm_calls") or 0),
                    "error_summary": error_summary,
                }

            return {
                "total": 0,
                "success_count": 0,
                "success_rate": 0,
                "avg_llm_calls": 0,
                "avg_llm_time_ms": 0,
                "avg_crawl_time_ms": 0,
                "llm_calls": 0,
                "error_summary": {},
            }
        except Exception:
            return {
                "total": 0,
                "success_count": 0,
                "success_rate": 0,
                "avg_llm_calls": 0,
                "avg_llm_time_ms": 0,
                "avg_crawl_time_ms": 0,
                "llm_calls": 0,
                "error_summary": {},
            }

    def get_domain_stats(self) -> list:
        today = datetime.date.today()
        start = datetime.datetime.combine(today, datetime.time.min)
        end = datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time.min)
        col = self.db.get_collection("task_logs")
        try:
            pipeline = [
                {
                    "$match": {
                        "created_at": {"$gte": start, "$lt": end},
                    }
                },
                {
                    "$group": {
                        "_id": "$domain",
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
            result = list(col.aggregate(pipeline))
            return [{"domain": doc["_id"], "count": doc["count"]} for doc in result]
        except Exception:
            return []
