import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from nia.storage.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])

_MAX_SEARCH_LEN = 100


@router.get("")
async def get_crawled_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=_MAX_SEARCH_LEN),
):
    search = (search or "").strip()[:_MAX_SEARCH_LEN] or None

    def _query() -> dict:
        db = get_db()
        if search:
            # LIKE 通配符转义，用户输入不会被解释为 SQL 模式。
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            from sqlalchemy import or_, select, func
            table = db.table("crawled_data")
            match = or_(table.c.url.ilike(f"%{escaped}%", escape="\\"), table.c.title.ilike(f"%{escaped}%", escape="\\"), table.c.domain.ilike(f"%{escaped}%", escape="\\"))
            with db.engine.connect() as conn:
                total = int(conn.execute(select(func.count()).select_from(table).where(match)).scalar_one())
                rows = conn.execute(select(table).where(match).order_by(table.c.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).mappings()
                data = [db.expand(row) for row in rows]
        else:
            total = db.count("crawled_data")
            data = db.list("crawled_data", order_by="created_at", limit=page_size, offset=(page - 1) * page_size)
        for item in data:
            item.pop("raw_html", None)
        return {"total": total, "page": page, "page_size": page_size, "data": data}

    try:
        return await asyncio.get_running_loop().run_in_executor(None, _query)
    except SQLAlchemyError as e:
        # 不要把数据库故障伪装成“没有数据”
        logger.error(f"Database query failed: {e}")
        raise HTTPException(503, f"数据库不可用: {str(e)[:120]}") from e


@router.get("/{data_id}")
async def get_crawled_item(data_id: str):
    """单条抓取详情（含原始 HTML，供详情弹窗使用）。"""

    def _query():
        return get_db().get("crawled_data", id=data_id)

    try:
        doc = await asyncio.get_running_loop().run_in_executor(None, _query)
    except SQLAlchemyError as e:
        logger.error(f"Database query failed: {e}")
        doc = None
    if not doc:
        raise HTTPException(404, "数据不存在")
    return doc
