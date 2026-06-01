import json
import logging
import uuid
import time
import threading
from datetime import datetime
from urllib.parse import urlparse

import redis
from fastapi import APIRouter
from pydantic import BaseModel

from nia.utils.config import Config

logger = logging.getLogger(__name__)
# 确保日志输出到控制台
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/api/crawl", tags=["crawl"])

redis_conn = redis.from_url(Config.REDIS_URL, decode_responses=True)


class CrawlRequest(BaseModel):
    url: str
    instruction: str
    use_js: bool = False


def _save_result(result: dict):
    """将任务结果写入 Redis"""
    try:
        existing = redis_conn.get("crawl_results")
        results = json.loads(existing) if existing else []
        if not isinstance(results, list):
            results = []
    except (redis.RedisError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to read crawl results from Redis: {e}")
        results = []

    task_id = result.get("task_id")
    updated = False
    for i, r in enumerate(results):
        if r.get("task_id") == task_id:
            results[i] = result
            updated = True
            break
    if not updated:
        results.append(result)

    results = results[-50:]

    try:
        redis_conn.set("crawl_results", json.dumps(results, ensure_ascii=False))
    except redis.RedisError as e:
        logger.error(f"Failed to persist crawl results to Redis: {e}")


def _do_crawl(task_id: str, url: str, instruction: str, use_js: bool):
    """在独立线程中执行爬取任务"""
    print(f"[CRAWL] Starting crawl for {url}", flush=True)
    logger.info(f"[{task_id}] Starting crawl for {url}")

    result = {
        "task_id": task_id,
        "url": url,
        "instruction": instruction,
        "use_js": use_js,
        "status": "running",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_result(result)

    try:
        # Step 1: 抓取页面
        print(f"[CRAWL] Fetching page...", flush=True)
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

        print(f"[CRAWL] Fetched {len(html_content)} bytes", flush=True)

        # Step 2: 提取标题和文本
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

        # Step 3: AI 提取
        extracted_data = {}
        extraction_method = "none"

        if instruction:
            print(f"[CRAWL] Running AI extraction...", flush=True)
            try:
                from nia.ai.ollama_client import OllamaClient
                from nia.ai.json_parser import RobustJsonOutputParser
                from langchain_core.messages import HumanMessage, SystemMessage

                ollama = OllamaClient()
                parser = RobustJsonOutputParser()

                messages = [
                    SystemMessage(content=(
                        "You are a web data extraction assistant. "
                        "Extract data from the HTML according to the instruction. "
                        "Return ONLY valid JSON with the extracted fields."
                    )),
                    HumanMessage(content=f"Instruction: {instruction}\n\nHTML:\n{html_content[:8000]}"),
                ]
                print(f"[CRAWL] Calling Ollama...", flush=True)
                response = ollama.chat(messages, temperature=0.1)
                print(f"[CRAWL] Got Ollama response, parsing...", flush=True)
                extracted_data = parser.parse(response)
                extraction_method = "ai"
                print(f"[CRAWL] AI extraction successful: {list(extracted_data.keys())}", flush=True)
            except Exception as e:
                print(f"[CRAWL] AI extraction failed: {e}", flush=True)
                logger.warning(f"[{task_id}] AI extraction failed: {e}")
                extraction_method = "failed"

        # Step 4: 存入 MongoDB
        print(f"[CRAWL] Storing in MongoDB...", flush=True)
        data_id = str(uuid.uuid4())
        domain = urlparse(url).netloc
        try:
            from nia.storage.database import DatabaseManager
            db_manager = DatabaseManager()
            db_manager.connect()
            collection = db_manager.get_collection("crawled_data")
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
            print(f"[CRAWL] Stored in MongoDB", flush=True)
        except Exception as e:
            print(f"[CRAWL] MongoDB failed: {e}", flush=True)
            logger.warning(f"[{task_id}] MongoDB storage failed: {e}")

        # Step 5: RAG 索引
        print(f"[CRAWL] Indexing for RAG...", flush=True)
        try:
            from nia.rag.rag_engine import RAGEngine
            rag = RAGEngine()
            rag.index_data(url=url, title=title, content=text_content, crawled_data_id=data_id)
            print(f"[CRAWL] RAG index updated", flush=True)
        except Exception as e:
            print(f"[CRAWL] RAG indexing failed: {e}", flush=True)
            logger.warning(f"[{task_id}] RAG indexing failed: {e}")

        result["status"] = "completed"
        result["title"] = title
        result["extracted_data"] = extracted_data
        result["extraction_method"] = extraction_method
        result["data_id"] = data_id
        print(f"[CRAWL] Crawl completed!", flush=True)

    except Exception as e:
        print(f"[CRAWL] Crawl failed: {e}", flush=True)
        logger.error(f"[{task_id}] Crawl failed: {e}", exc_info=True)
        result["status"] = "failed"
        result["error"] = str(e)[:500]

    _save_result(result)


@router.post("")
async def create_crawl_task(req: CrawlRequest):
    """提交爬取任务（异步执行）"""
    task_id = str(uuid.uuid4())

    result = {
        "task_id": task_id,
        "url": req.url,
        "instruction": req.instruction,
        "use_js": req.use_js,
        "status": "queued",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_result(result)

    # 启动后台线程
    t = threading.Thread(
        target=_do_crawl,
        args=(task_id, req.url, req.instruction, req.use_js),
        daemon=True,
    )
    t.start()
    print(f"[CRAWL] Thread started for task {task_id}", flush=True)

    return {"task_id": task_id, "status": "queued"}


@router.get("/results")
async def get_crawl_results():
    try:
        existing = redis_conn.get("crawl_results")
        results = json.loads(existing) if existing else []
        if not isinstance(results, list):
            return {"results": []}
        return {"results": results}
    except (redis.RedisError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to read crawl results from Redis: {e}")
        return {"results": []}
