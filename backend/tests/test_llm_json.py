"""ai.llm_client.loads_json_loose：三级宽松解析 + 注释剥离不碰 URL 的回归。"""

from __future__ import annotations

from nia.ai.llm_client import loads_json_loose


def test_plain_json():
    assert loads_json_loose('{"a": 1}') == {"a": 1}


def test_markdown_fenced_block():
    text = '提取结果如下：\n```json\n{"title": "T", "items": [1, 2]}\n```\n以上。'
    assert loads_json_loose(text) == {"title": "T", "items": [1, 2]}


def test_salvage_from_prose():
    text = '好的，以下是提取结果 {"name": "n", "count": 3} 请查收'
    assert loads_json_loose(text) == {"name": "n", "count": 3}


def test_trailing_comma_fixed():
    assert loads_json_loose('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_line_comment_stripped():
    text = '{"a": 1, // 注释\n "b": 2}'
    assert loads_json_loose(text) == {"a": 1, "b": 2}


def test_url_slashes_survive_comment_stripping():
    """回归：旧版正则会把 "http://x" 里的 //x 当注释删掉 —— URL 是本项目主要载荷。"""
    text = '{"url": "http://example.com/path", "n": 1}'
    out = loads_json_loose(text)
    assert out is not None
    assert out["url"] == "http://example.com/path"


def test_url_inside_fenced_block_with_comments():
    text = '```json\n{\n  // 目标页\n  "url": "https://a.com/x?y=1",\n  "ok": true,\n}\n```'
    out = loads_json_loose(text)
    assert out == {"url": "https://a.com/x?y=1", "ok": True}


def test_block_comment_stripped():
    text = '{"a": /* inline */ 1}'
    assert loads_json_loose(text) == {"a": 1}


def test_invalid_returns_none():
    assert loads_json_loose("") is None
    assert loads_json_loose("完全没有结构化内容") is None


def test_non_dict_payload_wrapped_or_none():
    """顶层不是对象时不应崩溃（_as_dict 约定）。"""
    out = loads_json_loose("[1, 2, 3]")
    assert out is None or isinstance(out, dict)
