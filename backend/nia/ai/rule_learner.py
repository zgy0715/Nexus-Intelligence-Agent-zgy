import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from nia.ai.json_parser import RobustJsonOutputParser
from nia.ai.ollama_client import OllamaClient
from nia.utils.config import Config

logger = logging.getLogger(__name__)


class RuleLearner:
    def __init__(self, redis_conn):
        self.redis = redis_conn
        self.ollama = OllamaClient()
        self.json_parser = RobustJsonOutputParser()
        self.threshold = Config.EXTRACTION_FAILURE_THRESHOLD

    def record_extraction(self, domain: str, success: bool):
        key = f"nia:stats:{domain}"
        record = json.dumps({"success": success})
        self.redis.lpush(key, record)
        self.redis.ltrim(key, 0, 19)

    def get_failure_rate(self, domain: str) -> float:
        key = f"nia:stats:{domain}"
        records = self.redis.lrange(key, 0, 19)
        if not records:
            return 0.0
        failures = sum(1 for r in records if not json.loads(r).get("success", True))
        return failures / len(records)

    def should_relearn(self, domain: str) -> bool:
        return self.get_failure_rate(domain) > self.threshold

    def trigger_relearn(self, domain: str, html: str, instruction: str) -> dict:
        messages = [
            SystemMessage(content="You are a web data extraction expert. Re-analyze the HTML and extract data according to the instruction. Also generate XPath and CSS selectors for each extracted field. Return a JSON object with 'data' (extracted fields) and 'selectors' (object with field names as keys, each containing 'type', 'value', and 'css'). Return ONLY valid JSON."),
            HumanMessage(content=f"Instruction: {instruction}\n\nHTML:\n{html[:8000]}"),
        ]
        response = self.ollama.chat(messages, temperature=0.1)
        try:
            result = self.json_parser.parse(response)
            return result
        except ValueError:
            logger.error(f"RuleLearner: failed to parse relearn response for domain {domain}")
            return {}

    def update_selectors(self, domain: str, new_selectors: dict):
        key = f"nia:selectors:{domain}"
        self.redis.set(key, json.dumps(new_selectors))
