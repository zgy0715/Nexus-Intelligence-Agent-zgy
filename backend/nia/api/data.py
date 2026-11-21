import asyncio
import csv
import io
import json
import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError

from nia.storage.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])

_MAX_SEARCH_LEN = 100
_MAX_EXPORT_ROWS = 5000
_EXPORT_COLUMNS = ("id", "url", "domain", "title", "extraction_method", "created_at", "content", "extracted_data")


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


@router.get("/export")
async def export_crawled_data(format: str = Query("json", pattern="^(json|csv)$")):
    """全量导出已爬取数据（JSON / CSV），供知识库迁移与答辩材料使用。"""

    def _build() -> tuple[str, str]:
        rows = get_db().list(
            "crawled_data",
            order_by="created_at",
            descending=False,
            limit=_MAX_EXPORT_ROWS,
            columns=_EXPORT_COLUMNS,
        )
        if format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(_EXPORT_COLUMNS)
            for r in rows:
                writer.writerow([
                    json.dumps(r[c], ensure_ascii=False) if c == "extracted_data" and r[c] is not None
                    else (r[c].isoformat() if c == "created_at" and r[c] is not None else r[c])
                    for c in _EXPORT_COLUMNS
                ])
            return buf.getvalue(), "text/csv; charset=utf-8"
        payload = [
            {
                **r,
                "created_at": r["created_at"].isoformat() if r.get("created_at") is not None else None,
            }
            for r in rows
        ]
        return json.dumps(payload, ensure_ascii=False, indent=2), "application/json; charset=utf-8"

    try:
        body, media = await asyncio.get_running_loop().run_in_executor(None, _build)
    except SQLAlchemyError as e:
        logger.error(f"Database export failed: {e}")
        raise HTTPException(503, f"数据库不可用: {str(e)[:120]}") from e
    # BOM 让 Excel 正确识别 UTF-8 CSV
    if format == "csv":
        body = "﻿" + body
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="nia-data-export.{format}"'},
    )


@router.get("/stats")
async def get_data_stats():
    """知识库总览统计（数据浏览页顶部卡片：文档数 / 站点数 / 总字数 / 最近更新）。"""
    def _query() -> dict:
        from sqlalchemy import func, select

        db = get_db()
        table = db.table("crawled_data")
        with db.engine.connect() as conn:
            total = int(conn.execute(select(func.count()).select_from(table)).scalar_one())
            domains = int(conn.execute(select(func.count(func.distinct(table.c.domain)))).scalar_one())
            chars = int(conn.execute(select(func.coalesce(func.sum(func.length(table.c.content)), 0))).scalar_one())
            latest = conn.execute(select(func.max(table.c.created_at))).scalar_one()
        return {
            "total": total,
            "domains": domains,
            "chars": chars,
            "latest": latest.isoformat() if latest else None,
        }

    try:
        return await asyncio.to_thread(_query)
    except SQLAlchemyError as e:
        logger.warning(f"data stats failed: {e}")
        raise HTTPException(503, "数据库不可用")


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
