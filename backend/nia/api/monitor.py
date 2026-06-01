import redis
from fastapi import APIRouter

from nia.monitoring.report import DailyReport
from nia.scheduler.priority_queue import PrioritySpiderScheduler
from nia.scheduler.retry_handler import RetryHandler
from nia.storage.database import DatabaseManager
from nia.utils.config import Config

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

db = DatabaseManager()
redis_conn = redis.from_url(Config.REDIS_URL, decode_responses=True)
report = DailyReport(db, redis_conn)
scheduler = PrioritySpiderScheduler()
retry_handler = RetryHandler()


@router.get("/stats")
async def get_monitor_stats():
    stats = report.get_task_stats()
    return {
        "total_tasks": stats.get("total", 0),
        "success_rate": stats.get("success_rate", 0),
        "llm_calls": stats.get("llm_calls", 0),
        "avg_llm_time": int(stats.get("avg_llm_time_ms", 0)),
        "queue_pending": scheduler.get_queue_size(),
        "dead_letter_count": retry_handler.get_dead_letter_count(),
    }


@router.get("/domains")
async def get_domain_stats():
    stats = report.get_domain_stats()
    return {"domains": stats}


@router.get("/alert")
async def check_alert():
    alert = report.check_alert()
    return {"alert": alert}
