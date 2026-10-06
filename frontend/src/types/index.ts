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

// ── 自主 Agent ────────────────────────────────────────────────────

export type AgentEventType =
  | "start"
  | "thought"
  | "action"
  | "observation"
  | "finding"
  | "progress"
  | "finish"
  | "error";

export interface AgentEvent {
  type: AgentEventType;
  // 各事件的负载字段（按 type 取用）
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: Record<string, unknown>;
  title?: string;
  url?: string;
  data?: Record<string, unknown>;
  content?: string;
  goal?: string;
  seeds?: string[];
  budget_pages?: number;
  budget_steps?: number;
  pages_used?: number;
  steps_used?: number;
  findings?: number | AgentFinding[];
  visited?: number;
  status?: string;
  reason?: string;
  report?: string;
  message?: string;
}

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
}

// ── 批量 / 整站爬取 ───────────────────────────────────────────────

export interface BatchEvent {
  event: string; // start | page | finding | page_error | done | result | error
  [k: string]: unknown;
}

export interface ServiceStatus {
  redis: { connected: boolean; version?: string };
  mongodb: { connected: boolean; version?: string };
  llm_provider?: { connected: boolean; provider: string; model: string; models?: string[] };
}
