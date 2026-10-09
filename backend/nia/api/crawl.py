"""
爬取 API — 异步后台任务 + SSE 实时进度 + MySQL 存储

注意：进度事件保存在进程内的环形缓冲中，SSE 端以 0.3s 轮询读取。
旧实现把同步 redis pubsub.get_message(timeout=1.0) 直接放进 async generator，
每个 SSE 连接都会阻塞事件循环最多 1 秒；而且 _publish_progress 每次进度
都新建一个 Redis 连接（不关闭），把内存状态更新放在 publish 之后同一个
try 里 —— Redis 一挂，任务进度就永远停在 0。
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from typing import AsyncGenerator
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from nia.utils.config import Config
from nia.utils.timeutil import utcnow
from nia.utils.url_safety import is_safe_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", tags=["crawl"])

# ── 内存任务状态（轻量级，适合单实例） ──────────────────────────
_tasks: dict[str, dict] = {}
_batches: dict[str, dict] = {}
_MAX_TASKS_IN_MEMORY = 200
_MAX_HISTORY = 500
_STREAM_WALL_LIMIT = 900.0


def _validate_url(url: str) -> str:
    """校验 URL 安全性，防止 SSRF。返回清理后的 URL。"""
    url = (url or "").strip()
    if not url:
        raise HTTPException(400, "URL 不能为空")
    ok, reason = is_safe_url(url, resolve=True)
    if not ok:
        raise HTTPException(400, reason)
    return url


# ── 数据模型 ─────────────────────────────────────────────────────


class CrawlRequest(BaseModel):
    url: str
    instruction: str = Field(min_length=1, max_length=2000)
    use_js: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("提取指令不能为空")
        return v


# ── MySQL 存储 ────────────────────────────────────────────────────


def _get_db():
    from nia.storage.database import get_db

    return get_db()


def _save_task(task: dict) -> None:
    """保存任务状态到内存 + MySQL（隐藏内存专用的 history 字段）。"""
    task_id = task["task_id"]
    _tasks[task_id] = task
    _gc_tasks()
    try:
        doc = {k: v for k, v in task.items() if k != "history"}
        _get_db().upsert("crawl_tasks", doc)
    except Exception as e:
        logger.warning(f"Failed to save task to MySQL: {e}")


def _load_task_from_db(task_id: str) -> dict | None:
    try:
        return _get_db().get("crawl_tasks", task_id=task_id)
    except Exception as e:
        logger.warning(f"Failed to read task from MySQL: {e}")
        return None


# ── 进度广播（内存环形缓冲 + 尽力而为的 Redis 发布） ──────────────

_redis_client = None
_redis_lock = threading.Lock()
# 主事件循环引用：线程池里的任务需要把浏览器渲染协程投递回来执行
_main_loop: asyncio.AbstractEventLoop | None = None


def _publish_redis(payload: str) -> None:
    """尽力而为地把进度发到 Redis（多进程/外部订阅用）；失败只记日志。"""
    global _redis_client
    try:
        import redis as redis_lib

        with _redis_lock:
            if _redis_client is None:
                _redis_client = redis_lib.from_url(Config.REDIS_URL, decode_responses=True)
        _redis_client.publish("nia:crawl:progress", payload)
    except Exception as e:
        logger.debug(f"Redis publish skipped: {e}")


def _publish_progress(task_id: str, step: str, progress: int, message: str, status: str | None = None) -> None:
    """更新内存任务状态并追加一条历史事件。先更新内存，再发 Redis。"""
    task = _tasks.get(task_id)
    entry = {"step": step, "progress": progress, "message": message}
    if task is not None:
        task["step"] = step
        task["progress"] = progress
        task["message"] = message
        if status:
            task["status"] = status
        history = task.setdefault("history", [])
        history.append(entry)
        if len(history) > _MAX_HISTORY:
            del history[: len(history) - _MAX_HISTORY]
    _publish_redis(json.dumps({"task_id": task_id, **entry}, ensure_ascii=False))


def _gc_tasks() -> None:
    if len(_tasks) <= _MAX_TASKS_IN_MEMORY:
        return
    finished = [tid for tid, t in _tasks.items() if t.get("status") in ("completed", "failed")]
    for tid in finished[: len(_tasks) - _MAX_TASKS_IN_MEMORY]:
        _tasks.pop(tid, None)


def _active_tasks() -> int:
    return sum(1 for t in list(_tasks.values()) + list(_batches.values())
               if t.get("status") not in ("completed", "failed"))


# ── 爬取核心逻辑 ─────────────────────────────────────────────────


def _sync_fetch(url: str, use_js: bool) -> str:
    """同步抓取（在线程池中运行）。非 JS 路径也要做 SSRF 校验与体积上限。"""
    ok, reason = is_safe_url(url, resolve=True)
    if not ok:
        raise ValueError(f"URL 不合法：{reason}")
    if use_js:
        # 浏览器池绑定在 FastAPI 主事件循环上（Playwright 不能跨事件循环复用），
        # 所以这里把协程投递回主循环执行，而不是在本线程里新建事件循环。
        if _main_loop is None or _main_loop.is_closed():
            raise RuntimeError("JS 渲染不可用：主事件循环未就绪")
        from nia.crawler.browser_pool import AsyncBrowserPool

        future = asyncio.run_coroutine_threadsafe(
            AsyncBrowserPool.fetch(url, timeout=max(30.0, Config.CRAWL_REQUEST_TIMEOUT * 2.0)),
            _main_loop,
        )
        data = future.result(timeout=max(60.0, Config.CRAWL_REQUEST_TIMEOUT * 2.0 + 30.0))
        if not data.get("success"):
            raise RuntimeError(f"JS 渲染失败: {data.get('error') or 'unknown'}")
        return data.get("html", "") or ""

    max_bytes = Config.CRAWL_MAX_CONTENT_BYTES
    with httpx.Client(
        timeout=httpx.Timeout(Config.CRAWL_REQUEST_TIMEOUT, connect=10.0),
        follow_redirects=False,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    ) as client:
        current = url
        for _ in range(5):
            resp = client.get(current)
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location")
                if not location:
                    raise RuntimeError(f"重定向缺少 Location (HTTP {resp.status_code})")
                current = urljoin(current, location)
                ok, reason = is_safe_url(current, resolve=True)
                if not ok:
                    raise ValueError(f"重定向目标不合法：{reason}")
                continue
            resp.raise_for_status()
            if len(resp.content) > max_bytes:
                return resp.text[:max_bytes]
            return resp.text
        raise RuntimeError("重定向次数过多")


def _do_crawl(task_id: str, url: str, instruction: str, use_js: bool) -> None:
    """同步执行爬取任务（在线程池中运行，不阻塞事件循环）。"""
    result = {
        "task_id": task_id,
        "url": url,
        "instruction": instruction,
        "use_js": use_js,
        "status": "running",
        "progress": 0,
        "step": "",
        "message": "",
        "history": [],
        "created_at": utcnow().isoformat(),
    }
    _save_task(result)

    data_id = ""
    data_stored = False
    try:
        # Step 1: 抓取页面
        _publish_progress(task_id, "fetch", 10, "正在抓取页面...")
        html_content = _sync_fetch(url, use_js)
        if not html_content:
            raise RuntimeError("Empty page content")
        _publish_progress(task_id, "fetch", 25, f"抓取完成，{len(html_content)} 字节")

        # Step 2: 解析 HTML
        _publish_progress(task_id, "parse", 30, "正在解析页面结构...")
        from lxml import html as lxml_html

        tree = lxml_html.fromstring(html_content)
        title = ""
        title_el = tree.cssselect("title")
        if title_el:
            title = title_el[0].text_content().strip()

        for tag in tree.cssselect("script, style, noscript"):
            parent = tag.getparent()
            if parent is not None:
                parent.remove(tag)
        text_content = tree.text_content()
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]
        text_content = "\n".join(lines)
        if len(text_content) > 10000:
            text_content = text_content[:10000]
        _publish_progress(task_id, "parse", 40, f"解析完成，标题: {title or '(无)'}")

        # Step 3: AI 提取
        extracted_data: dict = {}
        extraction_method = "none"
        if instruction:
            _publish_progress(task_id, "ai", 50, "AI 正在提取数据...")
            try:
                from nia.ai.llm_client import LLMClient, loads_json_loose

                llm = LLMClient()
                try:
                    messages = [
                        {"role": "system", "content": (
                            "You are a web data extraction assistant. "
                            "Extract data from the HTML according to the instruction. "
                            "Return ONLY valid JSON with the extracted fields."
                        )},
                        {"role": "user", "content": (
                            f"Instruction: {instruction}\n\n"
                            f"<<<PAGE_HTML_START>>>\n{html_content[:8000]}\n<<<PAGE_HTML_END>>>"
                        )},
                    ]
                    _publish_progress(task_id, "ai", 60, "调用 LLM 中...")
                    response = llm.chat(messages, temperature=0.1)
                    _publish_progress(task_id, "ai", 75, "解析提取结果...")
                    extracted_data = loads_json_loose(response) or {}
                    # 空结果不算成功，避免把"没提取到"当成"已提取"
                    extraction_method = "ai" if extracted_data else "failed"
                    _publish_progress(task_id, "ai", 80, f"提取完成，{len(extracted_data)} 个字段")
                finally:
                    llm.close()
            except Exception as e:
                logger.error(f"AI extraction failed: {e}")
                _publish_progress(task_id, "ai", 80, f"AI 提取失败: {str(e)[:100]}")
                extraction_method = "failed"

        # Step 4: 存入 MySQL
        _publish_progress(task_id, "store", 85, "保存到数据库...")
        data_id = str(uuid.uuid4())
        domain = urlparse(url).netloc
        try:
            _get_db().insert("crawled_data", {
                "id": data_id,
                "url": url,
                "domain": domain,
                "title": title,
                "content": text_content,
                "raw_html": html_content,
                "extracted_data": extracted_data,
                "extraction_method": extraction_method,
                "dom_hash": "",
                "metadata": {},
                "created_at": utcnow(),
            })
            data_stored = True
        except Exception as e:
            logger.error(f"MySQL insert failed: {e}")

        # Step 5: RAG 索引（失败不影响主流程；只有真的存进库才索引）
        if data_stored:
            _publish_progress(task_id, "index", 90, "构建语义索引...")
            try:
                from nia.rag.rag_engine import get_rag_engine

                get_rag_engine().index_data(
                    url=url, title=title, content=text_content, crawled_data_id=data_id
                )
            except Exception as e:
                logger.warning(f"RAG indexing failed: {e}")
                _publish_progress(task_id, "index", 92, f"语义索引跳过: {str(e)[:100]}")

        _publish_progress(task_id, "done", 100, "爬取完成！", status="completed")
        result.update({
            "status": "completed",
            "title": title,
            "domain": domain,
            "extracted_data": extracted_data,
            "extraction_method": extraction_method,
            "data_id": data_id if data_stored else "",
            "progress": 100,
            "step": "done",
            "message": "爬取完成！",
        })

    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        result.update({
            "status": "failed",
            "error": str(e)[:500],
            "progress": 100,
            "step": "error",
            "message": str(e)[:200],
        })
        _publish_progress(task_id, "error", 100, f"失败: {str(e)[:200]}", status="failed")

    _save_task(result)


# 线程池 future 的强引用（否则可能被 GC 掉，且无法观测失败）
_crawl_futures: set = set()


def _crawl_done(fut) -> None:
    _crawl_futures.discard(fut)
    exc = fut.exception()
    if exc is not None:
        logger.error(f"crawl task crashed: {exc}")


# ── API 端点 ─────────────────────────────────────────────────────


@router.get("/results")
async def get_crawl_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取爬取结果列表（从 MySQL 分页查询）。

    注意：本路由必须注册在 `/{task_id}` 之前，否则 "/api/crawl/results"
    会被当成 task_id="results" 匹配掉，永远返回 404。
    """
    try:
        db = _get_db()
        filters = {"status": ["completed", "failed"]}
        total = db.count("crawl_tasks", filters=filters)
        results = db.list("crawl_tasks", filters=filters, order_by="created_at", limit=page_size, offset=(page - 1) * page_size, exclude=("history",))
        return {
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.warning(f"Failed to read results from MySQL: {e}")
        return {"results": [], "total": 0, "page": page, "page_size": page_size}


@router.post("")
async def create_crawl_task(req: CrawlRequest):
    """提交爬取任务（异步后台执行，立即返回 task_id）"""
    if _active_tasks() >= Config.MAX_CONCURRENT_CRAWLS:
        raise HTTPException(429, f"同时运行的爬取任务已达上限（{Config.MAX_CONCURRENT_CRAWLS}），请稍后再试")

    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "task_id": task_id,
        "url": req.url,
        "instruction": req.instruction,
        "use_js": req.use_js,
        "status": "queued",
        "progress": 0,
        "step": "",
        "message": "已排队",
        "history": [],
        "created_at": utcnow().isoformat(),
    }
    loop = asyncio.get_running_loop()
    global _main_loop
    _main_loop = loop
    fut = loop.run_in_executor(None, _do_crawl, task_id, req.url, req.instruction, req.use_js)
    _crawl_futures.add(fut)
    fut.add_done_callback(_crawl_done)
    _gc_tasks()
    return {"task_id": task_id, "status": "queued", "message": "任务已提交，正在后台执行"}


