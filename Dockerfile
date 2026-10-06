# =============================================================================
# Nexus Intelligence Agent — 多阶段构建
# Stage 1: 构建前端 (Vite + React + TS)
# Stage 2: 后端运行环境 (FastAPI + Uvicorn)
# =============================================================================

# ── Stage 1: Frontend Build ──────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# ── Stage 2: Backend Runtime ────────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ .

# 从前端构建产物复制静态文件（后端会挂载 STATIC_DIR 提供 SPA）
COPY --from=frontend-builder /app/frontend/dist /app/static

# 运行时数据目录：FAISS 索引 + embedding 模型缓存（建议挂载 volume 持久化，
# 否则每次重建容器都要重新下载 ONNX 模型）
RUN mkdir -p /app/data
ENV FASTEMBED_CACHE_DIR=/app/data/fastembed \
    FAISS_INDEX_PATH=/app/data/faiss_index \
    STATIC_DIR=/app/static

# 后端 FastAPI 端口
EXPOSE 8000

# 注意：任务/事件状态保存在进程内存里，请勿使用 --workers > 1
CMD ["uvicorn", "nia.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
