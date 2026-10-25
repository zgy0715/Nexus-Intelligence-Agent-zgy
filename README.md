# Nexus Intelligence Agent (NIA)

<p align="center">
  <strong>私有化的智能爬虫与情报分析系统</strong><br/>
  自主爬取 Agent · 混合检索 RAG · 采集即知识库 · 全栈本地运行
</p>

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind](https://img.shields.io/badge/Tailwind-4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![shadcn/ui](https://img.shields.io/badge/shadcn/ui-Radix-000)](https://ui.shadcn.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/Redis-5+-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![ECharts](https://img.shields.io/badge/ECharts-6-AA344D)](https://echarts.apache.org/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3-4D6BFE)](https://platform.deepseek.com/)
[![Ollama](https://img.shields.io/badge/Ollama-辅助模型-000?logo=ollama&logoColor=white)](https://ollama.com/)

---

## 这是什么

NIA 是一个**运行在你自己电脑上**的智能爬虫 + 情报问答系统。给它一个目标和几个种子 URL，Agent 会自主规划爬哪些页、跟随哪些链接、何时停止；抓到的每一页**实时入库并建立检索索引**，随后就能用自然语言对采集内容做**流式问答（带来源引用）**。

与商业爬取 SaaS 的区别：**数据全部本地、逻辑全部开源可改、辅助智能零 API 成本**。它不追求在反爬对抗上超越商业产品，而是提供它们给不了的「私有化 + 采集即知识库」闭环。

## 核心特性

- **🤖 自主爬取 Agent**：原生 tool-calling 多步循环。上下文滚动压缩（长任务不爆窗口）、同批工具并行执行、Pydantic 类型化工具注册表、三维预算（页面/步数/token）、无进展检测强制收尾、领域记忆（同站点经验注入）
- **⚡ 并发爬取引擎**：异步抓取 + trafilatura 正文密度提取 + 抓取/提取流水线重叠 + HTML 磁盘缓存 + 锚文本相关性打分 + SSRF 纵深防御 + robots/限速礼貌抓取
- **🔀 混合检索问答**：BM25Plus（jieba）+ 向量双路召回 RRF 融合 + 辅助模型查询改写 + 可选交叉编码重排 + 流式 SSE 输出（来源引用先行）
- **🧠 双模型路由**：主力模型（DeepSeek，推理/报告）+ 本地辅助模型（Ollama，摘要/改写，零 token 成本），运行时健康探测、离线自动回退——模型角色在 UI 全程可视化（侧边栏状态卡、时间线事件徽章、问答链路行）
- **📡 事件溯源可观测**：Agent 事件写 Redis Stream，SSE 断线续读（Last-Event-ID），**历史运行一键回放**；Redis 3.x 自动降级纯内存
- **🎨 现代前端**：React 19 + Vite 8 (Rolldown) + Tailwind 4 + shadcn/ui（Radix）+ motion 动效；暗色高级感（光晕/玻璃/发光 CTA）、指令台布局、爬取过程流光进度条 + 数字滚动 + 结果行滑入、Ctrl+K 命令面板、明暗主题全局一致过渡

## 技术点（有代码佐证）

| 模块 | 技术点 |
|---|---|
| `agent/agent.py` | tool-calling 循环的消息序列合法性处理（finish/取消回填全部 tool 消息）、预算与无进展收尾、协作式取消 |
| `agent/context.py` | CJK 启发式 token 估算、工具结果按字段结构化截断、历史步骤组滚动压缩（保持消息序列合法） |
| `ai/llm_client.py` | OpenAI 兼容多 Provider、指数退避重试、宽松 JSON 解析（不误伤 URL）、辅助模型路由与 qwen3 think 模式关闭 |
| `crawler/fetcher.py` | SSRF 逐跳校验、流式字节上限防解压炸弹、Retry-After、单域名限速 |
| `crawler/parser.py` | trafilatura 正文密度提取（lxml 兜底）、JSON-LD/OpenGraph 元数据、锚文本 |
| `rag/bm25.py` | jieba + BM25Plus（修复 BM25Okapi 小语料 IDF 为负的坑）、增量索引 |
| `rag/rag_engine.py` | 双路召回 RRF 融合、RAG_THRESHOLD 过滤 + BM25 top-5 豁免、流式答案 |
| `rag/vector_store.py` | FAISS IndexIDMap2 O(1) 删除、Windows 非 ASCII 路径 serialize 读写 |
| `api/agent.py` | 事件总线（内存 + Redis Stream 双模）、seq/Last-Event-ID 续读、历史回放 |

## 架构

```
浏览器 (React 19 + shadcn/ui + motion)
   │  REST / SSE
   ▼
FastAPI (单进程)
   ├─ Agent 内核 ── tool-calling ── 主力模型 (DeepSeek)
   │       │                        辅助模型 (Ollama, 摘要/改写)
   │       └─ on_page ──┐
   ├─ 爬取引擎 ─────────┤
   │                    ▼
   │        crawled_data (MySQL) + RAG 索引 (FAISS + BM25) + 提取缓存 (Redis)
   │                    │
   └─ 问答 / 监控 / 设置 ◀─ 混合检索 (RRF) + 流式答案
```

## 快速开始

```bash
# 0) 前置：Node 18+ / Python 3.11+ / Redis 5+ / MySQL 8（Redis 3.x 可用但事件回放降级）
#    可选：Ollama + qwen3:8b（辅助模型；不装则自动回退主模型）

# 1) 后端依赖
cd backend && pip install -r requirements.txt

# 2) 前端依赖
cd ../frontend && npm install

# 3) 配置（模板在 backend/.env.example，注意不在根目录）
cd ../backend && copy .env.example .env
#    编辑 .env：填 DEEPSEEK_API_KEY、改 MYSQL_URL、加 HF_ENDPOINT=https://hf-mirror.com

# 4) 建库（MySQL 中执行一次）
#    CREATE DATABASE nia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 5) 初始化表 + 自检
python -c "from nia.storage.database import DatabaseManager; DatabaseManager().init_db(); print('OK')"
python verify.py          # 退出码 0 = 可启动

# 6) 启动（两个终端）
#    backend:  python -m uvicorn nia.api.app:app --port 8000
#    frontend: cd frontend && npm run dev
#    打开 http://localhost:5173
```

JS 渲染（抓重 JS 站点时勾选）：`python -m playwright install chromium`

## 关键配置（backend/.env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | 主力模型 Key（必填） |
| `MYSQL_URL` | `mysql+pymysql://root:…@localhost:3306/nia` | 按本机账号修改 |
| `HF_ENDPOINT` | — | 国内必填 `https://hf-mirror.com`（embedding 模型下载） |
| `AUX_LLM_PROVIDER` / `AUX_LLM_MODEL` | `ollama` / `qwen3:8b` | 辅助模型；留空禁用 |
| `RAG_HYBRID` / `RAG_THRESHOLD` | `true` / `0.3` | 混合检索开关与相关度阈值 |
| `RAG_QUERY_REWRITE` | `true` | 查询改写（走辅助模型） |
| `RERANK_MODEL` | 空 | 设 `BAAI/bge-reranker-base` 开启重排（约 1GB） |
| `CRAWL_HTML_CACHE_TTL` | `86400` | HTML 磁盘缓存秒数（0 禁用） |
| `AGENT_CONTEXT_TOKEN_BUDGET` | `24000` | Agent 上下文压缩阈值 |
| `API_AUTH_TOKEN` | 空 | 设置后所有 `/api/*` 需带 `X-API-Token` |

完整配置见 `backend/.env.example`，运维细节见《运行步骤.md》。

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent` | 启动自主 Agent |
| GET | `/api/agent/{id}/stream` | SSE 事件流（Last-Event-ID 断线续读） |
| GET | `/api/agent/{id}/events` | 历史运行回放 |
| POST | `/api/agent/{id}/cancel` | 取消 |
| POST | `/api/crawl` / `/api/crawl/batch` | 单 URL / 批量·整站爬取 |
| GET | `/api/crawl/batch/{id}/stream` | 批量 SSE 进度 |
| POST | `/api/query` · `/api/query/stream` | 问答 / **流式问答** |
| GET/DELETE | `/api/query/history` | 聊天历史 |
| GET | `/api/data` · `/api/data/{id}` | 数据浏览（详情含 raw_html） |
| GET | `/api/monitor/stats` · `/domains` · `/timeseries` · `/alert` | 监控统计 |
| GET | `/api/settings/config` · `/status` | 配置（含模型角色）与服务状态（含辅助模型探测） |
| POST | `/api/admin/reindex` | 全量重建向量 + BM25 索引 |
| GET | `/api/health` · `/api/ready` | 存活 / 就绪探针 |

## 使用建议

1. **Agent 页**：目标 + 种子 → 启动 → 看实时时间线（每个事件标注产生它的模型）→ 报告生成 → 「历史运行」可回放
2. **批量爬取页**：指令台填 URL → 爬取中顶部流光进度 + 计数滚动 → 抓取即入库可问答
3. **语义问答**：基于全部已采集内容流式作答，来源可溯
4. **数据浏览**：JSON 树 / 正文 / 原始 HTML 沙箱预览
5. **任务监控**：14 天任务量/成功率时间序列 + 域名分布

## 生产部署

前端 `npm run build` 后设 `STATIC_DIR` 指向 `frontend/dist`，FastAPI 同端口托管 SPA；公网务必设置 `API_AUTH_TOKEN` 并收紧 `CORS_ORIGINS`。

## 更新日志

### 2026-10-25 — v4：视觉动效改版 + 采集问答闭环

- **修复采集→问答闭环**：批量爬取入库后补建 RAG 索引；Agent 抓取页面落库+索引（此前两者都进不了语义问答）
- **shadcn/ui**：Button（Radix Slot+CVA，兼容原 API）、Dialog（Radix a11y）、tw-animate-css
- **暗色高级感**：品牌光晕、玻璃拟态、发光 CTA、指令台聚焦描边
- **爬取动效**：指令台 + 全屏接管、顶部流光进度条、数字滚动、结果行 stagger 滑入；Agent 运行视图同款进度条
- **主题切换一致性修复**：切换时全站统一 250ms 颜色过渡（修复不同页面/元素快慢不一）

### 2026-10-25 — v3.1：模型角色可视化

- 侧边栏常驻模型状态卡（主力/辅助 + 在线状态）；Agent 时间线事件级模型徽章；问答模型链路行；导航三组分区；Agent 页两阶段布局；数据页 Dialog 三 Tab；设置页模型分工区

### 2026-10-25 — v3.0：Agent 内核 / 混合检索 / 前端现代化

- Agent 上下文滚动压缩、并行工具、Pydantic 工具注册表、领域记忆、双模型路由
- BM25+向量 RRF 混合检索、Ollama 查询改写、可选重排、流式问答、FAISS IDMap2
- React 19 / Vite 8 / Tailwind 4 / ECharts 6，首屏 bundle -84%，路由 lazy

### 更早

- 2026-10-15 移除 Docker 化本地直跑；2026-10-09 MongoDB→MySQL；2026-06 v2/v1 演进见 git 历史

---

## 许可与说明

本项目为学习/自用目的开发，DeepSeek/Ollama 调用请遵守对应服务条款，抓取请遵守目标站点 robots.txt 与当地法规。
