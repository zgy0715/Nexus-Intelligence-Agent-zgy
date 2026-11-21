"""rag.bm25：BM25Plus 小语料正分 / jieba 中文检索 / 脏标记懒重建。"""

from __future__ import annotations

from nia.rag.bm25 import BM25Doc, BM25Index


def test_build_and_chinese_search():
    idx = BM25Index()
    idx.build([
        BM25Doc("1", "苹果公司发布了新一代芯片，性能大幅提升"),
        BM25Doc("2", "香蕉是一种常见的水果，富含钾元素"),
        BM25Doc("3", "FAISS 向量检索引擎支持 GPU 加速"),
    ])
    hits = idx.search("香蕉 水果", top_k=2)
    assert hits
    assert hits[0][0] == "2"


def test_bm25plus_positive_idf_on_common_term():
    """回归：BM25Okapi 在「词出现在所有文档」时 IDF 为负（小语料必现），
    全查询得负分被 `s > 0` 过滤后永远 0 命中；BM25Plus 必须恒正。"""
    idx = BM25Index()
    idx.build([
        BM25Doc("1", "系统设计概述"),
        BM25Doc("2", "系统架构详解"),
        BM25Doc("3", "系统部署指南"),
    ])
    hits = idx.search("系统", top_k=5)
    assert hits, "常见词在 BM25Plus 下必须有正分命中"
    assert all(s > 0 for _, s in hits)


def test_add_triggers_lazy_rebuild_on_search():
    """脏标记：add 不立即重建，search 前自动重建 —— 新文档必须可检索。"""
    idx = BM25Index()
    idx.build([BM25Doc("1", "已有文档：向量检索")])
    idx.add("2", "新增文档：爬虫调度策略")
    assert idx.size == 2
    hits = idx.search("爬虫调度", top_k=2)
    assert hits and hits[0][0] == "2"


def test_remove_lazy_and_stale():
    idx = BM25Index()
    idx.build([BM25Doc("1", "向量检索"), BM25Doc("2", "爬虫调度")])
    idx.remove("2")
    assert idx.size == 1
    assert all(doc_id != "2" for doc_id, _ in idx.search("爬虫调度", top_k=5))


def test_duplicate_add_updates_in_place():
    idx = BM25Index()
    idx.add("1", "第一版内容")
    idx.add("1", "第二版内容")
    assert idx.size == 1
    hits = idx.search("第二版", top_k=3)
    assert hits and hits[0][0] == "1"


def test_empty_index_search_returns_empty():
    assert BM25Index().search("任意", top_k=5) == []


def test_empty_text_add_ignored():
    idx = BM25Index()
    idx.add("1", "")
    assert idx.size == 0
