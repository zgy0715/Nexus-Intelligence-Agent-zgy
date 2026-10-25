/**
 * Timeline — 虚拟化 Agent 事件时间线。
 *
 * 用 @tanstack/react-virtual 渲染可变高度的虚拟列表（替换旧版 slice(-250) 截断 +
 * 全量 DOM 渲染），配合 measureElement 支持展开/折叠后的高度回收。
 * 运行中自动吸附底部；用户向上滚动即暂停吸附（不抢滚动条）。
 */

import { useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { AnimatePresence, motion } from "motion/react";
import ReactMarkdown from "react-markdown";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Eye,
  Lightbulb,
  Play,
  Sparkles,
  Target,
  Wrench,
  Brain,
} from "lucide-react";
import type { AgentEvent } from "@/types";
import { cn } from "@/lib/utils";
import { TypewriterText } from "./TypewriterText";

interface TimelineProps {
  events: AgentEvent[];
  running: boolean;
  className?: string;
}

/** 进度事件只驱动仪表盘，不进时间线 */
const isTimelineEvent = (e: AgentEvent) => e.type !== "progress";

export function Timeline({ events, running, className }: TimelineProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  const rows = events.filter(isTimelineEvent);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 64,
    overscan: 8,
    getItemKey: (i) => {
      const e = rows[i];
      return `${e?.type ?? "?"}-${e?.seq ?? i}`;
    },
  });

  // 运行中且用户停在底部时自动吸附最新事件
  useEffect(() => {
    if (!running || !atBottom || rows.length === 0) return;
    const el = parentRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight });
    });
  }, [rows.length, running, atBottom]);

  const handleScroll = () => {
    const el = parentRef.current;
    if (!el) return;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  };

  const lastEvent = rows.length > 0 ? rows[rows.length - 1] : undefined;
  const lastSeq = lastEvent ? lastEvent.seq : -1;

  return (
    <div
      ref={parentRef}
      onScroll={handleScroll}
      className={cn("relative overflow-y-auto", className)}
    >
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((vi) => {
          const e = rows[vi.index];
          if (!e) return null;
          const isLast = e.seq === lastSeq;
          return (
            <div
              key={vi.key}
              data-index={vi.index}
              ref={virtualizer.measureElement}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${vi.start}px)`,
              }}
            >
              <EventRow event={e} animate={isLast && running} />
            </div>
          );
        })}
      </div>
      {rows.length === 0 && (
        <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Play className="h-8 w-8 opacity-30" />
          <p className="text-sm">填写目标与种子 URL，点击「启动 Agent」开始自主探索。</p>
        </div>
      )}
      {!atBottom && running && (
        <button
          onClick={() => {
            const el = parentRef.current;
            if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
            setAtBottom(true);
          }}
          className="sticky bottom-2 left-full mr-2 rounded-full border bg-background/90 px-3 py-1 text-xs shadow backdrop-blur transition hover:bg-accent"
        >
          回到最新 ↓
        </button>
      )}
    </div>
  );
}

// ── 单行渲染 ─────────────────────────────────────────────────────

function EventRow({ event: e, animate }: { event: AgentEvent; animate: boolean }) {
  return (
    <motion.div
      initial={animate ? { opacity: 0, y: 8 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="px-1 py-1.5"
    >
      {e.type === "start" && <StartRow event={e} />}
      {e.type === "thought" && <ThoughtRow event={e} />}
      {e.type === "action" && <ActionRow event={e} />}
      {e.type === "observation" && <ObservationRow event={e} />}
      {e.type === "finding" && <FindingRow event={e} />}
      {e.type === "compaction" && <CompactionRow event={e} />}
      {e.type === "finish" && <FinishRow event={e} />}
      {e.type === "error" && <ErrorRow event={e} />}
    </motion.div>
  );
}

function RowShell({
  icon,
  tint,
  label,
  children,
}: {
  icon: React.ReactNode;
  tint: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-2.5">
      <div className={cn("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border", tint)}>
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        {children}
      </div>
    </div>
  );
}

function StartRow({ event: e }: { event: Extract<AgentEvent, { type: "start" }> }) {
  return (
    <RowShell icon={<Target className="h-3.5 w-3.5" />} tint="border-primary/40 bg-primary/10 text-primary" label="开始">
      <p className="text-sm">{e.goal}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        预算：{e.budget_pages} 页 / {e.budget_steps} 步 · 种子 {e.seeds.length} 个
      </p>
    </RowShell>
  );
}

function ThoughtRow({ event: e, typewriter }: { event: Extract<AgentEvent, { type: "thought" }>; typewriter?: boolean }) {
  return (
    <RowShell icon={<Brain className="h-3.5 w-3.5" />} tint="border-border bg-muted text-foreground" label="思考">
      {typewriter ? (
        <TypewriterText text={e.text} className="text-sm leading-relaxed" />
      ) : (
        <div className="markdown text-sm leading-relaxed text-foreground/90">
          <ReactMarkdown>{e.text}</ReactMarkdown>
        </div>
      )}
    </RowShell>
  );
}

function ActionRow({ event: e }: { event: Extract<AgentEvent, { type: "action" }> }) {
  const argsBrief = formatArgs(e.args);
  return (
    <RowShell icon={<Wrench className="h-3.5 w-3.5" />} tint="border-blue-500/30 bg-blue-500/10 text-blue-500" label={`动作 · ${e.tool}`}>
      <code className="block truncate font-mono text-xs text-muted-foreground">{argsBrief}</code>
    </RowShell>
  );
}

function ObservationRow({ event: e }: { event: Extract<AgentEvent, { type: "observation" }> }) {
  const [open, setOpen] = useState(false);
  const brief = observationBrief(e.result);
  return (
    <div className="flex gap-2.5 pl-4">
      <div className="flex flex-col items-center">
        <div className="flex h-5 w-5 items-center justify-center rounded border border-border bg-muted/50 text-muted-foreground">
          <Eye className="h-3 w-3" />
        </div>
        <div className="mt-1 w-px flex-1 bg-border" />
      </div>
      <div className="min-w-0 flex-1 pb-1">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-1 text-left text-xs text-muted-foreground transition hover:text-foreground"
        >
          <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
          <span className="truncate">{brief}</span>
        </button>
        <AnimatePresence initial={false}>
          {open && (
            <motion.pre
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="mt-1 max-h-64 overflow-auto rounded-md border bg-muted/40 p-2 font-mono text-[11px] leading-relaxed"
            >
              {JSON.stringify(e.result, null, 2)}
            </motion.pre>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function FindingRow({ event: e }: { event: Extract<AgentEvent, { type: "finding" }> }) {
  return (
    <RowShell icon={<Lightbulb className="h-3.5 w-3.5" />} tint="border-amber-500/40 bg-amber-500/10 text-amber-500" label="发现">
      <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-2.5 py-2">
        <p className="text-sm font-medium">{e.title || "（无标题）"}</p>
        {e.url && (
          <a href={e.url} target="_blank" rel="noreferrer" className="mt-0.5 block truncate text-xs text-muted-foreground hover:text-foreground">
            {e.url}
          </a>
        )}
        {e.content && <p className="mt-1 line-clamp-3 text-xs text-foreground/80">{e.content}</p>}
      </div>
    </RowShell>
  );
}

function CompactionRow({ event: e }: { event: Extract<AgentEvent, { type: "compaction" }> }) {
  return (
    <RowShell icon={<Sparkles className="h-3.5 w-3.5" />} tint="border-violet-500/30 bg-violet-500/10 text-violet-500" label="上下文压缩">
      <p className="text-xs text-muted-foreground">
        历史步骤已滚动压缩，释放约 {e.saved_tokens.toLocaleString()} tokens（第 {e.count} 次）
      </p>
    </RowShell>
  );
}

function FinishRow({ event: e }: { event: Extract<AgentEvent, { type: "finish" }> }) {
  return (
    <RowShell icon={<CheckCircle2 className="h-3.5 w-3.5" />} tint="border-emerald-500/40 bg-emerald-500/10 text-emerald-500" label="完成">
      <p className="text-sm">
        {e.reason} · {e.finding_count} 条发现 · {e.pages_used} 页
      </p>
    </RowShell>
  );
}

function ErrorRow({ event: e }: { event: Extract<AgentEvent, { type: "error" }> }) {
  return (
    <RowShell icon={<AlertCircle className="h-3.5 w-3.5" />} tint="border-destructive/40 bg-destructive/10 text-destructive" label="出错">
      <p className="text-sm text-destructive">{e.message}</p>
    </RowShell>
  );
}

// ── 工具函数 ─────────────────────────────────────────────────────

function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args || {});
  if (entries.length === 0) return "{}";
  return entries
    .map(([k, v]) => {
      const s = typeof v === "string" ? v : JSON.stringify(v);
      return `${k}=${s && s.length > 80 ? s.slice(0, 80) + "…" : s}`;
    })
    .join(", ");
}

function observationBrief(result: Record<string, unknown>): string {
  if (!result || typeof result !== "object") return "（空结果）";
  if (result.ok === false) {
    const err = (result.error || result.message || "失败") as string;
    return `✗ ${err}`;
  }
  const parts: string[] = [];
  for (const key of ["title", "url", "summary", "chars", "num_links", "note", "message"]) {
    const v = result[key];
    if (v !== undefined && v !== null && v !== "") {
      const s = String(v);
      parts.push(s.length > 120 ? s.slice(0, 120) + "…" : s);
    }
  }
  if (Array.isArray(result.pages)) parts.push(`共 ${result.pages.length} 页`);
  return parts.join(" · ") || "完成";
}
