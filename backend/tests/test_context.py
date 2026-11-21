"""agent.context：token 估算 / 结构化截断 / 滚动压缩的消息序列合法性。"""

from __future__ import annotations

from nia.agent.context import (
    ContextManager,
    _scan_groups,
    estimate_messages_tokens,
    estimate_tokens,
    truncate_tool_result,
)


# ── token 估算 ──────────────────────────────────────────────────

def test_estimate_tokens_cjk_vs_latin():
    assert estimate_tokens("") == 0
    assert estimate_tokens("你好世界") == 4  # CJK 1 字 ≈ 1 token
    assert estimate_tokens("abcdefgh") == 2  # 8 字符 ≈ 2 token


def test_estimate_messages_counts_structure():
    msgs = [{"role": "user", "content": "hello"}]
    assert estimate_messages_tokens(msgs) == estimate_tokens("hello") + 4


# ── 结构化截断 ──────────────────────────────────────────────────

def test_truncate_long_string():
    out = truncate_tool_result("x" * 10000, limit=6000)
    assert len(out) < 10000
    assert "截断" in out


def test_truncate_list_keeps_first_20():
    out = truncate_tool_result(list(range(50)), limit=6000)
    assert len(out) == 21  # 20 项 + 1 条总数标注
    assert out[-1] == "…(共 50 项，仅显示前 20 项)"


def test_truncate_deep_nesting():
    obj = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": 1}}}}}}}}
    out = truncate_tool_result(obj, limit=6000)
    assert "层级过深" in json_dumps(out)


def test_truncate_result_remains_jsonable():
    import json

    obj = {"pages": [{"title": "t" * 500, "links": list(range(40))}], "ok": True}
    json.dumps(truncate_tool_result(obj, limit=1000))


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


# ── 组扫描 ──────────────────────────────────────────────────────

def _group(step: int) -> list[dict]:
    """构造一组「assistant(tool_calls) + tool 回复」消息。"""
    return [
        {"role": "assistant", "content": None, "tool_calls": [{"id": f"c{step}", "type": "function"}]},
        {"role": "tool", "tool_call_id": f"c{step}", "content": f"result {step}"},
    ]


def _history(groups: int) -> list[dict]:
    msgs: list[dict] = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "目标"},
    ]
    for s in range(groups):
        msgs.extend(_group(s))
    return msgs


def test_scan_groups():
    msgs = _history(3)
    groups = _scan_groups(msgs)
    assert len(groups) == 3
    assert groups[0] == (2, 3)


# ── 滚动压缩：核心不变量 = 消息序列合法性 ─────────────────────────

def test_compact_keeps_sequence_legal():
    cm = ContextManager(token_budget=1_000_000, keep_recent_steps=2)
    msgs = _history(5)
    for gi in range(5):
        cm.record_batch([f"第{gi}批：抓取了页面 {gi}"])

    out, saved = cm.compact(msgs)

    # 不变量 1：任何 tool 消息的前一条必须是带 tool_calls 的 assistant
    for i, m in enumerate(out):
        if m.get("role") == "tool":
            prev = out[i - 1]
            assert prev.get("role") == "assistant" and prev.get("tool_calls"), i

    # 不变量 2：摘要替换后不再出现旧 tool_calls（旧组整体消失）
    assert saved >= 0
    assert cm.compactions == 1
    digest_msgs = [
        m for m in out
        if m.get("role") == "assistant" and "已压缩" in (m.get("content") or "")
    ]
    assert len(digest_msgs) == 3  # 5 组 - 保留 2 组（插入的系统提示是 user 角色，不计入）

    # 不变量 3：system / 最初的 user 永远保留
    assert out[0]["role"] == "system"
    assert out[1]["content"] == "目标"

    # 不变量 4：已消费的摘要批次被清掉（保持与消息组对齐）
    assert len(cm.batches) == 2


def test_compact_noop_when_few_groups():
    cm = ContextManager(token_budget=1_000_000, keep_recent_steps=4)
    msgs = _history(3)
    out, saved = cm.compact(msgs)
    assert out == msgs
    assert saved == 0


def test_should_compact_threshold():
    cm = ContextManager(token_budget=50)
    small = [{"role": "user", "content": "hi"}]
    assert not cm.should_compact(small)
    big = [{"role": "user", "content": "字" * 200}]
    assert cm.should_compact(big)
