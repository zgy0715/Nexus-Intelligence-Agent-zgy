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
| Embedding | fastembed (本地 ONNX) | bge-m3，CPU 即可，无需 Ollama |
| 缓存/锁 | Redis | 提取缓存 / SSE |
| 数据库 | MongoDB | 任务状态、聊天记录、Agent 运行 |
| 向量存储 | FAISS (本地) | 语义检索向量索引 |

## 环境要求

- Node.js 18+
- Python 3.11+
- Redis 7+
- MongoDB 7+

> 无需 Qdrant、Ollama、Docker。

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
│   │   ├── ai/
│   │   │   ├── llm_client.py         # LLM 客户端 (同步 + async + tool-calling + 流式)
│   │   │   └── json_parser.py        # 健壮 JSON 解析器
│   │   ├── rag/
│   │   │   ├── embedding.py          # 嵌入管理器 (fastembed 本地 ONNX)
│   │   │   ├── vector_store.py       # 向量存储 (FAISS)
│   │   │   └── rag_engine.py         # RAG 引擎
│   │   ├── storage/                  # database.py (MongoDB) + models.py
│   │   ├── captcha/                  # 验证码识别 (ddddocr, 可选)
│   │   ├── monitoring/               # 监控报告
│   │   └── utils/                    # config.py / url_safety.py / crawl4ai_engine.py
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
| GET | /api/crawl/{task_id}/progress | SSE 单任务进度推送 |
| GET | /api/crawl/results | 获取爬取结果列表 |
| DELETE | /api/crawl/{task_id} | 删除任务 |
| POST | /api/query | 语义问答 |
| GET | /api/query/history | 获取问答历史 |
| DELETE | /api/query/history | 清空聊天记录 |
| GET | /api/data | 分页浏览爬取数据 |
| GET | /api/monitor/stats | 任务统计指标 |
| GET | /api/monitor/domains | 域名分布统计 |
| GET | /api/monitor/alert | 告警检查 |
| GET | /api/settings/config | 系统配置 |
| GET | /api/settings/status | 服务连接状态 |
| GET | /api/health | 健康检查 |

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

默认使用 fastembed（本地 ONNX），首次运行会**自动下载** bge-m3 并缓存，无需手动安装 Ollama。

### 6. 安装 Python 依赖

```bash
cd "D:\Nexus Intelligence Agent\backend"
pip install -r requirements.txt
```

### 7. 安装 Node.js 依赖

```bash
cd "D:\Nexus Intelligence Agent\frontend"
npm install
```

### 8. 配置环境变量

```bash
cd "D:\Nexus Intelligence Agent\backend"
copy .env.example .env
```

编辑 `.env` 文件，填入你的 DeepSeek API Key：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-deepseek-api-key
```

### 9. 初始化数据库

```bash
cd "D:\Nexus Intelligence Agent\backend"
python -c "from nia.storage.database import DatabaseManager; db = DatabaseManager(); db.init_db(); print('OK')"
```

### 10. 启动

确保 Redis 与 MongoDB 已在运行，然后：

```bash
# 终端1: 启动后端 API（用 JS 渲染时请去掉 --reload，避免反复重启浏览器）
cd "D:\Nexus Intelligence Agent\backend"
uvicorn nia.api.app:app --host 0.0.0.0 --port 8000

# 终端2: 启动前端
cd "D:\Nexus Intelligence Agent\frontend"
npm run dev
```

浏览器访问 http://localhost:5173 ，首页即「🤖 自主 Agent」控制台。

> 💡 启动前可先运行 `python verify.py` 做后端自检（语法 / 导入 / 依赖）。

## 更新日志

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
