"""
后端自检脚本 —— 验证语法、导入、依赖与关键链路（含 RAG 真实冒烟测试）。

用法：cd backend && python verify.py
退出码：0 = 通过，1 = 存在阻断性问题。
"""

import ast
import glob
import importlib
import os
import pathlib
import sys

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

FAILURES: list[str] = []
WARNINGS: list[str] = []


def _fail(msg: str) -> None:
    FAILURES.append(msg)


def _warn(msg: str) -> None:
    WARNINGS.append(msg)


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
    if bad:
        _fail("语法检查未通过")
    return bad == 0


def check_imports() -> bool:
    # 覆盖全部子包：以前这里不导入 nia.rag.* / nia.monitoring.*，
    # 结果是 RAG 完全坏掉、自检依然“通过”。
    mods = [
        "nia.utils.config",
        "nia.utils.timeutil",
        "nia.utils.url_safety",
        "nia.ai.llm_client",
        "nia.crawler",
        "nia.crawler.engine",
        "nia.crawler.fetcher",
        "nia.crawler.robots",
        "nia.crawler.cache",
        "nia.crawler.extractor",
        "nia.rag.embedding",
        "nia.rag.vector_store",
        "nia.rag.rag_engine",
        "nia.monitoring.report",
        "nia.agent",
        "nia.agent.agent",
        "nia.agent.tools",
        "nia.api.app",
        "nia.api.agent",
        "nia.api.crawl",
        "nia.api.query",
        "nia.api.data",
        "nia.api.monitor",
        "nia.api.settings",
    ]
    ok = True
    for m in mods:
        try:
            importlib.import_module(m)
            print(f"{GREEN}OK{RESET}  import {m}")
        except Exception as e:
            ok = False
            print(f"{RED}FAIL{RESET} import {m} -> {type(e).__name__}: {e}")
            _fail(f"import {m} 失败: {type(e).__name__}: {e}")
    return ok


def check_dependencies() -> None:
    """必需/可选依赖检查（必需项缺失会导致 RAG 或解析不可用）。"""
    required = [
        ("fastembed", "本地 Embedding（RAG 索引/问答）", "pip install fastembed"),
        ("faiss", "向量存储", "pip install faiss-cpu"),
        ("numpy", "向量运算", "pip install numpy"),
        ("lxml", "HTML 解析", "pip install lxml"),
        ("cssselect", "HTML 解析（lxml.cssselect）", "pip install cssselect"),
        ("httpx", "抓取 + LLM 调用", "pip install httpx"),
        ("sqlalchemy", "MySQL 数据库工具", "pip install SQLAlchemy PyMySQL"),
        ("pymysql", "MySQL 驱动", "pip install PyMySQL"),
        ("redis", "Redis 驱动", "pip install redis"),
    ]
    for name, hint, fix in required:
        try:
            importlib.import_module(name)
            print(f"{GREEN}OK{RESET}  {name:12} {DIM}{hint}{RESET}")
        except Exception:
            print(f"{RED}缺失{RESET} {name:12} {DIM}{hint} → {fix}{RESET}")
            _fail(f"必需依赖缺失: {name}（{fix}）")

    optional = [
        ("crawl4ai", "JS 渲染（可选，还需 playwright install chromium）", "pip install crawl4ai"),
        ("ddddocr", "验证码识别（可选）", "pip install ddddocr"),
    ]
    for name, hint, fix in optional:
        try:
            importlib.import_module(name)
            print(f"{GREEN}OK{RESET}  {name:12} {DIM}{hint}{RESET}")
        except Exception:
            print(f"{YELLOW}可选{RESET} {name:12} {DIM}{hint} → {fix}{RESET}")
            _warn(f"可选依赖未安装: {name}")


def check_embed_config() -> bool:
    """校验 EMBED_MODEL 是否真的是 fastembed 支持的模型，并核对向量维度。"""
    from nia.utils.config import Config

    if Config.EMBED_PROVIDER != "fastembed":
        print(f"{DIM}跳过（EMBED_PROVIDER={Config.EMBED_PROVIDER}）{RESET}")
        return True

    try:
        from fastembed import TextEmbedding

        supported = {m["model"] for m in TextEmbedding.list_supported_models()}
    except Exception as e:
        print(f"{RED}FAIL{RESET} 无法列出 fastembed 支持的模型 -> {e}")
        _fail(f"fastembed 不可用: {e}")
        return False

    # 允许直接指向本地已下载的模型目录（离线 / 内网环境）
    if os.path.isdir(Config.EMBED_MODEL):
        print(f"{GREEN}OK{RESET}  EMBED_MODEL={Config.EMBED_MODEL} {DIM}(本地模型目录, dim={Config.EMBED_DIM}){RESET}")
        return True

    if Config.EMBED_MODEL not in supported:
        print(f"{RED}FAIL{RESET} EMBED_MODEL={Config.EMBED_MODEL} 不在 fastembed 支持列表中")
        print(f"{DIM}    可用示例: {', '.join(sorted(supported)[:6])} …{RESET}")
        _fail(f"EMBED_MODEL={Config.EMBED_MODEL} 不是合法的 fastembed 模型 id")
        return False

    dims = {m["model"]: m.get("dim") for m in TextEmbedding.list_supported_models()}
    real_dim = dims.get(Config.EMBED_MODEL)
    print(f"{GREEN}OK{RESET}  EMBED_MODEL={Config.EMBED_MODEL} {DIM}(dim={real_dim}){RESET}")
    if real_dim and int(real_dim) != int(Config.EMBED_DIM):
        print(
            f"{RED}FAIL{RESET} EMBED_DIM={Config.EMBED_DIM} 与模型实际维度 {real_dim} 不一致"
        )
        _fail(f"EMBED_DIM={Config.EMBED_DIM} 与 {Config.EMBED_MODEL} 的 {real_dim} 维不匹配")
        return False
    return True


