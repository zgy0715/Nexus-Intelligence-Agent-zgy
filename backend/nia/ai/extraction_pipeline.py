import hashlib
import json
import logging
from urllib.parse import urlparse

import redis
from langchain_core.messages import HumanMessage, SystemMessage
from lxml import html as lxml_html

from nia.ai.json_parser import RobustJsonOutputParser
from nia.ai.ollama_client import OllamaClient
from nia.utils.config import Config

logger = logging.getLogger(__name__)


class AIExtractionPipeline:
    def __init__(self):
        self.ollama = OllamaClient()
        self.json_parser = RobustJsonOutputParser()
        self.redis = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.cache_ttl = Config.AI_CACHE_DAYS * 86400
        self.stats = {
            "total": 0,
            "cached": 0,
            "ai_extracted": 0,
            "selector_extracted": 0,
            "failed": 0,
        }

    def process_item(self, item, spider):
        self.stats["total"] += 1
        url = item.get("url", "")
        url_hash = hashlib.md5(url.encode()).hexdigest()
        domain = urlparse(url).netloc

        cached = self._get_cached(url)
        if cached is not None:
            self.stats["cached"] += 1
            for key, value in cached.items():
                item[key] = value
            item["extraction_method"] = "cache"
            return item

        extracted = None
        has_instruction = hasattr(spider, "ai_instruction") and spider.ai_instruction

        if has_instruction:
            domain_selectors = self._get_selectors(domain)
            if domain_selectors:
                try:
                    extracted = self._selector_extract(item, spider)
                    if extracted:
                        self.stats["selector_extracted"] += 1
                        item["extraction_method"] = "selector"
                except Exception as e:
                    logger.debug(f"Selector extraction failed for {url}: {e}")
                    extracted = None

            if not extracted:
                try:
                    extracted = self._ai_extract(item, spider)
                    if extracted:
                        self.stats["ai_extracted"] += 1
                        item["extraction_method"] = "ai"
                        html_content = item.get("raw_html", "")
                        new_selectors = self._generate_selectors(html_content, extracted)
                        if new_selectors:
                            self._save_selectors(domain, new_selectors)
                except Exception as e:
                    logger.error(f"AI extraction failed for {url}: {e}")
                    extracted = None

        if extracted:
            for key, value in extracted.items():
                if not key.startswith("_"):
                    item[key] = value
            item["extracted_data"] = {k: v for k, v in extracted.items() if not k.startswith("_")}
            self._cache_result(url, extracted)
        else:
            self.stats["failed"] += 1

        return item

    def _ai_extract(self, item, spider) -> dict:
        html_content = item.get("raw_html", "")
        instruction = getattr(spider, "ai_instruction", "")
        messages = [
            SystemMessage(content="You are a web data extraction assistant. Extract data from the HTML according to the instruction. Return ONLY valid JSON with the extracted fields."),
            HumanMessage(content=f"Instruction: {instruction}\n\nHTML:\n{html_content[:8000]}"),
        ]
        response = self.ollama.chat(messages, temperature=0.1)
        parsed = self.json_parser.parse(response)
        return parsed

    def _selector_extract(self, item, spider) -> dict:
        url = item.get("url", "")
        domain = urlparse(url).netloc
        selectors = self._get_selectors(domain)
        if not selectors:
            return {}
        html_content = item.get("raw_html", "")
        if not html_content:
            return {}
        tree = lxml_html.fromstring(html_content)
        result = {}
        for field_name, selector_info in selectors.items():
            selector_type = selector_info.get("type", "xpath")
            selector_value = selector_info.get("value", "")
            try:
                if selector_type == "xpath":
                    values = tree.xpath(selector_value)
                else:
                    values = tree.cssselect(selector_value)
                if values:
                    if isinstance(values[0], str):
                        result[field_name] = values[0].strip()
                    elif hasattr(values[0], "text_content"):
                        result[field_name] = values[0].text_content().strip()
                    else:
                        result[field_name] = str(values[0]).strip()
            except Exception:
                return {}
        return result if result else {}

    def _generate_selectors(self, html_content: str, extracted_data: dict) -> dict:
        if not html_content:
            return {}
        selectors = {}
        for field_name, field_value in extracted_data.items():
            if field_name.startswith("_") or not isinstance(field_value, str):
                continue
            try:
                xpath = self.ollama.generate_xpath(html_content, field_name, field_value)
                css = self.ollama.generate_css_selector(html_content, field_name, field_value)
                selectors[field_name] = {
                    "type": "xpath",
                    "value": xpath,
                    "css": css,
                }
            except Exception:
                continue
        return selectors

    def _save_selectors(self, domain: str, selectors: dict):
        if not selectors:
            return
        key = f"nia:selectors:{domain}"
        self.redis.set(key, json.dumps(selectors))

    def _get_selectors(self, domain: str) -> dict:
        key = f"nia:selectors:{domain}"
        data = self.redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return {}

    def _cache_result(self, url: str, data: dict):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        key = f"nia:cache:extract:{url_hash}"
        cache_data = {k: v for k, v in data.items() if not k.startswith("_")}
        self.redis.setex(key, self.cache_ttl, json.dumps(cache_data))

    def _get_cached(self, url: str):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        key = f"nia:cache:extract:{url_hash}"
        data = self.redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    def open_spider(self, spider):
        logger.info("AIExtractionPipeline opened")

    def close_spider(self, spider):
        logger.info(f"AIExtractionPipeline closed. Stats: {self.stats}")
