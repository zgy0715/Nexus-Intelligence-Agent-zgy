"""
通用 LLM 客户端 — 直接调用 OpenAI 兼容 API（DeepSeek/OpenAI/Qwen/Ollama）。

- 同步路径：chat / extract_json / generate_xpath ...（向后兼容旧代码）
- 异步路径：achat / achat_json / achat_tools / astream（并发引擎与自主 Agent 使用）
  · 共享 httpx.AsyncClient（连接池）
  · 指数退避重试（429 / 5xx / 超时 / 网络错误）
  · 原生 tool-calling（返回 message，含 tool_calls）
  · 流式输出（astream）
"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator

import httpx

from nia.utils.config import Config, LLMProvider

logger = logging.getLogger(__name__)


# ── 宽松 JSON 解析（无 LLM 依赖，供 async 路径与工具参数解析复用） ──────


def loads_json_loose(text: str) -> dict | None:
    """尽力从文本中解析出 JSON 对象，失败返回 None。"""
    if not text:
        return None
    text = text.strip()
    # 1) 直接解析
    for candidate in (text,):
        try:
            data = json.loads(candidate)
            return _as_dict(data)
        except (json.JSONDecodeError, TypeError):
            pass
    # 2) markdown 代码块
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if m:
        try:
            return _as_dict(json.loads(m.group(1).strip()))
        except (json.JSONDecodeError, TypeError):
            pass
    # 3) 截取第一个 { 到最后一个 }，去注释/尾逗号
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        body = text[start : end + 1]
        body = re.sub(r"//.*?$", "", body, flags=re.MULTILINE)
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        body = re.sub(r",\s*([}\]])", r"\1", body)
        try:
            return _as_dict(json.loads(body))
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _as_dict(data: Any) -> dict:
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"items": data}
    return {"result": str(data)}


# 触发重试的 HTTP 状态码
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class LLMClient:
    """通用 LLM 客户端，直接 HTTP 调用，OpenAI 兼容。"""

    def __init__(self):
        self._provider: LLMProvider = Config.LLM_PROVIDER
        self._config = Config.get_llm_config()
        self._base_url = self._config["base_url"].rstrip("/")
        self._api_key = self._config["api_key"]
        self._model = self._config["model"]
        self._client = httpx.Client(timeout=60)
        self._aclient: httpx.AsyncClient | None = None
        logger.info(f"LLM client: provider={self._provider.value}, model={self._model}")

    # ── 同步路径（向后兼容） ──────────────────────────────────────

    def _chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 4096) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = self._client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise

    def chat(self, messages: list, temperature: float = 0.1) -> str:
        """发送消息列表，返回文本响应。兼容 LangChain 消息格式。"""
        return self._chat(_normalize_messages(messages), temperature=temperature)

    def chat_with_vision(self, prompt: str, images: list[str]) -> str:
        content_parts: list[dict] = [{"type": "text", "text": prompt}]
        for img_b64 in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
            })
        return self._chat([{"role": "user", "content": content_parts}], temperature=0.1)

    def extract_json(self, text: str) -> dict:
        response = self._chat([
            {"role": "system", "content": "You are a data extraction assistant. Extract structured JSON data from the given text. Return ONLY valid JSON, no other text."},
            {"role": "user", "content": f"Extract structured JSON from the following text:\n\n{text}"},
        ], temperature=0.1)
        return loads_json_loose(response) or {}

    def generate_xpath(self, html: str, field_name: str, field_value: str) -> str:
        return self._chat([
            {"role": "system", "content": "You are an HTML/XPath expert. Generate a precise XPath selector that uniquely identifies the given field in the HTML. Return ONLY the XPath expression, nothing else."},
            {"role": "user", "content": f"HTML:\n{html[:5000]}\n\nField name: {field_name}\nField value: {field_value}\n\nGenerate an XPath selector:"},
        ], temperature=0.3).strip()

    def generate_css_selector(self, html: str, field_name: str, field_value: str) -> str:
        return self._chat([
            {"role": "system", "content": "You are an HTML/CSS expert. Generate a precise CSS selector that uniquely identifies the given field in the HTML. Return ONLY the CSS selector, nothing else."},
            {"role": "user", "content": f"HTML:\n{html[:5000]}\n\nField name: {field_name}\nField value: {field_value}\n\nGenerate a CSS selector:"},
        ], temperature=0.3).strip()

    def check_dom_change(self, old_html: str, new_html: str) -> dict:
        response = self._chat([
            {"role": "system", "content": "You are a web structure analysis expert. Compare two versions of HTML and determine if the DOM structure has changed significantly. Return a JSON object with keys: 'is_changed' (boolean) and 'similarity' (float 0.0-1.0). Return ONLY valid JSON."},
            {"role": "user", "content": f"Old HTML:\n{old_html[:3000]}\n\nNew HTML:\n{new_html[:3000]}\n\nCompare the DOM structures:"},
        ], temperature=0.1)
        return loads_json_loose(response) or {"is_changed": True, "similarity": 0.0}

    def extract_with_instruction(self, html: str, instruction: str) -> dict:
        response = self._chat([
            {"role": "system", "content": "You are a web data extraction assistant. Extract data from the HTML according to the instruction. Return ONLY valid JSON with the extracted fields."},
            {"role": "user", "content": f"Instruction: {instruction}\n\nHTML:\n{html[:8000]}"},
        ], temperature=0.1)
        return loads_json_loose(response) or {}

    # ── 异步路径 ──────────────────────────────────────────────────

    def _get_aclient(self) -> httpx.AsyncClient:
        if self._aclient is None or self._aclient.is_closed:
            self._aclient = httpx.AsyncClient(
                timeout=httpx.Timeout(Config.LLM_TIMEOUT, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._aclient

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _arequest(self, payload: dict) -> dict:
        """带退避重试的 chat/completions 调用，返回完整 JSON 响应。"""
        url = f"{self._base_url}/chat/completions"
        client = self._get_aclient()
        last_exc: Exception | None = None
        for attempt in range(Config.LLM_MAX_RETRIES + 1):
            try:
                resp = await client.post(url, json=payload, headers=self._headers())
                if resp.status_code in _RETRY_STATUS:
                    raise httpx.HTTPStatusError(
                        f"retryable status {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
                last_exc = e
                # 4xx（非重试码）直接抛出
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in _RETRY_STATUS:
                    logger.error(f"LLM API non-retryable error: {e.response.status_code} {e.response.text[:200]}")
                    raise
                if attempt < Config.LLM_MAX_RETRIES:
                    delay = 0.5 * (2 ** attempt) + (0.1 * attempt)
                    logger.warning(f"LLM request retry {attempt + 1}/{Config.LLM_MAX_RETRIES} after {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
        logger.error(f"LLM request failed after retries: {last_exc}")
        raise last_exc  # type: ignore[misc]

    async def achat(self, messages: list, *, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        payload = {
            "model": self._model,
            "messages": _normalize_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = await self._arequest(payload)
        return data["choices"][0]["message"]["content"] or ""

    async def achat_json(self, messages: list, *, temperature: float = 0.1, max_tokens: int = 4096) -> dict:
        """请求结构化 JSON。尽量启用 response_format，失败用宽松解析兜底。"""
        msgs = _normalize_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # DeepSeek/OpenAI 兼容 json_object 模式（要求 prompt 含 "json" 字样）
        if self._provider in (LLMProvider.DEEPSEEK, LLMProvider.OPENAI, LLMProvider.QWEN):
            joined = " ".join(m.get("content", "") for m in msgs if isinstance(m.get("content"), str))
            if "json" in joined.lower():
                payload["response_format"] = {"type": "json_object"}
        try:
            data = await self._arequest(payload)
        except httpx.HTTPStatusError:
            # 某些模型不支持 response_format → 去掉重试一次
            payload.pop("response_format", None)
            data = await self._arequest(payload)
        content = data["choices"][0]["message"]["content"] or ""
        return loads_json_loose(content) or {}

    async def achat_tools(
        self,
        messages: list,
        *,
        tools: list[dict],
        tool_choice: str | dict = "auto",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """原生 tool-calling。返回 choices[0].message（可能含 tool_calls）。"""
        payload = {
            "model": self._model,
            "messages": _normalize_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        data = await self._arequest(payload)
        return data["choices"][0]["message"]

    async def astream(self, messages: list, *, temperature: float = 0.7, max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """流式输出，逐段 yield 文本增量。"""
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": _normalize_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        client = self._get_aclient()
        async with client.stream("POST", url, json=payload, headers=self._headers()) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk)["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def aclose(self) -> None:
        if self._aclient is not None and not self._aclient.is_closed:
            await self._aclient.aclose()


def _normalize_messages(messages: list) -> list[dict]:
    """把 LangChain 消息对象 / 字符串 / dict 统一成 OpenAI 消息 dict 列表。"""
    formatted: list[dict] = []
    for msg in messages:
        if isinstance(msg, dict):
            formatted.append(msg)
        elif hasattr(msg, "content"):
            cls = msg.__class__.__name__
            if cls == "SystemMessage":
                role = "system"
            elif cls == "AIMessage":
                role = "assistant"
            else:
                role = "user"
            formatted.append({"role": role, "content": msg.content})
        else:
            formatted.append({"role": "user", "content": str(msg)})
    return formatted
