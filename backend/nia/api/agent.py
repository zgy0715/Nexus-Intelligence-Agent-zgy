"""
自主爬取 Agent API — 启动 / SSE 实时事件流 / 取消。

事件走进程内 asyncio.Queue（同进程直连，不经 Redis）。
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

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


@dataclass
class AgentRun:
    state: AgentState
    queue: "asyncio.Queue[AgentEvent]"
    task: asyncio.Task | None = None


_runs: dict[str, AgentRun] = {}


# ── 请求模型 ─────────────────────────────────────────────────────


class AgentRequest(BaseModel):
    goal: str
    seeds: list[str]
    max_pages: int | None = None
    max_depth: int | None = None
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
        from nia.storage.database import DatabaseManager

        db = DatabaseManager()
        db.connect()
        db.get_collection("agent_runs").update_one(
            {"run_id": state.run_id}, {"$set": state.to_dict()}, upsert=True
        )
    except Exception as e:
        logger.warning(f"persist agent run failed: {e}")


async def _runner(run_id: str) -> None:
    run = _runs[run_id]
    agent = AutonomousCrawlAgent(run.state, _make_config(run))
    try:
        async for ev in agent.run():
            await run.queue.put(ev)
    except Exception as e:
        logger.exception("agent runner crashed")
        await run.queue.put(AgentEvent("error", {"message": str(e)[:300]}))
    finally:
        await asyncio.get_event_loop().run_in_executor(None, _persist_run, run.state)
        await run.queue.put(_EOF)


_run_configs: dict[str, CrawlConfig] = {}


def _make_config(run: AgentRun) -> CrawlConfig:
    return _run_configs.get(run.state.run_id, CrawlConfig())


def _gc_runs() -> None:
    """限制内存中保留的 run 数量。"""
    if len(_runs) <= _MAX_RUNS_IN_MEMORY:
        return
    done = [rid for rid, r in _runs.items() if r.task and r.task.done()]
    for rid in done[: len(_runs) - _MAX_RUNS_IN_MEMORY]:
        _runs.pop(rid, None)
        _run_configs.pop(rid, None)


# ── 端点 ─────────────────────────────────────────────────────────


@router.post("")
async def start_agent(req: AgentRequest):
    """启动一个自主爬取 Agent，立即返回 run_id。"""
    run_id = uuid.uuid4().hex
    state = AgentState(run_id=run_id, goal=req.goal, seeds=req.seeds)
    if req.max_pages:
        state.budget_pages = max(1, min(req.max_pages, 200))
    config = CrawlConfig(
        max_depth=req.max_depth if req.max_depth is not None else Config.CRAWL_MAX_DEPTH,
        max_pages=state.budget_pages,
        use_js=req.use_js,
    )
    _run_configs[run_id] = config
    queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
    run = AgentRun(state=state, queue=queue)
    _runs[run_id] = run
    run.task = asyncio.create_task(_runner(run_id))
    _gc_runs()
    return {"run_id": run_id, "status": "running", "goal": req.goal, "seeds": req.seeds}


@router.get("/{run_id}/stream")
async def stream_agent(run_id: str):
    """SSE：实时推送 Agent 的思考/动作/观察/发现/报告。"""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "任务不存在或已过期")

    async def event_generator():
        while True:
            try:
                ev = await asyncio.wait_for(run.queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if ev.type == "_eof":
                yield "data: [DONE]\n\n"
                break
            yield ev.to_sse()

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
    run.state.cancel_flag.set()
    return {"message": "已请求取消，Agent 将尽快收尾汇总"}


@router.get("/{run_id}")
async def get_agent_run(run_id: str):
    run = _runs.get(run_id)
    if run is not None:
        return run.state.to_dict()
    # 回退 MongoDB
    try:
        from nia.storage.database import DatabaseManager

        db = DatabaseManager()
        db.connect()
        doc = db.get_collection("agent_runs").find_one({"run_id": run_id}, {"_id": 0})
        if doc:
            return doc
    except Exception as e:
        logger.warning(f"read agent run failed: {e}")
    raise HTTPException(404, "任务不存在")


@router.get("")
async def list_agent_runs(limit: int = Query(20, ge=1, le=100)):
    """最近的 Agent 运行记录（MongoDB）。"""
    try:
        from nia.storage.database import DatabaseManager

        db = DatabaseManager()
        db.connect()
        cursor = (
            db.get_collection("agent_runs")
            .find({}, {"_id": 0, "report": 0})
            .sort("created_at", -1)
            .limit(limit)
        )
        return {"runs": list(cursor)}
    except Exception as e:
        logger.warning(f"list agent runs failed: {e}")
        return {"runs": []}
