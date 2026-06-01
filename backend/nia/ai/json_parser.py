import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from nia.ai.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class RobustJsonOutputParser:
    def __init__(self):
        self._ollama = OllamaClient()

    def parse(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        json_block = self._extract_json_block(text)
        if json_block:
            try:
                return json.loads(json_block)
            except json.JSONDecodeError:
                pass

        cleaned = self._remove_comments(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        no_trailing = self._remove_trailing_commas(cleaned)
        try:
            return json.loads(no_trailing)
        except json.JSONDecodeError:
            pass

        return self._llm_self_correct(text)

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
            SystemMessage(content="You are a JSON repair assistant. The following text is supposed to be valid JSON but has errors. Fix all errors and return ONLY valid JSON. Do not include any explanation or markdown formatting."),
            HumanMessage(content=f"Fix this broken JSON:\n\n{text}"),
        ]
        response = self._ollama.chat(messages, temperature=0.1)
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
