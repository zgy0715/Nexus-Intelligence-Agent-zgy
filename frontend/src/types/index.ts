export interface CrawlResult {
  // `/api/crawl/results` 返回的是 crawl_tasks 文档（主键是 task_id，没有 id），
  // `/api/data` 返回的是 crawled_data 文档（没有 status）——两者都不要写成必填。
  id?: string;
  task_id?: string;
  url: string;
  timestamp?: string;
  created_at?: string;
  status?: 'queued' | 'pending' | 'running' | 'completed' | 'failed';
  extracted_data?: Record<string, unknown>;
  domain?: string;
  title?: string;
  content?: string;
  method?: string;
  extraction_method?: string;
  instruction?: string;
  use_js?: boolean;
  error?: string;
  progress?: number;
  step?: string;
  message?: string;
}

export interface Source {
  url: string;
  title?: string;
  snippet?: string;
  content_snippet?: string;
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp?: string;
  created_at?: string;
}

export interface MonitorStats {
  total_tasks: number;
  finished_tasks?: number;
  success_rate: number;
  llm_calls: number;
  avg_llm_time?: number;
  avg_llm_time_ms?: number;
  avg_crawl_time_ms?: number;
  avg_llm_calls?: number;
  queue_pending: number;
  dead_letter_count: number;
  error_summary?: Record<string, number>;
  degraded?: boolean;
}

/** GET /api/monitor/timeseries 的按天聚合点 */
export interface TimeseriesPoint {
  day: string;
  total: number;
  completed: number;
  success_rate: number;
  avg_crawl_ms: number;
  llm_calls: number;
}

/** POST /api/query/stream 的事件（sources → delta* → done） */
export type QueryStreamEvent =
  | { type: 'sources'; sources: Source[]; relevance: number; debug?: Record<string, unknown> }
  | { type: 'delta'; text: string }
  | { type: 'done'; mode: 'rag' | 'chat' }
  | { type: 'error'; message: string };

// ── 自主 Agent ────────────────────────────────────────────────────

export interface AgentUsage {
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export type AgentEventType =
  | "start"
  | "thought"
  | "action"
  | "observation"
  | "finding"
  | "progress"
  | "compaction"
  | "finish"
  | "error";

interface AgentEventBase {
  /** 全局事件序号（后端分配，SSE id / Last-Event-ID 用） */
  seq: number;
}

/**
 * 判别式联合：switch (e.type) 时各分支字段类型自动收窄，
 * 替代旧版「所有字段全部可选」的伪联合。
 */
export type AgentEvent =
  | (AgentEventBase & {
      type: "start";
      goal: string;
      seeds: string[];
      budget_pages: number;
      budget_steps: number;
    })
  | (AgentEventBase & { type: "thought"; text: string })
  | (AgentEventBase & { type: "action"; tool: string; args: Record<string, unknown> })
  | (AgentEventBase & { type: "observation"; tool: string; result: Record<string, unknown> })
  | (AgentEventBase & {
      type: "finding";
      title: string;
      url: string;
      data?: Record<string, unknown>;
      content: string;
    })
  | (AgentEventBase & {
      type: "progress";
      pages_used: number;
      budget_pages: number;
      steps_used: number;
      budget_steps: number;
      findings: number;
      visited: number;
      usage?: AgentUsage;
      est_context_tokens?: number;
    })
  | (AgentEventBase & {
      type: "compaction";
      saved_tokens: number;
      est_tokens: number;
      count: number;
    })
  | (AgentEventBase & {
      type: "finish";
      status: string;
      reason: string;
      report: string;
      findings: AgentFinding[];
      finding_count: number;
      pages_used: number;
      steps_used: number;
      usage?: AgentUsage;
    })
  | (AgentEventBase & { type: "error"; message: string });

export interface AgentFinding {
  url?: string;
  title?: string;
  data?: Record<string, unknown>;
  content?: string;
}

export interface AgentRunSummary {
  run_id: string;
  goal: string;
  seeds: string[];
  status: string;
  pages_used: number;
  steps_used: number;
  created_at: string;
  usage?: AgentUsage;
  finding_count?: number;
}

/** 历史回放端点（GET /api/agent/{run_id}/events）的响应 */
export interface AgentEventReplay {
  run_id: string;
  finished: boolean;
  events: AgentEvent[];
}

// ── 批量 / 整站爬取 ───────────────────────────────────────────────

export interface BatchEvent {
  event: string; // start | page | finding | page_error | done | result | error
  [k: string]: unknown;
}

export interface ServiceStatus {
  redis: { connected: boolean; version?: string };
  mysql: { connected: boolean; version?: string };
  llm_provider?: { connected: boolean; provider: string; model: string; models?: string[] };
}
