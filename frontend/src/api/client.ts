/**
 * API 客户端 — 支持 REST + SSE 实时进度
 */

import type {
  CrawlResult,
  ChatMessage,
  MonitorStats,
  ServiceStatus,
  Source,
  AgentEvent,
  AgentRunSummary,
  BatchEvent,
} from '@/types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || '/api';

// 可选鉴权：后端配置 API_AUTH_TOKEN 后，这里通过 VITE_API_TOKEN 提供 X-API-Token
const API_TOKEN = import.meta.env.VITE_API_TOKEN as string | undefined;

function authHeaders(): Record<string, string> {
  return API_TOKEN ? { 'X-API-Token': API_TOKEN } : {};
}

/** 通用 SSE 订阅（约定终止符 data: [DONE]）。返回清理函数。 */
function subscribeSSE<T>(
  path: string,
  onMessage: (data: T) => void,
  onDone: () => void,
  onError: (error: string) => void,
): () => void {
  let finished = false;
  const es = new EventSource(`${BASE_URL}${path}`);
  es.onmessage = (event) => {
    if (event.data === '[DONE]') {
      finished = true;
      es.close();
      onDone();
      return;
    }
    try {
      onMessage(JSON.parse(event.data) as T);
    } catch {
      /* 忽略心跳/非法帧，不让单个坏帧中断整条流 */
    }
  };
  es.onerror = () => {
    if (finished) return;
    // readyState=CONNECTING 表示浏览器会自动重连（服务端有心跳），
    // 此时只是提示，不要立刻关闭长连接。
    if (es.readyState === EventSource.CONNECTING) {
      onError('连接不稳定，正在重连…');
      return;
    }
    es.close();
    onError('连接中断');
  };
  return () => {
    finished = true;
    es.close();
  };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    ...options,
  });
  if (!res.ok) {
    // 尽量还原后端返回的 detail 字段，而不是把整段 JSON 拼进消息
    const raw = await res.text().catch(() => '');
    let detail = '';
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === 'string') detail = parsed.detail;
    } catch {
      detail = raw;
    }
    throw new Error(detail || `请求失败: HTTP ${res.status}`);
  }
  const text = await res.text();
  if (!text) {
    throw new Error(`API 返回了空响应: ${path}`);
  }
  return JSON.parse(text) as T;
}

export interface CrawlProgress {
  step: string;
  progress: number;
  message: string;
}

export interface AgentStartParams {
  goal: string;
  seeds: string[];
  max_pages?: number;
  max_depth?: number;
  use_js?: boolean;
}

export interface BatchCrawlParams {
  seeds: string[];
  instruction?: string;
  use_js?: boolean;
  max_depth?: number;
  max_pages?: number;
  same_domain_only?: boolean;
}

export const api = {
  // ── 自主 Agent ──────────────────────────────────────────────────

  startAgent(params: AgentStartParams) {
    return request<{ run_id: string; status: string; goal: string; seeds: string[] }>('/agent', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  subscribeAgent(
    runId: string,
    onEvent: (e: AgentEvent) => void,
    onDone: () => void,
    onError: (err: string) => void,
  ) {
    return subscribeSSE<AgentEvent>(`/agent/${runId}/stream`, onEvent, onDone, onError);
  },

  cancelAgent(runId: string) {
    return request<{ message: string }>(`/agent/${runId}/cancel`, { method: 'POST' });
  },

  listAgentRuns(limit = 20) {
    return request<{ runs: AgentRunSummary[] }>(`/agent?limit=${limit}`);
  },

  // ── 爬取 ────────────────────────────────────────────────────────

  crawl(url: string, instruction: string, useJs?: boolean) {
    return request<{ task_id: string; status: string; message: string }>('/crawl', {
      method: 'POST',
      body: JSON.stringify({ url, instruction, use_js: useJs }),
    });
  },

  batchCrawl(params: BatchCrawlParams) {
    return request<{ task_id: string; status: string; seeds: string[] }>('/crawl/batch', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  subscribeBatch(
    taskId: string,
    onEvent: (e: BatchEvent) => void,
    onDone: () => void,
    onError: (err: string) => void,
  ) {
    return subscribeSSE<BatchEvent>(`/crawl/batch/${taskId}/stream`, onEvent, onDone, onError);
  },

  cancelBatch(taskId: string) {
    return request<{ message: string; status: string }>(`/crawl/batch/${taskId}/cancel`, {
      method: 'POST',
    });
  },

  /**
   * SSE 订阅爬取进度
   * @returns 清理函数
   */
  subscribeCrawlProgress(
    taskId: string,
    onProgress: (data: CrawlProgress) => void,
    onDone: () => void,
    onError: (error: string) => void,
  ): () => void {
    const eventSource = new EventSource(`${BASE_URL}/crawl/${taskId}/progress`);

    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        eventSource.close();
        onDone();
        return;
      }
      try {
        const data = JSON.parse(event.data) as CrawlProgress;
        onProgress(data);
      } catch {
        // ignore parse errors
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      onError('连接中断');
    };

    return () => eventSource.close();
  },

  getTaskStatus(taskId: string) {
    return request<CrawlResult>(`/crawl/${taskId}`);
  },

  getCrawlResults(page = 1, pageSize = 20) {
    return request<{ results: CrawlResult[]; total: number; page: number; page_size: number }>(
      `/crawl/results?page=${page}&page_size=${pageSize}`,
    );
  },

  deleteTask(taskId: string) {
    return request<{ message: string }>(`/crawl/${taskId}`, { method: 'DELETE' });
  },

  // ── 问答 ────────────────────────────────────────────────────────

  query(question: string) {
    return request<{ answer: string; sources: Source[] }>('/query', {
      method: 'POST',
      body: JSON.stringify({ question }),
    });
  },

  getQueryHistory(limit = 50) {
    return request<{ history: ChatMessage[] }>(`/query/history?limit=${limit}`);
  },

  clearChatHistory() {
    return request<{ message: string }>('/query/history', { method: 'DELETE' });
  },

  // ── 数据 ────────────────────────────────────────────────────────

  getData(page: number, pageSize: number, search?: string, signal?: AbortSignal) {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.set('search', search);
    return request<{ total: number; page: number; page_size: number; data: CrawlResult[] }>(
      `/data?${params}`,
      { signal },
    );
  },

  getDataItem(dataId: string) {
    return request<CrawlResult>(`/data/${encodeURIComponent(dataId)}`);
  },

  // ── 监控 ────────────────────────────────────────────────────────

  getMonitorStats() {
    return request<MonitorStats>('/monitor/stats');
  },

  getMonitorDomains() {
    return request<{ domains: { domain: string; count: number }[] }>('/monitor/domains');
  },

  getMonitorAlert() {
    return request<{ alert: string | null }>('/monitor/alert');
  },

  // ── 设置 ────────────────────────────────────────────────────────

  getConfig() {
    return request<{ config: Record<string, string> }>('/settings/config');
  },

  getServiceStatus() {
    return request<ServiceStatus>('/settings/status');
  },
};
