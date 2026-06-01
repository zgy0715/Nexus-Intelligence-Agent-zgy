import logging

from nia.items import NiaItem
from nia.spiders.base_spider import BaseSpider
from nia.utils.crawl4ai_engine import Crawl4AIEngine

logger = logging.getLogger(__name__)


class SmartSpider(BaseSpider):
    name = "smart"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
    }

    def __init__(self, start_urls=None, ai_instruction=None, use_js=False, *args, **kwargs):
        if start_urls is None:
            start_urls = []
        if isinstance(start_urls, str):
            start_urls = [u.strip() for u in start_urls.split(",") if u.strip()]
        super().__init__(ai_instruction=ai_instruction, *args, **kwargs)
        self.start_urls = start_urls
        self.use_js = use_js
        self._crawl4ai = None

    def _get_crawl4ai(self):
        if self._crawl4ai is None:
            self._crawl4ai = Crawl4AIEngine.get_instance()
        return self._crawl4ai

    def start_requests(self):
        for url in self.start_urls:
            if self.use_js:
                yield self._make_js_request(url)
            else:
                import scrapy
                yield scrapy.Request(url, callback=self.parse)

    def _make_js_request(self, url):
        import scrapy
        return scrapy.Request(url, callback=self.parse_js, meta={"js_url": url}, dont_filter=True)

    def parse_js(self, response):
        url = response.meta.get("js_url", response.url)
        try:
            engine = self._get_crawl4ai()
            result = engine.fetch_sync(url)
            if result.get("success"):
                from scrapy.http import HtmlResponse
                js_response = HtmlResponse(
                    url=url,
                    body=result["html"].encode("utf-8"),
                    encoding="utf-8",
                )
                yield from self.parse(js_response)
            else:
                logger.warning(f"Crawl4AI failed for {url}, falling back to normal response")
                yield from self.parse(response)
        except Exception as e:
            logger.error(f"Crawl4AI error for {url}: {e}")
            yield from self.parse(response)

    def parse(self, response):
        for item_or_request in super().parse(response):
            if isinstance(item_or_request, NiaItem):
                instruction = self.ai_instruction
                extracted = self.ai_extract(response, instruction=instruction)
                if extracted:
                    item_or_request["extracted_data"] = extracted
                    item_or_request["extraction_method"] = "ai"
                yield item_or_request
            else:
                yield item_or_request

        for request in self._detect_pagination(response):
            yield request

    def _detect_pagination(self, response):
        pagination_selectors = [
            'a.next::attr(href)',
            'a[rel="next"]::attr(href)',
            'li.next a::attr(href)',
            '.pagination .next a::attr(href)',
            '.pager .next a::attr(href)',
            'a[aria-label="Next"]::attr(href)',
            'a[aria-label="Next page"]::attr(href)',
        ]

        seen = set()
        for selector in pagination_selectors:
            href = response.css(selector).get()
            if href:
                from urllib.parse import urljoin
                url = urljoin(response.url, href.strip())
                if url not in seen:
                    seen.add(url)
                    if self.use_js:
                        yield self._make_js_request(url)
                    else:
                        yield response.follow(url, callback=self.parse)

    def closed(self, reason):
        if self._crawl4ai is not None:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._crawl4ai.close())
                else:
                    loop.run_until_complete(self._crawl4ai.close())
            except Exception:
                pass
