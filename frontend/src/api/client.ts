import type { CrawlResult, ChatMessage, MonitorStats, ServiceStatus, Source } from '@/types';

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const errorText = await res.text().catch(() => '');
    throw new Error(`请求失败: ${res.status}${errorText ? ` - ${errorText}` : ''}`);
  }
  const data: unknown = await res.json();
  if (data === null || data === undefined) {
    throw new Error(`API 返回了空响应: ${path}`);
  }
  return data as T;
}

export const api = {
  crawl(url: string, instruction: string, useJs?: boolean) {
    return request<{ task_id: string; status: string }>('/crawl', {
      method: 'POST',
      body: JSON.stringify({ url, instruction, use_js: useJs }),
    });
  },

  getCrawlResults() {
    return request<{ results: CrawlResult[] }>('/crawl/results');
  },

  query(question: string) {
    return request<{ answer: string; sources: Source[] }>('/query', {
      method: 'POST',
      body: JSON.stringify({ question }),
    });
  },

  getQueryHistory() {
    return request<{ history: ChatMessage[] }>('/query/history');
  },

  getData(page: number, pageSize: number, search?: string) {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.set('search', search);
    return request<{ total: number; page: number; page_size: number; data: CrawlResult[] }>(`/data?${params}`);
  },

  getMonitorStats() {
    return request<MonitorStats>('/monitor/stats');
  },

  getMonitorDomains() {
    return request<{ domains: { domain: string; count: number }[] }>('/monitor/domains');
  },

  getMonitorAlert() {
    return request<{ alert: string | null }>('/monitor/alert');
  },

  getConfig() {
    return request<{ config: Record<string, string> }>('/settings/config');
  },

  getServiceStatus() {
    return request<ServiceStatus>('/settings/status');
  },
};
