# Nexus Intelligence Agent (NIA)

下一代智能网络爬虫与情报分析系统，完全基于本地免费 AI 技术构建。

## 核心特性

- **全程离线零成本** - 所有 AI 能力基于本地 Ollama 运行，零 API 费用
- **混合提取与规则自学习** - AI 提取 → 生成选择器 → 优先使用选择器 → 失败回退 AI
- **页面结构自动适应** - DOM 相似度检测，自动识别网站改版并更新规则
- **采集与分析一体化** - 内置 RAG 语义检索和自然语言问答
- **本地验证码破解** - 支持文字/滑块/点选验证码
- **现代化前端界面** - React + TypeScript 赛博朋克暗色主题

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React 18 + TypeScript + Vite | 现代化 SPA 应用 |
| 前端样式 | Tailwind CSS | 赛博朋克暗色主题 |
| 状态管理 | Zustand | 轻量级响应式状态 |
| 路由 | React Router v6 | 客户端路由 |
| 图表 | Recharts | 监控数据可视化 |
| 后端 API | FastAPI | Python 异步 Web 框架 |
| 爬虫框架 | Scrapy + Scrapy-Redis | 分布式爬虫 |
| JS 渲染 | Crawl4AI | 异步 JS 渲染引擎 |
| 本地 LLM | Ollama (qwen2:7b-instruct) | 主力语言模型 |
| 多模态 | qwen2.5-vl:3b-instruct | 验证码识别 |
| 嵌入模型 | nomic-embed-text | 文本向量化 |
| AI 框架 | LangChain | LLM 编排 |
| 消息队列 | Redis | 分布式队列/缓存/锁 |
| 数据库 | MongoDB | 文档数据存储 |
| 向量存储 | FAISS | 语义检索向量索引 |
| 部署 | Docker Compose | 一键部署 |

## 环境要求

- Node.js 18+
- Python 3.11+
- Redis 7+
- MongoDB 7+
- Ollama (含 qwen2:7b-instruct, nomic-embed-text 模型)

## 项目结构

