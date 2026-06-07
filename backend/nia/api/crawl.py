"""
爬取 API — 异步后台任务 + SSE 实时进度 + MongoDB 存储
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from pymongo.errors import PyMongoError

from nia.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", tags=["crawl"])

# ── 内存任务状态（轻量级，适合单实例） ──────────────────────────
_tasks: dict[str, dict] = {}
_tasks_lock = asyncio.Lock()

# ── URL 安全校验 ─────────────────────────────────────────────────
_BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "vbscript"}
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]", "metadata.google.internal", "169.254.169.254"}


def _validate_url(url: str) -> str:
    """校验 URL 安全性，防止 SSRF。返回清理后的 URL。"""
    url = url.strip()
    if not url:
        raise HTTPException(400, "URL 不能为空")
    if not re.match(r'^https?://', url):
        raise HTTPException(400, "仅支持 http/https 协议")
    parsed = urlparse(url)
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        raise HTTPException(400, f"禁止协议: {parsed.scheme}")
    if parsed.hostname and parsed.hostname.lower() in _BLOCKED_HOSTS:
        raise HTTPException(400, "禁止访问内网地址")
    # 禁止私有 IP（简单检查）
    if parsed.hostname:
        import ipaddress
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise HTTPException(400, "禁止访问私有网络地址")
        except ValueError:
            pass  # 域名，不是 IP
    return url


# ── 数据模型 ─────────────────────────────────────────────────────


class CrawlRequest(BaseModel):
    url: str
    instruction: str
    use_js: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_url(v)

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("提取指令不能为空")
        return v


# ── MongoDB 存储 ─────────────────────────────────────────────────


def _get_db():
    from nia.storage.database import DatabaseManager
    db = DatabaseManager()
    db.connect()
    return db


def _save_task(task: dict):
    """保存任务状态到内存 + MongoDB"""
    task_id = task["task_id"]
    _tasks[task_id] = task

    # 同步写 MongoDB（后台线程调用）
    try:
        db = _get_db()
        collection = db.get_collection("crawl_tasks")
        collection.update_one(
            {"task_id": task_id},
            {"$set": task},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Failed to save task to MongoDB: {e}")


def _publish_progress(task_id: str, step: str, progress: int, message: str):
    """发布进度到 Redis pub/sub（SSE 消费）"""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(Config.REDIS_URL, decode_responses=True)
        payload = json.dumps({
            "task_id": task_id,
            "step": step,
            "progress": progress,
            "message": message,
        })
        r.publish(f"nia:crawl:{task_id}", payload)
        # 同时更新内存状态
        if task_id in _tasks:
            _tasks[task_id]["progress"] = progress
            _tasks[task_id]["step"] = step
            _tasks[task_id]["message"] = message
    except Exception as e:
        logger.warning(f"Failed to publish progress: {e}")


# ── 爬取核心逻辑 ─────────────────────────────────────────────────


def _do_crawl(task_id: str, url: str, instruction: str, use_js: bool):
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
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_task(result)

    try:
        # Step 1: 抓取页面
        _publish_progress(task_id, "fetch", 10, "正在抓取页面...")
        html_content = ""
        if use_js:
            from nia.utils.crawl4ai_engine import Crawl4AIEngine
            engine = Crawl4AIEngine.get_instance()
            fetch_result = engine.fetch_sync(url)
            if fetch_result.get("success"):
                html_content = fetch_result.get("html", "")
            else:
                raise Exception(f"Crawl4AI failed: {fetch_result.get('error', 'unknown')}")
        else:
            import httpx
            resp = httpx.get(url, follow_redirects=True, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            html_content = resp.text

        if not html_content:
            raise Exception("Empty page content")

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
            tag.getparent().remove(tag)
        text_content = tree.text_content()
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]
        text_content = "\n".join(lines)
        if len(text_content) > 10000:
            text_content = text_content[:10000]

        _publish_progress(task_id, "parse", 40, f"解析完成，标题: {title or '(无)'}")

        # Step 3: AI 提取
        extracted_data = {}
        extraction_method = "none"

        if instruction:
            _publish_progress(task_id, "ai", 50, "AI 正在提取数据...")
            try:
                from nia.ai.llm_client import LLMClient
                from nia.ai.json_parser import RobustJsonOutputParser

                llm = LLMClient()
                parser = RobustJsonOutputParser()

                messages = [
                    {"role": "system", "content": (
                        "You are a web data extraction assistant. "
                        "Extract data from the HTML according to the instruction. "
                        "Return ONLY valid JSON with the extracted fields."
                    )},
                    {"role": "user", "content": f"Instruction: {instruction}\n\nHTML:\n{html_content[:8000]}"},
                ]
                _publish_progress(task_id, "ai", 60, "调用 LLM 中...")
                response = llm.chat(messages, temperature=0.1)
                _publish_progress(task_id, "ai", 75, "解析提取结果...")
                extracted_data = parser.parse(response)
                extraction_method = "ai"
                _publish_progress(task_id, "ai", 80, f"提取完成，{len(extracted_data)} 个字段")
            except Exception as e:
                logger.error(f"AI extraction failed: {e}")
                _publish_progress(task_id, "ai", 80, f"AI 提取失败: {str(e)[:100]}")
                extraction_method = "failed"

        # Step 4: 存入 MongoDB
        _publish_progress(task_id, "store", 85, "保存到数据库...")
        data_id = str(uuid.uuid4())
        domain = urlparse(url).netloc
        try:
            db = _get_db()
            collection = db.get_collection("crawled_data")
            doc = {
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
                "created_at": datetime.utcnow().isoformat(),
            }
            collection.insert_one(doc)
        except PyMongoError as e:
            logger.error(f"MongoDB insert failed: {e}")

        # Step 5: RAG 索引（可选，失败不影响主流程）
        _publish_progress(task_id, "index", 90, "构建语义索引...")
        try:
            from nia.utils.config import Config as _Cfg
            # 只有配置了可用的 embedding provider 才做 RAG 索引
            if _Cfg.EMBED_PROVIDER in ("bge-m3",):
                from nia.rag.rag_engine import RAGEngine
                rag = RAGEngine()
                rag.index_data(url=url, title=title, content=text_content, crawled_data_id=data_id)
            else:
                logger.info("Skipping RAG indexing (embedding provider not configured for local use)")
        except Exception as e:
            logger.warning(f"RAG indexing skipped: {e}")

        _publish_progress(task_id, "done", 100, "爬取完成！")
        result["status"] = "completed"
        result["title"] = title
        result["domain"] = domain
        result["extracted_data"] = extracted_data
        result["extraction_method"] = extraction_method
        result["data_id"] = data_id
        result["progress"] = 100
        result["step"] = "done"
        result["message"] = "爬取完成！"

    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        _publish_progress(task_id, "error", 100, f"失败: {str(e)[:200]}")
        result["status"] = "failed"
        result["error"] = str(e)[:500]
        result["progress"] = 100
        result["step"] = "error"
        result["message"] = str(e)[:200]

    _save_task(result)


# ── API 端点 ─────────────────────────────────────────────────────


@router.post("")
async def create_crawl_task(req: CrawlRequest):
    """提交爬取任务（异步后台执行，立即返回 task_id）"""
    task_id = str(uuid.uuid4())

    # 在线程池中运行，不阻塞事件循环
    asyncio.get_event_loop().run_in_executor(
        None, _do_crawl, task_id, req.url, req.instruction, req.use_js
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "任务已提交，正在后台执行",
    }


@router.get("/{task_id}/progress")
async def stream_progress(task_id: str):
    """SSE 实时推送爬取进度"""
    import redis as redis_lib

    async def event_generator() -> AsyncGenerator[str, None]:
        r = redis_lib.from_url(Config.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        pubsub.subscribe(f"nia:crawl:{task_id}")

        # 先发送当前状态
        if task_id in _tasks:
            task = _tasks[task_id]
            yield f"data: {json.dumps({'step': task.get('step', ''), 'progress': task.get('progress', 0), 'message': task.get('message', '')})}\n\n"
            if task.get("status") in ("completed", "failed"):
                yield "data: [DONE]\n\n"
                return

        timeout = time.time() + 300  # 5 分钟超时
        while time.time() < timeout:
            message = pubsub.get_message(timeout=1.0)
            if message and message["type"] == "message":
                data = message["data"]
                yield f"data: {data}\n\n"
                try:
                    parsed = json.loads(data)
                    if parsed.get("step") in ("done", "error"):
                        yield "data: [DONE]\n\n"
                        return
                except json.JSONDecodeError:
                    pass
            await asyncio.sleep(0.1)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """查询单个任务状态"""
    if task_id in _tasks:
        return _tasks[task_id]
    # 尝试从 MongoDB 读取
    try:
        db = _get_db()
        collection = db.get_collection("crawl_tasks")
        task = collection.find_one({"task_id": task_id}, {"_id": 0})
        if task:
            return task
    except Exception as e:
        logger.warning(f"Failed to read task from MongoDB: {e}")
    raise HTTPException(404, "任务不存在")


@router.get("/results")
async def get_crawl_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取爬取结果列表（从 MongoDB 分页查询）"""
    try:
        db = _get_db()
        collection = db.get_collection("crawl_tasks")
        total = collection.count_documents({"status": {"$in": ["completed", "failed"]}})
        cursor = collection.find(
            {"status": {"$in": ["completed", "failed"]}},
            {"_id": 0},
        ).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
        results = list(cursor)
        return {
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except PyMongoError as e:
        logger.warning(f"Failed to read results from MongoDB: {e}")
        return {"results": [], "total": 0, "page": page, "page_size": page_size}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    try:
        db = _get_db()
        collection = db.get_collection("crawl_tasks")
        result = collection.delete_one({"task_id": task_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "任务不存在")
        _tasks.pop(task_id, None)
        return {"message": "已删除"}
    except PyMongoError as e:
        raise HTTPException(500, f"删除失败: {e}")


# ── 并发批量 / 整站爬取（CrawlEngine） ──────────────────────────────

_batch_queues: dict[str, asyncio.Queue] = {}


class BatchCrawlRequest(BaseModel):
    seeds: list[str]
    instruction: str = ""
    use_js: bool = False
    max_depth: int = 0          # 0 = 仅抓给定 URL；>0 = 整站跟随链接
    max_pages: int = 20
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


def _persist_page(page_url: str, title: str, content: str) -> str:
    """把抓取到的页面存入 crawled_data（同步，executor 中调用）。"""
    data_id = str(uuid.uuid4())
    try:
        db = _get_db()
        db.get_collection("crawled_data").insert_one({
            "id": data_id,
            "url": page_url,
            "domain": urlparse(page_url).netloc,
            "title": title,
            "content": content,
            "extracted_data": {},
            "extraction_method": "batch",
            "created_at": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.warning(f"persist batch page failed: {e}")
    return data_id


async def _run_batch(task_id: str, req: "BatchCrawlRequest"):
    from nia.crawler import CrawlConfig, CrawlEngine

    queue = _batch_queues[task_id]
    loop = asyncio.get_event_loop()

    async def cb(ev: dict):
        await queue.put(ev)

    async def on_page(page):
        # 持久化放到线程池，避免阻塞事件循环
        await loop.run_in_executor(None, _persist_page, page.url, page.title, page.text)

    cfg = CrawlConfig(
        max_depth=req.max_depth,
        max_pages=req.max_pages,
        same_domain_only=req.same_domain_only,
        use_js=req.use_js,
    )
    try:
        result = await CrawlEngine(cfg).crawl(req.seeds, req.instruction, progress_cb=cb, on_page=on_page)
        await queue.put({"event": "result", **result})
    except Exception as e:
        logger.exception("batch crawl failed")
        await queue.put({"event": "error", "error": str(e)[:300]})
    finally:
        await queue.put({"event": "_eof"})


@router.post("/batch")
async def create_batch_crawl(req: BatchCrawlRequest):
    """并发批量 / 整站爬取，立即返回 task_id，进度经 /batch/{id}/stream 推送。"""
    task_id = str(uuid.uuid4())
    _batch_queues[task_id] = asyncio.Queue(maxsize=2000)
    asyncio.create_task(_run_batch(task_id, req))
    # 简单 GC：超过 50 个就清理已结束的
    if len(_batch_queues) > 50:
        for tid in list(_batch_queues)[:10]:
            _batch_queues.pop(tid, None)
    return {"task_id": task_id, "status": "running", "seeds": req.seeds}


@router.get("/batch/{task_id}/stream")
async def stream_batch(task_id: str):
    """SSE 推送批量爬取进度（page/finding/done/result）。"""
    queue = _batch_queues.get(task_id)
    if queue is None:
        raise HTTPException(404, "任务不存在或已过期")

    async def event_generator():
        while True:
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if ev.get("event") == "_eof":
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
