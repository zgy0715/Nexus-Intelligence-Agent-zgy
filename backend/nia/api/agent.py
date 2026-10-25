"""
自主爬取 Agent API — 启动 / SSE 实时事件流 / 取消 / 历史回放。

v3 事件总线设计（对比旧版纯内存环形缓冲）：
- 每个事件在内存缓冲之外**同步追加到 Redis Stream**（`nia:agent:{run_id}:events`，
  MAXLEN 裁剪 + 24h TTL）。Redis 不可用时静默降级为纯内存模式（旧行为）。
- SSE 帧带 `id: <seq>`；浏览器 EventSource 断线重连自动携带 Last-Event-ID 头，
  服务端从 seq+1 续传 —— 内存路径与 Redis 路径同一套序号语义。
- run 被内存 GC 或后端重启后，SSE 与 `GET /{run_id}/events` 回放端点直接读
  Redis Stream 补齐历史 —— 任务状态不再"重启即失忆"。
- 没有消费方时也不会阻塞后台任务（事件先落缓冲，消费方按 seq 增量拉取）。
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from nia.agent.agent import AutonomousCrawlAgent
from nia.agent.events import AgentEvent, AgentEventType
from nia.agent.state import AgentState
from nia.crawler.models import CrawlConfig
from nia.utils.config import Config
from nia.utils.url_safety import is_safe_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

_MAX_RUNS_IN_MEMORY = 50
_MAX_EVENTS_BUFFERED = 2000
_STREAM_WALL_LIMIT = 3600.0
_STREAM_TTL = 24 * 3600
_STREAM_MAXLEN = 5000


@dataclass
class AgentRun:
    state: AgentState
    config: CrawlConfig
    events: list[AgentEvent] = field(default_factory=list)
    dropped: int = 0
    seq: int = 0  # 全局事件序号（内存与 Redis Stream 共用一套编号）
    finished: bool = False
    notify: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


_runs: dict[str, AgentRun] = {}


# ── Redis Stream 事件总线（尽力而为，失败降级纯内存） ────────────


class _EventBus:
    def __init__(self):
        self._redis = None
        self._disabled = False
        self._version_checked = False

    async def _get_redis(self):
        if self._disabled:
            return None
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(Config.REDIS_URL, decode_responses=True)
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"agent event bus: Redis 不可用，降级纯内存模式（{e}）")
                self._disabled = True
                return None
        if not self._version_checked:
            self._version_checked = True
            # Redis Stream 需要 5.0+（Windows 老版 3.0.504 没有 XADD/XRANGE）。
            # 不支持时显式警告并降级 —— 回放/重启恢复仅限 run 存活于内存期间。
            try:
                version = (await self._redis.info("server")).get("redis_version", "0")
                major = int(version.split(".")[0] or 0)
                if major < 5:
                    logger.warning(
                        f"agent event bus: Redis {version} 不支持 Stream（需要 5.0+），"
                        "事件持久化/重启恢复已降级为纯内存模式。请升级 Redis 后自动恢复。"
                    )
                    self._disabled = True
                    return None
            except Exception as e:
                logger.debug(f"redis version check failed: {e}")
        return self._redis

    @staticmethod
    def _key(run_id: str) -> str:
        return f"nia:agent:{run_id}:events"

    async def publish(self, run_id: str, ev: AgentEvent) -> None:
        client = await self._get_redis()
        if client is None:
            return
        try:
            payload = json.dumps(ev.to_payload(), ensure_ascii=False)
            await client.xadd(
                self._key(run_id),
                {"type": ev.type.value, "payload": payload},
                id=f"{ev.seq}-0",  # 与内存 seq 对齐，Last-Event-ID 续读语义一致
                maxlen=_STREAM_MAXLEN,
                approximate=True,
            )
            if ev.seq == 1:  # 首事件时设置整条流的过期
                await client.expire(self._key(run_id), _STREAM_TTL)
        except Exception as e:
            logger.debug(f"event bus publish failed: {e}")

    async def read_since(self, run_id: str, after_seq: int, count: int = 200) -> list[dict]:
        """读取 seq > after_seq 的事件（按 payload 内 seq 过滤，容忍 Redis id 漂移）。"""
        client = await self._get_redis()
        if client is None:
            return []
        try:
            start = f"({max(0, after_seq)}-0" if after_seq > 0 else "-"
            entries = await client.xrange(self._key(run_id), min=start, max="+", count=count * 2)
            out: list[dict] = []
            for _entry_id, fields in entries:
                try:
                    payload = json.loads(fields.get("payload", "{}"))
                except (json.JSONDecodeError, AttributeError):
                    continue
                if isinstance(payload, dict) and payload.get("seq", 0) > after_seq:
                    out.append(payload)
            out.sort(key=lambda p: p.get("seq", 0))
            return out[:count]
        except Exception as e:
            logger.debug(f"event bus read failed: {e}")
            return []

    async def finished_marker(self, run_id: str) -> bool:
        """run 是否已终结（流里存在 finish/error/_eof）。"""
        client = await self._get_redis()
        if client is None:
            return False
        try:
            entries = await client.xrange(self._key(run_id), min="-", max="+", count=_STREAM_MAXLEN)
            for _eid, fields in entries:
                if fields.get("type") in ("finish", "error", AgentEventType.EOF.value):
                    return True
            return False
        except Exception:
            return False


_bus = _EventBus()

# publish 任务引用集：asyncio.create_task 的返回值若无人引用可能被 GC 中途回收
_pending_publishes: set[asyncio.Task] = set()


def _emit(run: AgentRun, ev: AgentEvent) -> None:
    """分配序号 → 追加内存缓冲 → 唤醒消费方 → 异步落 Redis Stream。"""
    run.seq += 1
    ev.seq = run.seq
    run.events.append(ev)
    overflow = len(run.events) - _MAX_EVENTS_BUFFERED
    if overflow > 0:
        del run.events[:overflow]
        run.dropped += overflow
    run.notify.set()
    if ev.type is not AgentEventType.EOF:
        task = asyncio.create_task(_bus.publish(run.state.run_id, ev))
        _pending_publishes.add(task)
        task.add_done_callback(_pending_publishes.discard)


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
    """把 agent run 记录落 MySQL；失败不影响实时运行。"""
    try:
        from nia.storage.database import get_db

        db = get_db()
        db.upsert("agent_runs", state.to_dict())
    except Exception as e:
        logger.warning(f"persist agent run failed: {e}")


async def _runner(run_id: str) -> None:
    run = _runs[run_id]

    # v3.2：Agent 抓到的页面落库 + RAG 索引（打通「Agent 采集 → 语义问答」闭环）。
    # metadata.task_id = run_id，删除时可按 run 精确清理；raw_html 留空避免大 HTML 撑库。
    from nia.api.crawl import _persist_page

    async def on_page(page) -> None:
        await asyncio.get_running_loop().run_in_executor(
            None,
            _persist_page,
            page.url,
            page.title,
            page.text,
            "",
            run.state.run_id,
            "agent",
        )

    agent = AutonomousCrawlAgent(run.state, run.config, on_page=on_page)
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
        _emit(run, AgentEvent(AgentEventType.EOF, {}))


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


def _sse_frame(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    seq = payload.get("seq", 0)
    return f"id: {seq}\ndata: {data}\n\n"


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
async def stream_agent(run_id: str, last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
    """SSE：实时推送 Agent 的思考/动作/观察/发现/报告。

    支持断线重连：浏览器自动携带 Last-Event-ID，从该 seq 之后续传；
    run 已被 GC/重启时从 Redis Stream 恢复。
    """
    after_seq = 0
    if last_event_id and last_event_id.isdigit():
        after_seq = int(last_event_id)

    run = _runs.get(run_id)
    if run is not None:
        return StreamingResponse(
            _stream_from_memory(run, after_seq),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # run 不在内存（GC/重启）：从 Redis Stream 恢复
    if not await _bus.finished_marker(run_id) and after_seq == 0 and not await _bus.read_since(run_id, 0, count=1):
        raise HTTPException(404, "任务不存在或已过期")
    return StreamingResponse(
        _stream_from_bus(run_id, after_seq),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


async def _stream_from_memory(run: AgentRun, after_seq: int):
    # 事件 i 的 seq = run.dropped + i + 1，故续传起点（列表下标）= after_seq - run.dropped
    idx = max(0, after_seq - run.dropped) if after_seq else 0
    deadline = time.monotonic() + _STREAM_WALL_LIMIT
    while True:
        if idx < run.dropped:  # 缓冲区被裁剪过，跳到现存最早事件
            idx = run.dropped
        while idx < run.dropped + len(run.events):
            ev = run.events[idx - run.dropped]
            idx += 1
            if ev.type is AgentEventType.EOF:
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


async def _stream_from_bus(run_id: str, after_seq: int):
    """从 Redis Stream 续传/回放（run 已不在内存时）。"""
    deadline = time.monotonic() + _STREAM_WALL_LIMIT
    idle_seconds = 0.0
    while True:
        payloads = await _bus.read_since(run_id, after_seq)
        for payload in payloads:
            after_seq = max(after_seq, payload.get("seq", 0))
            if payload.get("type") in ("finish", "error", AgentEventType.EOF.value):
                yield _sse_frame(payload)
                yield "data: [DONE]\n\n"
                return
            yield _sse_frame(payload)
        if time.monotonic() > deadline:
            yield "event: timeout\ndata: [DONE]\n\n"
            return
        await asyncio.sleep(1.0)
        idle_seconds += 1.0
        if idle_seconds >= 15.0:  # 与内存路径一致的心跳，防代理掐断空闲连接
            idle_seconds = 0.0
            yield ": heartbeat\n\n"


@router.get("/{run_id}/events")
async def replay_agent_events(
    run_id: str,
    after: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=2000),
):
    """历史回放：返回 run 的事件列表（内存优先，回退 Redis Stream）。

    前端「历史运行回放」用这个端点把时间线复原。
    """
    run = _runs.get(run_id)
    if run is not None:
        events = [ev.to_payload() for ev in run.events if ev.seq > after and ev.type is not AgentEventType.EOF]
        return {"run_id": run_id, "finished": run.finished, "events": events[:limit]}

    payloads = await _bus.read_since(run_id, after, count=limit)
    finished = await _bus.finished_marker(run_id)
    return {"run_id": run_id, "finished": finished, "events": payloads}


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
    # 回退 MySQL
    try:
        from nia.storage.database import get_db

        doc = get_db().get("agent_runs", run_id=run_id)
        if doc:
            return doc
    except Exception as e:
        logger.warning(f"read agent run failed: {e}")
    raise HTTPException(404, "任务不存在")


@router.get("")
async def list_agent_runs(limit: int = Query(20, ge=1, le=100)):
    """最近的 Agent 运行记录。"""
    try:
        from nia.storage.database import get_db

        return {"runs": get_db().list("agent_runs", order_by="created_at", limit=limit, exclude=("report", "findings"))}
    except Exception as e:
        logger.warning(f"list agent runs failed: {e}")
        return {"runs": []}
