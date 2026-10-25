/**
 * RunHistory — 历史运行列表 + 一键回放。
 *
 * 数据来自 GET /api/agent（MySQL agent_runs 表）；点击某条运行调用
 * GET /api/agent/{run_id}/events 把时间线完整复原（v3 事件总线）。
 */

import { useCallback, useEffect, useState } from "react";
import { History, Loader2, RotateCcw, X } from "lucide-react";
import { api } from "@/api/client";
import type { AgentRunSummary } from "@/types";
import { cn } from "@/lib/utils";

interface RunHistoryProps {
  open: boolean;
  onClose: () => void;
  onReplay: (runId: string) => void;
  activeRunId: string | null;
}

const STATUS_VARIANT: Record<string, string> = {
  finished: "text-emerald-500 border-emerald-500/30 bg-emerald-500/10",
  budget_exhausted: "text-amber-500 border-amber-500/30 bg-amber-500/10",
  cancelled: "text-muted-foreground border-border bg-muted",
  no_progress: "text-amber-500 border-amber-500/30 bg-amber-500/10",
  error: "text-destructive border-destructive/30 bg-destructive/10",
  running: "text-blue-500 border-blue-500/30 bg-blue-500/10",
};

function relativeTime(iso: string): string {
  // 后端 utcnow().isoformat() 是无时区标记的 UTC 时间，补 'Z' 防止按本地时间解析（差 8 小时）
  const normalized = /\dZ$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const t = new Date(normalized).getTime();
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  if (diff < 60_000) return "刚刚";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`;
  return `${Math.floor(diff / 86400_000)} 天前`;
}

export function RunHistory({ open, onClose, onReplay, activeRunId }: RunHistoryProps) {
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listAgentRuns(20);
      setRuns(res.runs);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  if (!open) return null;

  return (
    <div className="rounded-xl border bg-card/60">
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm font-medium">
          <History className="h-4 w-4 text-primary" />
          历史运行
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={load}
            className="rounded-md p-1.5 text-muted-foreground transition hover:bg-accent hover:text-foreground"
            title="刷新"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-muted-foreground transition hover:bg-accent hover:text-foreground"
            title="收起"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="max-h-64 overflow-y-auto p-2">
        {error && <p className="px-2 py-3 text-sm text-destructive">{error}</p>}
        {!error && runs.length === 0 && !loading && (
          <p className="px-2 py-3 text-sm text-muted-foreground">还没有运行记录</p>
        )}
        {runs.map((run) => (
          <button
            key={run.run_id}
            onClick={() => {
              onReplay(run.run_id);
              onClose();
            }}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition hover:bg-accent/60",
              run.run_id === activeRunId && "bg-accent",
            )}
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">{run.goal}</p>
              <p className="text-xs text-muted-foreground">
                {relativeTime(run.created_at)} · {run.pages_used} 页 / {run.steps_used} 步
                {run.finding_count !== undefined && run.finding_count > 0 && ` · ${run.finding_count} 发现`}
              </p>
            </div>
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px]",
                STATUS_VARIANT[run.status] || STATUS_VARIANT.cancelled,
              )}
            >
              {run.status}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
