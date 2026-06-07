/**
 * 批量 / 整站爬取页面 — 并发抓取多个 URL 或按深度跟随链接，实时进度 + 结构化提取
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Globe, Play, Link2, FileText, CheckCircle2, XCircle, Gauge } from "lucide-react";
import { api } from "@/api/client";
import type { BatchEvent } from "@/types";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";

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

  const [running, setRunning] = useState(false);
  const [pages, setPages] = useState<PageRow[]>([]);
  const [findings, setFindings] = useState<FindingRow[]>([]);
  const [stats, setStats] = useState<{ pages_crawled: number; findings: number; elapsed: number } | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // 卸载时关闭 SSE
  useEffect(() => () => cleanupRef.current?.(), []);

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
      case "result":
        setFindings(((e.findings as FindingRow[]) || []).map((f) => ({ url: f.url, title: f.title, data: f.data })));
        setStats(e.stats as { pages_crawled: number; findings: number; elapsed: number });
        break;
      case "done":
        setStats({
          pages_crawled: (e.pages_crawled as number) ?? pages.length,
          findings: (e.findings as number) ?? 0,
          elapsed: (e.elapsed as number) ?? 0,
        });
        break;
      case "error":
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

    setPages([]);
    setFindings([]);
    setStats(null);

    try {
      const { task_id } = await api.batchCrawl({
        seeds: seedList,
        instruction: instruction.trim(),
        use_js: useJs,
        max_depth: maxDepth,
        max_pages: maxPages,
        same_domain_only: sameDomain,
      });
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
      toast.error("启动失败", { description: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <div className="mx-auto max-w-6xl p-4 lg:p-6">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary shadow-sm">
          <Globe className="h-6 w-6 text-primary-foreground" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">批量 / 整站爬取</h1>
          <p className="text-sm text-muted-foreground">并发抓取多个 URL，或按深度跟随链接，可选 AI 结构化提取</p>
        </div>
      </div>

      <Card className="mb-6 p-5">
        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-foreground">
              <Link2 className="h-4 w-4" /> 起始 URL（每行一个）
            </label>
            <Textarea
              value={seeds}
              onChange={(e) => setSeeds(e.target.value)}
              placeholder={"https://example.com\nhttps://example.com/page2"}
              className="min-h-[96px] font-mono text-xs"
              disabled={running}
            />
          </div>
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-foreground">
              <FileText className="h-4 w-4" /> 提取指令（可选）
            </label>
            <Textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="留空则只抓取正文；填写则对每页做 AI 结构化提取，如：标题、日期、作者、要点"
              className="min-h-[96px]"
              disabled={running}
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-4">
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
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">最大页数</label>
            <Input
              type="number"
              min={1}
              max={100}
              value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value))}
              className="h-9 w-24"
              disabled={running}
            />
          </div>
          <label className="flex h-9 cursor-pointer items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={sameDomain}
              onChange={(e) => setSameDomain(e.target.checked)}
              disabled={running}
              className="h-4 w-4 rounded border-border accent-[hsl(var(--primary))]"
            />
            仅同域
          </label>
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
            <Button onClick={handleStart} loading={running}>
              <Play className="h-4 w-4" /> {running ? "爬取中…" : "开始爬取"}
            </Button>
          </div>
        </div>
      </Card>

      {stats && (
        <div className="mb-6 grid grid-cols-3 gap-3">
          <Card className="flex items-center gap-3 p-4">
            <Gauge className="h-5 w-5 text-primary" />
            <div>
              <div className="text-xl font-bold text-foreground">{stats.pages_crawled}</div>
              <div className="text-xs text-muted-foreground">已抓取页面</div>
            </div>
          </Card>
          <Card className="flex items-center gap-3 p-4">
            <FileText className="h-5 w-5 text-success" />
            <div>
              <div className="text-xl font-bold text-foreground">{stats.findings}</div>
              <div className="text-xs text-muted-foreground">提取发现</div>
            </div>
          </Card>
          <Card className="flex items-center gap-3 p-4">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            <div>
              <div className="text-xl font-bold text-foreground">{stats.elapsed}s</div>
              <div className="text-xs text-muted-foreground">总耗时</div>
            </div>
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 抓取进度 */}
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            抓取进度（{pages.length}）
            {running && <span className="h-2 w-2 animate-pulse rounded-full bg-success" />}
          </h2>
          <Card className="max-h-[520px] min-h-[240px] overflow-auto p-3">
            {pages.length === 0 ? (
              <EmptyState icon={Globe} title="尚未开始" description="填写 URL 后点击开始爬取。" />
            ) : (
              <div className="space-y-1.5">
                {pages.map((p, i) => (
                  <div
                    key={i}
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
                    {p.ok && p.chars != null && (
                      <Badge variant="outline">{(p.chars / 1000).toFixed(1)}k</Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 提取结果 */}
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            提取结果（{findings.length}）
          </h2>
          <Card className="max-h-[520px] min-h-[240px] overflow-auto p-3">
            {findings.length === 0 ? (
              <p className="px-2 py-12 text-center text-sm text-muted-foreground">
                {instruction.trim() ? "等待提取结果…" : "未填写提取指令"}
              </p>
            ) : (
              <div className="space-y-2">
                {findings.map((f, i) => (
                  <div key={i} className="rounded-lg border border-border bg-background/40 p-3">
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
