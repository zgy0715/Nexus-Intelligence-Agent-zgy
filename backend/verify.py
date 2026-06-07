"""
后端自检脚本 —— 验证语法、导入与关键模块可用性。
用法：cd backend && python verify.py
"""

import ast
import glob
import importlib
import pathlib
import sys

GREEN, RED, DIM, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[0m"


def check_syntax() -> bool:
    files = glob.glob("nia/**/*.py", recursive=True)
    bad = 0
    for f in files:
        try:
            ast.parse(pathlib.Path(f).read_text(encoding="utf-8-sig"))  # utf-8-sig 兼容 BOM
        except SyntaxError as e:
            bad += 1
            print(f"{RED}SYNTAX ERROR{RESET} {f} -> {e}")
    print(f"{'✅' if bad == 0 else '❌'} 语法检查：{len(files)} 个文件，{bad} 个错误")
    return bad == 0


def check_imports() -> bool:
    mods = [
        "nia.utils.config",
        "nia.utils.url_safety",
        "nia.ai.llm_client",
        "nia.crawler",
        "nia.crawler.engine",
        "nia.agent",
        "nia.agent.agent",
        "nia.api.app",
    ]
    ok = True
    for m in mods:
        try:
            importlib.import_module(m)
            print(f"{GREEN}OK{RESET}  import {m}")
        except Exception as e:
            ok = False
            print(f"{RED}FAIL{RESET} import {m} -> {type(e).__name__}: {e}")
    return ok


def check_optional() -> None:
    """可选依赖（缺失不致命，但功能受限）。"""
    for name, hint in [
        ("fastembed", "本地 Embedding（RAG 索引/问答）"),
        ("faiss", "向量存储"),
        ("crawl4ai", "JS 渲染（可选）"),
        ("cssselect", "HTML 解析"),
    ]:
        try:
            importlib.import_module(name)
            print(f"{GREEN}OK{RESET}  {name:12} {DIM}{hint}{RESET}")
        except Exception:
            print(f"{RED}缺失{RESET} {name:12} {DIM}{hint} → pip install {name}{RESET}")


if __name__ == "__main__":
    print("── 1. 语法 ──")
    s = check_syntax()
    print("\n── 2. 核心模块导入 ──")
    i = check_imports()
    print("\n── 3. 可选依赖 ──")
    check_optional()
    print()
    if s and i:
        print(f"{GREEN}✅ 后端自检通过，可启动：uvicorn nia.api.app:app --port 8000{RESET}")
        sys.exit(0)
    print(f"{RED}❌ 存在问题，请按上面的提示修复{RESET}")
    sys.exit(1)
