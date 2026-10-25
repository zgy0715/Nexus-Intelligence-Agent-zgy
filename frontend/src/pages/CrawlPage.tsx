/**
 * 批量 / 整站爬取页面 — 并发抓取多个 URL 或按深度跟随链接，实时进度 + 结构化提取。
 *
 * v3.1 信息架构：左侧固定「启动配置」卡（sticky），右侧结果区（统计条 +
 * 进度/提取 Tab 切换）——配置与结果不再上下堆叠抢视线。
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Globe, Play, Square, Link2, FileText, CheckCircle2, XCircle, Gauge, LayoutList, Lightbulb } from "lucide-react";
import { api } from "@/api/client";
import type { BatchEvent } from "@/types";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { cn } from "@/lib/utils";

interface PageRow {
  url: string;
  title?: string;
  chars?: number;
  ok: boolean;
  error?: string;
}

interface FindingRow {
  url: string;
  title?: string;
  data?: Record<string, unknown>;
}

export default function CrawlPage() {
  const [seeds, setSeeds] = useState("");
  const [instruction, setInstruction] = useState("");
  const [maxDepth, setMaxDepth] = useState(0);
  const [maxPages, setMaxPages] = useState(20);
  const [sameDomain, setSameDomain] = useState(true);
  const [useJs, setUseJs] = useState(false);
  const [tab, setTab] = useState<"pages" | "findings">("pages");

  const [running, setRunning] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [pages, setPages] = useState<PageRow[]>([]);
  const [findings, setFindings] = useState<FindingRow[]>([]);
  const [stats, setStats] = useState<{ pages_crawled: number; findings: number; elapsed: number } | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  // SSE 回调里读 state 会拿到创建时的闭包快照，计数用 ref 兜底
  const pagesCountRef = useRef(0);

  // 卸载时关闭 SSE
  useEffect(() => () => cleanupRef.current?.(), []);

  useEffect(() => {
    pagesCountRef.current = pages.length;
  }, [pages]);

  // 有提取发现到达时自动切到发现 Tab（用户手动切换后不再打扰）
  const autoSwitchRef = useRef(true);
  useEffect(() => {
    if (autoSwitchRef.current && findings.length > 0) setTab("findings");
  }, [findings.length]);

  const handleEvent = (e: BatchEvent) => {
    switch (e.event) {
      case "page":
        setPages((p) => [
          ...p,
          { url: String(e.url), title: e.title as string, chars: e.chars as number, ok: true },
        ]);
        break;
      case "page_error":
        setPages((p) => [...p, { url: String(e.url), ok: false, error: e.error as string }]);
        break;
      case "finding":
        // 引擎会边抓边发 finding，长任务不必等最后一次 result 才能看到结果
        setFindings((f) => [
          ...f,
          { url: String(e.url), title: e.title as string, data: e.data as Record<string, unknown> },
        ]);
        break;
      case "result": {
        const rows = (e.findings as FindingRow[]) || [];
        if (rows.length > 0) {
          setFindings(rows.map((f) => ({ url: f.url, title: f.title, data: f.data })));
        }
        setStats(e.stats as { pages_crawled: number; findings: number; elapsed: number });
        break;
      }
      case "done":
        setStats((prev) => ({
          pages_crawled: (e.pages_crawled as number) ?? prev?.pages_crawled ?? pagesCountRef.current,
          findings: (e.findings as number) ?? prev?.findings ?? 0,
          elapsed: (e.elapsed as number) ?? prev?.elapsed ?? 0,
        }));
        setRunning(false);
        break;
      case "cancelled":
        setRunning(false);
        toast.info("爬取已取消");
        break;
      case "error":
        // 出错必须复位按钮，否则主按钮会永久停在「爬取中…」
        setRunning(false);
        toast.error("爬取出错", { description: e.error as string });
        break;
    }
  };

  const handleStart = async () => {
    const seedList = seeds
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (seedList.length === 0) return toast.error("请至少填写一个 URL");
    if (!Number.isFinite(maxPages) || maxPages < 1) return toast.error("最大页数需要是 ≥1 的整数");
    if (!Number.isFinite(maxDepth) || maxDepth < 0) return toast.error("跟随深度需要是 ≥0 的整数");

    setPages([]);
    setFindings([]);
    setStats(null);
    setTab("pages");
    autoSwitchRef.current = true;

    try {
      const { task_id } = await api.batchCrawl({
        seeds: seedList,
        instruction: instruction.trim(),
        use_js: useJs,
        max_depth: maxDepth,
        max_pages: maxPages,
        same_domain_only: sameDomain,
      });
      setTaskId(task_id);
      setRunning(true);
      cleanupRef.current = api.subscribeBatch(
        task_id,
        handleEvent,
        () => {
          setRunning(false);
          toast.success("爬取完成");
        },
        (err) => {
          setRunning(false);
          toast.error(err);
        },
      );
    } catch (e) {
      setRunning(false);
      toast.error("启动失败", { description: e instanceof Error ? e.message : String(e) });
    }
  };

  const handleStop = async () => {
    if (!taskId) return;
    try {
      const res = await api.cancelBatch(taskId);
      toast.info(res.message);
    } catch (e) {
      toast.error("取消失败", { description: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <div className="mx-auto max-w-7xl p-4 lg:p-6">
      <PageHeader
        icon={Globe}
        title="批量 / 整站爬取"
        subtitle="并发抓取多个 URL 或按深度跟随链接，可选 AI 结构化提取"
      />

      <div className="grid items-start gap-5 lg:grid-cols-[380px_1fr]">
        {/* ── 左：启动配置（sticky） ── */}
        <Card className="p-5 lg:sticky lg:top-4">
          <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-foreground">
            <Link2 className="h-4 w-4" /> 起始 URL（每行一个）
          </label>
          <Textarea
            value={seeds}
            onChange={(e) => setSeeds(e.target.value)}
            placeholder={"https://example.com\nhttps://example.com/page2"}
            className="min-h-[88px] font-mono text-xs"
            disabled={running}
          />

          <label className="mb-1.5 mt-4 flex items-center gap-1.5 text-sm font-medium text-foreground">
            <FileText className="h-4 w-4" /> 提取指令（可选）
          </label>
          <Textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="留空只抓正文；填写则对每页做 AI 结构化提取"
            className="min-h-[72px]"
            disabled={running}
          />

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">跟随深度</label>
              <Input
                type="number"
                min={0}
                max={5}
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                className="h-9"
                disabled={running}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">最大页数</label>
              <Input
                type="number"
                min={1}
                max={100}
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                className="h-9"
                disabled={running}
              />
            </div>
          </div>

          <div className="mt-3 flex gap-4">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={sameDomain}
                onChange={(e) => setSameDomain(e.target.checked)}
                disabled={running}
                className="h-4 w-4 rounded border-border accent-[hsl(var(--primary))]"
              />
              仅同域
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={useJs}
                onChange={(e) => setUseJs(e.target.checked)}
                disabled={running}
                className="h-4 w-4 rounded border-border accent-[hsl(var(--primary))]"
              />
              JS 渲染
            </label>
          </div>

          <div className="mt-5 flex gap-2">
            {running && (
              <Button variant="outline" className="flex-1" onClick={handleStop}>
                <Square className="h-4 w-4" /> 停止
              </Button>
            )}
            <Button className="flex-1" onClick={handleStart} loading={running}>
              <Play className="h-4 w-4" /> {running ? "爬取中…" : "开始爬取"}
            </Button>
          </div>
        </Card>

        {/* ── 右：结果区 ── */}
        <div className="space-y-4">
          {/* 统计条 */}
          <Card className="flex items-center divide-x divide-border p-4">
            <div className="flex flex-1 items-center gap-2.5 px-1">
              <Gauge className="h-4 w-4 text-primary" />
              <div>
                <div className="text-lg font-bold leading-5 tabular-nums">{stats?.pages_crawled ?? pages.filter((p) => p.ok).length}</div>
                <div className="text-[11px] text-muted-foreground">已抓取页面</div>
              </div>
            </div>
            <div className="flex flex-1 items-center gap-2.5 px-4">
              <FileText className="h-4 w-4 text-success" />
              <div>
                <div className="text-lg font-bold leading-5 tabular-nums">{stats?.findings ?? findings.length}</div>
                <div className="text-[11px] text-muted-foreground">提取发现</div>
              </div>
            </div>
            <div className="flex flex-1 items-center gap-2.5 px-4">
              <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
              <div>
                <div className="text-lg font-bold leading-5 tabular-nums">{stats ? `${stats.elapsed}s` : "—"}</div>
                <div className="text-[11px] text-muted-foreground">总耗时</div>
              </div>
            </div>
          </Card>

          {/* Tab：抓取进度 | 提取结果 */}
          <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
            {(
              [
                { key: "pages", label: `抓取进度（${pages.length}）`, icon: LayoutList },
                { key: "findings", label: `提取结果（${findings.length}）`, icon: Lightbulb },
              ] as const
            ).map((t) => (
              <button
                key={t.key}
                onClick={() => {
                  setTab(t.key);
                  autoSwitchRef.current = false; // 用户手动选择后关闭自动切换
                }}
                className={cn(
                  "flex items-center gap-1.5 rounded-[7px] px-3.5 py-1.5 text-sm transition",
                  tab === t.key
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <t.icon className="h-3.5 w-3.5" />
                {t.label}
                {running && tab === t.key && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />}
              </button>
            ))}
          </div>

          <Card className="min-h-[420px] p-3">
            {tab === "pages" ? (
              pages.length === 0 ? (
                <EmptyState icon={Globe} title="尚未开始" description="在左侧填写 URL 并点击「开始爬取」。" />
              ) : (
                <div className="max-h-[560px] space-y-1.5 overflow-auto">
                  {pages.map((p, i) => (
                    <div
                      key={`${p.url}-${i}`}
                      className="flex animate-fade-in items-start gap-2 rounded-lg border border-border bg-background/40 p-2.5"
                    >
                      {p.ok ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                      ) : (
                        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-xs font-medium text-foreground">{p.title || p.url}</div>
                        <div className="truncate text-[11px] text-muted-foreground">{p.url}</div>
                        {p.error && <div className="text-[11px] text-destructive">{p.error}</div>}
                      </div>
                      {p.ok && p.chars != null && <Badge variant="outline">{(p.chars / 1000).toFixed(1)}k</Badge>}
                    </div>
                  ))}
                </div>
              )
            ) : findings.length === 0 ? (
              <p className="px-2 py-16 text-center text-sm text-muted-foreground">
                {instruction.trim() ? "等待提取结果…" : "未填写提取指令，只有抓取进度"}
              </p>
            ) : (
              <div className="max-h-[560px] space-y-2 overflow-auto">
                {findings.map((f, i) => (
                  <div key={`${f.url}-${i}`} className="rounded-lg border border-border bg-background/40 p-3">
                    <div className="mb-1 text-sm font-medium text-foreground">{f.title || f.url}</div>
                    <a href={f.url} target="_blank" rel="noreferrer" className="line-clamp-1 text-xs text-primary hover:underline">
                      {f.url}
                    </a>
                    {f.data && (
                      <pre className="mt-1.5 max-h-40 overflow-auto rounded bg-secondary p-2 text-[11px] text-muted-foreground">
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
    </div>
  );
}
