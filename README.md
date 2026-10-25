# Nexus Intelligence Agent (NIA)

[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=white)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?style=flat&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/Redis-5+-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?style=flat&logo=mysql&logoColor=white)](https://www.mysql.com/)
[![ECharts](https://img.shields.io/badge/ECharts-6-AA344D?style=flat&logo=apacheecharts&logoColor=white)](https://echarts.apache.org/)
[![Zustand](https://img.shields.io/badge/Zustand-5.0-333?style=flat)](https://zustand-demo.pmnd.rs/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=flat&logo=node.js&logoColor=white)](https://nodejs.org/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3-4D6BFE?style=flat)](https://platform.deepseek.com/)
[![Ollama](https://img.shields.io/badge/Ollama-辅助模型-000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

下一代智能网络爬虫与情报分析系统 —— 基于 DeepSeek 的**自主爬取 Agent** + 并发爬取引擎 + **混合检索 RAG**，精简到只需 Redis + MySQL（本地 Ollama 可选加速）。

## 核心特性

- **🤖 自主爬取 Agent v3** - 原生 tool-calling 多步循环：**上下文滚动压缩**（长任务不爆窗口）、同批工具**并行执行**、Pydantic 类型化工具注册表（schema 自动生成）、**领域记忆**（同站点经验注入）、token/成本实时仪表；全程 SSE 实时流式可视化，支持断线重连（Last-Event-ID）与**历史运行回放**
- **⚡ 并发爬取引擎 v3** - 异步抓取 + **trafilatura 正文密度提取**（导航/页脚噪声不再污染 LLM）+ 抓取与 LLM 提取**流水线重叠** + **HTML 磁盘缓存**（重复任务零网络请求）+ 锚文本目标相关性打分 + SSRF 纵深防御
- **🔀 混合检索 RAG** - BM25（jieba 分词）+ 向量双路召回 **RRF 融合** + **Ollama 查询改写**（本地模型，零 token 成本）+ 可选交叉编码重排（`RERANK_MODEL`）+ 流式问答（`POST /api/query/stream`）
- **🧠 模型路由** - 主模型（DeepSeek）只做推理/报告；后台杂事（摘要、查询改写）路由到**本地 Ollama 辅助模型**，不可用自动回退，功能不降级
- **🎨 前端 2026 技术栈** - React 19 + Vite 8 (Rolldown) + Tailwind CSS 4（CSS-first）+ ECharts 6 按需引入 + TanStack Query / react-virtual / motion；**首屏 bundle 1.49MB → 237KB（-84%）**；Ctrl+K 命令面板、明暗双主题、黑白灰精修 + 品牌靛蓝
- **🪶 精简基础设施** - Embedding 走本地 fastembed（ONNX/CPU），向量库用本地 FAISS（**IndexIDMap2**，O(1) 删除 + 一键重建），只依赖 Redis + MySQL

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | React 19 + TypeScript + Vite 8 | React 19（StrictMode 回归）+ Rolldown 构建 + 路由级代码分割 |
| 前端样式 | Tailwind CSS 4 + 自建组件库 | CSS-first 配置（@theme），黑白灰 + 品牌靛蓝强调色 |
| 图表 | ECharts 6（按需引入） | 统一 `<Chart>` 封装，颜色读 CSS token 随主题变色 |
| 数据层 | TanStack Query + react-virtual | 服务端状态 + 虚拟化时间线/表格 |
| 动效 | motion（原 framer-motion） | 时间线/面板过渡动画 |
| 路由 | React Router v7 | 客户端路由 + lazy 分包 |
| 后端 API | FastAPI | Python 异步 Web 框架 |
| 爬取引擎 | httpx (async) + trafilatura | 并发抓取 + 正文密度提取 + 流水线 + HTML 缓存 |
| Agent | 原生 tool-calling（OpenAI 兼容） | 上下文压缩 + 并行工具 + 类型化注册表 + 领域记忆 |
| 主力 LLM | DeepSeek-V3 | 推理 / 工具调用 / 报告 |
| 辅助模型 | Ollama（本地，可选） | 上下文摘要 / 查询改写；默认 `qwen3:8b`，不可用自动回退 |
| Embedding | fastembed (本地 ONNX) | 默认 `BAAI/bge-small-zh-v1.5`（512 维），CPU 即可 |
| 检索 | FAISS IndexIDMap2 + BM25(rank-bm25+jieba) | 双路召回 RRF 融合 + 可选 fastembed 交叉编码重排 |
| 缓存/事件 | Redis | 提取缓存 / **事件总线**（Agent 事件流持久化 + 断线续读） |
| 数据库 | MySQL 8 + SQLAlchemy | 任务状态、聊天记录、Agent 运行与抓取内容 |

## 环境要求

- Node.js 18+
- Python 3.11+
- Redis **5.0+**（默认端口 **6379**；事件总线的 Stream 需要 5.0+，3.x 老版会自动降级为纯内存模式并打警告）
- MySQL 8+（默认端口 **3306**）
- Ollama（**可选**，辅助模型；默认 `qwen3:8b`，未安装则相关后台任务自动回退主模型）

> 无需 Qdrant、Docker。
>
> MySQL 未启动时服务仍能启动，但爬取结果与问答历史无法持久化，`GET /api/monitor/stats` 会返回 `degraded: true`。

## 项目结构

```
Nexus Intelligence Agent/
├── README.md                         # 项目说明
├── 运行步骤.md                        # 运行指南
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
│   │   ├── storage/                  # database.py (MySQL) + models.py
│   │   ├── captcha/                  # 验证码识别 (ddddocr, 可选)
│   │   ├── monitoring/               # 监控报告
│   │   └── utils/                    # config.py / url_safety.py / timeutil.py
│   ├── requirements.txt              # Python 依赖
│   ├── verify.py                     # 后端自检脚本
│   ├── scripts/
│   │   └── diag_agent.py             # Agent 链路诊断脚本
│   └── .env.example                  # 环境变量模板
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
| DELETE | /api/crawl/{task_id} | 删除任务（按任务归属精确清理数据与向量索引，返回 `deleted_data` 数量） |
| POST | /api/query | 语义问答（非流式，兼容保留） |
| POST | /api/query/stream | **流式问答**（SSE：sources → delta* → done，混合检索） |
| GET | /api/query/history | 获取问答历史 |
| DELETE | /api/query/history | 清空聊天记录 |
| GET | /api/agent/{run_id}/events | **历史运行回放**（事件列表，内存优先 / Redis Stream 兜底） |
| GET | /api/monitor/timeseries?days=N | **按天聚合时间序列**（任务量/成功率/LLM 耗时，近 N 天） |
| POST | /api/admin/reindex | **全量重建向量索引 + BM25 索引**（升级索引格式/换模型后用） |
| GET | /api/data | 分页浏览爬取数据（**不含** `raw_html`） |
| GET | /api/data/{data_id} | 单个爬取数据的完整文档（**含** `raw_html`） |
| GET | /api/monitor/stats | 任务统计指标 |
| GET | /api/monitor/domains?days_ago=N | 域名分布统计（按 `crawled_data` 聚合真实域名） |
| GET | /api/monitor/alert | 告警检查 |
| GET | /api/settings/config | 系统配置 |
| GET | /api/settings/status | 服务连接状态 |
| GET | /api/health | 存活探针，返回 `{status, version}`（不探测外部依赖） |
| GET | /api/ready | 就绪探针，返回 `{status, mysql, redis}`，任一依赖不可用时 `status="degraded"` |

> **并发上限**：批量爬取与 Agent 都有并发上限（`MAX_CONCURRENT_CRAWLS`，默认 4），超出时返回 HTTP 429。
>
> **`GET /api/agent/{run_id}`**：查询单次 Agent 运行状态。

`GET /api/monitor/stats` 返回字段：`total_tasks`、`finished_tasks`、`success_rate`、`llm_calls`、`avg_llm_time_ms`、`avg_llm_time`（兼容旧字段）、`avg_crawl_time_ms`、`avg_llm_calls`、`queue_pending`、`dead_letter_count`、`error_summary`、`degraded`。

## MySQL 数据表

| 表名 | 说明 | 索引 |
|--------|------|------|
| agent_runs | 自主 Agent 运行记录 | run_id (unique), created_at |
| crawled_data | 爬取数据 | url, domain, created_at |
| crawl_tasks | 任务状态 | task_id (unique), status, created_at |
| chat_history | 聊天记录 | created_at, role |
| websites | 网站信息 | domain |
| extraction_rules | 提取规则 (XPath/CSS) | website_id |
| vector_data | 向量元数据 | crawled_data_id |
| task_logs | 任务日志 | url, domain, created_at |

> 旧 MongoDB 中已有的数据不会自动转入 MySQL；需要保留历史数据时，请在切换前自行导出并导入对应表。

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

### 4. 安装 MySQL

```bash
winget install Oracle.MySQL
net start MySQL80
```

首次安装后，用 MySQL 管理员账号创建应用数据库和用户：

```sql
CREATE DATABASE nia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'nia'@'localhost' IDENTIFIED BY 'nia';
GRANT ALL PRIVILEGES ON nia.* TO 'nia'@'localhost';
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

编辑 `backend/.env`，填入 DeepSeek API Key，并按本机 MySQL 用户更新 `MYSQL_URL`：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-deepseek-api-key
MYSQL_URL=mysql+pymysql://root:你的密码@localhost:3306/nia?charset=utf8mb4

# HF 镜像（国内网络必加，fastembed 模型下载）
HF_ENDPOINT=https://hf-mirror.com

# ── v3 新增（都有默认值，可不配）─────────────────────────
# 辅助模型：本地 Ollama 承担压缩摘要/查询改写（留空禁用）
AUX_LLM_PROVIDER=ollama
AUX_LLM_MODEL=qwen3:8b
AUX_LLM_BASE_URL=http://localhost:11434
# 混合检索开关与融合参数
RAG_HYBRID=true
RAG_RRF_K=60
RAG_CANDIDATE_K=20
RAG_THRESHOLD=0.3
# 查询改写（走辅助模型）
RAG_QUERY_REWRITE=true
# 交叉编码重排（默认关；开启需下载 BAAI/bge-reranker-base 约 1GB，走 HF 镜像）
# RERANK_MODEL=BAAI/bge-reranker-base
# HTML 磁盘缓存 TTL 秒（0 禁用，默认 24h）
CRAWL_HTML_CACHE_TTL=86400
# Agent 上下文压缩阈值（估算 token）
AGENT_CONTEXT_TOKEN_BUDGET=24000
```

本地运行前需先在 MySQL 中创建 `nia` 数据库和对应用户；启动时应用会自动创建业务表。

### 9. 初始化数据库

在 `backend` 目录下执行：

```bash
python -c "from nia.storage.database import DatabaseManager; db = DatabaseManager(); db.init_db(); print('OK')"
```

### 10. 启动

确保 Redis 与 MySQL 已在运行（Redis 默认 `6379`，MySQL 默认 `3306`），然后：

```bash
# 终端1: 在 backend 目录下启动后端 API（单进程；用 JS 渲染时不要加 --reload）
uvicorn nia.api.app:app --host 0.0.0.0 --port 8000

# 终端2: 在 frontend 目录下启动前端
npm run dev
```

浏览器访问 http://localhost:5173 ，首页即「🤖 自主 Agent」控制台。

> ⚠️ **必须单进程运行**（默认即 `workers=1`，不要加 `--workers`）：任务与事件状态保存在进程内存中，多 worker 会导致状态串台。
> ⚠️ 用 JS 渲染时不要加 `--reload`（reloader 会反复重启浏览器）。

> 💡 启动前可先运行 `python verify.py` 做后端自检。它会检查语法 / 模块导入 / 依赖 / Embedding 维度配置 / RAG 真实冒烟测试（向量化 → FAISS 插入 → 检索）/ Redis、MySQL 连通性；退出码 `0` = 可启动，`1` = 存在阻断性问题。模型因网络下载失败只报警告（属环境问题），MySQL 未启动也只警告。

## 可选：API 鉴权

默认不鉴权（仅建议本机使用）。设置环境变量 `API_AUTH_TOKEN` 后，所有 `/api/*` 请求必须携带请求头 `X-API-Token: <值>`，否则返回 401（`/api/health` 除外）；SSE 端点（`/stream`、`/progress`）因浏览器 EventSource 无法携带自定义请求头，额外接受 `?token=<值>` 查询参数（前端已自动处理）：

```env
API_AUTH_TOKEN=your-random-token
```

前端通过 `VITE_API_TOKEN` 传入同一个值；前端后端地址可用 `VITE_API_BASE_URL` 覆盖（默认 `/api`，开发时由 Vite 代理到 `:8000`）。

## 部署说明

本项目**不使用 Docker**，全部本地直接运行（见《运行步骤.md》）。如需生产部署：前端 `npm run build` 后把 `frontend/dist` 作为静态站点托管，并设置后端 `STATIC_DIR` 指向该目录即可由 FastAPI 同端口托管 SPA；公网部署务必设置 `API_AUTH_TOKEN`。

## 更新日志

### 2026-10-25 — v3.1 前端信息架构重设计（模型角色可视化）

- **常驻模型状态卡**：侧边栏底部显示主力模型（推理/报告）与辅助模型（本地，摘要/改写）的名称与在线状态（绿/红点，60s 自动刷新）；侧边栏折叠时收缩为两个状态点
- **事件级模型标注**：Agent 时间线每个事件带模型徽章（思考/动作/发现=主力模型灰标，压缩=辅助模型品牌色标）；`start` 事件携带 `main_model/aux_model`
- **问答模型链路**：回答气泡底部显示「改写 · qwen3:8b → 回答 · deepseek-chat」（`/api/query/stream` 的 sources 事件新增 `models` 字段）
- **导航分组**：侧边栏按「采集 / 情报 / 系统」三组分区
- **Agent 控制台两阶段布局**：「新建任务 | 历史运行」Tab 分离；新建态只显示一张启动卡（一屏一事），运行/完成/回放共用同一运行视图（状态条 + 预算仪表 + 时间线/发现 + 报告）
- **爬取页左右布局**：左侧 sticky 启动配置卡，右侧统计条 + 「抓取进度/提取结果」Tab 切换
- **数据页翻新**：迁移 TanStack Query（placeholderData 翻页不闪）；详情改 a11y Dialog（焦点陷阱/Esc），内容三 Tab：结构化数据 JSON 树 / 正文 / 原始 HTML sandbox iframe 预览
- **设置页重做**：服务状态四卡（Redis/MySQL/主力模型/辅助模型）+ 模型分工双卡 + 配置六组（新增模型组与 RAG 参数组，`AUX_LLM_*` 首次可见）；TanStack Query 化
- **后端配合**：`/api/settings/config` 暴露 `AUX_LLM_*` 与 RAG 参数；`/api/settings/status` 新增 `aux_llm` 健康探测（复用 60s 缓存）；Agent 事件与流式问答携带模型名

### 2026-10-25 — v3.0 大改版（Agent 内核 / 混合检索 / 前端 2026 化）

**Agent 内核（backend/nia/agent/）**

- **上下文工程**：新增 `context.py` —— 工具结果按字段结构化截断（替代裸字符切片）；历史估算 token 超 `AGENT_CONTEXT_TOKEN_BUDGET`（默认 24k）时把最旧步骤组**滚动压缩**为摘要（assistant.tool_calls 与 tool 消息成组替换，消息序列始终合法），前端收到 `compaction` 事件
- **工具注册表**：`tools.py` 重构为 `@tool_spec` + Pydantic 参数模型 **自动生成 OpenAI tools schema**（消除手写 schema 漂移）；同响应多个工具调用 `dispatch_many` **并行执行**
- **类型化事件**：`events.py` 改 StrEnum + Pydantic，事件带全局 `seq`，SSE 帧携带 `id:` 行
- **领域记忆**：新增 `memory.py` —— Redis 记录同站点历史运行经验（状态/发现数/有效入口，TTL 7 天），下次运行注入 system prompt
- **模型路由**：`llm_client.py` 支持辅助模型（默认本地 Ollama `qwen3:8b`，健康探测 60s 缓存，失败自动回退）；Ollama 走原生 `/api/chat` + `think:false`（qwen3 思考模式只能在原生端点关闭）
- 进度事件携带累计 token 与上下文估算；usage 随 run 落库

**事件总线（backend/nia/api/agent.py）**

- Agent 事件同步写入 **Redis Stream**（MAXLEN 5000 + 24h TTL）；SSE 支持 **Last-Event-ID 断线续读**；新增 `GET /api/agent/{run_id}/events` **历史回放**；Redis 3.x（无 Stream）自动降级纯内存并打警告
- 新增 `POST /api/admin/reindex` 全量重建向量 + BM25 索引（shield 保护，断连不中断）

**爬取引擎（backend/nia/crawler/）**

- **trafilatura 正文密度提取**（`parser.py`，失败回退 lxml）：导航/页脚噪声不再进入 LLM/RAG；新增 JSON-LD / OpenGraph / meta 元数据提取与**锚文本**（`PageContent.anchors`）
- **流水线化**（`engine.py`）：批间 LLM 提取与抓取重叠执行（异步任务投递，结束统一 gather）；事件新增 `from_cache`
- **HTML 磁盘缓存**：新增 `html_cache.py`（TTL 24h、单文件 5MB 上限、数量上限清理），重复任务零网络请求
- **frontier 相关性打分**：`goal_keywords` 命中锚文本/URL 的链接大幅加权

**RAG（backend/nia/rag/）**

- **混合检索**：新增 `bm25.py`（jieba + **BM25Plus**——BM25Okapi 小语料 IDF 为负的坑）与向量双路召回，**RRF 融合**（`RAG_RRF_K`）
- **查询改写**：辅助模型（Ollama）生成 2 个检索变体并集召回，不可用静默跳过
- **可选重排**：新增 `reranker.py`（fastembed TextCrossEncoder，`RERANK_MODEL` 默认关）
- **`RAG_THRESHOLD` 真正生效**（旧版为死配置）：低分块不进上下文；BM25 top-5 命中豁免
- **FAISS 升级 IndexIDMap2**：删除从「全量 reconstruct 重建索引」变 `remove_ids` O(1)；旧格式索引自动丢弃（用 reindex 重建）；`RAGEngine` 新增 `aquery_stream` 流式问答与 `remove_data`
- `POST /api/query/stream` 流式问答端点；删除爬取数据同步清理 BM25

**前端（frontend/）**

- **技术栈**：React 18→**19**（StrictMode 回归）、Vite 6→**8**（Rolldown，manualChunks 函数形式）、Tailwind 3→**4**（`@theme` CSS-first，删除 tailwind.config.js / postcss.config.js）、ECharts 5→**6**（`echarts/core` 按需）；**主包 1.49MB → 237KB（-84%）**，echarts 独立分包 + 路由 lazy
- **Agent 控制台重构**（`features/agent/`）：`useAgentRun` 状态机 + **react-virtual 虚拟化时间线**（不再 slice(-250)）+ 预算四仪表（页面/步数/token/上下文，含压缩徽标）+ 结构化发现卡片 + Markdown 报告 + **历史运行一键回放**；AgentEvent 类型改判别式联合
- **流式问答页**：消费 `/api/query/stream`（fetch + ReadableStream 手工解析 SSE），来源 chips 先行、逐字渲染、停止/重新生成；历史走 TanStack Query
- **监控页重写**：TanStack Query refetchInterval 替代手写 setInterval；新增 `/api/monitor/timeseries` 14 天任务量/成功率双轴图；`<Chart>` 统一封装（echarts/core + CSS token 取色随主题变色）
- **全局**：**Ctrl+K 命令面板**（导航/搜索/键盘操作）；品牌靛蓝强调色 + 顶部光晕精修；时区显示修复（UTC 无标记补 Z）
- 删除死代码：framer-motion 依赖、`components/Toast.tsx`

**其它**

- `requirements.txt`：新增 trafilatura / jieba / rank-bm25 / aiomysql / alembic / pydantic-settings；lxml 锁定 `>=5.3,<6`（crawl4ai 兼容）
- `database.py` `list()` 新增 `columns` 参数（轻量读取，BM25 构建用）

### 2026-10-15 — 移除 Docker 与缺陷修复

- **移除 Docker**：删除 `Dockerfile`、`docker-compose.yml`、`.dockerignore`，全部改为本地直接运行
- **删除修复**：`DELETE /api/crawl/{task_id}` 改为按任务归属（`metadata.task_id` / `data_id`）精确清理数据，不再误删其它任务的同 URL 页面，并同步清理 FAISS 向量索引与 `vector_data`
- **SSE 鉴权兼容**：浏览器 EventSource 无法携带请求头，后端额外接受 `?token=` 查询参数，前端 SSE 统一携带
- **FAISS 中文路径修复**：Windows 下项目路径含非 ASCII 字符时 FAISS C 层 fopen 读写失败，改用 `serialize_index` + Python 文件 IO
- **其它修复**：批量爬取 `duplicates` 统计恒 0；`EMBED_DIM` 对非 fastembed 模型未显式配置时启动报错而非静默错配；后端重启后旧任务 SSE 立即返回终态而非空等超时；单 URL 爬取改流式读取防大文件进内存
- **目录整理**：诊断脚本移入 `backend/scripts/`，清理 `nia.egg-info` 等构建垃圾

### 2026-10-09 — 数据库从 MongoDB 迁移到 MySQL

- **存储实现**：使用 SQLAlchemy + PyMySQL 替换 PyMongo；爬取数据、任务、Agent 运行、聊天记录、提取规则、日志及向量元数据统一写入 MySQL。
- **启动初始化**：后端启动时自动创建所需业务表；应用数据库本身需预先创建。MySQL 不可用时后端仍可启动，但持久化相关功能不可用，就绪状态会显示 `degraded`。
- **连接配置**：新增 `MYSQL_URL`，默认地址为 `mysql+pymysql://nia:nia@localhost:3306/nia?charset=utf8mb4`；请按本机 MySQL 账号修改，默认端口为 `3306`。
- **接口与界面**：数据、爬取、问答、Agent 和监控 API 改用 MySQL；`/api/ready` 检查 MySQL 与 Redis；设置页和监控页改为显示 MySQL 状态。
- **部署与依赖**：Docker Compose 改用 MySQL 8 和 `mysql_data` 持久化卷；移除 MongoDB 服务及 PyMongo 依赖，新增 SQLAlchemy、PyMySQL。
- **数据迁移说明**：已有 MongoDB 数据不会自动迁移。需要保留历史数据时，应在切换前导出，并映射导入相应 MySQL 表。

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
- 只依赖 **Redis + MySQL**；依赖大幅瘦身（移除 scrapy / scrapy-redis / qdrant-client / langchain-ollama）
- 删除死代码：`pipelines.py`、`rule_learner.py`（伪规则学习）、`extraction_pipeline.py`、`spiders/`、`scheduler/` 等

**前端翻新**

- 设计系统：HSL 设计 token + **明暗双主题**（持久化）+ shadcn 风格组件库（`components/ui/`）
- 新增 **Agent 控制台页**（首页）：实时活动时间线 + 发现侧栏 + 预算进度 + Markdown 报告
- 翻新 5 页：批量/整站爬取、Markdown 问答、可搜索数据表、暗色图表监控、设置
- 接入 framer-motion（动画）、sonner（通知）、TanStack Query、react-markdown

**修复**

- 修复 `crawl.py` SSE 首屏 `_tasks[task]` 拼写 bug；修复 `chunk_text` 潜在死循环

### 2026-06-06 — v1 全面重构（历史）

- 异步爬取 + SSE 实时进度；聊天记录存 MySQL；URL 安全校验防 SSRF
- 前端：Recharts → ECharts，赛博朋克暗色 → 明亮主题，新增错误边界
