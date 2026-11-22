/**
 * API 客户端 — 支持 REST + SSE 实时进度
 */

import type {
  CrawlResult,
  ChatMessage,
  MonitorStats,
  ServiceStatus,
  AgentEvent,
  AgentEventReplay,
  AgentRunSummary,
  BatchEvent,
  QueryStreamEvent,
  TimeseriesPoint,
  Schedule,
  SchedulePayload,
  CrawlGraph,
  CostReport,
  SiteChange,
} from '@/types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || '/api';

// 可选鉴权：后端配置 API_AUTH_TOKEN 后，这里通过 VITE_API_TOKEN 提供 X-API-Token
const API_TOKEN = import.meta.env.VITE_API_TOKEN as string | undefined;

function authHeaders(): Record<string, string> {
  return API_TOKEN ? { 'X-API-Token': API_TOKEN } : {};
}

/**
 * SSE 端点的鉴权 URL。浏览器 EventSource 无法携带自定义请求头，
 * 后端（app.py api_token_guard）额外接受 ?token= 查询参数。
 */
function sseUrl(path: string): string {
  if (!API_TOKEN) return `${BASE_URL}${path}`;
  const sep = path.includes('?') ? '&' : '?';
  return `${BASE_URL}${path}${sep}token=${encodeURIComponent(API_TOKEN)}`;
}

/** 通用 SSE 订阅（约定终止符 data: [DONE]）。返回清理函数。 */
function subscribeSSE<T>(
  path: string,
  onMessage: (data: T) => void,
  onDone: () => void,
  onError: (error: string) => void,
): () => void {
  let finished = false;
  const es = new EventSource(sseUrl(path));
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

  /** 历史回放：读取某次运行的完整事件列表（内存优先，回退 Redis Stream） */
  getAgentEvents(runId: string, after = 0) {
    return request<AgentEventReplay>(`/agent/${runId}/events?after=${after}`);
  },

  // ── 爬取 ────────────────────────────────────────────────────────

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

  // ── 问答 ────────────────────────────────────────────────────────

  /**
   * 流式问答（POST SSE）。EventSource 不支持 POST，这里用 fetch + ReadableStream
   * 手工解析 SSE 帧：sources → delta* → done（终止符 data: [DONE]）。
   * @returns abort 函数（停止生成）
   */
  streamQuery(
    question: string,
    onEvent: (e: QueryStreamEvent) => void,
    signal?: AbortSignal,
  ): () => void {
    const controller = new AbortController();
    const onAbort = () => controller.abort();
    signal?.addEventListener('abort', onAbort);

    (async () => {
      try {
        const res = await fetch(`${BASE_URL}/query/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ question }),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) {
          const raw = await res.text().catch(() => '');
          onEvent({ type: 'error', message: raw.slice(0, 200) || `HTTP ${res.status}` });
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finished = false;
        while (!finished) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split('\n\n');
          buffer = blocks.pop() ?? '';
          for (const block of blocks) {
            const line = block.split('\n').find((l) => l.startsWith('data: '));
            if (!line) continue;
            const payload = line.slice(6);
            if (payload === '[DONE]') {
              finished = true;
              break;
            }
            try {
              onEvent(JSON.parse(payload) as QueryStreamEvent);
            } catch {
              /* 跳过坏帧 */
            }
          }
        }
      } catch (e) {
        if (!(e instanceof DOMException && e.name === 'AbortError')) {
          onEvent({ type: 'error', message: e instanceof Error ? e.message : String(e) });
        }
      } finally {
        signal?.removeEventListener('abort', onAbort);
      }
    })();

    return () => controller.abort();
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

  /** 知识库总览统计（数据浏览页顶部卡片） */
  getDataStats() {
    return request<{ total: number; domains: number; chars: number; latest: string | null }>('/data/stats');
  },

  // ── 监控 ────────────────────────────────────────────────────────

  getMonitorStats() {
    return request<MonitorStats>('/monitor/stats');
  },

  /** 知识库站点构成：默认取全部历史（大窗口），而非仅当天 */
  getMonitorDomains(days = 3650) {
    return request<{ domains: { domain: string; count: number }[] }>(`/monitor/domains?days=${days}`);
  },

  /** 按天聚合的采集活跃度热力图（站点变更数 + 爬取任务数） */
  getMonitorHeatmap(days = 84) {
    return request<{ heatmap: { date: string; changes: number; tasks: number }[] }>(
      `/monitor/heatmap?days=${days}`,
    );
  },

  getMonitorAlert() {
    return request<{ alert: string | null }>('/monitor/alert');
  },

  getMonitorTimeseries(days = 14) {
    return request<{ series: TimeseriesPoint[] }>(`/monitor/timeseries?days=${days}`);
  },

  getMonitorGraph() {
    return request<CrawlGraph>('/monitor/graph');
  },

  getMonitorCost() {
    return request<CostReport>('/monitor/cost');
  },

  getMonitorChanges(limit = 50) {
    return request<{ changes: SiteChange[] }>(`/monitor/changes?limit=${limit}`);
  },

  // ── 定时采集 ────────────────────────────────────────────────────

  listSchedules() {
    return request<{ schedules: Schedule[] }>('/schedules');
  },

  createSchedule(payload: SchedulePayload) {
    return request<Schedule>('/schedules', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  updateSchedule(id: string, patch: Partial<SchedulePayload>) {
    return request<Schedule>(`/schedules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },

  deleteSchedule(id: string) {
    return request<{ message: string }>(`/schedules/${id}`, { method: 'DELETE' });
  },

  runSchedule(id: string) {
    return request<{ message: string }>(`/schedules/${id}/run`, { method: 'POST' });
  },

  // ── 导出 ────────────────────────────────────────────────────────

  /** 数据全量导出下载地址（带鉴权 token，如已配置） */
  dataExportUrl(format: 'json' | 'csv'): string {
    return sseUrl(`/data/export?format=${format}`);
  },

  // ── 设置 ────────────────────────────────────────────────────────

  getConfig() {
    return request<{ config: Record<string, string> }>('/settings/config');
  },

  getServiceStatus() {
    return request<ServiceStatus>('/settings/status');
  },
};
