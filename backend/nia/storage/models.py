from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class Website:
    id: str = field(default_factory=lambda: str(uuid4()))
    domain: str = ""
    name: str | None = None
    description: str | None = None
    dom_signature: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "name": self.name,
            "description": self.description,
            "dom_signature": self.dom_signature,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Website":
        return cls(
            id=data.get("id", str(uuid4())),
            domain=data.get("domain", ""),
            name=data.get("name"),
            description=data.get("description"),
            dom_signature=data.get("dom_signature"),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
        )


@dataclass
class ExtractionRule:
    id: str = field(default_factory=lambda: str(uuid4()))
    website_id: str = ""
    field_name: str = ""
    selector_type: str = ""
    selector_value: str = ""
    css_selector: str | None = None
    success_rate: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "website_id": self.website_id,
            "field_name": self.field_name,
            "selector_type": self.selector_type,
            "selector_value": self.selector_value,
            "css_selector": self.css_selector,
            "success_rate": self.success_rate,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractionRule":
        return cls(
            id=data.get("id", str(uuid4())),
            website_id=data.get("website_id", ""),
            field_name=data.get("field_name", ""),
            selector_type=data.get("selector_type", ""),
            selector_value=data.get("selector_value", ""),
            css_selector=data.get("css_selector"),
            success_rate=data.get("success_rate", 0.0),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
        )


@dataclass
class CrawledData:
    id: str = field(default_factory=lambda: str(uuid4()))
    url: str = ""
    domain: str = ""
    title: str | None = None
    content: str | None = None
    raw_html: str | None = None
    extracted_data: dict | None = None
    extraction_method: str | None = None
    dom_hash: str | None = None
    metadata: dict | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "content": self.content,
            "raw_html": self.raw_html,
            "extracted_data": self.extracted_data,
            "extraction_method": self.extraction_method,
            "dom_hash": self.dom_hash,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CrawledData":
        return cls(
            id=data.get("id", str(uuid4())),
            url=data.get("url", ""),
            domain=data.get("domain", ""),
            title=data.get("title"),
            content=data.get("content"),
            raw_html=data.get("raw_html"),
            extracted_data=data.get("extracted_data"),
            extraction_method=data.get("extraction_method"),
            dom_hash=data.get("dom_hash"),
            metadata=data.get("metadata"),
            created_at=data.get("created_at", datetime.utcnow()),
        )


@dataclass
class VectorMeta:
    id: str = field(default_factory=lambda: str(uuid4()))
    crawled_data_id: str = ""
    chunk_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "crawled_data_id": self.crawled_data_id,
            "chunk_index": self.chunk_index,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VectorMeta":
        return cls(
            id=data.get("id", str(uuid4())),
            crawled_data_id=data.get("crawled_data_id", ""),
            chunk_index=data.get("chunk_index", 0),
            created_at=data.get("created_at", datetime.utcnow()),
        )


@dataclass
class DataVersion:
    id: str = field(default_factory=lambda: str(uuid4()))
    crawled_data_id: str = ""
    field_name: str = ""
    old_value: str | None = None
    new_value: str | None = None
    version_number: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "crawled_data_id": self.crawled_data_id,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "version_number": self.version_number,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataVersion":
        return cls(
            id=data.get("id", str(uuid4())),
            crawled_data_id=data.get("crawled_data_id", ""),
            field_name=data.get("field_name", ""),
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            version_number=data.get("version_number", 0),
            created_at=data.get("created_at", datetime.utcnow()),
        )


@dataclass
class TaskLog:
    id: str = field(default_factory=lambda: str(uuid4()))
    url: str = ""
    spider_name: str | None = None
    domain: str = ""
    status: str = ""
    llm_calls: int = 0
    llm_time_ms: int | None = None
    crawl_time_ms: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "spider_name": self.spider_name,
            "domain": self.domain,
            "status": self.status,
            "llm_calls": self.llm_calls,
            "llm_time_ms": self.llm_time_ms,
            "crawl_time_ms": self.crawl_time_ms,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskLog":
        return cls(
            id=data.get("id", str(uuid4())),
            url=data.get("url", ""),
            spider_name=data.get("spider_name"),
            domain=data.get("domain", ""),
            status=data.get("status", ""),
            llm_calls=data.get("llm_calls", 0),
            llm_time_ms=data.get("llm_time_ms"),
            crawl_time_ms=data.get("crawl_time_ms"),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
            created_at=data.get("created_at", datetime.utcnow()),
        )