@router.get("/{task_id}/progress")
async def stream_progress(task_id: str):
    """SSE 实时推送爬取进度。"""
    if task_id not in _tasks and task_id in _batches:
        # 批量任务的事件流复用 /batch/{id}/stream
        return await stream_batch(task_id)
    if task_id not in _tasks:
        doc = await asyncio.get_running_loop().run_in_executor(None, _load_task_from_db, task_id)
        if doc is None:
            raise HTTPException(404, "任务不存在")

    async def event_generator() -> AsyncGenerator[str, None]:
        deadline = time.monotonic() + _STREAM_WALL_LIMIT
        idx = 0
        while True:
            task = _tasks.get(task_id)
            if task is not None:
                history = task.get("history") or []
                while idx < len(history):
                    yield f"data: {json.dumps(history[idx], ensure_ascii=False)}\n\n"
                    idx += 1
                if task.get("status") in ("completed", "failed"):
                    yield "data: [DONE]\n\n"
                    return
            if time.monotonic() > deadline:
                yield "event: timeout\ndata: [DONE]\n\n"
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务（同时清理其落库数据与向量索引）。"""
    _tasks.pop(task_id, None)
    _batches.pop(task_id, None)
    try:
        db = _get_db()
        doc = db.get("crawl_tasks", task_id=task_id) or {}
        deleted = db.delete("crawl_tasks", filters={"task_id": task_id})
        url = doc.get("url")
        if url:
            db.delete("crawled_data", filters={"url": url})
        if deleted == 0 and not url:
            raise HTTPException(404, "任务不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"删除失败: {e}")
    return {"message": "已删除"}


# ── 并发批量 / 整站爬取（CrawlEngine） ──────────────────────────────


class BatchCrawlRequest(BaseModel):
    seeds: list[str]
    instruction: str = Field("", max_length=2000)
    use_js: bool = False
    max_depth: int = Field(0, ge=0, le=5)      # 0 = 仅抓给定 URL；>0 = 整站跟随链接
    max_pages: int = Field(20, ge=1, le=500)
    same_domain_only: bool = True

    @field_validator("seeds")
    @classmethod
    def validate_seeds(cls, v: list[str]) -> list[str]:
        cleaned = [_validate_url(s) for s in (v or []) if s and s.strip()]
        if not cleaned:
            raise ValueError("至少需要一个有效的 URL")
        if len(cleaned) > 20:
            raise ValueError("URL 最多 20 个")
        return cleaned


def _persist_page(page_url: str, title: str, content: str, raw_html: str = "") -> str:
    """把抓取到的页面存入 crawled_data（同步，executor 中调用）。"""
    data_id = str(uuid.uuid4())
    try:
        _get_db().insert("crawled_data", {
            "id": data_id,
            "url": page_url,
            "domain": urlparse(page_url).netloc,
            "title": title,
            "content": content,
            "raw_html": raw_html,
            "extracted_data": {},
            "extraction_method": "batch",
            "dom_hash": "",
            "metadata": {},
            "created_at": utcnow(),
        })
    except Exception as e:
        logger.warning(f"persist batch page failed: {e}")
    return data_id


def _batch_emit(task_id: str, ev: dict) -> None:
    b = _batches.get(task_id)
    if b is None:
        return
    b["events"].append(ev)
    if len(b["events"]) > _MAX_HISTORY:
        del b["events"][: len(b["events"]) - _MAX_HISTORY]


class CrawlCancelled(Exception):
    """用户取消批量爬取时，从进度回调中抛出以中断引擎循环。"""


async def _run_batch(task_id: str, req: "BatchCrawlRequest") -> None:
    from nia.crawler import CrawlConfig, CrawlEngine

    loop = asyncio.get_running_loop()

    async def cb(ev: dict):
        b = _batches.get(task_id)
        if b is not None and b.get("cancel_requested"):
            raise CrawlCancelled()
        _batch_emit(task_id, ev)

    async def on_page(page):
        # 持久化放到线程池，避免阻塞事件循环
        await loop.run_in_executor(None, _persist_page, page.url, page.title, page.text)

    cfg = CrawlConfig(
        max_depth=req.max_depth,
        max_pages=req.max_pages,
        same_domain_only=req.same_domain_only,
        use_js=req.use_js,
    )
    status = "failed"
    try:
        result = await CrawlEngine(cfg).crawl(req.seeds, req.instruction, progress_cb=cb, on_page=on_page)
        _batch_emit(task_id, {"event": "result", **result})
        status = "completed"
    except CrawlCancelled:
        logger.info(f"batch crawl {task_id} cancelled by user")
        _batch_emit(task_id, {"event": "cancelled"})
        status = "cancelled"
    except Exception as e:
        logger.exception("batch crawl failed")
        _batch_emit(task_id, {"event": "error", "error": str(e)[:300]})
        status = "failed"
    finally:
        b = _batches.get(task_id)
        if b is not None:
            b["status"] = status
        _batch_emit(task_id, {"event": "_eof"})


@router.post("/batch")
async def create_batch_crawl(req: BatchCrawlRequest):
    """并发批量 / 整站爬取，立即返回 task_id，进度经 /batch/{id}/stream 推送。"""
    if _active_tasks() >= Config.MAX_CONCURRENT_CRAWLS:
        raise HTTPException(429, f"同时运行的爬取任务已达上限（{Config.MAX_CONCURRENT_CRAWLS}），请稍后再试")

    task_id = str(uuid.uuid4())
    _batches[task_id] = {
        "status": "running",
        "events": [],
        "seeds": req.seeds,
        "created_at": utcnow().isoformat(),
    }
    asyncio.create_task(_run_batch(task_id, req))
    # 只清理已结束的批量任务，避免误删正在跑的任务流
    if len(_batches) > 50:
        finished = [
            tid for tid, b in _batches.items()
            if b.get("status") in ("completed", "failed", "cancelled")
        ]
        for tid in finished[: len(_batches) - 50]:
            _batches.pop(tid, None)
    return {"task_id": task_id, "status": "running", "seeds": req.seeds}


@router.post("/batch/{task_id}/cancel")
async def cancel_batch_crawl(task_id: str):
    """请求取消批量爬取任务（引擎在下一个进度回调处停止）。"""
    b = _batches.get(task_id)
    if b is None:
        raise HTTPException(404, "任务不存在或已过期")
    if b.get("status") != "running":
        return {"message": f"任务已结束（{b.get('status')}）", "status": b.get("status")}
    b["cancel_requested"] = True
    return {"message": "已请求取消，任务将在当前批次结束后停止", "status": "cancelling"}


@router.get("/batch/{task_id}/stream")
async def stream_batch(task_id: str):
    """SSE 推送批量爬取进度（page/finding/done/result）。"""
    if task_id not in _batches:
        raise HTTPException(404, "任务不存在或已过期")

    async def event_generator():
        idx = 0
        deadline = time.monotonic() + _STREAM_WALL_LIMIT
        while True:
            b = _batches.get(task_id)
            if b is not None:
                while idx < len(b["events"]):
                    ev = b["events"][idx]
                    idx += 1
                    if ev.get("event") == "_eof":
                        yield "data: [DONE]\n\n"
                        return
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if b.get("status") in ("completed", "failed", "cancelled"):
                    yield "data: [DONE]\n\n"
                    return
            if time.monotonic() > deadline:
                yield "event: timeout\ndata: [DONE]\n\n"
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """查询单个任务状态。注意：必须注册在 /results 之后。"""
    if task_id in _tasks:
        task = dict(_tasks[task_id])
        task.pop("history", None)
        return task
    b = _batches.get(task_id)
    if b is not None:
        events = b.get("events") or []
        return {
            "task_id": task_id,
            "status": b.get("status"),
            "batch": True,
            "seeds": b.get("seeds"),
            "created_at": b.get("created_at"),
            "pages": sum(1 for e in events if e.get("event") == "page"),
            "findings": sum(1 for e in events if e.get("event") == "finding"),
            "progress": 100 if b.get("status") in ("completed", "failed", "cancelled") else 0,
        }
    doc = await asyncio.get_running_loop().run_in_executor(None, _load_task_from_db, task_id)
    if doc:
        doc.pop("history", None)
        return doc
    raise HTTPException(404, "任务不存在")
