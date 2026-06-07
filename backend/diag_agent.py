"""
Agent 诊断脚本 —— 单独跑通 Agent 链路，定位"启动 Agent 有问题"的根因。
用法：cd backend && python diag_agent.py
"""

import asyncio
import traceback


async def test_tools():
    print("=== 1. 测试 DeepSeek tool-calling（最关键）===")
    from nia.ai.llm_client import LLMClient

    llm = LLMClient()
    print(f"  provider={llm._provider.value}  model={llm._model}  base={llm._base_url}")
    print(f"  api_key 是否配置: {'是' if llm._api_key and llm._api_key != 'your-deepseek-api-key' else '❌ 否/默认值'}")
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }]
    try:
        msg = await llm.achat_tools(
            [{"role": "user", "content": "北京今天天气怎么样？请调用工具查询。"}],
            tools=tools,
        )
        print("  返回 message 字段:", list(msg.keys()))
        print("  content:", str(msg.get("content"))[:120])
        tcs = msg.get("tool_calls")
        if tcs:
            print(f"  ✅ tool-calling 正常，返回 {len(tcs)} 个 tool_call:", tcs[0]["function"])
        else:
            print("  ⚠️ 未返回 tool_calls（模型没调用工具）")
    except Exception as e:
        print("  ❌ tool-calling 失败:", repr(e))
        traceback.print_exc()
    finally:
        await llm.aclose()


async def test_fetch():
    print("\n=== 2. 测试异步抓取 ===")
    from nia.crawler.fetcher import AsyncFetcher
    from nia.crawler.models import CrawlConfig

    try:
        async with AsyncFetcher(CrawlConfig()) as f:
            r = await f.fetch("https://example.com")
            print(f"  example.com → success={r.success} status={r.status_code} html={len(r.html)} 字节")
            print("  ✅ 抓取正常" if r.success else "  ❌ 抓取失败: " + r.error)
    except Exception as e:
        print("  ❌ 抓取异常:", repr(e))
        traceback.print_exc()


async def test_agent():
    print("\n=== 3. 跑一个迷你 Agent（example.com）===")
    from nia.agent.agent import AutonomousCrawlAgent
    from nia.agent.state import AgentState
    from nia.crawler.models import CrawlConfig

    st = AgentState(run_id="diag", goal="抓取 example.com 首页并总结它讲了什么", seeds=["https://example.com"])
    st.budget_pages = 3
    st.budget_steps = 5
    agent = AutonomousCrawlAgent(st, CrawlConfig(max_depth=1, max_pages=3))
    try:
        async for ev in agent.run():
            data = {k: v for k, v in ev.data.items() if k != "report"}
            line = str(data)
            print(f"  [{ev.type:11}]", line[:180])
            if ev.type == "finish":
                print("\n  ── 报告 ──\n" + (ev.data.get("report", "")[:500] or "(空)"))
        print(f"\n  ✅ Agent 结束，status={st.status}，findings={len(st.findings)}")
    except Exception as e:
        print("  ❌ Agent 异常:", repr(e))
        traceback.print_exc()


async def main():
    await test_tools()
    await test_fetch()
    await test_agent()


if __name__ == "__main__":
    asyncio.run(main())
