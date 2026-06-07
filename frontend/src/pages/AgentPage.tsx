/**
 * 自主爬取 Agent 控制台 —— 给定目标与种子，实时观看 Agent 思考/动作/发现，最终生成报告。
 */

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import {
  Bot,
  Brain,
  Wrench,
  Eye,
  Lightbulb,
  Play,
  Square,
  Link2,
  FileText,
  Target,
  Copy,
  Check,
  AlertCircle,
} from "lucide-react";
import { api } from "@/api/client";
import type { AgentEvent, AgentFinding } from "@/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/utils";

interface TimelineItem extends AgentEvent {
  _id: number;
}

interface Progress {
  pages_used: number;
  budget_pages: number;
  steps_used: number;
  budget_steps: number;
  findings: number;
  visited: number;
}

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

  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [findings, setFindings] = useState<AgentFinding[]>([]);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [report, setReport] = useState("");
  const [finishReason, setFinishReason] = useState("");
  const [copied, setCopied] = useState(false);

  const idRef = useRef(0);
  const cleanupRef = useRef<(() => void) | null>(null);

  // 卸载时关闭 SSE，避免 EventSource 泄漏
  useEffect(() => () => cleanupRef.current?.(), []);

  const push = (e: AgentEvent) =>
    setTimeline((t) => [...t, { ...e, _id: idRef.current++ }].slice(-250));

  const handleEvent = (e: AgentEvent) => {
    switch (e.type) {
      case "progress":
        setProgress({
          pages_used: e.pages_used ?? 0,
          budget_pages: e.budget_pages ?? 0,
          steps_used: e.steps_used ?? 0,
          budget_steps: e.budget_steps ?? 0,
          findings: typeof e.findings === "number" ? e.findings : 0,
          visited: e.visited ?? 0,
        });
        break;
      case "finding":
        setFindings((f) => [...f, { title: e.title, url: e.url, data: e.data, content: e.content }]);
        push(e);
        break;
      case "finish":
        setReport(e.report ?? "");
        setFinishReason(e.reason ?? "");
        setRunning(false);
        push(e);
        toast.success("Agent 任务完成", { description: e.reason });
        break;
      case "error":
        push(e);
        toast.error("Agent 出错", { description: e.message });
        break;
      default:
        push(e);
    }
  };

  const handleStart = async () => {
    const seedList = seeds
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!goal.trim()) return toast.error("请填写目标");
    if (seedList.length === 0) return toast.error("请至少填写一个种子 URL");

    setTimeline([]);
    setFindings([]);
    setReport("");
    setProgress(null);
    setFinishReason("");
    idRef.current = 0;
    setStarting(true);

    try {
      const { run_id } = await api.startAgent({
        goal: goal.trim(),
        seeds: seedList,
        max_pages: maxPages,
        max_depth: maxDepth,
        use_js: useJs,
      });
      setRunId(run_id);
      setRunning(true);
      cleanupRef.current = api.subscribeAgent(
        run_id,
        handleEvent,
        () => setRunning(false),
        (err) => {
          setRunning(false);
          toast.error(err);
        },
      );
    } catch (e) {
      toast.error("启动失败", { description: e instanceof Error ? e.message : String(e) });
    } finally {
      setStarting(false);
    }
  };

  const handleCancel = async () => {
    if (!runId) return;
    try {
      await api.cancelAgent(runId);
      toast("已请求取消，Agent 正在收尾…");
    } catch {
      /* ignore */
    }
  };

  const copyReport = () => {
    navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const pagePct = progress && progress.budget_pages ? (progress.pages_used / progress.budget_pages) * 100 : 0;
  const stepPct = progress && progress.budget_steps ? (progress.steps_used / progress.budget_steps) * 100 : 0;

  return (
    <div className="mx-auto max-w-7xl p-4 lg:p-6">
      {/* 标题 */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary shadow-sm">
          <Bot className="h-6 w-6 text-primary-foreground" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">自主爬取 Agent</h1>
          <p className="text-sm text-muted-foreground">
            给一个目标和起点，Agent 自主规划、跟随链接、提取并汇总成报告
          </p>
        </div>
      </div>

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
              <Button variant="destructive" size="lg" onClick={handleCancel}>
                <Square className="h-4 w-4" /> 取消
              </Button>
            ) : (
              <Button size="lg" onClick={handleStart} loading={starting}>
                <Play className="h-4 w-4" /> 启动 Agent
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* 进度条 */}
      {progress && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatBar label="页面预算" value={`${progress.pages_used}/${progress.budget_pages}`} pct={pagePct} />
          <StatBar label="步数预算" value={`${progress.steps_used}/${progress.budget_steps}`} pct={stepPct} />
          <StatTile label="已访问页面" value={progress.visited} />
          <StatTile label="发现条数" value={progress.findings} />
        </div>
      )}

      {/* 主区：时间线 + 侧栏 */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* 事件时间线 */}
        <div className="lg:col-span-2">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Brain className="h-4 w-4" /> 实时活动
            {running && <span className="h-2 w-2 animate-pulse rounded-full bg-success" />}
          </h2>
          <Card className="max-h-[600px] min-h-[300px] overflow-auto p-4">
            {timeline.length === 0 ? (
              <EmptyState
                icon={Bot}
                title="Agent 待命中"
                description="填写目标与种子 URL，点击「启动 Agent」开始自主探索。"
              />
            ) : (
              <div className="space-y-2">
                {timeline.map((item) => (
                  <TimelineRow key={item._id} item={item} />
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 发现侧栏 */}
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Lightbulb className="h-4 w-4" /> 发现（{findings.length}）
          </h2>
          <Card className="max-h-[600px] min-h-[300px] overflow-auto p-3">
            {findings.length === 0 ? (
              <p className="px-2 py-8 text-center text-sm text-muted-foreground">尚无发现</p>
            ) : (
              <div className="space-y-2">
                {findings.map((f, i) => (
                  <div key={i} className="rounded-lg border border-border bg-background/50 p-3">
                    <div className="mb-1 text-sm font-medium text-foreground">
                      {f.title || "（无标题）"}
                    </div>
                    {f.url && (
                      <a
                        href={f.url}
                        target="_blank"
                        rel="noreferrer"
                        className="line-clamp-1 text-xs text-primary hover:underline"
                      >
                        {f.url}
                      </a>
                    )}
                    {f.content && (
                      <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">{f.content}</p>
                    )}
                    {f.data && Object.keys(f.data).length > 0 && (
                      <pre className="mt-1.5 max-h-28 overflow-auto rounded bg-secondary p-2 text-[11px] text-muted-foreground">
                        {JSON.stringify(f.data, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* 最终报告 */}
      {report && (
        <Card className="mt-6 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
              <FileText className="h-5 w-5" /> 情报报告
              {finishReason && <Badge variant="secondary">{finishReason}</Badge>}
            </h2>
            <Button variant="outline" size="sm" onClick={copyReport}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "已复制" : "复制"}
            </Button>
          </div>
          <div className="markdown">
            <ReactMarkdown>{report}</ReactMarkdown>
          </div>
        </Card>
      )}
    </div>
  );
}

// ── 时间线单行 ───────────────────────────────────────────────────

function TimelineRow({ item }: { item: TimelineItem }) {
  const meta = rowMeta(item);
  return (
    <div className={cn("flex animate-fade-in gap-3 rounded-lg border p-3", meta.box)}>
      <div className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", meta.iconBg)}>
        <meta.Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 text-xs font-medium text-muted-foreground">{meta.label}</div>
        <div className="text-sm text-foreground">{meta.body}</div>
      </div>
    </div>
  );
}

function rowMeta(item: TimelineItem) {
  switch (item.type) {
    case "start":
      return {
        Icon: Target,
        label: "开始",
        iconBg: "bg-accent text-accent-foreground",
        box: "border-border bg-background/40",
        body: <span className="text-muted-foreground">{item.goal}</span>,
      };
    case "thought":
      return {
        Icon: Brain,
        label: "思考",
        iconBg: "bg-accent text-accent-foreground",
        box: "border-border bg-background/40",
        body: <span className="italic text-foreground/90">{item.text}</span>,
      };
    case "action":
      return {
        Icon: Wrench,
        label: "动作",
        iconBg: "bg-primary/15 text-primary",
        box: "border-primary/20 bg-primary/5",
        body: (
          <span>
            <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs">{item.tool}</code>
            <span className="ml-2 text-xs text-muted-foreground">{summarizeArgs(item.args)}</span>
          </span>
        ),
      };
    case "observation":
      return {
        Icon: Eye,
        label: "观察",
        iconBg: "bg-secondary text-muted-foreground",
        box: "border-border bg-background/40",
        body: <span className="text-xs text-muted-foreground">{summarizeArgs(item.result)}</span>,
      };
    case "finding":
      return {
        Icon: Lightbulb,
        label: "发现",
        iconBg: "bg-success/15 text-success",
        box: "border-success/30 bg-success/5",
        body: <span className="font-medium text-foreground">{item.title || item.url}</span>,
      };
    case "finish":
      return {
        Icon: Check,
        label: "完成",
        iconBg: "bg-success/15 text-success",
        box: "border-success/30 bg-success/5",
        body: <span className="text-muted-foreground">{item.reason}</span>,
      };
    case "error":
      return {
        Icon: AlertCircle,
        label: "错误",
        iconBg: "bg-destructive/15 text-destructive",
        box: "border-destructive/30 bg-destructive/5",
        body: <span className="text-destructive">{item.message}</span>,
      };
    default:
      return {
        Icon: Eye,
        label: item.type,
        iconBg: "bg-secondary text-muted-foreground",
        box: "border-border",
        body: null,
      };
  }
}

function summarizeArgs(obj?: Record<string, unknown>): string {
  if (!obj) return "";
  const parts: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    if (k === "ok") continue;
    let val = typeof v === "string" ? v : JSON.stringify(v);
    if (val && val.length > 70) val = val.slice(0, 70) + "…";
    parts.push(`${k}: ${val}`);
  }
  return parts.join("  ·  ");
}

// ── 进度小组件 ───────────────────────────────────────────────────

function StatBar({ label, value, pct }: { label: string; value: string; pct: number }) {
  return (
    <Card className="p-3">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs font-medium text-foreground">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </Card>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-bold text-foreground">{value}</div>
    </Card>
  );
}
