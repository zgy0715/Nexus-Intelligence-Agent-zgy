import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse

import scrapy

from nia.items import NiaItem


class BaseSpider(scrapy.Spider):
    name = "base"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
    }

    def __init__(self, ai_instruction=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_instruction = ai_instruction

    def ai_extract(self, response, instruction=None):
        return {}

    def parse(self, response):
        item = NiaItem()
        item["url"] = response.url
        item["title"] = response.css("title::text").get("").strip()
        item["raw_html"] = response.text
        item["dom_hash"] = self._compute_dom_hash(response.text)
        item["metadata"] = {
            "status": response.status,
            "headers": dict(response.headers),
            "encoding": response.encoding,
        }
        item["spider_name"] = self.name
        item["crawl_time"] = datetime.utcnow().isoformat()
        item["content"] = ""
        item["extracted_data"] = {}
        item["extraction_method"] = "none"
        yield item

        for request in self._extract_links(response):
            yield request

    @staticmethod
    def _compute_dom_hash(html):
        stripped = html.strip()
        return hashlib.md5(stripped.encode("utf-8")).hexdigest()

    def _extract_links(self, response):
        base_url = response.url
        parsed_base = urlparse(base_url)
        allowed_domains = getattr(self, "allowed_domains", None)

        for href in response.css("a::attr(href)").getall():
            if not href:
                continue
            url = urljoin(base_url, href)
            parsed_url = urlparse(url)

            if parsed_url.scheme not in ("http", "https"):
                continue

            if allowed_domains and parsed_url.netloc not in allowed_domains:
                if not any(
                    parsed_url.netloc.endswith("." + d) for d in allowed_domains
                ):
                    continue

            if parsed_url.netloc != parsed_base.netloc:
                if not allowed_domains:
                    continue

            yield scrapy.Request(url, callback=self.parse)
