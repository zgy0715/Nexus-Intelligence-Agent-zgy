import json
import logging
import re
from urllib.parse import urljoin

import redis
import requests
from scrapy.http import Request

from nia.captcha.captcha_solver import CaptchaSolver
from nia.utils.config import Config

logger = logging.getLogger(__name__)


class CaptchaMiddleware:
    _CAPTCHA_KEYWORDS = {
        "text": [
            "captcha", "验证码", "verify_code", "checkcode",
            "captcha_img", "captcha-image", "randcode",
        ],
        "slider": [
            "slider", "滑块", "drag", "puzzle", "slide-verify",
            "slider-verify", "nc_1_n1z",
        ],
        "click": [
            "点选", "click_captcha", "click-verify", "select_words",
            "字体验证", "click_word",
        ],
    }

    def __init__(self):
        self.solver = CaptchaSolver()
        self.redis = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.max_retries = 3

    def process_response(self, request, response, spider):
        captcha_type = self._detect_captcha(response)
        if captcha_type is None:
            return response

        logger.info(f"检测到验证码: {captcha_type}, URL: {request.url}")

        retry_count = request.meta.get("captcha_retry_count", 0)
        if retry_count >= self.max_retries:
            logger.warning(f"验证码重试次数已达上限: {request.url}")
            self._move_to_dead_letter(request, spider, "验证码重试次数超限")
            return response

        try:
            if captcha_type == "text":
                captcha_image = self._extract_captcha_image(response)
                if captcha_image:
                    result = self.solver.solve_text_captcha(captcha_image)
                    if result:
                        new_request = request.replace(
                            meta={
                                **request.meta,
                                "captcha_retry_count": retry_count + 1,
                                "captcha_token": result,
                            },
                            dont_filter=True,
                        )
                        return new_request

            elif captcha_type == "slider":
                bg_image, slider_image = self._extract_slider_images(response)
                if bg_image and slider_image:
                    result = self.solver.solve_slider_captcha(bg_image, slider_image)
                    if result.get("x_offset", 0) > 0:
                        new_request = request.replace(
                            meta={
                                **request.meta,
                                "captcha_retry_count": retry_count + 1,
                                "captcha_slider_offset": result["x_offset"],
                            },
                            dont_filter=True,
                        )
                        return new_request

            elif captcha_type == "click":
                captcha_image = self._extract_captcha_image(response)
                instruction = self._extract_click_instruction(response)
                if captcha_image and instruction:
                    result = self.solver.solve_click_captcha(captcha_image, instruction)
                    if result:
                        new_request = request.replace(
                            meta={
                                **request.meta,
                                "captcha_retry_count": retry_count + 1,
                                "captcha_click_positions": result,
                            },
                            dont_filter=True,
                        )
                        return new_request

        except Exception as e:
            logger.error(f"验证码处理异常: {e}")

        self._move_to_dead_letter(request, spider, f"无法解决{captcha_type}验证码")
        return response

    def _detect_captcha(self, response) -> str | None:
        try:
            url_lower = response.url.lower()
            html_lower = response.text.lower() if response.text else ""

            for captcha_type, keywords in self._CAPTCHA_KEYWORDS.items():
                for keyword in keywords:
                    if keyword.lower() in url_lower or keyword.lower() in html_lower:
                        return captcha_type
        except Exception:
            pass
        return None

    def _extract_captcha_image(self, response) -> bytes | None:
        try:
            img_pattern = re.compile(
                r'<img[^>]*(?:captcha|verify|code|验证)[^>]*src=["\']([^"\']+)["\']',
                re.IGNORECASE,
            )
            match = img_pattern.search(response.text)
            if match:
                img_url = match.group(1)
                if not img_url.startswith("http"):
                    img_url = urljoin(response.url, img_url)
                resp = requests.get(img_url, timeout=10)
                if resp.status_code == 200:
                    return resp.content
        except Exception:
            pass
        return None

    def _extract_slider_images(self, response) -> tuple:
        bg_image = None
        slider_image = None
        try:
            bg_pattern = re.compile(
                r'<img[^>]*(?:bg|background)[^>]*src=["\']([^"\']+)["\']',
                re.IGNORECASE,
            )
            slider_pattern = re.compile(
                r'<img[^>]*(?:slider|puzzle|cut)[^>]*src=["\']([^"\']+)["\']',
                re.IGNORECASE,
            )
            bg_match = bg_pattern.search(response.text)
            slider_match = slider_pattern.search(response.text)
            if bg_match:
                bg_url = bg_match.group(1)
                if not bg_url.startswith("http"):
                    bg_url = urljoin(response.url, bg_url)
                resp = requests.get(bg_url, timeout=10)
                if resp.status_code == 200:
                    bg_image = resp.content
            if slider_match:
                slider_url = slider_match.group(1)
                if not slider_url.startswith("http"):
                    slider_url = urljoin(response.url, slider_url)
                resp = requests.get(slider_url, timeout=10)
                if resp.status_code == 200:
                    slider_image = resp.content
        except Exception:
            pass
        return bg_image, slider_image

    def _extract_click_instruction(self, response) -> str:
        try:
            pattern = re.compile(
                r'(?:请|请依次)?点击[：:]\s*([^\n<]+)',
                re.IGNORECASE,
            )
            match = pattern.search(response.text)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return ""

    def _move_to_dead_letter(self, request, spider, error: str):
        try:
            item = json.dumps({
                "url": request.url,
                "spider": spider.name if spider else "unknown",
                "error": error,
                "meta": dict(request.meta) if request.meta else {},
            }, ensure_ascii=False)
            self.redis.rpush(
                f"nia:dead_letter:{spider.name if spider else 'unknown'}", item
            )
        except Exception as e:
            logger.error(f"写入死信队列失败: {e}")
