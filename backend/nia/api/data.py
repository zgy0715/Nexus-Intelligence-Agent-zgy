import logging

from fastapi import APIRouter, Query
from pymongo.errors import PyMongoError

from nia.storage.database import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])

db = DatabaseManager()


@router.get("")
async def get_crawled_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
):
    try:
        collection = db.get_collection("crawled_data")
        query_filter = {}
        if search:
            query_filter = {
                "$or": [
                    {"url": {"$regex": search, "$options": "i"}},
                    {"title": {"$regex": search, "$options": "i"}},
                    {"domain": {"$regex": search, "$options": "i"}},
                ]
            }
        total = collection.count_documents(query_filter)
        skip = (page - 1) * page_size
        cursor = collection.find(query_filter).sort("created_at", -1).skip(skip).limit(page_size)
        data = []
        for doc in cursor:
            try:
                doc.pop("_id", None)
                data.append(doc)
            except (TypeError, AttributeError) as e:
                logger.warning(f"Failed to serialize document: {e}")
                continue
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": data,
        }
    except PyMongoError as e:
        logger.error(f"Database query failed: {e}")
        return {
            "total": 0,
            "page": page,
            "page_size": page_size,
            "data": [],
        }
