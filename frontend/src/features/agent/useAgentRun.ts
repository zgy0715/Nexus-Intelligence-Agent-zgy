/**
 * useAgentRun — 自主 Agent 运行状态机。
 *
 * 封装：启动 → SSE 事件流消费 → 状态归约 → 取消 → 历史回放。
 * 事件按后端 seq 递增有序；progress/compaction 归约到面板状态，
 * 其余事件进时间线。回放（loadReplay）静默灌入历史事件，不触发 toast。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { AgentStartParams } from "@/api/client";
import type { AgentEvent, AgentFinding, AgentUsage } from "@/types";

export interface AgentProgress {
  pages_used: number;
  budget_pages: number;
  steps_used: number;
  budget_steps: number;
  findings: number;
  visited: number;
}

export type AgentRunStatus = "idle" | "starting" | "running" | "finished" | "error";

export interface AgentSnapshot {
  status: AgentRunStatus;
  runId: string | null;
  /** 是否处于历史回放展示 */
  replaying: boolean;
  timeline: AgentEvent[];
  findings: AgentFinding[];
  progress: AgentProgress | null;
  usage: AgentUsage | null;
  /** 当前上下文估算 token（后端 ContextManager 估算） */
  estTokens: number;
  compactions: number;
  compactionSaved: number;
  report: string;
  finishReason: string;
  error: string;
}

const INITIAL: AgentSnapshot = {
  status: "idle",
  runId: null,
  replaying: false,
  timeline: [],
  findings: [],
  progress: null,
  usage: null,
  estTokens: 0,
  compactions: 0,
  compactionSaved: 0,
  report: "",
  finishReason: "",
  error: "",
};

// 时间线上限：防止超长任务撑爆内存（后端事件有 seq，这里只做展示裁剪）
const MAX_TIMELINE = 600;

export function useAgentRun() {
  const [snapshot, setSnapshot] = useState<AgentSnapshot>(INITIAL);
  const cleanupRef = useRef<(() => void) | null>(null);

  // 卸载时关闭 SSE，避免 EventSource 泄漏
  useEffect(() => () => cleanupRef.current?.(), []);

  const applyEvent = useCallback((e: AgentEvent, opts?: { silent?: boolean }) => {
    setSnapshot((prev) => {
      const next: AgentSnapshot = { ...prev };
      switch (e.type) {
        case "start":
          next.status = "running";
          next.timeline = [...prev.timeline, e].slice(-MAX_TIMELINE);
          break;
        case "progress":
          next.progress = {
            pages_used: e.pages_used,
            budget_pages: e.budget_pages,
            steps_used: e.steps_used,
            budget_steps: e.budget_steps,
            findings: e.findings,
            visited: e.visited,
          };
          if (e.usage) next.usage = e.usage;
          if (typeof e.est_context_tokens === "number") next.estTokens = e.est_context_tokens;
          break;
        case "compaction":
          next.compactions = e.count;
          next.compactionSaved += e.saved_tokens;
          next.timeline = [...prev.timeline, e].slice(-MAX_TIMELINE);
          break;
        case "finding":
          next.findings = [
            ...prev.findings,
            { title: e.title, url: e.url, data: e.data, content: e.content },
          ];
          next.timeline = [...prev.timeline, e].slice(-MAX_TIMELINE);
          break;
        case "finish": {
          next.report = e.report;
          next.finishReason = e.reason;
          next.status = "finished";
          if (e.usage) next.usage = e.usage;
          // finish 携带完整发现列表，兜底补齐（事件丢失时侧栏不残缺）
          if (Array.isArray(e.findings) && e.findings.length > 0) {
            next.findings = e.findings;
          }
          next.timeline = [...prev.timeline, e].slice(-MAX_TIMELINE);
          if (!opts?.silent) {
            toast.success("Agent 任务完成", { description: e.reason });
          }
          break;
        }
        case "error":
          next.status = "error";
          next.error = e.message;
          next.timeline = [...prev.timeline, e].slice(-MAX_TIMELINE);
          if (!opts?.silent) {
            toast.error("Agent 出错", { description: e.message });
          }
          break;
        default:
          next.timeline = [...prev.timeline, e].slice(-MAX_TIMELINE);
      }
      return next;
    });
  }, []);

  const start = useCallback(
    async (params: AgentStartParams) => {
      cleanupRef.current?.();
      setSnapshot({ ...INITIAL, status: "starting" });
      try {
        const res = await api.startAgent(params);
        setSnapshot((prev) => ({ ...prev, runId: res.run_id, status: "running" }));
        cleanupRef.current = api.subscribeAgent(
          res.run_id,
          (e) => applyEvent(e),
          () => setSnapshot((prev) => (prev.status === "running" ? { ...prev, status: "finished" } : prev)),
          (err) => {
            setSnapshot((prev) => ({ ...prev, error: err }));
            toast.error("事件流中断", { description: err });
          },
        );
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setSnapshot((prev) => ({ ...prev, status: "error", error: message }));
        toast.error("启动失败", { description: message });
      }
    },
    [applyEvent],
  );

  const cancel = useCallback(async () => {
    const runId = snapshot.runId;
    if (!runId) return;
    try {
      await api.cancelAgent(runId);
      toast.info("已请求取消", { description: "Agent 将尽快收尾并生成报告" });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      toast.error("取消失败", { description: message });
    }
  }, [snapshot.runId]);

  const reset = useCallback(() => {
    cleanupRef.current?.();
    setSnapshot(INITIAL);
  }, []);

  /** 历史回放：拉取一次运行的完整事件并静默灌入（报告/发现/时间线全部复原） */
  const loadReplay = useCallback(
    async (runId: string) => {
      cleanupRef.current?.();
      setSnapshot({ ...INITIAL, status: "starting", replaying: true });
      try {
        const replay = await api.getAgentEvents(runId);
        for (const e of replay.events) {
          applyEvent(e, { silent: true });
        }
        setSnapshot((prev) => ({
          ...prev,
          runId,
          status: replay.finished ? "finished" : "running",
          replaying: true,
        }));
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setSnapshot((prev) => ({ ...prev, status: "error", error: message }));
        toast.error("回放加载失败", { description: message });
      }
    },
    [applyEvent],
  );

  return { snapshot, start, cancel, reset, loadReplay };
}
