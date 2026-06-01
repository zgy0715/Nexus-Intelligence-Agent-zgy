import asyncio

import nest_asyncio
from crawl4ai import AsyncWebCrawler

nest_asyncio.apply()


class Crawl4AIEngine:
    _instance = None

    @classmethod
    def get_instance(cls, headless=True, verbose=False):
        if cls._instance is None:
            cls._instance = cls(headless=headless, verbose=verbose)
        return cls._instance

    def __init__(self, headless=True, verbose=False):
        self.headless = headless
        self.verbose = verbose
        self._crawler = None
        self._loop = None

    def _get_loop(self):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def _ensure_crawler(self):
        if self._crawler is None:
            try:
                from crawl4ai import BrowserConfig
                config = BrowserConfig(headless=self.headless, verbose=self.verbose)
                self._crawler = AsyncWebCrawler(config=config)
            except (ImportError, TypeError):
                self._crawler = AsyncWebCrawler(
                    headless=self.headless,
                    verbose=self.verbose,
                )
            await self._crawler.start()

    async def fetch(self, url):
        await self._ensure_crawler()
        try:
            result = await self._crawler.arun(url=url)
            return {
                "html": result.html if result else "",
                "status_code": result.status_code if result else None,
                "success": result.success if result else False,
            }
        except Exception as e:
            return {
                "html": "",
                "status_code": None,
                "success": False,
                "error": str(e),
            }

    async def fetch_with_js(self, url, wait_for=None, js_code=None):
        await self._ensure_crawler()
        try:
            result = await self._crawler.arun(
                url=url,
                js_code=js_code,
                wait_for=wait_for,
            )
            return {
                "html": result.html if result else "",
                "status_code": result.status_code if result else None,
                "success": result.success if result else False,
            }
        except Exception as e:
            return {
                "html": "",
                "status_code": None,
                "success": False,
                "error": str(e),
            }

    async def close(self):
        if self._crawler is not None:
            await self._crawler.close()
            self._crawler = None

    def fetch_sync(self, url):
        loop = self._get_loop()
        return loop.run_until_complete(self.fetch(url))

    def fetch_with_js_sync(self, url, wait_for=None, js_code=None):
        loop = self._get_loop()
        return loop.run_until_complete(self.fetch_with_js(url, wait_for=wait_for, js_code=js_code))
