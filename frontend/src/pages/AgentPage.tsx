/**
 * 自主爬取 Agent 控制台（v3.1 两阶段布局）。
 *
 * 「新建任务 | 历史运行」Tab 二选一：
 * - 新建：idle 时只有一张干净的启动卡（一屏一事）；启动后切换为运行视图
 *   （状态条 + 预算仪表 + 时间线/发现 + 报告）
 * - 历史：运行记录列表，一键回放（复用同一运行视图 + 回放横幅）
 * 时间线每个事件带模型徽章（主力=灰、辅助本地=品牌色）。
 */

import { useMemo, useState } from "react";
import { History, Lightbulb, Link2, Play, Plus, Square, Target } from "lucide-react";
import type { AgentStartParams } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Input";
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
  const auxModel = startEvent && startEvent.type === "start" ? startEvent.aux_model : undefined;
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
    <div className="mx-auto max-w-7xl p-4 lg:p-6">
      <PageHeader
        icon={Target}
        title="自主爬取 Agent"
        subtitle="给定目标与种子，Agent 自主规划、跟随链接、提取并汇总成报告"
        actions={
          mainModel ? (
            <span className="hidden font-mono text-[11px] text-muted-foreground md:inline" title={`主力 ${mainModel}${auxModel ? ` / 辅助 ${auxModel}（本地）` : ""}`}>
              {mainModel}
              {auxModel && <span className="text-brand"> + {auxModel}</span>}
            </span>
          ) : undefined
        }
      />

      {/* 模式切换：新建任务 | 历史运行 */}
      <div className="mb-5 inline-flex rounded-lg border border-border bg-card p-0.5">
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
                if (running && t.key === "history") return; // 运行中不允许切走
                setMode(t.key);
                setHistoryOpen(t.key === "history");
                if (t.key === "new" && snapshot.status === "finished") reset();
              }}
              disabled={running && t.key === "history"}
              className={cn(
                "flex items-center gap-1.5 rounded-[7px] px-3.5 py-1.5 text-sm transition",
                active
                  ? "bg-accent font-medium text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground",
                running && t.key === "history" && "cursor-not-allowed opacity-40",
              )}
            >
              <t.icon className="h-3.5 w-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* ── 历史运行 Tab ── */}
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

      {/* ── 运行视图（新建运行中 / 已完成 / 回放）── */}
      {showRuntime ? (
        <div className="space-y-5">
          {/* 回放横幅 */}
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

          {/* 状态条：进度条 + 状态 + 取消 */}
          <div className="overflow-hidden rounded-xl border bg-card/60">
          <TopProgressBar running={running} />
          <div className="flex items-center gap-3 px-4 py-2.5">
            <Badge variant="outline" className={cn("rounded-full", badge?.className)}>
              {statusText}
            </Badge>
            <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
              {snapshot.error || snapshot.finishReason || snapshot.runId?.slice(0, 8)}
            </span>
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

          {/* 预算仪表 */}
          <BudgetPanel
            progress={snapshot.progress}
            usage={snapshot.usage}
            estTokens={snapshot.estTokens}
            compactions={snapshot.compactions}
            compactionSaved={snapshot.compactionSaved}
          />

          {/* 时间线 + 发现 */}
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="flex min-w-0 flex-col lg:col-span-2">
              <h2 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-foreground">
                实时活动
                {running && <span className="h-2 w-2 animate-pulse rounded-full bg-success" />}
              </h2>
              <Card className="p-1">
                <Timeline
                  events={snapshot.timeline}
                  running={running}
                  auxModel={auxModel}
                  className="h-[520px] px-3 py-2"
                />
              </Card>
            </div>
            <div className="flex min-w-0 flex-col">
              <h2 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Lightbulb className="h-4 w-4" /> 发现（{snapshot.findings.length}）
              </h2>
              <Card className="h-[520px] overflow-hidden p-3">
                <FindingsPanel findings={snapshot.findings} />
              </Card>
            </div>
          </div>

          {/* 报告 */}
          {snapshot.report && (
            <ReportView report={snapshot.report} reason={snapshot.finishReason} />
          )}
        </div>
      ) : mode === "new" ? (
        /* ── 新建任务：干净的启动卡（一屏一事）── */
        <div className="mx-auto max-w-3xl">
          <Card className="p-6">
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-foreground">
              <Target className="h-4 w-4" /> 目标
            </label>
            <Textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="例如：收集某主题近期资讯并整理要点"
              className="min-h-[88px]"
              disabled={running}
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setGoal(ex)}
                  disabled={running}
                  className="rounded-full bg-secondary px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
                >
                  {ex.length > 22 ? ex.slice(0, 22) + "…" : ex}
                </button>
              ))}
            </div>

            <label className="mb-1.5 mt-5 flex items-center gap-1.5 text-sm font-medium text-foreground">
              <Link2 className="h-4 w-4" /> 种子 URL（每行一个）
            </label>
            <Textarea
              value={seeds}
              onChange={(e) => setSeeds(e.target.value)}
              placeholder={"https://example.com\nhttps://example.com/news"}
              className="min-h-[80px] font-mono text-xs"
              disabled={running}
            />

            <div className="mt-5 flex flex-wrap items-end gap-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">最大页数</label>
                <Input
                  type="number"
                  min={1}
                  max={200}
                  value={maxPages}
                  onChange={(e) => setMaxPages(Number(e.target.value))}
                  className="h-9 w-24"
                  disabled={running}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">跟随深度</label>
                <Input
                  type="number"
                  min={0}
                  max={5}
                  value={maxDepth}
                  onChange={(e) => setMaxDepth(Number(e.target.value))}
                  className="h-9 w-24"
                  disabled={running}
                />
              </div>
              <label className="flex h-9 cursor-pointer items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={useJs}
                  onChange={(e) => setUseJs(e.target.checked)}
                  disabled={running}
                  className="h-4 w-4 rounded border-border accent-[hsl(var(--primary))]"
                />
                JS 渲染
              </label>
              <div className="ml-auto">
                <Button size="lg" onClick={handleStart} loading={busy} disabled={!goal.trim() || !seeds.trim()}>
                  <Play className="h-4 w-4" /> 启动 Agent
                </Button>
              </div>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
