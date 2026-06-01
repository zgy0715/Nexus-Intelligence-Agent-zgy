import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from nia.utils.config import Config

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = Config.OLLAMA_BASE_URL
        self.model = Config.OLLAMA_LLM_MODEL
        self.vl_model = Config.OLLAMA_VL_MODEL
        self._extraction_llm = ChatOllama(
            base_url=self.base_url,
            model=self.model,
            temperature=0.1,
        )
        self._generation_llm = ChatOllama(
            base_url=self.base_url,
            model=self.model,
            temperature=0.3,
        )

    def chat(self, messages: list, temperature: float = 0.1) -> str:
        if temperature <= 0.1:
            llm = self._extraction_llm
        elif temperature >= 0.3:
            llm = self._generation_llm
        else:
            llm = ChatOllama(
                base_url=self.base_url,
                model=self.model,
                temperature=temperature,
            )
        response = llm.invoke(messages)
        return response.content

    def chat_with_vision(self, prompt: str, images: list) -> str:
        content_parts = [{"type": "text", "text": prompt}]
        for img_b64 in images:
            content_parts.append({
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_b64}",
            })
        vl_llm = ChatOllama(
            base_url=self.base_url,
            model=self.vl_model,
            temperature=0.1,
        )
        message = HumanMessage(content=content_parts)
        response = vl_llm.invoke([message])
        return response.content

    def extract_json(self, text: str) -> dict:
        messages = [
            SystemMessage(content="You are a data extraction assistant. Extract structured JSON data from the given text. Return ONLY valid JSON, no other text."),
            HumanMessage(content=f"Extract structured JSON from the following text:\n\n{text}"),
        ]
        response = self._extraction_llm.invoke(messages)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM response. Response preview: {str(response.content)[:300]}")
            return {}

    def generate_xpath(self, html: str, field_name: str, field_value: str) -> str:
        messages = [
            SystemMessage(content="You are an HTML/XPath expert. Generate a precise XPath selector that uniquely identifies the given field in the HTML. Return ONLY the XPath expression, nothing else."),
            HumanMessage(content=f"HTML:\n{html[:5000]}\n\nField name: {field_name}\nField value: {field_value}\n\nGenerate an XPath selector:"),
        ]
        response = self._generation_llm.invoke(messages)
        return response.content.strip()

    def generate_css_selector(self, html: str, field_name: str, field_value: str) -> str:
        messages = [
            SystemMessage(content="You are an HTML/CSS expert. Generate a precise CSS selector that uniquely identifies the given field in the HTML. Return ONLY the CSS selector, nothing else."),
            HumanMessage(content=f"HTML:\n{html[:5000]}\n\nField name: {field_name}\nField value: {field_value}\n\nGenerate a CSS selector:"),
        ]
        response = self._generation_llm.invoke(messages)
        return response.content.strip()

    def check_dom_change(self, old_html: str, new_html: str) -> dict:
        messages = [
            SystemMessage(content="You are a web structure analysis expert. Compare two versions of HTML and determine if the DOM structure has changed significantly. Return a JSON object with keys: 'is_changed' (boolean) and 'similarity' (float 0.0-1.0). Return ONLY valid JSON."),
            HumanMessage(content=f"Old HTML:\n{old_html[:3000]}\n\nNew HTML:\n{new_html[:3000]}\n\nCompare the DOM structures:"),
        ]
        response = self._extraction_llm.invoke(messages)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse DOM change result. Response preview: {str(response.content)[:300]}")
            return {"is_changed": True, "similarity": 0.0}

    def extract_with_instruction(self, html: str, instruction: str) -> dict:
        messages = [
            SystemMessage(content="You are a web data extraction assistant. Extract data from the HTML according to the instruction. Return ONLY valid JSON with the extracted fields."),
            HumanMessage(content=f"Instruction: {instruction}\n\nHTML:\n{html[:8000]}"),
        ]
        response = self._extraction_llm.invoke(messages)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse extraction result. Response preview: {str(response.content)[:300]}")
            return {}