```
Nexus Intelligence Agent/
├── frontend/                     # React 前端
│   ├── src/
│   │   ├── api/client.ts         # API 客户端 (fetch 封装)
│   │   ├── components/
│   │   │   ├── Layout.tsx        # 侧边栏布局
│   │   │   └── StatusBadge.tsx   # 状态徽章组件
│   │   ├── pages/
│   │   │   ├── CrawlPage.tsx     # 零配置抓取
│   │   │   ├── QueryPage.tsx     # 语义问答
│   │   │   ├── DataPage.tsx      # 数据浏览
│   │   │   ├── MonitorPage.tsx   # 任务监控
│   │   │   └── SettingsPage.tsx  # 系统设置
│   │   ├── store/index.ts        # Zustand 状态管理
│   │   ├── types/index.ts        # TypeScript 类型定义
│   │   ├── App.tsx               # 主应用 (路由配置)
│   │   ├── main.tsx              # 入口
│   │   └── index.css             # 全局样式 (赛博朋克主题)
│   ├── public/                   # 静态资源
│   ├── index.html                # Vite 入口
│   ├── package.json              # Node.js 依赖
│   ├── vite.config.ts            # Vite 配置 (含 API 代理)
│   ├── tsconfig.json             # TypeScript 配置
│   ├── tailwind.config.js        # Tailwind CSS 主题
│   ├── postcss.config.js         # PostCSS 配置
│   └── eslint.config.js          # ESLint 配置
│
├── backend/                      # Python 后端
│   ├── nia/
│   │   ├── api/                  # FastAPI 后端 API
│   │   │   ├── app.py            # 主应用 (CORS + 路由注册)
│   │   │   ├── crawl.py          # POST /api/crawl, GET /api/crawl/results
│   │   │   ├── query.py          # POST /api/query, GET /api/query/history
│   │   │   ├── data.py           # GET /api/data (分页+搜索)
│   │   │   ├── monitor.py        # GET /api/monitor/stats, /domains, /alert
│   │   │   └── settings.py       # GET /api/settings/config, /status
│   │   ├── ai/                   # AI 核心模块
│   │   │   ├── ollama_client.py  # Ollama 客户端 (LLM + VL + 嵌入)
│   │   │   ├── json_parser.py    # 健壮 JSON 解析器 (含 LLM 自修正)
│   │   │   ├── extraction_pipeline.py # AI 提取管道
│   │   │   ├── rule_learner.py   # 规则自学习
│   │   │   └── dom_detector.py   # DOM 结构变化检测
│   │   ├── storage/              # 存储模块 (MongoDB)
│   │   │   ├── database.py       # DatabaseManager (连接池 + 索引)
│   │   │   ├── models.py         # 数据模型 (6 个 dataclass)
│   │   │   └── data_version.py   # 数据版本控制
│   │   ├── rag/                  # RAG 系统 (FAISS)
│   │   │   ├── embedding.py      # 嵌入管理器
│   │   │   ├── vector_store.py   # FAISS 向量存储
│   │   │   └── rag_engine.py     # RAG 引擎
│   │   ├── spiders/              # Scrapy 爬虫
│   │   │   ├── base_spider.py    # 基础爬虫
│   │   │   └── smart_spider.py   # 智能爬虫
│   │   ├── captcha/              # 验证码破解
│   │   ├── scheduler/            # 任务调度 (Redis)
│   │   ├── monitoring/           # 监控报告
│   │   ├── utils/                # 工具模块
│   │   ├── middlewares.py        # 防反爬中间件
│   │   ├── items.py              # Scrapy Item 定义
│   │   ├── pipelines.py          # 数据处理管道
│   │   └── settings.py           # Scrapy 设置
│   ├── pyproject.toml            # Python 项目配置
│   ├── requirements.txt          # Python 依赖
│   ├── scrapy.cfg                # Scrapy 配置
│   └── .env                      # 环境变量
│
├── Dockerfile                    # Docker 镜像
├── docker-compose.yml            # 一键部署
├── .gitignore
├── README.md
└── 运行步骤.md
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/crawl | 提交抓取任务 |
| GET | /api/crawl/results | 获取抓取结果列表 |
| POST | /api/query | 语义问答 |
| GET | /api/query/history | 获取问答历史 |
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
| websites | 网站信息 | domain |
| extraction_rules | 提取规则 (XPath/CSS) | website_id |
| crawled_data | 爬取数据 | url, domain, created_at |
| vector_data | 向量元数据 (实际向量在 FAISS) | crawled_data_id |
| data_versions | 数据版本控制 | crawled_data_id |
| task_logs | 任务日志 | url, domain, created_at |

## 快速开始

### 1. 安装 Ollama 和模型

```bash
ollama pull qwen2:7b-instruct
ollama pull qwen2.5-vl:3b
ollama pull nomic-embed-text
```

### 2. 安装 Redis

```bash
winget install Redis.Redis
redis-server
```

### 3. 安装 MongoDB

```bash
winget install MongoDB.Server
mongod --dbpath D:\MongoDB\data
```

### 4. 安装 Python 依赖

```bash
cd "D:\Nexus Intelligence Agent\backend"
pip install -e .
```

### 5. 安装 Node.js 依赖

```bash
cd "D:\Nexus Intelligence Agent\frontend"
npm install
```

### 6. 配置环境变量

```bash
cd "D:\Nexus Intelligence Agent\backend"
copy .env.example .env
```

### 7. 初始化数据库

```bash
cd "D:\Nexus Intelligence Agent\backend"
python -c "from nia.storage.database import DatabaseManager; db = DatabaseManager(); db.init_db(); print('OK')"
```

### 8. 启动

```bash
# 终端1: 启动后端 API
cd "D:\Nexus Intelligence Agent\backend"
uvicorn nia.api.app:app --reload --host 0.0.0.0 --port 8000

