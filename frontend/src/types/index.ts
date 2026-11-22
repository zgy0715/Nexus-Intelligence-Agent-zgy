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
  /** 仅 GET /api/data/{id} 详情返回 */
  raw_html?: string;
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
  /** 仅 assistant：产生该回答的问题（供“重新生成”使用，刷新后仍可用） */
  question?: string;
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
  | {
      type: 'sources';
      sources: Source[];
      relevance: number;
      debug?: Record<string, unknown>;
      /** 模型链路（回答=主模型） */
      models?: { answer?: string };
    }
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
 * 判别式联合：switch (e.type) 时各分支字段类型自动收窄。
 * v3.1：带 model 字段（该事件由哪个模型产生）用于时间线模型徽章。
 */
export type AgentEvent =
  | (AgentEventBase & {
      type: "start";
      goal: string;
      seeds: string[];
      budget_pages: number;
      budget_steps: number;
      main_model?: string;
    })
  | (AgentEventBase & { type: "thought"; text: string; model?: string })
  | (AgentEventBase & { type: "action"; tool: string; args: Record<string, unknown>; model?: string })
  | (AgentEventBase & { type: "observation"; tool: string; result: Record<string, unknown>; model?: string })
  | (AgentEventBase & {
      type: "finding";
      title: string;
      url: string;
      data?: Record<string, unknown>;
      content: string;
      model?: string;
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
      model?: string;
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
      model?: string;
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
  redis: { connected: boolean; version?: string; error?: string };
  mysql: { connected: boolean; version?: string; error?: string };
  llm_provider: {
    connected: boolean;
    provider: string;
    model: string;
    models?: string[];
    error?: string;
  };
  /** 辅助模型（本地 Ollama 等，角色：上下文摘要/查询改写） */
  aux_llm?: {
    connected: boolean;
    provider: string;
    model: string;
    enabled: boolean;
    role?: string;
    error?: string;
  };
}

// ── 定时采集 ──────────────────────────────────────────────────────

export interface SchedulePayload {
  name: string;
  seeds: string[];
  instruction?: string;
  interval_minutes: number;
  max_depth?: number;
  max_pages?: number;
  same_domain_only?: boolean;
  use_js?: boolean;
  enabled?: boolean;
}

export interface Schedule extends SchedulePayload {
  id: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_status?: string;
  created_at?: string;
}

export interface SiteChange {
  id: string;
  url: string;
  title?: string;
  domain?: string;
  version_number?: number;
  created_at?: string;
  old_snippet?: string;
  new_snippet?: string;
}

// ── 图谱 / 成本 ───────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  name: string;
  count?: number;
  domain?: string;
}

export interface GraphLink {
  source: string;
  target: string;
  weight?: number;
}

export interface CrawlGraph {
  domains: { nodes: GraphNode[]; links: GraphLink[] };
  pages: { nodes: GraphNode[]; links: GraphLink[] };
}

export interface CostReport {
  total: { calls: number; prompt_tokens: number; completion_tokens: number; total_tokens: number };
  estimated_cost: number;
  currency: string;
  price_per_m: { input: number; output: number };
  runs: {
    run_id: string;
    goal: string;
    created_at?: string | null;
    total_tokens: number;
    cost: number;
  }[];
}
