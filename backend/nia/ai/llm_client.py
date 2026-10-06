"""
通用 LLM 客户端 — 直接调用 OpenAI 兼容 API（DeepSeek/OpenAI/Qwen/Ollama）。

- 同步路径：chat / extract_json / generate_xpath ...（向后兼容旧代码）
- 异步路径：achat / achat_json / achat_tools / astream（并发引擎与自主 Agent 使用）
  · 共享 httpx.AsyncClient（连接池）
  · 指数退避重试（429 / 5xx / 超时 / 网络错误），尊重 Retry-After
  · 原生 tool-calling（返回 message，含 tool_calls）
  · 流式输出（astream，带跨行缓冲）
  · token 用量累计（usage）
"""

import asyncio
import json
import logging
import re
import threading
from typing import Any, AsyncGenerator

import httpx

from nia.utils.config import Config, LLMProvider

logger = logging.getLogger(__name__)


# ── 宽松 JSON 解析（无 LLM 依赖，供 async 路径与工具参数解析复用） ──────


def _strip_json_comments(text: str) -> str:
    """去掉 JSON 里的 // 与 /* */ 注释，但**不碰字符串内部**。

    旧实现直接用 `re.sub(r"//.*?$", ...)`，会把 `"url": "http://x"` 里的
    `//x` 当成注释删掉 —— 而 URL 正是这个项目的主要载荷。
    """
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escaped = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < n and text[i] not in "\r\n":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def loads_json_loose(text: str) -> dict | None:
    """尽力从文本中解析出 JSON 对象，失败返回 None。"""
    if not text:
        return None
    text = text.strip()
    # 1) 直接解析
    try:
        return _as_dict(json.loads(text))
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
        for candidate in (
            _strip_json_comments(body),
            re.sub(r",\s*([}\]])", r"\1", _strip_json_comments(body)),
        ):
            try:
                return _as_dict(json.loads(candidate))
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def _as_dict(data: Any) -> dict:
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"items": data}
    return {"result": str(data)}


# 触发重试的 HTTP 状态码
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}
# 去掉 response_format 后重试的状态码（模型不支持该参数）
_UNSUPPORTED_PARAM_STATUS = {400, 404, 422}
# o1/o3/gpt-5 系列不接受 max_tokens，改用 max_completion_tokens
_MAX_COMPLETION_TOKENS_PREFIXES = ("o1", "o3", "o4", "gpt-5")


