"""HTML 解析 — 提取标题、正文、绝对链接（lxml）。"""

from __future__ import annotations

import logging

from lxml import html as lxml_html

from nia.crawler.models import PageContent
from nia.utils.url_safety import normalize_url

logger = logging.getLogger(__name__)

_MAX_TEXT = 20000  # 正文最大字符数（防超大页面拖垮 LLM/内存）


def parse_html(html_content: str, url: str, max_text: int = _MAX_TEXT) -> PageContent:
    """把原始 HTML 解析为 PageContent。失败时降级返回空结构。"""
    if not html_content:
        return PageContent(url=url, html="")
    try:
        tree = lxml_html.fromstring(html_content)
    except Exception as e:  # lxml 对畸形 HTML 偶发抛错
        logger.warning(f"parse_html failed for {url}: {e}")
        return PageContent(url=url, html=html_content)

    # 标题
    title = ""
    title_el = tree.cssselect("title")
    if title_el:
        title = (title_el[0].text_content() or "").strip()

    # 链接（去重 + 归一化为绝对 URL，同时过滤锚点/JS）
    links: list[str] = []
    seen: set[str] = set()
    for a in tree.cssselect("a[href]"):
        href = a.get("href", "")
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        norm = normalize_url(href, base=url)
        if norm and norm not in seen:
            seen.add(norm)
            links.append(norm)

    # 正文（移除脚本/样式/导航类噪声后取文本）
    for tag in tree.cssselect("script, style, noscript, template, svg"):
        parent = tag.getparent()
        if parent is not None:
            parent.remove(tag)
    raw_text = tree.text_content() or ""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    text = "\n".join(lines)
    if len(text) > max_text:
        text = text[:max_text]

    return PageContent(url=url, title=title, text=text, links=links, html=html_content)
