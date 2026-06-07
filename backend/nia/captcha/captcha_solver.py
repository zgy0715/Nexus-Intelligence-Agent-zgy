"""
验证码识别模块 — 支持文字/滑块/点选三种验证码

⚠️ 注意：此模块已实现但尚未接入任何 API 或爬取流程。
如需启用，在 crawl.py 的 _do_crawl 中合适位置调用 CaptchaSolver。
"""

import base64
import hashlib
import json

import ddddocr
import redis

from nia.ai.llm_client import LLMClient
from nia.utils.config import Config


class CaptchaSolver:
    def __init__(self):
        self.llm = LLMClient()
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.redis = redis.from_url(Config.REDIS_URL, decode_responses=True)

    def solve_text_captcha(self, image_bytes: bytes) -> str:
        captcha_hash = self._compute_hash(image_bytes)
        cached = self._get_cached_captcha(captcha_hash)
        if cached:
            return cached
        result = self._solve_with_ddddocr(image_bytes)
        if not result:
            result = self._solve_with_vl(
                image_bytes,
                "请识别这张验证码图片中的文字或数字，只返回识别结果，不要其他内容",
            )
        if result:
            self._cache_captcha(captcha_hash, result)
        return result or ""

    def solve_slider_captcha(self, bg_image_bytes: bytes, slider_image_bytes: bytes) -> dict:
        bg_b64 = base64.b64encode(bg_image_bytes).decode("utf-8")
        slider_b64 = base64.b64encode(slider_image_bytes).decode("utf-8")
        prompt = (
            "这是滑块验证码的背景图和滑块图。请判断滑块在背景图上应该滑动到的x轴偏移位置（像素）。"
            "背景图：<image>，滑块图：<image>。只返回x偏移量的数字，不要其他内容。"
        )
        response = self.llm.chat_with_vision(prompt, [bg_b64, slider_b64])
        try:
            x_offset = int("".join(c for c in response if c.isdigit()))
        except (ValueError, TypeError):
            x_offset = 0
        return {"x_offset": x_offset}

    def solve_click_captcha(self, image_bytes: bytes, instruction: str) -> list:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            f"这是点选验证码图片，指令为：{instruction}。"
            "请返回需要点击的位置坐标，格式为JSON数组，每个元素包含x和y。"
            '例如：[{"x": 100, "y": 50}]。只返回JSON，不要其他内容。'
        )
        response = self.llm.chat_with_vision(prompt, [image_b64])
        try:
            clean = response.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()
            positions = json.loads(clean)
            return [{"x": int(p["x"]), "y": int(p["y"])} for p in positions]
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return []

    def _solve_with_vl(self, image_bytes: bytes, prompt: str) -> str:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = self.llm.chat_with_vision(prompt, [image_b64])
        return response.strip()

    def _solve_with_ddddocr(self, image_bytes: bytes) -> str:
        try:
            result = self.ocr.classification(image_bytes)
            return result.strip() if result else ""
        except Exception:
            return ""

    def _get_cached_captcha(self, captcha_hash: str) -> str | None:
        return self.redis.get(f"nia:captcha:{captcha_hash}")

    def _cache_captcha(self, captcha_hash: str, result: str):
        self.redis.setex(f"nia:captcha:{captcha_hash}", 86400, result)

    def _compute_hash(self, data: bytes) -> str:
        return hashlib.md5(data).hexdigest()