class LLMClient:
    """通用 LLM 客户端，直接 HTTP 调用，OpenAI 兼容。"""

    def __init__(self):
        self._provider: LLMProvider = Config.LLM_PROVIDER
        self._config = Config.get_llm_config()
        base_url = (self._config["base_url"] or "").rstrip("/")
        # Ollama 的 OpenAI 兼容端点挂在 /v1 下；配置里通常只写 http://localhost:11434
        if self._provider == LLMProvider.OLLAMA and not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        self._base_url = base_url
        self._api_key = self._config["api_key"]
        self._model = self._config["model"]
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()
        self._aclient: httpx.AsyncClient | None = None
        self._usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        logger.info(f"LLM client: provider={self._provider.value}, model={self._model}")

    # ── 用量统计 ──────────────────────────────────────────────────

    def _record_usage(self, data: dict) -> None:
        usage = data.get("usage") if isinstance(data, dict) else None
        if not isinstance(usage, dict):
            return
        self._usage["calls"] += 1
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                self._usage[key] += value

    @property
    def usage(self) -> dict:
        """累计 token 用量（进程内），供监控/成本估算使用。"""
        return dict(self._usage)

    def reset_usage(self) -> None:
        for key in self._usage:
            self._usage[key] = 0

    # ── 同步路径（向后兼容） ──────────────────────────────────────

    def _get_client(self) -> httpx.Client:
        """惰性创建同步客户端；不再在 __init__ 里无条件占用连接与 FD。"""
        if self._client is None or self._client.is_closed:
            with self._client_lock:
                if self._client is None or self._client.is_closed:
                    self._client = httpx.Client(timeout=httpx.Timeout(Config.LLM_TIMEOUT, connect=10.0))
        return self._client

    def _token_param(self) -> str:
        model = (self._model or "").lower()
        return "max_completion_tokens" if model.startswith(_MAX_COMPLETION_TOKENS_PREFIXES) else "max_tokens"

    def _chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 4096) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            self._token_param(): max_tokens,
        }
        try:
            resp = self._get_client().post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            self._record_usage(data)
            return data["choices"][0]["message"]["content"] or ""
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
            "Authorization": f"Bearer {self._api_key or 'ollama'}",
            "Content-Type": "application/json",
        }

    def _retry_delay(self, attempt: int, response: httpx.Response | None = None) -> float:
        delay = 0.5 * (2**attempt) + (0.1 * attempt)
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    delay = max(delay, min(float(retry_after), 30.0))
                except ValueError:
                    from email.utils import parsedate_to_datetime
                    import time as _time
                    try:
                        dt = parsedate_to_datetime(retry_after)
                        if dt is not None:
                            delay = max(delay, min(dt.timestamp() - _time.time(), 30.0))
                    except (TypeError, ValueError):
                        pass
        return max(0.0, delay)

    async def _arequest(self, payload: dict) -> dict:
        """带退避重试的 chat/completions 调用，返回完整 JSON 响应。"""
        url = f"{self._base_url}/chat/completions"
        client = self._get_aclient()
        max_retries = max(0, Config.LLM_MAX_RETRIES)
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = await client.post(url, json=payload, headers=self._headers())
                if resp.status_code in _RETRY_STATUS:
                    raise httpx.HTTPStatusError(
                        f"retryable status {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                self._record_usage(data)
                return data
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
                last_exc = e
                response = getattr(e, "response", None)
                # 4xx（非重试码）直接抛出
                if isinstance(e, httpx.HTTPStatusError) and response is not None and response.status_code not in _RETRY_STATUS:
                    logger.error(
                        "LLM API non-retryable error: %s %s", response.status_code, response.text[:200]
                    )
                    raise
                if attempt < max_retries:
                    delay = self._retry_delay(attempt, response)
                    logger.warning(
                        "LLM request retry %d/%d after %.1fs: %s", attempt + 1, max_retries, delay, e
                    )
                    await asyncio.sleep(delay)
        if last_exc is None:  # 理论上不可达（max_retries<0 时旧实现会在这里 TypeError）
            raise RuntimeError("LLM 请求失败：未捕获到具体异常")
        logger.error(f"LLM request failed after retries: {last_exc}")
        raise last_exc

    async def achat(self, messages: list, *, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        payload = {
            "model": self._model,
            "messages": _normalize_messages(messages),
            "temperature": temperature,
            self._token_param(): max_tokens,
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
            self._token_param(): max_tokens,
        }
        # DeepSeek/OpenAI 兼容 json_object 模式（要求 prompt 含 "json" 字样）
        wants_json_format = False
        if self._provider in (LLMProvider.DEEPSEEK, LLMProvider.OPENAI, LLMProvider.QWEN):
            joined = " ".join(m.get("content", "") for m in msgs if isinstance(m.get("content"), str))
            if "json" in joined.lower():
                payload["response_format"] = {"type": "json_object"}
                wants_json_format = True
        try:
            data = await self._arequest(payload)
        except httpx.HTTPStatusError as e:
            # 只有「模型不支持该参数」时才降级重试；429/5xx 已经在 _arequest 里退避过了，
            # 旧实现无条件重发一次，等于把已经花掉的成本再花一遍。
            status = getattr(e.response, "status_code", None)
            if not wants_json_format or status not in _UNSUPPORTED_PARAM_STATUS:
                raise
            logger.info("LLM 不支持 response_format（HTTP %s），去掉后重试一次", status)
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
            self._token_param(): max_tokens,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        data = await self._arequest(payload)
        message = data["choices"][0]["message"]
        if message.get("content") is None:
            message["content"] = ""
        return message

    async def astream(self, messages: list, *, temperature: float = 0.7, max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """流式输出，逐段 yield 文本增量。

        修复点：SSE 的 JSON 可能被切成多行（跨行缓冲）；`delta` 可能是 null；
        tool-call 增量没有 content 直接跳过而不是抛 AttributeError。
        """
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": _normalize_messages(messages),
            "temperature": temperature,
            self._token_param(): max_tokens,
            "stream": True,
        }
        client = self._get_aclient()
        async with client.stream("POST", url, json=payload, headers=self._headers()) as resp:
            resp.raise_for_status()
            buffer = ""
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    break
                buffer += chunk
                try:
                    parsed = json.loads(buffer)
                except json.JSONDecodeError:
                    # 可能是被截断的半行，等下一行拼上再试
                    continue
                buffer = ""
                choices = parsed.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content
                if parsed.get("usage"):
                    self._record_usage(parsed)

    async def aclose(self) -> None:
        if self._aclient is not None and not self._aclient.is_closed:
            await self._aclient.aclose()
        if self._client is not None and not self._client.is_closed:
            self._client.close()

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()


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
