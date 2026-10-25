/**
 * 批量 / 整站爬取（v4）— 指令台 + 全屏接管。
 * 未开始：居中指令台（发光输入卡 + chips 选项 + 发光 CTA）；
 * 运行中：指令台收起为状态条（顶部流光进度条 + 数字滚动计数）→ 结果流逐行滑入。
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

  // 卸载时关闭 SSE
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

  return (
    <div className="mx-auto max-w-5xl p-4 lg:p-6">
      <PageHeader
        icon={Globe}
        title="批量 / 整站爬取"
        subtitle="并发抓取多个 URL 或按深度跟随链接，可选 AI 结构化提取"
      />

      {/* 指令台（未开始时居中展示；启动后收起） */}
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
            <Card className="deck-focus mt-8 p-6 transition-all duration-300">
              <label className="mb-2 flex items-center gap-1.5 text-sm font-medium text-foreground">
                <Link2 className="h-4 w-4" /> 起始 URL（每行一个）
              </label>
              <Textarea
                value={seeds}
                onChange={(e) => setSeeds(e.target.value)}
                placeholder={"https://www.anthropic.com\nhttps://www.anthropic.com/news"}
                className="min-h-[96px] border-border/70 bg-background/50 font-mono text-xs"
                disabled={running}
              />
              <label className="mb-2 mt-4 block text-xs font-medium text-muted-foreground">
                提取指令（可选，填写则对每页做 AI 结构化提取）
              </label>
              <Input
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="留空只抓正文，如：标题、日期、要点"
                className="h-9"
                disabled={running}
              />
              <div className="mt-5 flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  深度
                  <Input type="number" min={0} max={5} value={maxDepth} onChange={(e) => setMaxDepth(Number(e.target.value))} className="h-8 w-16" disabled={running} />
                </label>
                <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  页数
                  <Input type="number" min={1} max={100} value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))} className="h-8 w-16" disabled={running} />
                </label>
                <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                  <input type="checkbox" checked={sameDomain} onChange={(e) => setSameDomain(e.target.checked)} disabled={running} className="h-3.5 w-3.5 rounded accent-[hsl(var(--primary))]" />
                  仅同域
                </label>
                <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                  <input type="checkbox" checked={useJs} onChange={(e) => setUseJs(e.target.checked)} disabled={running} className="h-3.5 w-3.5 rounded accent-[hsl(var(--primary))]" />
                  JS 渲染
                </label>
              </div>
              <Button
                size="lg"
                className="glow-cta mt-6 w-full text-base"
                onClick={handleStart}
                loading={running}
                disabled={!seeds.trim()}
              >
                <Play className="h-4 w-4" /> 开始爬取
              </Button>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 运行/结果视图（全屏接管） */}
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

            <Card className="min-h-[420px] p-3">
              {pages.length === 0 && findings.length === 0 ? (
                <EmptyState icon={Globe} title={running ? "正在启动…" : "尚无结果"} description={running ? "正在抓取第一个页面" : "在指令台填写 URL 并开始爬取"} />
              ) : (
                <div className="max-h-[600px] space-y-1.5 overflow-auto p-1">
                  {pages.map((p, i) => (
                    <motion.div key={`p-${p.url}-${i}`} variants={rowVariants} initial="hidden" animate="show" custom={i}
                      className="flex items-start gap-2 rounded-lg border border-border/70 bg-background/40 p-2.5">
                      {p.ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-xs font-medium text-foreground">{p.title || p.url}</div>
                        <div className="truncate text-[11px] text-muted-foreground">{p.url}</div>
                        {p.error && <div className="text-[11px] text-destructive">{p.error}</div>}
                      </div>
                      {p.ok && p.chars != null && <Badge variant="outline">{(p.chars / 1000).toFixed(1)}k</Badge>}
                    </motion.div>
                  ))}
                  {findings.map((f, i) => (
                    <motion.div key={`f-${f.url}-${i}`} variants={rowVariants} initial="hidden" animate="show" custom={i}
                      className="rounded-lg border border-success/20 bg-success/5 p-3">
                      <div className="mb-1 text-sm font-medium text-foreground">{f.title || f.url}</div>
                      <a href={f.url} target="_blank" rel="noreferrer" className="line-clamp-1 text-xs text-primary hover:underline">{f.url}</a>
                      {f.data && (
                        <pre className="mt-1.5 max-h-40 overflow-auto rounded bg-secondary p-2 text-[11px] text-muted-foreground">
                          {JSON.stringify(f.data, null, 2)}
                        </pre>
                      )}
                    </motion.div>
                  ))}
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