# 终端2: 启动前端
cd "D:\Nexus Intelligence Agent\frontend"
npm run dev
```

浏览器访问: http://localhost:5173

## 常见问题

### ModuleNotFoundError: No module named 'nia'

```bash
pip install -e .
```

### FastAPI 未安装

```bash
pip install fastapi uvicorn
```

### nest_asyncio 未安装

```bash
pip install nest-asyncio
```

### Ollama 连接失败

```bash
ollama serve
```

### Redis 连接失败

```bash
redis-server
```

### MongoDB 连接失败

```bash
mongod --dbpath D:\MongoDB\data
```

## 更新日志

### 2026-05-23 — 全面代码审查与修复

**Python 后端修复 (10 项)**

1. **nia/api/crawl.py** — Redis 异常处理增强
   - 添加 try/except 包装 Redis 读写操作，捕获 `redis.RedisError`、`json.JSONDecodeError` 和 `TypeError`
   - 写入结果前增加 `isinstance(results, list)` 类型检查，防止损坏数据污染缓存
   - 添加结构化日志记录 (logger)，记录所有 Redis 操作失败
   - 影响范围：POST /api/crawl、GET /api/crawl/results

2. **nia/api/query.py** — Redis 异常处理增强
   - 添加 try/except 包装聊天历史的 Redis 读写操作
   - 写入前增加 list 类型验证
   - 添加结构化日志记录
   - 影响范围：POST /api/query、GET /api/query/history

3. **nia/api/data.py** — MongoDB 异常处理增强
   - 整个数据库查询逻辑包装在 try/except `PyMongoError` 中
   - `doc.pop("_id")` 增加 `TypeError`/`AttributeError` 捕获
   - 数据库异常时返回空数据集而非崩溃
   - 影响范围：GET /api/data

4. **nia/api/monitor.py** — API 响应格式修复
   - 修复 `/stats` 端点：统一字段名为前端期望的 `total_tasks`、`queue_pending`、`avg_llm_time`
   - 修复 `/domains` 端点：返回 `{"domains": [...]}` 包装格式而非裸数组
   - 影响范围：GET /api/monitor/stats、GET /api/monitor/domains

5. **nia/api/settings.py** — API 响应格式修复
   - 修复 `/config` 端点：返回 `{"config": {...}}` 包装格式
   - 影响范围：GET /api/settings/config

6. **nia/ai/ollama_client.py** — JSON 解析错误日志
   - `extract_json()`、`check_dom_change()`、`extract_with_instruction()` 中的 `json.JSONDecodeError` 静默失败改为 warning 级别日志
   - 日志包含 LLM 响应的前 300 字符预览，便于诊断 AI 输出异常
   - 影响范围：AI 提取管道、DOM 检测、规则学习

7. **nia/ai/json_parser.py** — LLM 自校正错误信息增强
   - `_llm_self_correct()` 的 `ValueError` 增加 LLM 校正响应的前 300 字符预览
   - 便于定位 LLM 输出导致解析失败的根本原因
   - 影响范围：AI 提取管道的 JSON 解析链路

8. **nia/rag/vector_store.py** — 数据结构验证
   - `_load_index()` 增加 metadata list 类型验证
   - 增加 index 向量数量与 metadata 条目数量的交叉验证 (ntotal vs len)
   - 数据不一致时自动重建索引并记录 warning
   - `Exception` 捕获改为具体日志记录
   - 影响范围：FAISS 向量存储的索引加载与持久化

9. **nia/storage/database.py** — 连接管理优化
   - `connect()` 增加幂等检查，重复调用不创建新连接
   - `MongoClient` 增加 `serverSelectionTimeoutMS=5000` 和 `connectTimeoutMS=5000`
   - `get_collection()` 增加 `self._db` 空值检查，自动触发 `connect()`
   - `init_db()` 中索引创建增加 `ConnectionFailure` 异常捕获
   - 影响范围：MongoDB 连接管理全模块

10. **nia/pipelines.py** — 分布式锁防御 + 错误日志增强
    - `process_item()` 增加 `distributed_lock is not None` 检查，避免 Redis 未启动时崩溃
    - `_store_data()` 错误日志增加 item 键名预览，便于定位数据结构异常
    - 影响范围：Scrapy 数据处理管道

**Python 后端 — 语法修复**

11. **nia/middlewares.py** — BOM 字符修复
    - 移除文件开头的 UTF-8 BOM (U+FEFF) 字符，修复 `SyntaxError: invalid non-printable character`
    - 增加 `request.headers is None` 防御性检查
    - 影响范围：Scrapy 反反爬中间件

12. **nia/spiders/__init__.py** — BOM 字符修复
    - 移除文件开头的双重 UTF-8 BOM (U+FEFF) 字符
    - 影响范围：爬虫包初始化

**React 前端修复 (7 项)**

13. **src/api/client.ts** — API 路由匹配修复
    - 修复 `getConfig()` 路径：`/config` → `/settings/config`
    - 修复 `getServiceStatus()` 路径：`/services/status` → `/settings/status`
    - `request()` 增加 HTTP 错误响应体输出，便于调试
    - 增加空响应 (null/undefined) 检查，抛出明确错误信息
    - 影响范围：设置页面、服务状态面板

14. **vite.config.ts** — 开发服务器 API 代理
    - 增加 `server.proxy` 配置，将 `/api` 请求代理到 `http://127.0.0.1:8000`
    - 前端开发时无需 CORS 配置即可调用后端 API
    - 影响范围：开发环境 API 调用

