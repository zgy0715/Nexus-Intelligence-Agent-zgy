"""agent.tools：Pydantic 工具注册表 schema 兼容性 + 防御性参数清洗。"""

from __future__ import annotations

import json

from nia.agent.tools import TOOL_REGISTRY, TOOLS, _as_text, _as_url_list


def test_five_tools_registered_in_order():
    assert [t["function"]["name"] for t in TOOLS] == [
        "fetch_page", "crawl_links", "extract_data", "record_finding", "finish",
    ]


def test_schemas_have_no_refs():
    """DeepSeek 等兼容端点对嵌套 $defs/$ref 支持不稳 —— schema 必须扁平。"""
    for t in TOOLS:
        params = t["function"]["parameters"]
        blob = json.dumps(params)
        assert "$defs" not in blob
        assert "$ref" not in blob
        assert params["type"] == "object"
        assert params.get("properties")


def test_finish_has_no_handler():
    """finish 由主循环特殊处理，不经过 executor 派发。"""
    assert TOOL_REGISTRY["finish"].handler is None
    assert "summary" in TOOL_REGISTRY["finish"].args_model.model_fields


def test_registry_covers_tools_list():
    for t in TOOLS:
        assert t["function"]["name"] in TOOL_REGISTRY


# ── 防御性参数清洗 ───────────────────────────────────────────────

def test_as_url_list_from_string():
    """回归：模型把 URL 列表给成字符串时，不能按字符拆成 h,t,t,p 烧预算。"""
    assert _as_url_list("http://a.com https://b.com/x") == [
        "http://a.com", "https://b.com/x",
    ]
    assert _as_url_list("http://a.com") == ["http://a.com"]


def test_as_url_list_from_list_and_json_string():
    assert _as_url_list(["http://a.com", "http://b.com"]) == ["http://a.com", "http://b.com"]
    assert _as_url_list("[http://a.com, http://b.com]") == ["http://a.com", "http://b.com"]


def test_as_url_list_filters_garbage_and_dedups():
    out = _as_url_list(["http://a.com", "http://a.com", "not-a-url", "", "ftp://x"])
    assert out == ["http://a.com"]


def test_as_url_list_none_and_other_types():
    assert _as_url_list(None) == []
    assert _as_url_list(123) == []


def test_as_text_variants():
    assert _as_text(None) == ""
    assert _as_text(42) == "42"
    assert _as_text(["a", "b"]) == "a b"
    assert _as_text({"k": "v"}) == '{"k": "v"}'
    long = _as_text("x" * 9999, limit=100)
    assert len(long) == 100
