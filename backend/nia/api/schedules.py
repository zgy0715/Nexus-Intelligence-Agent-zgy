"""定时采集 API + 进程内调度器。

调度器每 30s 扫描到期任务（next_run_at <= now 且 enabled），到期即跑一次
CrawlEngine；页面经 crawl._persist_page 落库 + 索引 + 变更检测。
单进程内存调度（与任务状态同生命周期），重启后按 next_run_at 自动恢复节奏。
"""

import asyncio
import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from nia.storage.database import get_db
from nia.utils.timeutil import utcnow
from nia.utils.url_safety import is_safe_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

_TICK_SECONDS = 30.0
_running: set[str] = set()


class ScheduleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    seeds: list[str]
    instruction: str = Field("", max_length=2000)
    interval_minutes: int = Field(60, ge=5, le=10080)
    max_depth: int = Field(0, ge=0, le=5)
    max_pages: int = Field(20, ge=1, le=500)
    same_domain_only: bool = True
    use_js: bool = False
    enabled: bool = True

    @field_validator("seeds")
    @classmethod
    def _seeds(cls, v: list[str]) -> list[str]:
        cleaned = []
        for s in v or []:
            s = (s or "").strip()
            if not s:
                continue
            # resolve=True 与 crawl/agent 入口一致：域名解析结果也过内网检查
            ok, reason = is_safe_url(s, resolve=True)
            if not ok:
                raise ValueError(f"URL 不合法（{reason}）: {s}")
            if s not in cleaned:  # 去重，与其他入口保持一致
                cleaned.append(s)
        if not cleaned:
            raise ValueError("至少需要一个有效的 URL")
        if len(cleaned) > 10:
            raise ValueError("URL 最多 10 个")
        return cleaned


class SchedulePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    instruction: str | None = Field(None, max_length=2000)
    interval_minutes: int | None = Field(None, ge=5, le=10080)
    max_depth: int | None = Field(None, ge=0, le=5)
    max_pages: int | None = Field(None, ge=1, le=500)
    enabled: bool | None = None


def _serialize(doc: dict) -> dict:
    out = dict(doc)
    for key in ("last_run_at", "next_run_at", "created_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


@router.get("")
async def list_schedules():
    def _read():
        return [_serialize(d) for d in get_db().list("crawl_schedules", order_by="created_at", limit=100)]

    try:
        return {"schedules": await asyncio.get_running_loop().run_in_executor(None, _read)}
    except Exception as e:
        logger.warning(f"list schedules failed: {e}")
        return {"schedules": []}


@router.post("")
async def create_schedule(req: ScheduleRequest):
    doc = {
        "id": uuid.uuid4().hex,
        **req.model_dump(),
        "last_run_at": None,
        "next_run_at": utcnow(),  # 创建后立即跑首轮
        "last_status": "",
        "created_at": utcnow(),
    }

    def _write():
        get_db().insert("crawl_schedules", doc)

    await asyncio.get_running_loop().run_in_executor(None, _write)
    return _serialize(doc)


@router.patch("/{schedule_id}")
async def update_schedule(schedule_id: str, req: SchedulePatch):
    def _update():
        db = get_db()
        doc = db.get("crawl_schedules", id=schedule_id)
        if not doc:
            return None
        patch = {k: v for k, v in req.model_dump().items() if v is not None}
        if "interval_minutes" in patch:
            base = doc.get("last_run_at") or utcnow()
            patch["next_run_at"] = base + timedelta(minutes=patch["interval_minutes"])
        if patch:
            db.upsert("crawl_schedules", {"id": schedule_id, **patch})
        return _serialize(db.get("crawl_schedules", id=schedule_id))

    updated = await asyncio.get_running_loop().run_in_executor(None, _update)
    if updated is None:
        raise HTTPException(404, "定时任务不存在")
    return updated


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    def _delete():
        return get_db().delete("crawl_schedules", filters={"id": schedule_id})

    deleted = await asyncio.get_running_loop().run_in_executor(None, _delete)
    if not deleted:
        raise HTTPException(404, "定时任务不存在")
    return {"message": "已删除"}


@router.post("/{schedule_id}/run")
async def run_schedule_now(schedule_id: str):
    def _read():
        return get_db().get("crawl_schedules", id=schedule_id)

    doc = await asyncio.get_running_loop().run_in_executor(None, _read)
    if not doc:
        raise HTTPException(404, "定时任务不存在")
    if schedule_id in _running:
        raise HTTPException(429, "该任务正在运行中")
    asyncio.create_task(_run_schedule(doc))
    return {"message": "已触发立即执行"}


# ── 调度器 ────────────────────────────────────────────────────────


async def _run_schedule(doc: dict) -> None:
    from nia.api.crawl import _persist_page
    from nia.crawler import CrawlConfig, CrawlEngine

    schedule_id = doc["id"]
    if schedule_id in _running:
        return
    _running.add(schedule_id)
    run_id = uuid.uuid4().hex
    loop = asyncio.get_running_loop()
    status = "completed"
    try:
        cfg = CrawlConfig(
            max_depth=doc.get("max_depth") or 0,
            max_pages=doc.get("max_pages") or 20,
            same_domain_only=bool(doc.get("same_domain_only", True)),
            use_js=bool(doc.get("use_js")),
        )

        async def on_page(page):
            await loop.run_in_executor(
                None, _persist_page, page.url, page.title, page.text, "", run_id, "schedule", page.parent_url
            )

        result = await CrawlEngine(cfg).crawl(
            doc.get("seeds") or [], doc.get("instruction") or "", on_page=on_page
        )
        logger.info(
            "schedule %s run done: %s pages", schedule_id, result["stats"]["pages_crawled"]
        )
    except Exception as e:
        status = "failed"
        logger.warning(f"schedule {schedule_id} run failed: {e}")
    finally:
        _running.discard(schedule_id)

        def _finish():
            get_db().upsert("crawl_schedules", {
                "id": schedule_id, "last_status": status, "last_run_at": utcnow(),
            })

        try:
            await loop.run_in_executor(None, _finish)
        except Exception as e:
            logger.warning(f"schedule {schedule_id} status write failed: {e}")


async def _tick() -> None:
    def _due():
        db = get_db()
        now = utcnow()
        due = []
        for row in db.list("crawl_schedules", filters={"enabled": True}, limit=100):
            nxt = row.get("next_run_at")
            if nxt is not None and nxt <= now and row["id"] not in _running:
                interval = max(5, int(row.get("interval_minutes") or 60))
                db.upsert("crawl_schedules", {
                    "id": row["id"], "next_run_at": now + timedelta(minutes=interval),
                })
                due.append(row)
        return due

    due = await asyncio.get_running_loop().run_in_executor(None, _due)
    for doc in due:
        asyncio.create_task(_run_schedule(doc))


async def scheduler_loop() -> None:
    """lifespan 启动的后台调度循环；MySQL 不可用时静默跳过本轮。"""
    logger.info("schedule runner started (tick=%.0fs)", _TICK_SECONDS)
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"scheduler tick skipped: {e}")
        await asyncio.sleep(_TICK_SECONDS)