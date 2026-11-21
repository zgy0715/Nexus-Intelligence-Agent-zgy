import asyncio
import logging

from fastapi import APIRouter, Query

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
async def get_domain_stats(days: int = 1):
    """近 days 天（含今天）的域名分布；前端「知识库站点构成」传大窗口取全部历史。"""
    try:
        report = _get_report()
        stats = await _run(report.get_domain_stats, days)
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


@router.get("/timeseries")
async def get_timeseries(days: int = 14):
    """按天聚合近 N 天的任务量 / 成功率 / LLM 均耗时（监控页时间序列图）。"""
    def _query():
        from sqlalchemy import text

        from nia.storage.database import get_db

        engine = get_db().engine
        sql = text(
            """
            SELECT DATE(created_at) AS day,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                   AVG(NULLIF(crawl_time_ms, 0)) AS avg_crawl_ms,
                   SUM(COALESCE(llm_calls, 0)) AS llm_calls
            FROM crawl_tasks
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """
        )
        with engine.connect() as conn:
            rows = conn.execute(sql, {"days": int(days)}).mappings().all()
        return [dict(r) for r in rows]

    try:
        rows = await _run(_query)
        series = [
            {
                "day": str(r["day"]),
                "total": int(r.get("total") or 0),
                "completed": int(r.get("completed") or 0),
                "success_rate": round(
                    100.0 * int(r.get("completed") or 0) / int(r["total"]), 2
                ) if r.get("total") else 0.0,
                "avg_crawl_ms": round(float(r.get("avg_crawl_ms") or 0), 1),
                "llm_calls": int(r.get("llm_calls") or 0),
            }
            for r in rows
        ]
        return {"series": series}
    except Exception as e:
        logger.warning(f"monitor timeseries failed: {e}")
        return {"series": []}


@router.get("/graph")
async def get_crawl_graph():
    """爬取路径图谱：域名级聚合图 + 最近页面级父子链接图（ECharts graph）。"""
    def _query():
        from urllib.parse import urlparse

        from nia.storage.database import get_db

        rows = get_db().list(
            "crawled_data",
            order_by="created_at",
            descending=False,
            limit=2000,
            columns=("id", "url", "domain", "title", "metadata"),
        )
        dcount: dict[str, int] = {}
        dlinks: dict[tuple[str, str], int] = {}
        # 同 URL 多版本只保留最新一条：graph 节点 id 重复会导致 ECharts 崩溃
        by_url: dict[str, dict] = {}
        for r in rows:
            dom = r.get("domain") or "(unknown)"
            dcount[dom] = dcount.get(dom, 0) + 1
            meta = r.get("metadata") or {}
            purl = meta.get("parent_url") or ""
            if purl:
                pdom = urlparse(purl).netloc or "(unknown)"
                # 同域内部导航聚合为自环边（权重=内部链接数），跨域为普通边
                dlinks[(pdom, dom)] = dlinks.get((pdom, dom), 0) + 1
            by_url[r["url"]] = {
                "url": r["url"],
                "domain": dom,
                "title": r.get("title") or r["url"],
                "parent_url": purl,
            }
        pages = list(by_url.values())

        recent = pages[-300:]
        known = {p["url"] for p in recent}
        edges = {
            (p["parent_url"], p["url"])
            for p in recent
            if p["parent_url"] in known and p["parent_url"] != p["url"]
        }
        return {
            "domains": {
                "nodes": [
                    {"id": d, "name": d, "count": c}
                    for d, c in sorted(dcount.items(), key=lambda x: -x[1])[:30]
                ],
                "links": [
                    {"source": s, "target": t, "weight": w}
                    for (s, t), w in sorted(dlinks.items(), key=lambda x: -x[1])[:60]
                ],
            },
            "pages": {
                "nodes": [
                    {"id": p["url"], "name": p["title"][:40], "domain": p["domain"]}
                    for p in recent
                ],
                "links": [{"source": s, "target": t} for s, t in edges],
            },
        }

    try:
        return await _run(_query)
    except Exception as e:
        logger.warning(f"monitor graph failed: {e}")
        return {"domains": {"nodes": [], "links": []}, "pages": {"nodes": [], "links": []}}