def check_rag_pipeline() -> bool:
    """RAG 冒烟测试：加载模型 → 向量化 → 插入 → 检索（不需要 Redis/MySQL）。"""
    tmpdir = None
    try:
        import shutil
        import tempfile

        from nia.rag.embedding import EmbeddingManager
        from nia.rag.vector_store import FAISSVectorStore

        embedder = EmbeddingManager()
        texts = [
            "Nexus Intelligence Agent 是一个智能网络爬虫与情报分析系统。",
            "它使用本地 fastembed 做向量化，用 FAISS 做向量检索。",
            "后端框架是 FastAPI，前端是 React + Vite。",
        ]
        vectors = embedder.embed_texts(texts)
        if len(vectors) != len(texts):
            print(f"{RED}FAIL{RESET} 向量数量 {len(vectors)} != 文本数量 {len(texts)}")
            _fail("EmbeddingManager.embed_texts 返回数量不正确")
            return False

        # 用临时目录，避免把自检数据写进真实索引
        tmpdir = tempfile.mkdtemp(prefix="nia_verify_")
        store = FAISSVectorStore(embedding_dim=len(vectors[0]))
        store._index_dir = tmpdir
        store._index_path = os.path.join(tmpdir, "index.faiss")
        store._metadata_path = os.path.join(tmpdir, "metadata.json")
        store.add_vectors("verify", texts, vectors, url="verify://local", title="verify")

        hits = store.similarity_search(embedder.embed_text("用什么做向量检索？"), top_k=2)
        if not hits:
            print(f"{RED}FAIL{RESET} 检索没有返回任何结果")
            _fail("FAISSVectorStore.similarity_search 返回空")
            return False
        print(
            f"{GREEN}OK{RESET}  RAG 冒烟测试 {DIM}({len(texts)} chunks → {len(hits)} hits){RESET}"
        )
        return True
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        # 模型下载受网络/权限限制属于环境问题，不应把整个自检判为失败
        env_markers = (
            "Could not download",
            "Could not load model",
            "from any source",
            "WinError 1314",
            "ReadTimeout",
            "ConnectTimeout",
            "ConnectionError",
            "Max retries exceeded",
            "ProxyError",
        )
        if any(m in msg for m in env_markers):
            try:
                cache_dir = __import__("nia.utils.config", fromlist=["Config"]).Config.FASTEMBED_CACHE_DIR
            except Exception:
                cache_dir = ""
            print(f"{YELLOW}WARN{RESET} RAG 冒烟测试跳过（模型不可用）-> {msg}")
            _warn(
                "RAG 冒烟测试跳过：fastembed 模型未能加载。首次使用需联网下载 ONNX 模型；"
                "国内网络可设置 HF_ENDPOINT=https://hf-mirror.com，"
                "或手动下载模型后设置 EMBED_MODEL=<本地模型目录>。"
                f"缓存目录: {cache_dir}"
            )
            return True
        print(f"{RED}FAIL{RESET} RAG 冒烟测试 -> {msg}")
        _fail(f"RAG 冒烟测试失败: {msg}")
        return False
    finally:
        if tmpdir:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def check_infra() -> None:
    """MySQL / Redis 连通性（不阻断启动，但会给出明确警告）。"""
    import asyncio

    from nia.storage.database import DatabaseManager
    from nia.utils.config import Config

    try:
        db = DatabaseManager()
        db.connect()
        db.ping()
        print(f"{GREEN}OK{RESET}  MySQL {DIM}{Config.MYSQL_URL}{RESET}")
        try:
            db.init_db()
        finally:
            db.close()
    except Exception as e:
        print(f"{YELLOW}警告{RESET} MySQL 不可用 -> {type(e).__name__}: {str(e)[:120]}")
        print(f"{DIM}    爬取结果与问答历史无法持久化；请检查 MySQL 服务与 MYSQL_URL{RESET}")
        _warn("MySQL 不可用")

    try:
        import redis as redis_lib

        client = redis_lib.from_url(
            Config.REDIS_URL, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        try:
            client.ping()
            print(f"{GREEN}OK{RESET}  Redis {DIM}{Config.REDIS_URL}{RESET}")
        finally:
            client.close()
    except Exception as e:
        print(f"{YELLOW}警告{RESET} Redis 不可用 -> {type(e).__name__}: {str(e)[:120]}")
        _warn("Redis 不可用（缓存/进度广播降级为内存模式）")


if __name__ == "__main__":
    print("── 1. 语法 ──")
    check_syntax()
    print("\n── 2. 模块导入 ──")
    check_imports()
    print("\n── 3. 依赖 ──")
    check_dependencies()
    print("\n── 4. Embedding 配置 ──")
    check_embed_config()
    print("\n── 5. RAG 冒烟测试 ──")
    check_rag_pipeline()
    print("\n── 6. 基础设施连通性 ──")
    check_infra()
    print()

    if WARNINGS:
        print(f"{YELLOW}⚠️  警告 {len(WARNINGS)} 项：{'; '.join(WARNINGS)}{RESET}")

    if FAILURES:
        print(f"{RED}❌ 自检未通过（{len(FAILURES)} 项失败）：{RESET}")
        for f in FAILURES:
            print(f"{RED}   - {f}{RESET}")
        sys.exit(1)

    print(f"{GREEN}✅ 后端自检通过，可启动：uvicorn nia.api.app:app --port 8000{RESET}")
    sys.exit(0)
