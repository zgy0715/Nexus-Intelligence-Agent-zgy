"""HTML 解析 — trafilatura 正文密度提取 + 元数据 + 锚文本（lxml 兜底）。

v3 变更（对比旧版「全文本抽取」）：
- 正文改用 trafilatura（可读性密度算法）：导航/页脚/面包屑/广告噪声不再混进
  text 喂给 LLM 与 RAG。trafilatura 失败（畸形 HTML/极简页面）时回退旧 lxml 方案。
- 新增 metadata：meta description / og:* / 文章日期 / JSON-LD 摘要。
- 新增 anchors：归一化 URL → 锚文本，frontier 用它做目标相关性打分。
"""

from __future__ import annotations

import json
import logging

from lxml import html as lxml_html

from nia.crawler.models import PageContent
from nia.utils.url_safety import normalize_url

logger = logging.getLogger(__name__)

_MAX_TEXT = 20000  # 正文最大字符数（防超大页面拖垮 LLM/内存）
_META_KEYS = ("description", "author", "date", "keywords")


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

    # 链接（去重 + 归一化为绝对 URL，同时过滤锚点/JS）+ 锚文本
    links: list[str] = []
    anchors: dict[str, str] = {}
    seen: set[str] = set()
    for a in tree.cssselect("a[href]"):
        href = a.get("href", "")
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        norm = normalize_url(href, base=url)
        if norm and norm not in seen:
            seen.add(norm)
            links.append(norm)
            text = (a.text_content() or "").strip()
            if text:
                anchors[norm] = text[:200]

    # 元数据：meta 标签 + Open Graph + JSON-LD
    metadata = _extract_metadata(tree)

    # 正文：trafilatura 密度提取，失败回退全文本
    text = _extract_text_trafilatura(html_content, url, max_text)
    if not text:
        text = _extract_text_lxml(tree, max_text)

    return PageContent(
        url=url, title=title, text=text, links=links, html=html_content,
        anchors=anchors, metadata=metadata,
    )


def _extract_text_trafilatura(html_content: str, url: str, max_text: int) -> str:
    """trafilatura 正文提取（延迟导入，失败静默返回空由调用方兜底）。"""
    try:
        import trafilatura

        extracted = trafilatura.extract(
            html_content,
            url=url,
            output_format="txt",
            include_comments=False,
            favor_recall=True,
        )
        if extracted:
            text = extracted.strip()
            return text[:max_text]
    except Exception as e:
        logger.debug(f"trafilatura extract failed for {url}: {e}")
    return ""


def _extract_text_lxml(tree, max_text: int) -> str:
    """旧版全文本提取（trafilatura 的兜底路径）。"""
    for tag in tree.cssselect("script, style, noscript, template, svg"):
        parent = tag.getparent()
        if parent is not None:
            parent.remove(tag)
    raw_text = tree.text_content() or ""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    return "\n".join(lines)[:max_text]


def _extract_metadata(tree) -> dict:
    meta: dict = {}
    try:
        for el in tree.cssselect("meta[name], meta[property]"):
            key = (el.get("name") or el.get("property") or "").lower()
            content = (el.get("content") or "").strip()
            if not content:
                continue
            if key == "description":
                meta["description"] = content[:500]
            elif key == "author" or key.endswith(":author"):
                meta.setdefault("author", content[:200])
            elif key in ("article:published_time", "date", "pubdate"):
                meta.setdefault("date", content[:60])
            elif key == "og:site_name":
                meta.setdefault("site_name", content[:200])
        # JSON-LD（常见于新闻/文档站，取 @type 摘要与标题/日期）
        for script in tree.cssselect('script[type="application/ld+json"]'):
            raw = (script.text_content() or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                meta.setdefault("jsonld_type", str(item.get("@type", ""))[:100])
                if item.get("headline"):
                    meta.setdefault("jsonld_headline", str(item["headline"])[:300])
                if item.get("datePublished"):
                    meta.setdefault("date", str(item["datePublished"])[:60])
                break
    except Exception as e:  # 元数据解析失败不影响正文
        logger.debug(f"metadata extraction failed: {e}")
    return {k: v for k, v in meta.items() if k in _META_KEYS or k.startswith(("og_", "jsonld_", "site_name"))}
