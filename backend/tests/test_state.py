"""agent.state：发现去重 / 预算 / 序列化。"""

from __future__ import annotations

from nia.agent.state import AgentState


def _state(pages: int = 10, steps: int = 10) -> AgentState:
    st = AgentState(run_id="r1", goal="g", seeds=["https://a.com"])
    st.budget_pages = pages
    st.budget_steps = steps
    return st


def test_add_finding_dedup_same_content():
    st = _state()
    f = {"url": "https://a.com/1", "title": "t", "content": "c"}
    assert st.add_finding(f) is True
    assert st.add_finding(dict(f)) is False  # 完全相同 → 去重
    assert len(st.findings) == 1


def test_add_finding_empty_url_title_dedup_by_content():
    """旧版 (url, title) 键会把两条空标题记录都收下或都丢掉；现在按内容哈希。"""
    st = _state()
    assert st.add_finding({"url": "", "title": "", "content": "abc"}) is True
    assert st.add_finding({"url": "", "title": "", "content": "abc"}) is False
    assert st.add_finding({"url": "", "title": "", "content": "different"}) is True
    assert len(st.findings) == 2


def test_add_finding_richer_overwrites():
    st = _state()
    st.add_finding({"url": "u", "title": "t", "content": "short"})
    st.add_finding({"url": "u", "title": "t", "content": "short" + " much richer content"})
    assert len(st.findings) == 1
    assert "richer" in st.findings[0]["content"]


def test_budget_left():
    st = _state(pages=2, steps=5)
    st.pages_used = 2
    assert st.budget_left() is False  # 页面预算尽
    st.pages_used = 1
    st.steps_used = 5
    assert st.budget_left() is False  # 步数预算尽
    st.steps_used = 2
    assert st.budget_left() is True


def test_cancel_idempotent():
    st = _state()
    assert st.cancelled is False
    st.cancel()
    st.cancel()
    assert st.cancelled is True


def test_to_dict_caps_findings():
    st = _state()
    for i in range(10):
        st.add_finding({"url": f"u{i}", "title": f"t{i}", "content": f"c{i}"})
    d = st.to_dict(max_findings=3)
    assert len(d["findings"]) == 3
    assert d["finding_count"] == 10  # 总数不受截断影响
