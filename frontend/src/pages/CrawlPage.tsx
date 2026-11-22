/**
 * 批量 / 整站爬取 — 指令台 + 全屏接管。
 * 未开始：居中指令台（聚焦光环 + 选项芯片 + 发光 CTA）；
 * 运行中：状态条（流光进度 + 数字滚动）→ 表格式结果流逐行滑入。
 */

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { toast } from "sonner";
import { Globe, Play, Square, Link2, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { api } from "@/api/client";
import type { BatchEvent } from "@/types";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { TopProgressBar } from "@/components/TopProgressBar";
import { AnimatedNumber } from "@/components/AnimatedNumber";
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

const rowVariants: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: Math.min(i, 8) * 0.05, duration: 0.28, ease: "easeOut" } }),
};

export default function CrawlPage() {
  const [seeds, setSeeds] = useState("");
  const [instruction, setInstruction] = useState("");
  const [maxDepth, setMaxDepth] = useState(0);
  const [maxPages, setMaxPages] = useState(20);
  const [sameDomain, setSameDomain] = useState(true);
  const [useJs, setUseJs] = useState(false);

  const [running, setRunning] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [pages, setPages] = useState<PageRow[]>([]);
  const [findings, setFindings] = useState<FindingRow[]>([]);
  const [stats, setStats] = useState<{ pages_crawled: number; findings: number; elapsed: number } | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  // SSE 回调里读 state 会拿到创建时的闭包快照，计数用 ref 兜底
  const pagesCountRef = useRef(0);

  useEffect(() => () => cleanupRef.current?.(), []);

  useEffect(() => {
    pagesCountRef.current = pages.length;
  }, [pages]);

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

  const started = running || pages.length > 0 || findings.length > 0 || !!stats;

  const optionChip = (active: boolean) =>
    cn(
      "flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors",
      active
        ? "border-brand/50 bg-brand/10 text-foreground"
        : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground",
    );

  return (
    <div className="mx-auto max-w-[1100px] p-4 lg:p-8">
      <PageHeader
        icon={Globe}
        eyebrow="采集 · Batch"
        title="批量 / 整站爬取"
        subtitle="并发抓取多个 URL 或按深度跟随链接，可选 AI 结构化提取"
      />

      {/* 指令台 */}
      <AnimatePresence initial={false}>
        {!started && (
          <motion.div
            key="deck"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="mx-auto max-w-2xl"
          >
            <Card className="composer-focus relative overflow-hidden p-6 transition-all duration-300">
              <div className="grid-bg pointer-events-none absolute inset-0 opacity-30" />
              <div className="relative">
                <label className="mb-2 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  <Link2 className="h-3.5 w-3.5 text-brand" /> 起始 URL · 每行一个
                </label>
                <Textarea
                  value={seeds}
                  onChange={(e) => setSeeds(e.target.value)}
                  placeholder={"https://www.anthropic.com\nhttps://www.anthropic.com/news"}
                  className="min-h-[96px] border-0 bg-transparent px-0 font-mono text-xs focus-visible:ring-0"
                  disabled={running}
                />
                <div className="mt-4 rounded-xl border border-border bg-secondary/30 p-4">
                  <label className="mb-2 block text-xs font-medium text-muted-foreground">
                    提取指令（可选，填写则对每页做 AI 结构化提取）
                  </label>
                  <Input
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="留空只抓正文，如：标题、日期、要点"
                    className="h-9 border-border/60 bg-card/60"
                    disabled={running}
                  />
                  <div className="mt-4 flex flex-wrap items-center gap-2.5">
                    <label className="flex items-center gap-1.5 rounded-lg border border-border bg-secondary/40 px-2.5 py-1.5 text-xs text-muted-foreground">
                      深度
                      <Input type="number" min={0} max={5} value={maxDepth} onChange={(e) => setMaxDepth(Number(e.target.value))} className="h-6 w-14 border-0 bg-transparent px-1 text-center font-mono focus-visible:ring-0" disabled={running} />
                    </label>
                    <label className="flex items-center gap-1.5 rounded-lg border border-border bg-secondary/40 px-2.5 py-1.5 text-xs text-muted-foreground">
                      页数
                      <Input type="number" min={1} max={100} value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))} className="h-6 w-14 border-0 bg-transparent px-1 text-center font-mono focus-visible:ring-0" disabled={running} />
                    </label>
                    <button type="button" role="switch" aria-checked={sameDomain} disabled={running} onClick={() => setSameDomain((v) => !v)} className={optionChip(sameDomain)}>
                      仅同域
                    </button>
                    <button type="button" role="switch" aria-checked={useJs} disabled={running} onClick={() => setUseJs((v) => !v)} className={optionChip(useJs)}>
                      JS 渲染
                    </button>
                  </div>
                </div>
                <Button
                  size="lg"
                  className="glow-cta mt-6 h-12 w-full text-base"
                  onClick={handleStart}
                  loading={running}
                  disabled={!seeds.trim()}
                >
                  <Play className="h-4 w-4" /> 开始爬取
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 运行 / 结果视图 */}
      <AnimatePresence>
        {started && (
          <motion.div
            key="runtime"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="space-y-4"
          >
            <Card className="overflow-hidden">
              <TopProgressBar running={running} done={!running && !!stats} />
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3.5">
                {running ? (
                  <span className="flex items-center gap-2 text-sm text-foreground">
                    <Loader2 className="h-4 w-4 animate-spin text-brand" /> 爬取中…
                  </span>
                ) : (
                  <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <CheckCircle2 className="h-4 w-4 text-success" /> 爬取完成
                  </span>
                )}
                <span className="text-sm text-muted-foreground">
                  已抓 <AnimatedNumber value={pages.filter((p) => p.ok).length} className="font-semibold tabular-nums text-foreground" /> 页
                </span>
                <span className="text-sm text-muted-foreground">
                  发现 <AnimatedNumber value={findings.length} className="font-semibold tabular-nums text-foreground" /> 条
                </span>
                {stats && (
                  <span className="text-sm text-muted-foreground">
                    耗时 <span className="font-semibold tabular-nums text-foreground">{stats.elapsed}s</span>
                  </span>
                )}
                <div className="ml-auto flex gap-2">
                  {running && (
                    <Button variant="outline" size="sm" onClick={handleStop}>
                      <Square className="h-3.5 w-3.5" /> 停止
                    </Button>
                  )}
                  {!running && (
                    <Button variant="outline" size="sm" onClick={() => { setPages([]); setFindings([]); setStats(null); }}>
                      新任务
                    </Button>
                  )}
                </div>
              </div>
            </Card>

            <Card className="min-h-[420px] overflow-hidden">
              {pages.length === 0 && findings.length === 0 ? (
                <EmptyState icon={Globe} title={running ? "正在启动…" : "尚无结果"} description={running ? "正在抓取第一个页面" : "在指令台填写 URL 并开始爬取"} />
              ) : (
                <div className="max-h-[600px] overflow-auto">
                  {/* 表格式结果流 */}
                  <div className="divide-y divide-border/60">
                    {pages.map((p, i) => (
                      <motion.div
                        key={`p-${p.url}-${i}`}
                        variants={rowVariants}
                        initial="hidden"
                        animate="show"
                        custom={i}
                        className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-accent/30"
                      >
                        {p.ok ? (
                          <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                        ) : (
                          <XCircle className="h-4 w-4 shrink-0 text-destructive" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[13px] font-medium text-foreground">{p.title || p.url}</p>
                          <p className="truncate font-mono text-[11px] text-muted-foreground">{p.url}</p>
                          {p.error && <p className="truncate text-[11px] text-destructive">{p.error}</p>}
                        </div>
                        {p.ok && p.chars != null && (
                          <Badge variant="outline" className="shrink-0 font-mono">{(p.chars / 1000).toFixed(1)}k</Badge>
                        )}
                      </motion.div>
                    ))}
                  </div>
                  {findings.length > 0 && (
                    <div className="space-y-2 border-t border-border bg-secondary/20 p-3">
                      <p className="px-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                        结构化提取 · {findings.length}
                      </p>
                      {findings.map((f, i) => (
                        <motion.div
                          key={`f-${f.url}-${i}`}
                          variants={rowVariants}
                          initial="hidden"
                          animate="show"
                          custom={i}
                          className="rounded-lg border border-success/20 bg-card p-3"
                        >
                          <div className="mb-1 text-sm font-medium text-foreground">{f.title || f.url}</div>
                          <a href={f.url} target="_blank" rel="noreferrer" className="line-clamp-1 font-mono text-xs text-brand hover:underline">{f.url}</a>
                          {f.data && (
                            <pre className="mt-1.5 max-h-40 overflow-auto rounded bg-secondary p-2 font-mono text-[11px] text-muted-foreground">
                              {JSON.stringify(f.data, null, 2)}
                            </pre>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}