import asyncio
import logging

from fastapi import APIRouter

from nia.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

# 延迟初始化（模块级初始化可能导致启动时因 Redis 不可用而崩溃）
_report = None


def _get_report():
    global _report
    if _report is None:
        from nia.monitoring.report import DailyReport
        from nia.storage.database import get_db

        redis_conn = None
        try:
            import redis as redis_lib

            redis_conn = redis_lib.from_url(Config.REDIS_URL, decode_responses=True)
        except Exception as e:
            logger.warning(f"monitor: redis unavailable: {e}")
        _report = DailyReport(get_db(), redis_conn)
    return _report


async def _run(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


def _queue_pending() -> int:
    """队列中等待/进行中的任务数（真实值，不再硬编码 0）。"""
    from nia.api.crawl import _active_tasks

    return _active_tasks()


@router.get("/stats")
async def get_monitor_stats():
    try:
        report = _get_report()
        stats = await _run(report.get_task_stats)
    except Exception as e:
        logger.warning(f"monitor stats failed: {e}")
        stats = {"total": 0, "success_rate": 0, "llm_calls": 0, "avg_llm_time_ms": 0}

    try:
        pending = _queue_pending()
    except Exception:
        pending = 0

    return {
        "total_tasks": stats.get("total", 0),
        "finished_tasks": stats.get("finished", 0),
        "success_rate": round(float(stats.get("success_rate", 0) or 0), 2),
        "llm_calls": stats.get("llm_calls", 0),
        "avg_llm_time_ms": int(stats.get("avg_llm_time_ms", 0) or 0),
        "avg_llm_time": int(stats.get("avg_llm_time_ms", 0) or 0),  # 兼容旧前端字段名
        "avg_crawl_time_ms": int(stats.get("avg_crawl_time_ms", 0) or 0),
        "avg_llm_calls": round(float(stats.get("avg_llm_calls", 0) or 0), 2),
        "queue_pending": pending,
        "dead_letter_count": 0,
        "error_summary": stats.get("error_summary", {}),
        "degraded": bool(stats.get("degraded")),
    }


@router.get("/domains")
async def get_domain_stats(days_ago: int = 0):
    try:
        report = _get_report()
        stats = await _run(report.get_domain_stats, days_ago)
        return {"domains": stats}
    except Exception as e:
        logger.warning(f"monitor domains failed: {e}")
        return {"domains": []}


@router.get("/alert")
async def check_alert():
    try:
        report = _get_report()
        alert = await _run(report.check_alert)
        return {"alert": alert}
    except Exception as e:
        logger.warning(f"monitor alert failed: {e}")
        return {"alert": f"监控检查失败: {str(e)[:200]}"}
