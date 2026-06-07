import json
import logging
import re

from nia.ai.llm_client import LLMClient

logger = logging.getLogger(__name__)


class RobustJsonOutputParser:
    def __init__(self):
        self._llm = LLMClient()

    def parse(self, text: str) -> dict:
        result = self._try_parse(text)
        if result is not None:
            return result
        return self._llm_self_correct(text)

    def _try_parse(self, text: str) -> dict | None:
        """尝试多种方式解析 JSON，返回 dict 或 None。"""
        # 尝试直接解析
        try:
            data = json.loads(text)
            return self._normalize(data)
        except (json.JSONDecodeError, TypeError):
            pass

        # 从 markdown 代码块提取
        json_block = self._extract_json_block(text)
        if json_block:
            try:
                data = json.loads(json_block)
                return self._normalize(data)
            except (json.JSONDecodeError, TypeError):
                pass

        # 移除注释
        cleaned = self._remove_comments(text)
        try:
            data = json.loads(cleaned)
            return self._normalize(data)
        except (json.JSONDecodeError, TypeError):
            pass

        # 移除尾部逗号
        no_trailing = self._remove_trailing_commas(cleaned)
        try:
            data = json.loads(no_trailing)
            return self._normalize(data)
        except (json.JSONDecodeError, TypeError):
            pass

        return None

    def _normalize(self, data) -> dict:
        """确保返回的是 dict。如果 LLM 返回了 array，转成 dict。"""
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            # 把 array 包装成 {"items": [...]}
            return {"items": data}
        return {"result": str(data)}

    def _extract_json_block(self, text: str) -> str:
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _remove_comments(self, text: str) -> str:
        text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return text

    def _remove_trailing_commas(self, text: str) -> str:
        text = re.sub(r',\s*([}\]])', r'\1', text)
        return text

    def _llm_self_correct(self, text: str) -> dict:
        messages = [
            {"role": "system", "content": "You are a JSON repair assistant. The following text is supposed to be valid JSON but has errors. Fix all errors and return ONLY valid JSON. Do not include any explanation or markdown formatting."},
            {"role": "user", "content": f"Fix this broken JSON:\n\n{text}"},
        ]
        response = self._llm.chat(messages, temperature=0.1)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        json_block = self._extract_json_block(response)
        if json_block:
            try:
                return json.loads(json_block)
            except json.JSONDecodeError:
                pass
        cleaned = self._remove_comments(response)
        no_trailing = self._remove_trailing_commas(cleaned)
        try:
            return json.loads(no_trailing)
        except json.JSONDecodeError:
            raise ValueError(
                f"Failed to parse JSON even after LLM self-correction. "
                f"Original text (first 200 chars): {text[:200]}. "
                f"LLM correction response (first 300 chars): {str(response)[:300]}"
            )
