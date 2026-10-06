"""
自主爬取 Agent API — 启动 / SSE 实时事件流 / 取消。

事件保存在进程内的环形缓冲里（同进程直连，不经 Redis），因此：
- 消费方断开后重连可以补发历史事件；
- 没有消费方时也不会阻塞后台任务（旧实现用有界 asyncio.Queue，
  没人看流时 put 会永远阻塞，run 卡死、_gc_runs 永远回收不掉）。
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from nia.agent.agent import AutonomousCrawlAgent
from nia.agent.events import AgentEvent
from nia.agent.state import AgentState
from nia.crawler.models import CrawlConfig
from nia.utils.config import Config
from nia.utils.url_safety import is_safe_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

_EOF = AgentEvent("_eof", {})
_MAX_RUNS_IN_MEMORY = 50
_MAX_EVENTS_BUFFERED = 2000
_STREAM_WALL_LIMIT = 3600.0


@dataclass
class AgentRun:
    state: AgentState
    config: CrawlConfig
    events: list[AgentEvent] = field(default_factory=list)
    dropped: int = 0
    finished: bool = False
    notify: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


_runs: dict[str, AgentRun] = {}


def _emit(run: AgentRun, ev: AgentEvent) -> None:
    """追加事件并唤醒所有等待的消费方（永不阻塞后台任务）。"""
    run.events.append(ev)
    overflow = len(run.events) - _MAX_EVENTS_BUFFERED
    if overflow > 0:
        del run.events[:overflow]
        run.dropped += overflow
    run.notify.set()


# ── 请求模型 ─────────────────────────────────────────────────────


class AgentRequest(BaseModel):
    goal: str
    seeds: list[str]
    max_pages: int | None = Field(default=None, ge=1, le=200)
    max_depth: int | None = Field(default=None, ge=0, le=5)
    use_js: bool = False

    @field_validator("goal")
    @classmethod
    def _goal(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("目标不能为空")
        if len(v) > 2000:
            raise ValueError("目标过长，最多 2000 字符")
        return v

    @field_validator("seeds")
    @classmethod
    def _seeds(cls, v: list[str]) -> list[str]:
        cleaned = []
        for s in v or []:
            s = (s or "").strip()
            if not s:
                continue
            ok, reason = is_safe_url(s)
            if not ok:
                raise ValueError(f"种子 URL 不合法（{reason}）: {s}")
            cleaned.append(s)
        if not cleaned:
            raise ValueError("至少需要一个有效的种子 URL")
        if len(cleaned) > 10:
            raise ValueError("种子 URL 最多 10 个")
        return cleaned


# ── 后台运行 + 持久化 ────────────────────────────────────────────


def _persist_run(state: AgentState) -> None:
    """把 agent run 记录落 MongoDB（同步，快速；失败静默）。"""
    try:
        from nia.storage.database import get_db

        db = get_db()
        db.get_collection("agent_runs").update_one(
            {"run_id": state.run_id}, {"$set": state.to_dict()}, upsert=True
        )
    except Exception as e:
        logger.warning(f"persist agent run failed: {e}")


async def _runner(run_id: str) -> None:
    run = _runs[run_id]
    agent = AutonomousCrawlAgent(run.state, run.config)
    try:
        async for ev in agent.run():
            _emit(run, ev)
    except asyncio.CancelledError:
        run.state.status = "cancelled"
        _emit(run, AgentEvent("error", {"message": "任务已被取消"}))
        raise
    except Exception as e:
        logger.exception("agent runner crashed")
        run.state.status = "error"
        run.state.error = str(e)[:300]
        _emit(run, AgentEvent("error", {"message": str(e)[:300]}))
    finally:
        run.finished = True
        try:
            await asyncio.get_running_loop().run_in_executor(None, _persist_run, run.state)
        except Exception as e:
            logger.warning(f"persist agent run failed: {e}")
        _emit(run, _EOF)


def _gc_runs() -> None:
    """限制内存中保留的 run 数量。"""
    if len(_runs) <= _MAX_RUNS_IN_MEMORY:
        return
    done = [rid for rid, r in _runs.items() if r.finished or (r.task and r.task.done())]
    for rid in done[: len(_runs) - _MAX_RUNS_IN_MEMORY]:
        r = _runs.pop(rid, None)
        if r is not None and r.task is not None and not r.task.done():
            r.task.cancel()


def _active_runs() -> int:
    return sum(1 for r in _runs.values() if not r.finished)


# ── 端点 ─────────────────────────────────────────────────────────


@router.post("")
async def start_agent(req: AgentRequest):
    """启动一个自主爬取 Agent，立即返回 run_id。"""
    if _active_runs() >= Config.MAX_CONCURRENT_CRAWLS:
        raise HTTPException(429, f"同时运行的 Agent 任务已达上限（{Config.MAX_CONCURRENT_CRAWLS}），请稍后再试")

    run_id = uuid.uuid4().hex
    state = AgentState(run_id=run_id, goal=req.goal, seeds=req.seeds)
    if req.max_pages is not None:
        state.budget_pages = req.max_pages
    config = CrawlConfig(
        max_depth=req.max_depth if req.max_depth is not None else Config.CRAWL_MAX_DEPTH,
        max_pages=state.budget_pages,
        use_js=req.use_js,
    )
    run = AgentRun(state=state, config=config)
    _runs[run_id] = run
    run.task = asyncio.create_task(_runner(run_id))
    _gc_runs()
    return {"run_id": run_id, "status": "running", "goal": req.goal, "seeds": req.seeds}


@router.get("/{run_id}/stream")
async def stream_agent(run_id: str):
    """SSE：实时推送 Agent 的思考/动作/观察/发现/报告。支持断线重连。"""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "任务不存在或已过期")

    async def event_generator():
        idx = run.dropped
        deadline = time.monotonic() + _STREAM_WALL_LIMIT
        while True:
            if idx < run.dropped:  # 缓冲区被裁剪过，跳到现存最早事件
                idx = run.dropped
            while idx < run.dropped + len(run.events):
                ev = run.events[idx - run.dropped]
                idx += 1
                if ev.type == "_eof":
                    yield "data: [DONE]\n\n"
                    return
                yield ev.to_sse()
            if run.finished:
                yield "data: [DONE]\n\n"
                return
            if time.monotonic() > deadline:
                yield "event: timeout\ndata: [DONE]\n\n"
                return
            run.notify.clear()
            try:
                await asyncio.wait_for(run.notify.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/cancel")
async def cancel_agent(run_id: str):
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "任务不存在")
    run.state.cancel()
    return {"message": "已请求取消，Agent 将尽快收尾汇总"}


@router.get("/{run_id}")
async def get_agent_run(run_id: str):
    run = _runs.get(run_id)
    if run is not None:
        data = run.state.to_dict()
        data["finished"] = run.finished
        return data
    # 回退 MongoDB
    try:
        from nia.storage.database import get_db

        doc = get_db().get_collection("agent_runs").find_one({"run_id": run_id}, {"_id": 0})
        if doc:
            return doc
    except Exception as e:
        logger.warning(f"read agent run failed: {e}")
    raise HTTPException(404, "任务不存在")


@router.get("")
async def list_agent_runs(limit: int = Query(20, ge=1, le=100)):
    """最近的 Agent 运行记录（MongoDB）。"""
    try:
        from nia.storage.database import get_db

        cursor = (
            get_db().get_collection("agent_runs")
            .find({}, {"_id": 0, "report": 0, "findings": 0})
            .sort("created_at", -1)
            .limit(limit)
        )
        return {"runs": list(cursor)}
    except Exception as e:
        logger.warning(f"list agent runs failed: {e}")
        return {"runs": []}
