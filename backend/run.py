"""Windows 安全启动入口。

Windows 默认 Proactor(IOCP) 事件循环在 SSE 客户端提前断开时，
会因 overlapped future 重复置异常抛 InvalidStateError 直接 crash 整个进程
（前端完成/卸载即关闭 SSE，演示必踩）。Selector 循环无此问题。

用法：cd backend && python run.py
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("nia.api.app:app", host="127.0.0.1", port=8000)