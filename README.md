# Nexus Intelligence Agent (NIA)

[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=white)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.4-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?style=flat&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7-47A248?style=flat&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![ECharts](https://img.shields.io/badge/ECharts-5.5-AA344D?style=flat&logo=apacheecharts&logoColor=white)](https://echarts.apache.org/)
[![Zustand](https://img.shields.io/badge/Zustand-5.0-333?style=flat)](https://zustand-demo.pmnd.rs/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=flat&logo=node.js&logoColor=white)](https://nodejs.org/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3-4D6BFE?style=flat)](https://platform.deepseek.com/)

下一代智能网络爬虫与情报分析系统 —— 基于 DeepSeek 的**自主爬取 Agent** + 并发爬取引擎，精简到只需 Redis + MongoDB。

## 核心特性

- **🤖 自主爬取 Agent** - 给定目标与种子 URL，Agent 用原生 tool-calling 自主规划爬哪些页、跟随链接、判断何时停止、提取并汇总成报告，全程 SSE 实时流式可视化（对标 Firecrawl / browser-use）
- **⚡ 并发爬取引擎** - 异步抓取 + 共享连接池 + 信号量限流 + 退避重试 + 缓存；支持批量 URL 与整站 BFS（相比旧串行实现数量级提速）
- **多 Provider LLM 支持** - DeepSeek / OpenAI / Qwen / Ollama，一处配置，处处可用；async + tool-calling + 流式
- **采集与分析一体化** - 内置 RAG 语义检索和自然语言问答
- **🪶 精简基础设施** - Embedding 走本地 fastembed（ONNX/CPU，无需 Ollama），向量库用本地 FAISS（无需 Docker/Qdrant），只依赖 Redis + MongoDB
- **🎨 高级感前端** - React + TypeScript + shadcn 风格组件 + Linear/Vercel 近无彩黑白灰设计 + 明暗双主题（默认暗色）+ ECharts

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | React 18 + TypeScript + Vite | 现代化 SPA 应用 |
| 前端样式 | Tailwind CSS + shadcn 风格组件 | Linear 风近无彩设计 token + 明暗双主题 |
| 图表 | ECharts | 监控数据可视化（适配暗色） |
| 状态管理 | Zustand (persist) | 轻量级响应式状态 + 主题持久化 |
| 路由 | React Router v7 | 客户端路由 |
| 通知/数据 | sonner + TanStack Query | 全局通知 + 服务端状态 |
| 后端 API | FastAPI | Python 异步 Web 框架 |
| 爬取引擎 | httpx (async) + asyncio | 并发抓取 + 连接池 + 信号量 + 重试 |
| Agent | 原生 tool-calling（OpenAI 兼容） | 自主多步爬取，无需 LangChain/LangGraph |
| JS 渲染 | Crawl4AI（可选） | 异步浏览器池，按需启动 |
| 主力 LLM | DeepSeek-V3 | 便宜、中文强、JSON 输出稳定 |
| Embedding | fastembed (本地 ONNX) | 默认 `BAAI/bge-small-zh-v1.5`（512 维，约 90MB），CPU 即可，无需 Ollama |
| 缓存/锁 | Redis | 提取缓存 / SSE |
| 数据库 | MongoDB | 任务状态、聊天记录、Agent 运行 |
| 向量存储 | FAISS (本地) | 语义检索向量索引 |

## 环境要求

- Node.js 18+
- Python 3.11+
- Redis 7+（默认端口 **6379**，需自行启动）
- MongoDB 7+（默认端口 **27017**，需自行启动）

> 无需 Qdrant、Ollama、Docker。
>
> MongoDB 未启动时服务仍能启动，但爬取结果与问答历史无法持久化，`GET /api/monitor/stats` 会返回 `degraded: true`。

## 项目结构

```
Nexus Intelligence Agent/
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── api/client.ts             # API 客户端 (REST + SSE)
│   │   ├── components/
│   │   │   ├── Layout.tsx            # 侧边栏 + 暗色切换
│   │   │   ├── ErrorBoundary.tsx     # 错误边界
│   │   │   └── ui/                   # shadcn 风格组件 (Button/Card/Input/Badge/Skeleton/EmptyState)
│   │   ├── pages/
│   │   │   ├── AgentPage.tsx         # 🤖 自主 Agent 控制台 (首页, 核心)
│   │   │   ├── CrawlPage.tsx         # 批量 / 整站爬取 (SSE 实时进度)
│   │   │   ├── QueryPage.tsx         # 语义问答 (Markdown 答案)
│   │   │   ├── DataPage.tsx          # 数据浏览
│   │   │   ├── MonitorPage.tsx       # 任务监控 (ECharts, 适配暗色)
│   │   │   └── SettingsPage.tsx      # 系统设置
│   │   ├── lib/utils.ts              # cn() 等工具
│   │   ├── store/index.ts            # Zustand (含主题持久化)
│   │   ├── types/index.ts            # TypeScript 类型定义
│   │   ├── App.tsx                   # 路由 + 错误边界
│   │   ├── main.tsx                  # 入口 (QueryClient + Toaster + 主题)
│   │   └── index.css                 # 设计 token + 全局样式
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── backend/                          # Python 后端
│   ├── nia/
│   │   ├── api/                      # FastAPI 后端 API
│   │   │   ├── app.py                # 主应用 (CORS + 路由 + lifespan)
│   │   │   ├── agent.py              # 🤖 自主 Agent API (启动 / SSE / 取消)
│   │   │   ├── crawl.py              # 单 URL + 批量/整站爬取 API
│   │   │   ├── query.py              # 问答 API
│   │   │   ├── data.py / monitor.py / settings.py
│   │   │   ├── ── 以下为业务模块 ──
│   │   ├── agent/                    # 🤖 自主爬取 Agent
│   │   │   ├── agent.py              # tool-calling 主循环 (async generator)
│   │   │   ├── tools.py              # 工具集 + 预算拦截
│   │   │   ├── state.py / events.py / prompts.py
│   │   ├── crawler/                  # ⚡ 并发爬取引擎
│   │   │   ├── engine.py             # BFS 整站 / 批量编排
│   │   │   ├── fetcher.py            # 共享 AsyncClient + 信号量 + 重试
│   │   │   ├── frontier.py           # BFS 队列 + 去重 + 预算
│   │   │   ├── parser.py / cache.py / extractor.py / browser_pool.py / models.py
│   │   │   └── robots.py             # robots.txt 解析与遵守策略
│   │   ├── ai/                       # llm_client.py (同步 + async + tool-calling + 流式)
│   │   ├── rag/
│   │   │   ├── embedding.py          # 嵌入管理器 (fastembed 本地 ONNX)
│   │   │   ├── vector_store.py       # 向量存储 (FAISS)
│   │   │   └── rag_engine.py         # RAG 引擎
│   │   ├── storage/                  # database.py (MongoDB) + models.py
│   │   ├── captcha/                  # 验证码识别 (ddddocr, 可选)
│   │   ├── monitoring/               # 监控报告
│   │   └── utils/                    # config.py / url_safety.py / timeutil.py
│   ├── requirements.txt              # Python 依赖
│   ├── verify.py                     # 后端自检脚本
│   └── .env.example                  # 环境变量模板
│
├── README.md                         # 项目说明
└── 运行步骤.md                        # 运行指南
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/agent | 启动自主爬取 Agent（目标 + 种子 URL + 预算） |
| GET | /api/agent/{run_id}/stream | SSE 实时 Agent 事件流（思考/动作/观察/发现/报告） |
| POST | /api/agent/{run_id}/cancel | 取消 Agent（协作式收尾） |
| GET | /api/agent | 最近的 Agent 运行记录 |
| POST | /api/crawl | 提交单 URL 爬取任务（异步） |
| POST | /api/crawl/batch | 并发批量 / 整站爬取 |
| GET | /api/crawl/batch/{task_id}/stream | SSE 批量爬取进度 |
| POST | /api/crawl/batch/{task_id}/cancel | 取消正在运行的批量爬取（SSE 收到 `{"event": "cancelled"}` 并以 `cancelled` 状态结束） |
| GET | /api/crawl/{task_id}/progress | SSE 单任务进度推送 |
| GET | /api/crawl/results | 获取爬取结果列表（此前被 `/{task_id}` 路由遮蔽恒 404，现已修复） |
| DELETE | /api/crawl/{task_id} | 删除任务 |
| POST | /api/query | 语义问答 |
| GET | /api/query/history | 获取问答历史 |
| DELETE | /api/query/history | 清空聊天记录 |
| GET | /api/data | 分页浏览爬取数据（**不含** `raw_html`） |
| GET | /api/data/{data_id} | 单个爬取数据的完整文档（**含** `raw_html`） |
| GET | /api/monitor/stats | 任务统计指标 |
| GET | /api/monitor/domains?days_ago=N | 域名分布统计（按 `crawled_data` 聚合真实域名） |
| GET | /api/monitor/alert | 告警检查 |
| GET | /api/settings/config | 系统配置 |
| GET | /api/settings/status | 服务连接状态 |
| GET | /api/health | 存活探针，返回 `{status, version}`（不探测外部依赖） |
| GET | /api/ready | 就绪探针，返回 `{status, mongodb, redis}`，任一依赖不可用时 `status="degraded"` |

> **并发上限**：批量爬取与 Agent 都有并发上限（`MAX_CONCURRENT_CRAWLS`，默认 4），超出时返回 HTTP 429。
>
> **`GET /api/agent/{run_id}`**：查询单次 Agent 运行状态。

`GET /api/monitor/stats` 返回字段：`total_tasks`、`finished_tasks`、`success_rate`、`llm_calls`、`avg_llm_time_ms`、`avg_llm_time`（兼容旧字段）、`avg_crawl_time_ms`、`avg_llm_calls`、`queue_pending`、`dead_letter_count`、`error_summary`、`degraded`。

## MongoDB 集合

| 集合名 | 说明 | 索引 |
|--------|------|------|
| agent_runs | 自主 Agent 运行记录 | run_id (unique), created_at |
| crawled_data | 爬取数据 | url, domain, created_at |
| crawl_tasks | 任务状态 | task_id (unique), status, created_at |
| chat_history | 聊天记录 | created_at, role |
| websites | 网站信息 | domain |
| extraction_rules | 提取规则 (XPath/CSS) | website_id |
| vector_data | 向量元数据 | crawled_data_id |
| task_logs | 任务日志 | url, domain, created_at |

## 快速开始

### 1. 注册 DeepSeek API

前往 [DeepSeek Platform](https://platform.deepseek.com/) 注册并获取 API Key。

### 2. 向量存储

默认使用本地 FAISS，**无需安装任何额外服务**。

### 3. 安装 Redis

```bash
winget install Redis.Redis
redis-server
```

### 4. 安装 MongoDB

```bash
winget install MongoDB.Server
mongod --dbpath D:\MongoDB\data
```

### 5. Embedding 模型

默认使用 fastembed（本地 ONNX，CPU 即可，无需 Ollama），默认模型 `BAAI/bge-small-zh-v1.5`（**512 维**，约 **90MB**）。首次使用需**联网下载** ONNX 模型，之后离线缓存可用。

模型缓存目录由 `FASTEMBED_CACHE_DIR` 控制，默认 `./data/fastembed`（相对 `backend/`）。**必须保持非空**，否则 fastembed 会改用临时目录、进程退出即删除，导致每次启动都重新下载。

> ⚠️ **fastembed 不支持 `BAAI/bge-m3`**（其内置模型列表中没有该 id）。想用 bge-m3 只能改走 `EMBED_PROVIDER=bge-m3`（需本地 Ollama + `pip install langchain-ollama`，可选功能）。
>
> 🌐 **国内网络**访问 `huggingface.co` 超时/失败时：设置 `HF_ENDPOINT=https://hf-mirror.com`；或手动下载模型后把 `EMBED_MODEL` 直接指向本地模型目录（例如 `EMBED_MODEL=./data/fastembed/bge-small-zh-v1.5`），此时可完全离线运行。

### 6. 安装 Python 依赖

在项目根目录的 `backend` 目录下执行：

```bash
pip install -r requirements.txt
```

### 7. 安装 Node.js 依赖

在项目根目录的 `frontend` 目录下执行：

```bash
npm install
```

### 8. 配置环境变量

环境变量模板位于 **`backend/.env.example`**（不在项目根目录）。在 `backend` 目录下复制为 `backend/.env`：

```bash
copy .env.example .env
```

编辑 `backend/.env`，只需填入你的 DeepSeek API Key：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-deepseek-api-key
```

### 9. 初始化数据库

在 `backend` 目录下执行：

```bash
python -c "from nia.storage.database import DatabaseManager; db = DatabaseManager(); db.init_db(); print('OK')"
```

### 10. 启动

确保 Redis 与 MongoDB 已在运行（Redis 默认 `6379`，MongoDB 默认 `27017`），然后：

```bash
# 终端1: 在 backend 目录下启动后端 API（单进程；用 JS 渲染时不要加 --reload）
uvicorn nia.api.app:app --host 0.0.0.0 --port 8000

# 终端2: 在 frontend 目录下启动前端
npm run dev
```

浏览器访问 http://localhost:5173 ，首页即「🤖 自主 Agent」控制台。

> ⚠️ **必须单进程运行**（默认即 `workers=1`，不要加 `--workers`）：任务与事件状态保存在进程内存中，多 worker 会导致状态串台。
> ⚠️ 用 JS 渲染时不要加 `--reload`（reloader 会反复重启浏览器）。

> 💡 启动前可先运行 `python verify.py` 做后端自检。它会检查语法 / 模块导入 / 依赖 / Embedding 维度配置 / RAG 真实冒烟测试（向量化 → FAISS 插入 → 检索）/ Redis、MongoDB 连通性；退出码 `0` = 可启动，`1` = 存在阻断性问题。模型因网络下载失败只报警告（属环境问题），MongoDB 未启动也只警告。

## 可选：API 鉴权

默认不鉴权（仅建议本机使用）。设置环境变量 `API_AUTH_TOKEN` 后，所有 `/api/*` 请求必须携带请求头 `X-API-Token: <值>`，否则返回 401（`/api/health` 除外）：

```env
API_AUTH_TOKEN=your-random-token
```

前端通过 `VITE_API_TOKEN` 传入同一个值；前端后端地址可用 `VITE_API_BASE_URL` 覆盖（默认 `/api`，开发时由 Vite 代理到 `:8000`）。

## Docker 部署

```bash
docker compose up --build
```

会启动 **redis + mongodb + api** 三个服务。api 容器用 `STATIC_DIR=/app/static` 把前端构建产物作为 SPA 挂在 8000 端口（前端路由回落到 `index.html`），因此生产环境只需访问 **http://localhost:8000**。embedding 模型缓存与 FAISS 索引持久化在 `app_data` 卷（容器内 `/app/data`）。仓库已包含 `.dockerignore`（会排除 `backend/.env`，避免真实 API Key 被打进镜像层）；compose 中已移除 qdrant 服务（v2 默认 FAISS，不再需要）。

## 更新日志

### 2026-06-07 — v2.1 维护与修复

- **路由修复**：`GET /api/crawl/results` 此前被 `/{task_id}` 动态路由遮蔽、恒定 404，现已在路由顺序上修正
- **监控统计修复**：`GET /api/monitor/stats` 返回字段补全（`finished_tasks`、`avg_crawl_time_ms`、`avg_llm_calls`、`queue_pending`、`dead_letter_count`、`error_summary`、`degraded`，并保留旧字段 `avg_llm_time`）；`GET /api/monitor/domains` 改为按 `crawled_data` 聚合真实域名分布
- **批量取消**：新增 `POST /api/crawl/batch/{task_id}/cancel`，SSE 收到 `{"event": "cancelled"}` 并以 `cancelled` 状态结束
- **并发上限**：批量爬取与 Agent 均受 `MAX_CONCURRENT_CRAWLS`（默认 4）限制，超限返回 HTTP 429
- **SPA 静态托管**：Docker 中 `STATIC_DIR=/app/static`，前端构建产物作为 SPA 挂在 8000 端口，生产环境只需访问 `http://localhost:8000`
- **可选鉴权**：设置 `API_AUTH_TOKEN` 后 `/api/*` 需带 `X-API-Token` 请求头
- **数据接口细化**：新增 `GET /api/data/{data_id}` 返回含 `raw_html` 的完整文档；`GET /api/data` 列表不再返回 `raw_html`
- **文档对齐**：本 README 与《运行步骤.md》按当前代码与 `.env.example` 默认值全面校正

### 2026-06-07 — UI 高级化改版

- **设计语言**：切换为 Linear/Vercel 风**近无彩黑白灰**——近黑背景 + 顶部柔光晕、1px 细边框分层、收紧字距；主按钮在暗色为近白、浅色为近黑
- **默认暗色主题**，明暗一键切换并持久化
- **交互**：按钮加入按压物理感（按下回缩 + 悬停微浮 + 辉光）；启动按钮即时 loading 反馈
- **稳定性修复**：`<html lang>` 改 `zh-CN` + `notranslate`，并去掉流式列表的 framer-motion，根治网页翻译/动画引发的 React `insertBefore` 报错

### 2026-06-07 — v2.0 激进重构

**核心**

- **🤖 新增自主爬取 Agent**：原生 tool-calling（OpenAI 兼容，DeepSeek）多步循环，给定目标自主规划爬取、跟随链接、判断停止、提取汇总；全程 SSE 实时事件流（思考/动作/观察/发现/报告）。`backend/nia/agent/` + `POST /api/agent`
- **⚡ 并发爬取引擎** `backend/nia/crawler/`：共享 `httpx.AsyncClient` + 信号量限流 + 退避重试 + Redis 缓存 + BFS frontier；支持批量 URL 与整站爬取（`POST /api/crawl/batch`），相比旧串行实现数量级提速
- **LLMClient 升级**：新增 async / 原生 tool-calling / 退避重试 / 流式，保留同步接口

**精简基础设施**

- Embedding：Ollama bge-m3 → **本地 fastembed**（ONNX/CPU，无需 Ollama）
- 向量库：Qdrant → **本地 FAISS**（无需 Docker）
- 只依赖 **Redis + MongoDB**；依赖大幅瘦身（移除 scrapy / scrapy-redis / qdrant-client / langchain-ollama）
- 删除死代码：`pipelines.py`、`rule_learner.py`（伪规则学习）、`extraction_pipeline.py`、`spiders/`、`scheduler/` 等

**前端翻新**

- 设计系统：HSL 设计 token + **明暗双主题**（持久化）+ shadcn 风格组件库（`components/ui/`）
- 新增 **Agent 控制台页**（首页）：实时活动时间线 + 发现侧栏 + 预算进度 + Markdown 报告
- 翻新 5 页：批量/整站爬取、Markdown 问答、可搜索数据表、暗色图表监控、设置
- 接入 framer-motion（动画）、sonner（通知）、TanStack Query、react-markdown

**修复**

- 修复 `crawl.py` SSE 首屏 `_tasks[task]` 拼写 bug；修复 `chunk_text` 潜在死循环

### 2026-06-06 — v1 全面重构（历史）

- 异步爬取 + SSE 实时进度；聊天记录存 MongoDB；URL 安全校验防 SSRF
- 前端：Recharts → ECharts，赛博朋克暗色 → 明亮主题，新增错误边界
