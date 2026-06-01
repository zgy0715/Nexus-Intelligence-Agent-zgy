export interface CrawlResult {
  id: string;
  url: string;
  timestamp: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  extracted_data?: Record<string, unknown>;
  domain?: string;
  title?: string;
  method?: string;
}

export interface Source {
  url: string;
  title?: string;
  snippet?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
}

export interface MonitorStats {
  total_tasks: number;
  success_rate: number;
  llm_calls: number;
  avg_llm_time: number;
  queue_pending: number;
  dead_letter_count: number;
}

export interface ServiceStatus {
  redis: { connected: boolean; version?: string };
  mongodb: { connected: boolean; version?: string };
  ollama: { connected: boolean; version?: string; models?: string[] };
}
