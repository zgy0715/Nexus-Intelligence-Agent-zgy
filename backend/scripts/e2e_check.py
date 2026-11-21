"""全模块端到端检验 — 真实调用后端 API（含 LLM 链路）。

用法：cd backend && python scripts/e2e_check.py
逐项打印 PASS/FAIL，退出码 0 = 全部通过。
"""

import asyncio
import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
RESULTS: list[tuple[str, bool, str]] = []


def ok(name: str, cond: bool, extra: str = "") -> None:
    RESULTS.append((name, bool(cond), extra))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  [{extra}]" if extra else ""), flush=True)


async def read_sse(c: httpx.AsyncClient, path: str, until: set[str], timeout: float = 180.0):
    events = []
    deadline = time.monotonic() + timeout
    async with c.stream("GET", BASE + path, timeout=timeout) as s:
        async for line in s.aiter_lines():
            if time.monotonic() > deadline:
                break
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                ev = json.loads(payload)
            except json.JSONDecodeError:
                continue
            events.append(ev)
            if ev.get("type") in until or ev.get("event") in until:
                break
    return events


async def main() -> int:
    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as c:
        # ── 基础设施 ──
        r = await c.get(BASE + "/api/health")
        ok("health 探针", r.status_code == 200)
        r = await c.get(BASE + "/api/ready")
        j = r.json()
        ok("ready 探针(mysql+redis)", j.get("status") == "ok", f"mysql={j.get('mysql')} redis={j.get('redis')}")
        r = await c.get(BASE + "/api/settings/status")
        j = r.json()
        ok("主力模型在线", j["llm_provider"]["connected"], j["llm_provider"].get("error", ""))
        if "aux_llm" in j:
            ok("辅助模型探测端点", isinstance(j.get("aux_llm"), dict))

        # ── 批量爬取 ──
        r = await c.post(BASE + "/api/crawl/batch", json={
            "seeds": ["https://example.com"], "max_depth": 0, "max_pages": 2,
        })
        ok("批量爬取提交", r.status_code == 200, r.text[:80] if r.status_code != 200 else "")
        tid = r.json().get("task_id", "")
        evs = await read_sse(c, f"/api/crawl/batch/{tid}/stream", {"done", "error", "cancelled"}, 90)
        pages = [e for e in evs if e.get("event") == "page"]
        ok("批量爬取执行", len(pages) >= 1, f"{len(pages)} pages")

        # ── 自主 Agent 实跑 ──
        r = await c.post(BASE + "/api/agent", json={
            "goal": "总结 example.com 首页的内容与用途",
            "seeds": ["https://example.com"],
            "max_pages": 3, "max_depth": 1,
        })
        ok("Agent 启动", r.status_code == 200, r.text[:80] if r.status_code != 200 else "")
        run_id = r.json().get("run_id", "")
        evs = await read_sse(c, f"/api/agent/{run_id}/stream", {"finish", "error"}, 240)
        finish = next((e for e in evs if e.get("type") == "finish"), None)
        thoughts = [e for e in evs if e.get("type") == "thought"]
        actions = [e for e in evs if e.get("type") == "action"]
        ok("Agent tool-calling 循环", len(actions) >= 1, f"{len(thoughts)} thoughts / {len(actions)} actions")
        ok("Agent 完成+报告", bool(finish and finish.get("report")), f"status={finish.get('status') if finish else 'none'} report={len(finish.get('report', '')) if finish else 0} chars")
        ok("Agent token 用量透出", bool(finish and finish.get("usage", {}).get("total_tokens")), str(finish.get("usage", {}).get("total_tokens")) if finish else "")

        # ── 历史回放 ──
        r = await c.get(BASE + f"/api/agent/{run_id}/events")
        j = r.json()
        ok("事件回放", j.get("finished") and len(j.get("events", [])) > 0, f"{len(j.get('events', []))} events")
        r = await c.get(BASE + "/api/agent")
        ok("运行记录落库", any(x.get("run_id") == run_id for x in r.json().get("runs", [])))

        # ── 流式问答 + 多轮 ──
        r = await c.post(BASE + "/api/query/stream", json={"question": "example.com 这个页面是做什么用的？"})
        sources, deltas, mode = [], [], ""
        async for line in r.aiter_lines():
            if not line.startswith("data: "):
                continue
            p = line[6:]
            if p == "[DONE]":
                break
            ev = json.loads(p)
            if ev["type"] == "sources":
                sources = ev.get("sources", [])
            elif ev["type"] == "delta":
                deltas.append(ev["text"])
            elif ev["type"] == "done":
                mode = ev.get("mode", "")
        answer = "".join(deltas)
        ok("RAG 流式问答命中", mode == "rag" and len(sources) > 0 and len(answer) > 20, f"mode={mode} sources={len(sources)} answer={len(answer)} chars")
        r = await c.post(BASE + "/api/query/stream", json={"question": "它背后是哪个组织？"})
        text2 = []
        async for line in r.aiter_lines():
            if line.startswith("data: ") and line[6:] != "[DONE]":
                ev = json.loads(line[6:])
                if ev["type"] == "delta":
                    text2.append(ev["text"])
        ok("多轮追问", len("".join(text2)) > 10, f"{len(''.join(text2))} chars")
        r = await c.get(BASE + "/api/query/history")
        ok("问答历史落库", r.json().get("count", 0) >= 4, f"count={r.json().get('count')}")

        # ── 数据浏览 + 导出 ──
        r = await c.get(BASE + "/api/data", params={"page": 1, "page_size": 5})
        ok("数据列表", r.json().get("total", 0) > 0, f"total={r.json().get('total')}")
        r = await c.get(BASE + "/api/data/export", params={"format": "csv"})
        ok("CSV 导出", r.status_code == 200 and "url" in r.text[:200], f"{len(r.text)} bytes")
        r = await c.get(BASE + "/api/data/export", params={"format": "json"})
        ok("JSON 导出", r.status_code == 200 and isinstance(r.json(), list))

        # ── 监控 / 图谱 / 成本 / 变更 ──
        r = await c.get(BASE + "/api/monitor/stats")
        ok("监控统计", r.status_code == 200 and not r.json().get("degraded"))
        r = await c.get(BASE + "/api/monitor/graph")
        j = r.json()
        ok("爬取图谱", len(j["domains"]["nodes"]) > 0, f"{len(j['domains']['nodes'])} domains / {len(j['pages']['nodes'])} pages")
        r = await c.get(BASE + "/api/monitor/cost")
        j = r.json()
        ok("成本看板", j["total"]["total_tokens"] > 0, f"¥{j['estimated_cost']} / {j['total']['total_tokens']} tokens")
        r = await c.get(BASE + "/api/monitor/changes")
        ok("变更列表端点", r.status_code == 200)
        r = await c.get(BASE + "/api/monitor/timeseries")
        ok("时间序列端点", r.status_code == 200)

        # ── 定时采集：创建→立即运行→状态→删除 ──
        r = await c.post(BASE + "/api/schedules", json={
            "name": "e2e 检验任务", "seeds": ["https://example.com"], "interval_minutes": 1440, "max_pages": 1,
        })
        ok("定时任务创建", r.status_code == 200, r.text[:80] if r.status_code != 200 else "")
        sid = r.json().get("id", "")
        r = await c.post(BASE + f"/api/schedules/{sid}/run")
        ok("定时任务触发", r.status_code == 200)
        last = ""
        for _ in range(60):
            await asyncio.sleep(2)
            r = await c.get(BASE + "/api/schedules")
            doc = next((x for x in r.json()["schedules"] if x["id"] == sid), None)
            last = (doc or {}).get("last_status", "")
            if last:
                break
        ok("定时任务执行完成", last == "completed", f"last_status={last}")
        r = await c.delete(BASE + f"/api/schedules/{sid}")
        ok("定时任务删除", r.status_code == 200)

        # ── 取消链路 ──
        r = await c.post(BASE + "/api/crawl/batch", json={
            "seeds": ["https://www.solidot.org"], "max_depth": 1, "max_pages": 12,
        })
        ctid = r.json().get("task_id", "")
        await asyncio.sleep(2)
        r = await c.post(BASE + f"/api/crawl/batch/{ctid}/cancel")
        ok("批量取消请求", r.status_code == 200)
        evs = await read_sse(c, f"/api/crawl/batch/{ctid}/stream", {"cancelled", "done", "error"}, 90)
        ok("批量取消生效", any(e.get("event") == "cancelled" for e in evs))

    failed = [n for n, c_, _ in RESULTS if not c_]
    print(f"\n{'✅ 全部通过' if not failed else '❌ 失败项: ' + ', '.join(failed)}  ({len(RESULTS) - len(failed)}/{len(RESULTS)})", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))