/**
 * 自主爬取 Agent 控制台 — 产品级重排。
 *
 * idle：居中「任务指令台」（大目标输入 + 种子区 + 步进器选项 + 发光 CTA）。
 * running：状态条 + 时间线主栏 / 右侧仪表轨（预算 + 发现）+ 全宽报告。
 * 历史：underline Tab 切换，回放复用运行视图。
 */

import { useMemo, useState } from "react";
import { History, Lightbulb, Link2, Minus, Play, Plus, Square, Target } from "lucide-react";
import type { AgentStartParams } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Input";
import { PageHeader } from "@/components/PageHeader";
import { TopProgressBar } from "@/components/TopProgressBar";
import { Badge } from "@/components/ui/Badge";
import { BudgetPanel } from "@/features/agent/BudgetPanel";
import { FindingsPanel } from "@/features/agent/FindingsPanel";
import { ReportView } from "@/features/agent/ReportView";
import { RunHistory } from "@/features/agent/RunHistory";
import { Timeline } from "@/features/agent/Timeline";
import { useAgentRun } from "@/features/agent/useAgentRun";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "收集 Anthropic 官网近期发布的产品与公告，整理成要点",
  "梳理这个文档站点的核心功能模块和使用方法",
  "收集该新闻站点首页关于 AI 的报道标题与摘要",
];

type Mode = "new" | "history";

const STATUS_BADGE: Record<string, { text: string; className: string }> = {
  running: { text: "运行中", className: "text-blue-500 border-blue-500/30 bg-blue-500/10" },
  finished: { text: "已完成", className: "text-emerald-500 border-emerald-500/30 bg-emerald-500/10" },
  error: { text: "出错", className: "text-destructive border-destructive/30 bg-destructive/10" },
};

function Stepper({
  label,
  value,
  min,
  max,
  onChange,
  disabled,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5 rounded-lg border border-border bg-secondary/40 px-2 py-1.5">
      <span className="mr-1 text-xs text-muted-foreground">{label}</span>
      <button
        type="button"
        disabled={disabled || value <= min}
        onClick={() => onChange(Math.max(min, value - 1))}
        className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground transition hover:bg-accent hover:text-foreground disabled:opacity-40"
        aria-label={`${label}减一`}
      >
        <Minus className="h-3 w-3" />
      </button>
      <span className="w-8 text-center font-mono text-sm tabular-nums text-foreground">{value}</span>
      <button
        type="button"
        disabled={disabled || value >= max}
        onClick={() => onChange(Math.min(max, value + 1))}
        className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground transition hover:bg-accent hover:text-foreground disabled:opacity-40"
        aria-label={`${label}加一`}
      >
        <Plus className="h-3 w-3" />
      </button>
    </div>
  );
}

