/**
 * 自主爬取 Agent 控制台 —— 给定目标与种子，实时观看 Agent 思考/动作/发现，最终生成报告。
 *
 * v3 重构：页面拆分为 features/agent/ 模块
 * - useAgentRun：运行状态机（SSE 消费 / 取消 / 历史回放）
 * - Timeline：虚拟化时间线（不再 slice(-250) 截断 DOM）
 * - BudgetPanel：页面/步数/token/上下文四仪表
 * - FindingsPanel：结构化发现卡片
 * - ReportView：Markdown 报告 + 复制
 * - RunHistory：历史运行一键回放（v3 事件总线）
 */

import { useState } from "react";
import { Bot, History, Lightbulb, Link2, Play, Square, Target } from "lucide-react";
import type { AgentStartParams } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Input";
import { BudgetPanel } from "@/features/agent/BudgetPanel";
import { FindingsPanel } from "@/features/agent/FindingsPanel";
import { ReportView } from "@/features/agent/ReportView";
import { RunHistory } from "@/features/agent/RunHistory";
import { Timeline } from "@/features/agent/Timeline";
import { useAgentRun } from "@/features/agent/useAgentRun";

const EXAMPLES = [
  "收集 Anthropic 官网近期发布的产品与公告，整理成要点",
  "梳理这个文档站点的核心功能模块和使用方法",
  "收集该新闻站点首页关于 AI 的报道标题与摘要",
];

export default function AgentPage() {
  const [goal, setGoal] = useState("");
  const [seeds, setSeeds] = useState("");
  const [maxPages, setMaxPages] = useState(20);
  const [maxDepth, setMaxDepth] = useState(2);
  const [useJs, setUseJs] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const { snapshot, start, cancel, loadReplay } = useAgentRun();
  const running = snapshot.status === "running" || snapshot.status === "starting";
  const busy = snapshot.status === "starting";

  const handleStart = async () => {
    const seedList = seeds
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!goal.trim()) return;
    if (seedList.length === 0) return;
    const params: AgentStartParams = {
      goal: goal.trim(),
      seeds: seedList,
      max_pages: maxPages,
      max_depth: maxDepth,
      use_js: useJs,
    };
    await start(params);
  };

  return (
    <div className="mx-auto max-w-7xl p-4 lg:p-6">
      {/* 标题 */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary shadow-sm">
          <Bot className="h-6 w-6 text-primary-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold text-foreground">自主爬取 Agent</h1>
          <p className="text-sm text-muted-foreground">
            给一个目标和起点，Agent 自主规划、跟随链接、提取并汇总成报告
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setHistoryOpen((v) => !v)}>
          <History className="h-4 w-4" />
          历史运行
        </Button>
      </div>

      {/* 历史运行（回放入口） */}
      {historyOpen && (
        <div className="mb-6">
          <RunHistory
            open={historyOpen}
            onClose={() => setHistoryOpen(false)}
            onReplay={(runId) => loadReplay(runId)}
            activeRunId={snapshot.runId}
          />
        </div>
      )}

      {/* 回放提示条 */}
      {snapshot.replaying && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-2 text-sm text-blue-600 dark:text-blue-400">
          <span>正在回放历史运行 {snapshot.runId?.slice(0, 8)}…（事件来自 Redis 事件总线）</span>
          <button onClick={() => window.location.reload()} className="text-xs underline underline-offset-2">
            退出回放
          </button>
        </div>
      )}

      {/* 配置表单 */}
      <Card className="mb-6 p-5">
        <div className="grid gap-4 lg:grid-cols-2">
          <div>
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
          </div>
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-foreground">
              <Link2 className="h-4 w-4" /> 种子 URL（每行一个）
            </label>
            <Textarea
              value={seeds}
              onChange={(e) => setSeeds(e.target.value)}
              placeholder={"https://example.com\nhttps://example.com/news"}
              className="min-h-[88px] font-mono text-xs"
              disabled={running}
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-4">
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
          <div className="ml-auto flex gap-2">
            {running ? (
              <Button variant="destructive" size="lg" onClick={cancel} disabled={snapshot.status === "starting"}>
                <Square className="h-4 w-4" /> 取消
              </Button>
            ) : (
              <Button size="lg" onClick={handleStart} loading={busy}>
                <Play className="h-4 w-4" /> 启动 Agent
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* 预算仪表盘 */}
      {(snapshot.progress || snapshot.usage) && (
        <div className="mb-6">
          <BudgetPanel
            progress={snapshot.progress}
            usage={snapshot.usage}
            estTokens={snapshot.estTokens}
            compactions={snapshot.compactions}
            compactionSaved={snapshot.compactionSaved}
          />
        </div>
      )}

      {/* 主区：时间线 + 发现侧栏 */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col lg:col-span-2">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            实时活动
            {running && <span className="h-2 w-2 animate-pulse rounded-full bg-success" />}
          </h2>
          <Card className="p-1">
            <Timeline
              events={snapshot.timeline}
              running={running}
              className="h-[560px] px-3 py-2"
            />
          </Card>
        </div>

        <div className="flex min-w-0 flex-col">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Lightbulb className="h-4 w-4" /> 发现（{snapshot.findings.length}）
          </h2>
          <Card className="h-[560px] overflow-hidden p-3">
            <FindingsPanel findings={snapshot.findings} />
          </Card>
        </div>
      </div>

      {/* 最终报告 */}
      {snapshot.report && (
        <div className="mt-6">
          <ReportView report={snapshot.report} reason={snapshot.finishReason} />
        </div>
      )}
    </div>
  );
}
