"""并发爬取引擎的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from nia.utils.config import Config


@dataclass
class CrawlConfig:
    """单次爬取任务的配置（带全局默认值，可逐字段覆盖）。"""

    max_depth: int = field(default_factory=lambda: Config.CRAWL_MAX_DEPTH)
    max_pages: int = field(default_factory=lambda: Config.CRAWL_MAX_PAGES)
    same_domain_only: bool = True
    allowed_domains: set[str] = field(default_factory=set)
    concurrency: int = field(default_factory=lambda: Config.CRAWL_CONCURRENCY)
    llm_concurrency: int = field(default_factory=lambda: Config.CRAWL_LLM_CONCURRENCY)
    js_concurrency: int = field(default_factory=lambda: Config.CRAWL_JS_CONCURRENCY)
    use_js: bool = False
    request_timeout: float = field(default_factory=lambda: Config.CRAWL_REQUEST_TIMEOUT)
    max_retries: int = field(default_factory=lambda: Config.CRAWL_MAX_RETRIES)
    cache_ttl: int = field(default_factory=lambda: Config.AI_CACHE_DAYS * 86400)
    # httpx 正文过短时是否回退到 JS 渲染（启发式）
    js_fallback: bool = False
    js_fallback_min_chars: int = 500
    # 单页最大响应体（字节）
    max_content_bytes: int = field(default_factory=lambda: Config.CRAWL_MAX_CONTENT_BYTES)
    # 单域名并发上限（礼貌抓取）
    per_domain_concurrency: int = field(default_factory=lambda: Config.CRAWL_PER_DOMAIN_CONCURRENCY)
    # 是否遵从 robots.txt
    respect_robots: bool = field(default_factory=lambda: Config.CRAWL_RESPECT_ROBOTS)


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    html: str = ""
    status_code: int = 0
    success: bool = False
    error: str = ""
    from_cache: bool = False
    elapsed: float = 0.0
    rendered_js: bool = False
    content_type: str = ""
    truncated: bool = False
    # 该 URL 是否被 robots.txt 禁止
    blocked_by_robots: bool = False


@dataclass
class PageContent:
    url: str
    title: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)
    html: str = ""


@dataclass
class Finding:
    url: str
    title: str = ""
    data: dict = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "data": self.data,
            "summary": self.summary,
        }
