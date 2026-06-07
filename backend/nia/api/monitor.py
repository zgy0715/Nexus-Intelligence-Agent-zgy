import logging

import redis
from fastapi import APIRouter

from nia.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

# 延迟初始化（模块级初始化可能导致启动时因 Redis 不可用而崩溃）
_db = None
_redis_conn = None
_report = None


def _get_report():
    global _db, _redis_conn, _report
    if _report is None:
        from nia.monitoring.report import DailyReport
        from nia.storage.database import DatabaseManager

        _db = DatabaseManager()
        _redis_conn = redis.from_url(Config.REDIS_URL, decode_responses=True)
        _report = DailyReport(_db, _redis_conn)
    return _report


@router.get("/stats")
async def get_monitor_stats():
    report = _get_report()
    stats = report.get_task_stats()
    return {
        "total_tasks": stats.get("total", 0),
        "success_rate": stats.get("success_rate", 0),
        "llm_calls": stats.get("llm_calls", 0),
        "avg_llm_time": int(stats.get("avg_llm_time_ms", 0)),
        "queue_pending": 0,
        "dead_letter_count": 0,
    }


@router.get("/domains")
async def get_domain_stats():
    report = _get_report()
    stats = report.get_domain_stats()
    return {"domains": stats}


@router.get("/alert")
async def check_alert():
    report = _get_report()
    alert = report.check_alert()
    return {"alert": alert}