@router.get("/cost")
async def get_cost():
    """token 用量与成本估算（数据来自 agent_runs 落库的 usage）。"""
    def _query():
        from nia.storage.database import get_db

        runs = get_db().list(
            "agent_runs", order_by="created_at", limit=100,
            columns=("run_id", "goal", "created_at", "extra"),
        )
        runs.reverse()  # 最新在前
        per_run = []
        total = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for r in runs:
            usage = (r.get("extra") or {}).get("usage") or {}
            for k in total:
                total[k] += int(usage.get(k) or 0)
            per_run.append({
                "run_id": r["run_id"],
                "goal": (r.get("goal") or "")[:60],
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                "total_tokens": int(usage.get("total_tokens") or 0),
                "cost": round(
                    int(usage.get("prompt_tokens") or 0) / 1e6 * Config.LLM_PRICE_INPUT_PER_M
                    + int(usage.get("completion_tokens") or 0) / 1e6 * Config.LLM_PRICE_OUTPUT_PER_M,
                    4,
                ),
            })
        cost = round(
            total["prompt_tokens"] / 1e6 * Config.LLM_PRICE_INPUT_PER_M
            + total["completion_tokens"] / 1e6 * Config.LLM_PRICE_OUTPUT_PER_M,
            4,
        )
        return {
            "total": total,
            "estimated_cost": cost,
            "currency": "CNY",
            "price_per_m": {"input": Config.LLM_PRICE_INPUT_PER_M, "output": Config.LLM_PRICE_OUTPUT_PER_M},
            "runs": per_run,
        }

    try:
        return await _run(_query)
    except Exception as e:
        logger.warning(f"monitor cost failed: {e}")
        return {"total": {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "estimated_cost": 0, "currency": "CNY",
                "price_per_m": {"input": Config.LLM_PRICE_INPUT_PER_M, "output": Config.LLM_PRICE_OUTPUT_PER_M},
                "runs": []}


@router.get("/changes")
async def get_changes(limit: int = Query(50, ge=1, le=200)):
    """站点变更列表（data_versions，定时采集/重复爬取时内容哈希比对产生）。"""
    def _query():
        from nia.storage.database import get_db

        db = get_db()
        rows = db.list("data_versions", order_by="created_at", limit=limit)
        out = []
        for r in rows:
            doc = db.get("crawled_data", id=r["crawled_data_id"]) or {}
            out.append({
                "id": r["id"],
                "url": doc.get("url", ""),
                "title": doc.get("title", ""),
                "domain": doc.get("domain", ""),
                "version_number": r.get("version_number"),
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                "old_snippet": (r.get("old_value") or "")[:200],
                "new_snippet": (r.get("new_value") or "")[:200],
            })
        return out

    try:
        return {"changes": await _run(_query)}
    except Exception as e:
        logger.warning(f"monitor changes failed: {e}")
        return {"changes": []}


@router.get("/heatmap")
async def get_activity_heatmap(days: int = Query(84, ge=7, le=366)):
    """按天聚合的采集活跃度热力图（定时采集页可视化）。

    返回窗口内每一天的：站点变更数（data_versions）与爬取任务数（crawl_tasks）。
    """
    def _query() -> list[dict]:
        from datetime import date, timedelta

        from sqlalchemy import func, select, text

        from nia.storage.database import get_db

        db = get_db()
        start = date.today() - timedelta(days=days - 1)
        vt = db.table("data_versions")
        tt = db.table("crawl_tasks")
        with db.engine.connect() as conn:
            ver_rows = conn.execute(
                select(func.date(vt.c.created_at).label("day"), func.count().label("n"))
                .where(vt.c.created_at >= start)
                .group_by(text("day"))
            ).all()
            task_rows = conn.execute(
                select(func.date(tt.c.created_at).label("day"), func.count().label("n"))
                .where(tt.c.created_at >= start)
                .group_by(text("day"))
            ).all()
        ver_map = {str(r.day): int(r.n) for r in ver_rows}
        task_map = {str(r.day): int(r.n) for r in task_rows}
        out = []
        for i in range(days):
            day = str(start + timedelta(days=i))
            out.append({"date": day, "changes": ver_map.get(day, 0), "tasks": task_map.get(day, 0)})
        return out

    try:
        return {"heatmap": await _run(_query)}
    except Exception as e:
        logger.warning(f"monitor heatmap failed: {e}")
        return {"heatmap": []}
