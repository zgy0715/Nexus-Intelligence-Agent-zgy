"""统一的时间工具。

所有写入 MongoDB 的时间字段都使用 **naive UTC datetime**（BSON date），
原因：
1. `datetime.utcnow()` 在 Python 3.12+ 已废弃；
2. 之前混用 ISO 字符串与 BSON date 导致监测聚合（按时间范围查询）永远匹配不到，
   因为 MongoDB 不会跨 BSON 类型做范围比较。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


def utcnow() -> datetime:
    """当前 UTC 时间（naive），可直接存入 MongoDB。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_today_range(days_ago: int = 0) -> tuple[datetime, datetime]:
    """返回 [start, end) 半开区间的 UTC 日窗口。

    旧实现用本地 `date.today()` 去比较 UTC 时间戳，在东八区会把当天
    0:00–8:00 的数据错误地划到前一天。
    """
    today = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today + timedelta(days=1), time.min)
    return start, end


def utc_date(days_ago: int = 0) -> date:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
