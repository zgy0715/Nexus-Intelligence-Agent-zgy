import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from nia.storage.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])

# 列表接口不返回原始 HTML（单页可达 MB 级），只在详情里按需取
_LIST_PROJECTION = {"_id": 0, "raw_html": 0}

_MAX_SEARCH_LEN = 100


@router.get("")
async def get_crawled_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=_MAX_SEARCH_LEN),
):
    search = (search or "").strip()[:_MAX_SEARCH_LEN] or None

    def _query() -> dict:
        collection = get_db().get_collection("crawled_data")
        query_filter: dict = {}
        if search:
            # 必须转义：用户输入直接进 $regex 会造成正则注入/ReDoS
            pattern = re.escape(search)
            query_filter = {
                "$or": [
                    {"url": {"$regex": pattern, "$options": "i"}},
                    {"title": {"$regex": pattern, "$options": "i"}},
                    {"domain": {"$regex": pattern, "$options": "i"}},
                ]
            }
        total = collection.count_documents(query_filter)
        cursor = (
            collection.find(query_filter, _LIST_PROJECTION)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return {"total": total, "page": page, "page_size": page_size, "data": list(cursor)}

    try:
        return await asyncio.get_running_loop().run_in_executor(None, _query)
    except PyMongoError as e:
        # 不要把数据库故障伪装成“没有数据”
        logger.error(f"Database query failed: {e}")
        raise HTTPException(503, f"数据库不可用: {str(e)[:120]}") from e


@router.get("/{data_id}")
async def get_crawled_item(data_id: str):
    """单条抓取详情（含原始 HTML，供详情弹窗使用）。"""

    def _query():
        return get_db().get_collection("crawled_data").find_one(
            {"id": data_id}, {"_id": 0}
        )

    try:
        doc = await asyncio.get_running_loop().run_in_executor(None, _query)
    except PyMongoError as e:
        logger.error(f"Database query failed: {e}")
        doc = None
    if not doc:
        raise HTTPException(404, "数据不存在")
    return doc