export default function AgentPage() {
  const [mode, setMode] = useState<Mode>("new");
  const [goal, setGoal] = useState("");
  const [seeds, setSeeds] = useState("");
  const [maxPages, setMaxPages] = useState(20);
  const [maxDepth, setMaxDepth] = useState(2);
  const [useJs, setUseJs] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);

  const { snapshot, start, cancel, reset, loadReplay } = useAgentRun();
  const running = snapshot.status === "running" || snapshot.status === "starting";
  const busy = snapshot.status === "starting";
  const showRuntime = snapshot.replaying || snapshot.status === "running" || snapshot.status === "finished" || snapshot.status === "error";

  const startEvent = useMemo(
    () => snapshot.timeline.find((e) => e.type === "start"),
    [snapshot.timeline],
  );
  const mainModel = startEvent && startEvent.type === "start" ? startEvent.main_model : undefined;

  const handleStart = async () => {
    const seedList = seeds
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!goal.trim() || seedList.length === 0) return;
    const params: AgentStartParams = {
      goal: goal.trim(),
      seeds: seedList,
      max_pages: maxPages,
      max_depth: maxDepth,
      use_js: useJs,
    };
    await start(params);
  };

  const badge = STATUS_BADGE[snapshot.replaying ? "finished" : snapshot.status];
  const statusText = snapshot.replaying ? "回放" : (badge?.text ?? snapshot.status);

  return (
    <div className="mx-auto max-w-[1200px] p-4 lg:p-8">
      <PageHeader
        icon={Target}
        eyebrow="采集 · Autonomous"
        title="自主爬取 Agent"
        subtitle="给定目标与种子，Agent 自主规划、跟随链接、提取并汇总成报告"
        actions={
          mainModel ? (
            <span className="hidden font-mono text-[11px] text-muted-foreground md:inline" title={`主力 ${mainModel}`}>
              {mainModel}
            </span>
          ) : undefined
        }
      />

      {/* underline 模式切换 */}
      <div className="mb-6 flex gap-1 border-b border-border">
        {(
          [
            { key: "new", label: "新建任务", icon: Plus },
            { key: "history", label: "历史运行", icon: History },
          ] as const
        ).map((t) => {
          const active = mode === t.key && !(t.key === "new" && showRuntime);
          return (
            <button
              key={t.key}
              onClick={() => {
                if (running && t.key === "history") return;
                setMode(t.key);
                setHistoryOpen(t.key === "history");
                if (t.key === "new" && snapshot.status === "finished") reset();
              }}
              disabled={running && t.key === "history"}
              className={cn(
                "-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition-colors",
                active
                  ? "border-brand font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
                running && t.key === "history" && "cursor-not-allowed opacity-40",
              )}
            >
              <t.icon className="h-3.5 w-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* ── 历史运行 ── */}
      {mode === "history" && !showRuntime && (
        <div className="mx-auto max-w-3xl">
          <RunHistory
            open={historyOpen}
            onClose={() => setMode("new")}
            onReplay={(runId) => loadReplay(runId)}
            activeRunId={snapshot.runId}
          />
        </div>
      )}

      {/* ── 运行视图 ── */}
      {showRuntime ? (
        <div className="space-y-5">
          {snapshot.replaying && (
            <div className="flex items-center justify-between rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-2 text-sm text-blue-600 dark:text-blue-400">
              <span>正在回放历史运行 {snapshot.runId?.slice(0, 8)}…（事件来自事件总线）</span>
              <button
                onClick={() => {
                  reset();
                  setMode("new");
                }}
                className="text-xs underline underline-offset-2"
              >
                退出回放
              </button>
            </div>
          )}

          {/* 状态条 */}
          <div className="overflow-hidden rounded-xl border bg-card/60">
            <TopProgressBar running={running} />
            <div className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <Badge variant="outline" className={cn("rounded-full", badge?.className)}>
                {statusText}
              </Badge>
              <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
                {snapshot.error || snapshot.finishReason || snapshot.runId?.slice(0, 8)}
              </span>
              {snapshot.usage && (
                <span className="hidden font-mono text-[11px] tabular-nums text-muted-foreground sm:inline">
                  {snapshot.usage.total_tokens.toLocaleString()} tokens
                </span>
              )}
              {!snapshot.replaying && running && (
                <Button variant="destructive" size="sm" onClick={cancel} disabled={busy}>
                  <Square className="h-3.5 w-3.5" /> 取消
                </Button>
              )}
              {!running && !snapshot.replaying && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    reset();
                    setMode("new");
                  }}
                >
                  <Plus className="h-3.5 w-3.5" /> 新任务
                </Button>
              )}
            </div>
          </div>

          {/* 时间线主栏 + 右轨 */}
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="min-w-0">
              <h2 className="mb-2.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                实时活动
                {running && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />}
              </h2>
              <Card className="p-1">
                <Timeline
                  events={snapshot.timeline}
                  running={running}
                  className="h-[560px] px-3 py-2"
                />
              </Card>
            </div>
            <div className="flex min-w-0 flex-col gap-4">
              <BudgetPanel
                progress={snapshot.progress}
                usage={snapshot.usage}
                estTokens={snapshot.estTokens}
                compactions={snapshot.compactions}
                compactionSaved={snapshot.compactionSaved}
                tokenSeries={snapshot.tokenSeries}
                compactionSteps={snapshot.compactionSteps}
              />
              <div className="flex min-h-0 flex-1 flex-col">
                <h2 className="mb-2.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  <Lightbulb className="h-3.5 w-3.5 text-brand" /> 发现（{snapshot.findings.length}）
                </h2>
                <Card className="h-[300px] overflow-hidden p-3 lg:h-auto lg:flex-1">
                  <FindingsPanel findings={snapshot.findings} />
                </Card>
              </div>
            </div>
          </div>

          {snapshot.report && (
            <ReportView report={snapshot.report} reason={snapshot.finishReason} />
          )}
        </div>
      ) : mode === "new" ? (
        /* ── 任务指令台 ── */
        <div className="mx-auto max-w-3xl">
          <Card className="composer-focus relative overflow-hidden p-6 transition-all duration-300 lg:p-8">
            <div className="grid-bg pointer-events-none absolute inset-0 opacity-30" />
            <div className="relative">
              <label className="mb-2 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                <Target className="h-3.5 w-3.5 text-brand" /> 目标
              </label>
              <Textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="用一句话描述要收集什么，例如：收集某主题近期资讯并整理要点"
                className="min-h-[96px] border-0 bg-transparent px-0 text-base focus-visible:ring-0"
                disabled={running}
              />
              <div className="mt-2 flex flex-wrap gap-1.5">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => setGoal(ex)}
                    disabled={running}
                    className="rounded-full border border-border bg-secondary/60 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground disabled:opacity-50"
                  >
                    {ex.length > 22 ? ex.slice(0, 22) + "…" : ex}
                  </button>
                ))}
              </div>

              <div className="mt-6 rounded-xl border border-border bg-secondary/30 p-4">
                <label className="mb-2 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  <Link2 className="h-3.5 w-3.5 text-brand" /> 种子 URL · 每行一个
                </label>
                <Textarea
                  value={seeds}
                  onChange={(e) => setSeeds(e.target.value)}
                  placeholder={"https://example.com\nhttps://example.com/news"}
                  className="min-h-[72px] border-border/60 bg-card/60 font-mono text-xs"
                  disabled={running}
                />
                <div className="mt-4 flex flex-wrap items-center gap-2.5">
                  <Stepper label="页数" value={maxPages} min={1} max={200} onChange={setMaxPages} disabled={running} />
                  <Stepper label="深度" value={maxDepth} min={0} max={5} onChange={setMaxDepth} disabled={running} />
                  <button
                    type="button"
                    role="switch"
                    aria-checked={useJs}
                    disabled={running}
                    onClick={() => setUseJs((v) => !v)}
                    className={cn(
                      "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition-colors",
                      useJs
                        ? "border-brand/50 bg-brand/10 text-foreground"
                        : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <span className={cn("relative h-3.5 w-6 rounded-full transition-colors", useJs ? "bg-brand" : "bg-muted")}>
                      <span className={cn("absolute top-0.5 h-2.5 w-2.5 rounded-full bg-card transition-all", useJs ? "left-[13px]" : "left-0.5")} />
                    </span>
                    JS 渲染
                  </button>
                </div>
              </div>

              <Button
                size="lg"
                className="glow-cta mt-6 h-12 w-full text-base"
                onClick={handleStart}
                loading={busy}
                disabled={!goal.trim() || !seeds.trim()}
              >
                <Play className="h-4 w-4" /> 启动 Agent
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}