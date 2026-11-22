/**
 * 定时采集页 — 周期任务管理 + 站点变更 feed。
 *
 * 任务到期由后端调度器自动执行（落库 + 索引 + 内容哈希变更检测）；
 * 变更 feed 来自 data_versions（同 URL 内容变化时产生）。
 */

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  CalendarClock,
  Plus,
  Play,
  Trash2,
  RefreshCw,
  GitCompareArrows,
  ExternalLink,
} from "lucide-react";
import { api } from "@/api/client";
import type { Schedule, SchedulePayload } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Input";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { PageHeader } from "@/components/PageHeader";
import { Dialog } from "@/components/Dialog";
import { cn, timeAgo } from "@/lib/utils";

const STATUS_BADGE: Record<string, { text: string; className: string }> = {
  completed: { text: "上次成功", className: "text-success border-success/30 bg-success/10" },
  failed: { text: "上次失败", className: "text-destructive border-destructive/30 bg-destructive/10" },
};

function intervalLabel(minutes: number): string {
  if (minutes % 1440 === 0) return `每 ${minutes / 1440} 天`;
  if (minutes % 60 === 0) return `每 ${minutes / 60} 小时`;
  return `每 ${minutes} 分钟`;
}

function nextRunLabel(iso: string): string {
  const normalized = /\dZ$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const diff = new Date(normalized).getTime() - Date.now();
  if (Number.isNaN(diff)) return "";
  if (diff <= 0) return "即将运行";
  const m = Math.ceil(diff / 60_000);
  if (m < 60) return `${m} 分钟后`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时后`;
  return `${Math.floor(h / 24)} 天后`;
}

function CreateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [seeds, setSeeds] = useState("");
  const [instruction, setInstruction] = useState("");
  const [interval, setInterval] = useState(60);
  const [maxPages, setMaxPages] = useState(20);
  const [maxDepth, setMaxDepth] = useState(0);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const seedList = seeds.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!name.trim() || seedList.length === 0) {
      toast.error("请填写任务名称与至少一个 URL");
      return;
    }
    setBusy(true);
    try {
      const payload: SchedulePayload = {
        name: name.trim(),
        seeds: seedList,
        instruction: instruction.trim(),
        interval_minutes: interval,
        max_pages: maxPages,
        max_depth: maxDepth,
      };
      await api.createSchedule(payload);
      toast.success("定时任务已创建", { description: "首轮将立即执行" });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      onClose();
      setName("");
      setSeeds("");
      setInstruction("");
    } catch (e) {
      toast.error("创建失败", { description: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="新建定时采集任务">
      <div className="space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium">任务名称</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：Anthropic 公告监控" />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium">起始 URL（每行一个）</label>
          <Textarea
            value={seeds}
            onChange={(e) => setSeeds(e.target.value)}
            placeholder={"https://www.anthropic.com/news"}
            className="min-h-[72px] font-mono text-xs"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted-foreground">提取指令（可选）</label>
          <Input value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="留空只抓正文" />
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">间隔（分钟）</label>
            <Input type="number" min={5} max={10080} value={interval} onChange={(e) => setInterval(Number(e.target.value))} className="h-9 w-28" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">最大页数</label>
            <Input type="number" min={1} max={500} value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))} className="h-9 w-24" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">跟随深度</label>
            <Input type="number" min={0} max={5} value={maxDepth} onChange={(e) => setMaxDepth(Number(e.target.value))} className="h-9 w-24" />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={submit} loading={busy}>创建任务</Button>
        </div>
      </div>
    </Dialog>
  );
}

function ScheduleRow({ schedule }: { schedule: Schedule }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["schedules"] });
  const badge = STATUS_BADGE[schedule.last_status ?? ""];

  const toggle = async () => {
    try {
      await api.updateSchedule(schedule.id, { enabled: !schedule.enabled });
      invalidate();
    } catch (e) {
      toast.error("更新失败", { description: e instanceof Error ? e.message : String(e) });
    }
  };

  const runNow = async () => {
    try {
      const res = await api.runSchedule(schedule.id);
      toast.info(res.message);
      setTimeout(invalidate, 1500);
    } catch (e) {
      toast.error("触发失败", { description: e instanceof Error ? e.message : String(e) });
    }
  };

  const remove = async () => {
    try {
      await api.deleteSchedule(schedule.id);
      toast.success("已删除");
      invalidate();
    } catch (e) {
      toast.error("删除失败", { description: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          role="switch"
          aria-checked={!!schedule.enabled}
          onClick={toggle}
          title={schedule.enabled ? "点击暂停" : "点击启用"}
          className={cn(
            "relative h-5 w-9 shrink-0 rounded-full transition-colors",
            schedule.enabled ? "bg-brand" : "bg-muted",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 h-4 w-4 rounded-full bg-card shadow transition-all",
              schedule.enabled ? "left-[18px]" : "left-0.5",
            )}
          />
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{schedule.name}</p>
          <p className="truncate text-xs text-muted-foreground">
            {intervalLabel(schedule.interval_minutes)} · {schedule.seeds.length} 个种子 · 最多 {schedule.max_pages} 页
            {schedule.next_run_at && schedule.enabled && ` · 下次 ${nextRunLabel(schedule.next_run_at)}`}
          </p>
        </div>
        {badge && (
          <Badge variant="outline" className={cn("rounded-full", badge.className)}>{badge.text}</Badge>
        )}
        {!schedule.enabled && <Badge variant="secondary">已暂停</Badge>}
        <div className="flex gap-1.5">
          <Button variant="outline" size="sm" onClick={runNow} title="立即执行一次">
            <Play className="h-3.5 w-3.5" /> 运行
          </Button>
          <Button variant="ghost" size="icon" onClick={remove} aria-label="删除任务">
            <Trash2 className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

/** 采集活跃度热力图：GitHub contributions 风格，每周一列、每天一格。 */
function ActivityHeatmap({ days }: { days: { date: string; changes: number; tasks: number }[] }) {
  if (days.length === 0) {
    return <p className="py-4 text-center text-xs text-muted-foreground">暂无数据。定时任务执行后这里会出现逐日活跃度。</p>;
  }
  const weeks: { date: string; changes: number; tasks: number }[][] = [];
  for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));
  const level = (n: number) => (n === 0 ? 0 : n <= 2 ? 1 : n <= 5 ? 2 : n <= 9 ? 3 : 4);
  const levelCls = ["bg-muted", "bg-brand/25", "bg-brand/45", "bg-brand/70", "bg-brand"];
  return (
    <div className="flex flex-wrap items-start gap-3">
      <div className="flex gap-1">
        {weeks.map((w, wi) => (
          <div key={wi} className="flex flex-col gap-1">
            {w.map((d) => (
              <div
                key={d.date}
                title={`${d.date} · 变更 ${d.changes} · 任务 ${d.tasks}`}
                className={cn("h-3 w-3 rounded-[3px] transition-colors", levelCls[level(d.changes + d.tasks)])}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-1 self-end pb-0.5 font-mono text-[10px] text-muted-foreground">
        <span>少</span>
        {levelCls.map((c, i) => (
          <div key={i} className={cn("h-3 w-3 rounded-[3px]", c)} />
        ))}
        <span>多</span>
      </div>
    </div>
  );
}

export default function SchedulesPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const schedulesQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: api.listSchedules,
    refetchInterval: 30_000,
  });
  const changesQuery = useQuery({
    queryKey: ["monitor-changes"],
    queryFn: () => api.getMonitorChanges(30),
    refetchInterval: 60_000,
  });
  const heatmapQuery = useQuery({
    queryKey: ["monitor-heatmap"],
    queryFn: () => api.getMonitorHeatmap(84),
    refetchInterval: 120_000,
  });

  const schedules = schedulesQuery.data?.schedules ?? [];
  const changes = changesQuery.data?.changes ?? [];
  const heatmap = heatmapQuery.data?.heatmap ?? [];

  return (
    <div className="mx-auto max-w-[1100px] p-4 lg:p-8">
      <PageHeader
        icon={CalendarClock}
        eyebrow="采集 · Scheduled"
        title="定时采集"
        subtitle="周期自动采集 · 同 URL 内容变更检测 · 变更即情报"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => { schedulesQuery.refetch(); changesQuery.refetch(); }}>
              <RefreshCw className="h-4 w-4" /> 刷新
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> 新建任务
            </Button>
          </>
        }
      />

      {/* 采集活跃度热力图：近 12 周，站点变更 + 爬取任务按天聚合（GitHub contributions 风格） */}
      <Card className="mb-4 p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
          <Activity className="h-4 w-4 text-brand" /> 采集活跃度
          <span className="font-mono text-[10px] font-normal text-muted-foreground">近 12 周 · 变更 + 任务</span>
        </h2>
        <ActivityHeatmap days={heatmap} />
      </Card>

      {schedulesQuery.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : schedules.length === 0 ? (
        <Card>
          <EmptyState
            icon={CalendarClock}
            title="还没有定时任务"
            description="创建一个周期任务，系统会按时自动采集并检测页面内容变化。"
            action={
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" /> 新建任务
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {schedules.map((s) => <ScheduleRow key={s.id} schedule={s} />)}
        </div>
      )}

      <h2 className="mb-3 mt-8 flex items-center gap-2 text-sm font-semibold">
        <GitCompareArrows className="h-4 w-4 text-brand" /> 站点变更（{changes.length}）
      </h2>
      {changes.length === 0 ? (
        <Card className="p-6 text-center text-sm text-muted-foreground">
          暂无变更记录。重复采集同一 URL 且内容发生变化时，这里会出现版本对比。
        </Card>
      ) : (
        <div className="space-y-2">
          {changes.map((c) => (
            <Card key={c.id} className="p-3.5">
              <div className="flex items-center gap-2">
                <Badge variant="warning" className="shrink-0 rounded-full">v{c.version_number}</Badge>
                <p className="min-w-0 flex-1 truncate text-sm font-medium">{c.title || c.url}</p>
                <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(c.created_at)}</span>
              </div>
              <a
                href={c.url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 flex items-center gap-1 truncate text-xs text-muted-foreground hover:text-foreground"
              >
                <ExternalLink className="h-3 w-3 shrink-0" /> {c.url}
              </a>
              {c.new_snippet && (
                <p className="mt-1.5 line-clamp-2 rounded-md bg-success/5 px-2 py-1 text-xs text-foreground/80">
                  {c.new_snippet}
                </p>
              )}
            </Card>
          ))}
        </div>
      )}

      <CreateDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}