15. **tsconfig.json** — TypeScript 严格模式增强
    - 启用 `noUnusedLocals: true` — 未使用局部变量报错
    - 启用 `noUnusedParameters: true` — 未使用参数报错
    - 启用 `noFallthroughCasesInSwitch: true` — switch 穿透报错
    - 启用 `noUncheckedSideEffectImports: true` — 副作用导入检查
    - 启用 `noUncheckedIndexedAccess: true` — 索引访问可空检查
    - 启用 `forceConsistentCasingInFileNames: true` — 文件名大小写一致
    - 影响范围：全前端 TypeScript 类型检查

16. **pyproject.toml** — 依赖更新
     - 新增 `fastapi>=0.109.0`、`uvicorn>=0.25.0`、`nest-asyncio>=1.6.0`
     - 移除已弃用的 `streamlit>=1.30.0`、`flask>=3.0.0`
     - 影响范围：Python 包依赖声明

17. **src/pages/DataPage.tsx** — ESLint 警告修复
    - useEffect 依赖数组补充 `fetchData`，消除 `react-hooks/exhaustive-deps` 警告
    - 影响范围：数据浏览页面的搜索+分页逻辑

**测试结果**

| 测试项 | 结果 | 详情 |
|--------|------|------|
| TypeScript 类型检查 | ✅ 通过 | tsc --noEmit 零错误（含 noUncheckedIndexedAccess 等 6 项严格选项） |
| Python 语法检查 | ✅ 通过 | 47 个文件全部通过编译检查 |
| Python 核心模块导入 | ✅ 通过 | config, database, ollama_client, json_parser, vector_store |
| Vite 生产构建 | ✅ 通过 | 2300 modules, 46.6s, dist 产出正常 |
| ESLint 代码规范 | ✅ 通过 | 0 errors, 0 warnings |
| API 路由映射一致性 | ✅ 通过 | 前端 client.ts 路径与后端路由完全匹配 |
| 前后端字段名一致性 | ✅ 通过 | monitor/stats, query/history, crawl/results, settings/config |

### 2026-05-23 — 运行时测试与修复

**新增修复**

18. **nia/api/query.py** — RAG 查询异常处理
    - POST `/api/query` 增加 try/except 包装 `rag_engine.query()`
    - Ollama 模型不可用时（如 nomic-embed-text 未安装）返回 200 + 友好错误信息，而非 500 Internal Server Error
    - 错误信息引导用户检查 Ollama 服务和模型安装状态
    - 影响范围：语义问答 API

**运行时测试结果**

| 测试项 | 结果 | 详情 |
|--------|------|------|
| 依赖安装 | ✅ | fastapi, crawl4ai 已通过 pip 安装 |
| .env 配置 | ✅ | 从 .env.example 自动创建 |
| FastAPI 启动 | ✅ | uvicorn 运行在 http://127.0.0.1:8000 |
| Vite 启动 | ✅ | 启动 3806ms, 运行在 http://127.0.0.1:5173 |
| API 代理 | ✅ | Vite proxy 正确转发 /api → 8000 |
| POST /api/crawl | ✅ | 返回 task_id + queued 状态 |
| POST /api/query | ✅ | nomic-embed-text 未安装时返回 200 + 指导信息 |
| GET /api/health | ✅ | {"status": "ok"} |
| GET /api/settings/config | ✅ | {"config": {...}} 格式正确 |
| GET /api/settings/status | ✅ | Redis ✅ MongoDB ✅ Ollama ✅ |
| GET /api/crawl/results | ✅ | {"results": []} |
| GET /api/query/history | ✅ | {"history": []} |
| GET /api/data | ✅ | 分页+搜索正常 |
| GET /api/monitor/stats | ✅ | 字段名与前端 Match |
| GET /api/monitor/domains | ✅ | {"domains": []} |
| GET /api/monitor/alert | ✅ | {"alert": null} |
| 前端页面渲染 | ✅ | 200 OK, HTML 正常返回 |

**已知待处理项**

- `nomic-embed-text` 模型未安装：需执行 `ollama pull nomic-embed-text` 下载嵌入模型后，RAG 语义问答功能才可正常使用
- Ollama 模型列表为空：Ollama 的 `/api/tags` 返回的 models 数组为空，需要确认模型迁移后服务是否正确加载模型
