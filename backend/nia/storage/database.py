"""Shared MySQL connection and persistence helpers."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
    text,
    delete,
    insert,
)
from sqlalchemy.dialects.mysql import LONGTEXT, insert as mysql_insert
from sqlalchemy.engine import Engine

from nia.utils.config import Config

logger = logging.getLogger(__name__)


def _table(name: str, *columns: Column) -> Table:
    return Table(name, MetaData(), Column("extra", JSON, nullable=True), *columns)


_TABLES: dict[str, Table] = {
    "websites": _table("websites", Column("id", String(64), primary_key=True), Column("domain", String(512), index=True), Column("name", String(512)), Column("description", Text), Column("dom_signature", Text), Column("created_at", DateTime), Column("updated_at", DateTime)),
    "extraction_rules": _table("extraction_rules", Column("id", String(64), primary_key=True), Column("website_id", String(64), index=True), Column("field_name", String(255)), Column("selector_type", String(64)), Column("selector_value", Text), Column("css_selector", Text), Column("success_rate", Float), Column("created_at", DateTime), Column("updated_at", DateTime)),
    "crawled_data": _table("crawled_data", Column("id", String(64), primary_key=True), Column("url", Text), Column("domain", String(512), index=True), Column("title", Text), Column("content", LONGTEXT), Column("raw_html", LONGTEXT), Column("extracted_data", JSON), Column("extraction_method", String(64)), Column("dom_hash", String(255)), Column("metadata", JSON), Column("created_at", DateTime, index=True)),
    "crawl_tasks": _table("crawl_tasks", Column("task_id", String(64), primary_key=True), Column("url", Text), Column("instruction", Text), Column("use_js", Boolean), Column("status", String(32), index=True), Column("progress", Integer), Column("step", String(128)), Column("message", Text), Column("title", Text), Column("domain", String(512)), Column("extracted_data", JSON), Column("extraction_method", String(64)), Column("data_id", String(64)), Column("error", Text), Column("error_type", String(255)), Column("llm_calls", Integer), Column("llm_time_ms", Integer), Column("crawl_time_ms", Integer), Column("created_at", DateTime, index=True), Column("updated_at", DateTime)),
    "chat_history": _table("chat_history", Column("id", String(64), primary_key=True), Column("role", String(32)), Column("content", Text), Column("sources", JSON), Column("created_at", DateTime, index=True)),
    "agent_runs": _table("agent_runs", Column("run_id", String(64), primary_key=True), Column("goal", Text), Column("seeds", JSON), Column("status", String(32)), Column("report", Text), Column("findings", JSON), Column("pages_used", Integer), Column("steps_used", Integer), Column("created_at", DateTime, index=True)),
    "task_logs": _table("task_logs", Column("id", String(64), primary_key=True), Column("url", Text), Column("spider_name", String(255)), Column("domain", String(512)), Column("status", String(32)), Column("llm_calls", Integer), Column("llm_time_ms", Integer), Column("crawl_time_ms", Integer), Column("error_type", String(255)), Column("error_message", Text), Column("created_at", DateTime, index=True)),
    "vector_data": _table("vector_data", Column("id", String(64), primary_key=True), Column("crawled_data_id", String(64), index=True), Column("chunk_index", Integer), Column("created_at", DateTime)),
    "data_versions": _table("data_versions", Column("id", String(64), primary_key=True), Column("crawled_data_id", String(64), index=True), Column("field_name", String(255)), Column("old_value", Text), Column("new_value", Text), Column("version_number", Integer), Column("created_at", DateTime)),
}

_KEYS = {"websites": "id", "extraction_rules": "id", "crawled_data": "id", "crawl_tasks": "task_id", "chat_history": "id", "agent_runs": "run_id", "task_logs": "id", "vector_data": "id", "data_versions": "id"}
Index("ix_crawled_data_url_prefix", _TABLES["crawled_data"].c.url, mysql_length=191)


def _normalize_value(key: str, value: Any) -> Any:
    if key.endswith("_at") and isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return value
    return value


class DatabaseManager:
    """Process-wide SQLAlchemy engine and MySQL schema access."""

    _instance: "DatabaseManager | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._engine = None
                    obj._engine_lock = threading.Lock()
                    cls._instance = obj
        return cls._instance

    def connect(self) -> "DatabaseManager":
        if self._engine is None:
            with self._engine_lock:
                if self._engine is None:
                    self._engine = create_engine(
                        Config.MYSQL_URL,
                        pool_pre_ping=True,
                        pool_recycle=1800,
                        pool_size=10,
                        max_overflow=20,
                        connect_args={"connect_timeout": 5},
                    )
        return self

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self.connect()
        return self._engine

    def table(self, name: str) -> Table:
        return _TABLES[name]

    @staticmethod
    def expand(row: dict | None) -> dict | None:
        return DatabaseManager._expand(dict(row) if row is not None else None)

    def ping(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def init_db(self) -> None:
        """Create application tables and indexes; safe to run on each startup."""
        for table in _TABLES.values():
            table.create(self.engine, checkfirst=True)
        logger.info("MySQL tables ensured (%s)", ", ".join(_TABLES))

    def _prepare(self, table_name: str, document: dict) -> dict:
        table = _TABLES[table_name]
        known = {column.name for column in table.columns}
        values = {k: _normalize_value(k, v) for k, v in document.items() if k in known and k != "extra"}
        extras = {k: v for k, v in document.items() if k not in known}
        if extras:
            values["extra"] = extras
        return values

    @staticmethod
    def _expand(row: dict | None) -> dict | None:
        if row is None:
            return None
        result = dict(row)
        extra = result.pop("extra", None) or {}
        result.update(extra)
        return result

    def upsert(self, table_name: str, document: dict) -> None:
        table = _TABLES[table_name]
        values = self._prepare(table_name, document)
        key = _KEYS[table_name]
        stmt = mysql_insert(table).values(**values)
        updates = {k: stmt.inserted[k] for k in values if k != key}
        if updates:
            stmt = stmt.on_duplicate_key_update(**updates)
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def insert(self, table_name: str, document: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(_TABLES[table_name]).values(**self._prepare(table_name, document)))

    def insert_many(self, table_name: str, documents: list[dict]) -> None:
        if not documents:
            return
        with self.engine.begin() as conn:
            conn.execute(insert(_TABLES[table_name]), [self._prepare(table_name, doc) for doc in documents])

    def get(self, table_name: str, **filters: Any) -> dict | None:
        table = _TABLES[table_name]
        stmt = select(table).where(*(table.c[k] == v for k, v in filters.items()))
        with self.engine.connect() as conn:
            return self._expand(conn.execute(stmt).mappings().first())

    def list(self, table_name: str, *, filters: dict | None = None, order_by: str | None = None, descending: bool = True, limit: int | None = None, offset: int = 0, exclude: tuple[str, ...] = ()) -> list[dict]:
        table = _TABLES[table_name]
        stmt = select(table)
        for key, value in (filters or {}).items():
            column = table.c[key]
            stmt = stmt.where(column.in_(value) if isinstance(value, (list, tuple, set)) else column == value)
        if order_by:
            stmt = stmt.order_by(table.c[order_by].desc() if descending else table.c[order_by].asc())
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        with self.engine.connect() as conn:
            rows = [self._expand(row) for row in conn.execute(stmt).mappings()]
        for row in rows:
            for key in exclude:
                row.pop(key, None)
        return rows

    def count(self, table_name: str, *, filters: dict | None = None) -> int:
        table = _TABLES[table_name]
        stmt = select(func.count()).select_from(table)
        for key, value in (filters or {}).items():
            column = table.c[key]
            stmt = stmt.where(column.in_(value) if isinstance(value, (list, tuple, set)) else column == value)
        with self.engine.connect() as conn:
            return int(conn.execute(stmt).scalar_one())

    def delete(self, table_name: str, *, filters: dict | None = None) -> int:
        table = _TABLES[table_name]
        stmt = delete(table)
        for key, value in (filters or {}).items():
            column = table.c[key]
            stmt = stmt.where(column.in_(value) if isinstance(value, (list, tuple, set)) else column == value)
        with self.engine.begin() as conn:
            return int(conn.execute(stmt).rowcount or 0)

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
        self._engine = None

    @classmethod
    def reset_instance(cls) -> None:
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None


def get_db() -> DatabaseManager:
    return DatabaseManager().connect()


def reset_instance() -> None:
    DatabaseManager.reset_instance()
