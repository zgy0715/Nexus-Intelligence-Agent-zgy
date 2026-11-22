/**
 * 监控面板 — 实时指标 + 时间序列 + 域名分布（ECharts，随主题变色）。
 *
 * v3：数据层迁移 TanStack Query（refetchInterval 替代手写 setInterval），
 * 图表走 <Chart> 封装（echarts/core 按需 + CSS token 取色），
 * 新增 14 天任务量/成功率时间序列图。
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ListChecks,
  TrendingUp,
  Cpu,
  Clock,
  Inbox,
  AlertTriangle,
  RefreshCw,
  Coins,
  GitCompareArrows,
  Waypoints,
  Maximize2,
  X,
} from "lucide-react";
import { api } from "@/api/client";
import { graphic } from "echarts/core";
import type { EChartsCoreOption } from "echarts/core";
import { Chart } from "@/components/Chart";
import { useChartTheme } from "@/hooks/useChartTheme";
import { applyTheme, useStore, type Theme } from "@/store";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn, timeAgo } from "@/lib/utils";

function MetricCard({
  icon: Icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  tone?: "danger";
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
          <p className={`mt-1.5 text-2xl font-bold tabular-nums tracking-tight ${tone === "danger" ? "text-destructive" : "text-foreground"}`}>
            {value}
          </p>
          {sub && <p className="mt-1 truncate text-[11px] text-muted-foreground">{sub}</p>}
        </div>
        <div className="rounded-lg bg-brand/10 p-2 text-brand">
          <Icon size={16} />
        </div>
      </div>
    </Card>
  );
}

export default function MonitorPage() {
  const t = useChartTheme();

  const statsQuery = useQuery({
    queryKey: ["monitor-stats"],
    queryFn: api.getMonitorStats,
    refetchInterval: 30_000,
  });
  const domainsQuery = useQuery({
    queryKey: ["monitor-domains"],
    queryFn: () => api.getMonitorDomains(3650),
    refetchInterval: 60_000,
  });
  const tsQuery = useQuery({
    queryKey: ["monitor-timeseries"],
    queryFn: () => api.getMonitorTimeseries(14),
    refetchInterval: 60_000,
  });
  const alertQuery = useQuery({
    queryKey: ["monitor-alert"],
    queryFn: api.getMonitorAlert,
    refetchInterval: 60_000,
  });
  const graphQuery = useQuery({
    queryKey: ["monitor-graph"],
    queryFn: api.getMonitorGraph,
    refetchInterval: 60_000,
  });
  const costQuery = useQuery({
    queryKey: ["monitor-cost"],
    queryFn: api.getMonitorCost,
    refetchInterval: 60_000,
  });
  const changesQuery = useQuery({
    queryKey: ["monitor-changes"],
    queryFn: () => api.getMonitorChanges(20),
    refetchInterval: 60_000,
  });

  const stats = statsQuery.data;
  // useMemo 稳定引用：作为下游 useMemo 的依赖，避免每次渲染重建 option
  const domains = useMemo(() => domainsQuery.data?.domains ?? [], [domainsQuery.data]);
  const series = useMemo(() => tsQuery.data?.series ?? [], [tsQuery.data]);
  const alert = alertQuery.data?.alert;
  const graph = graphQuery.data;
  const cost = costQuery.data;
  const changes = useMemo(() => changesQuery.data?.changes ?? [], [changesQuery.data]);
  const [graphMode, setGraphMode] = useState<"domains" | "pages">("domains");

  // 简单字符串哈希 → 调色板取色：同域名永远同色（页面级图谱的分组着色）
  const colorOfDomain = useMemo(() => {
    const palette = t.palette;
    return (key: string) => {
      let h = 0;
      for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
      return palette[h % palette.length];
    };
  }, [t]);

  const graphOption = useMemo<EChartsCoreOption>(() => {
    const g = graphMode === "domains" ? graph?.domains : graph?.pages;
    // 节点 id 去重保险：重复 id 会使 ECharts graph 边端点查找崩溃
    const seen = new Set<string>();
    const nodes = (g?.nodes ?? [])
      .filter((n) => !seen.has(n.id) && seen.add(n.id))
      .map((n) => ({
      id: n.id,
      name: n.name,
      value: n.count ?? 1,
      symbolSize: graphMode === "domains" ? Math.min(42, 12 + (n.count ?? 1) * 2) : Math.min(16, 7 + (n.count ?? 1)),
      // 按域名分组着色：同站点的页面同色，图谱一眼能读出"从哪来"
      itemStyle: {
        color: colorOfDomain("domain" in n && typeof n.domain === "string" && n.domain ? n.domain : n.id),
        borderColor: t.tooltipBg,
        borderWidth: 1.5,
        opacity: 0.92,
      },
      label: {
        show: graphMode === "domains",
        color: t.label,
        fontSize: 10,
        formatter: "{b}",
      },
    }));
    const links = (g?.links ?? []).map((l) => ({
      source: l.source,
      target: l.target,
      lineStyle: {
        color: t.split,
        width: Math.min(4, l.weight ?? 1),
        curveness: 0.15,
        opacity: 0.7,
      },
    }));
    return {
      tooltip: {
        backgroundColor: t.tooltipBg,
        borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 12 },
        formatter: (p: { dataType?: string; name?: string; value?: number }) =>
          p.dataType === "edge" ? "" : `${p.name}${p.value ? ` · ${p.value} 页` : ""}`,
      },
      series: [
        {
          type: "graph",
          // 无父子路径时 force 布局会把节点随机漂散成"孤点云"——
          // 改用环形布局让孤立节点整齐排一圈，视觉上是有意的构图
          layout: links.length === 0 ? "circular" : "force",
          roam: true,
          draggable: true,
          circular: { rotateLabel: true },
          force: {
            repulsion: graphMode === "domains" ? 220 : 120,
            edgeLength: graphMode === "domains" ? 90 : 60,
            gravity: 0.18,
          },
          emphasis: {
            focus: "adjacency",
            label: { show: true, color: t.label, fontSize: 10 },
          },
          data: nodes,
          links,
        },
      ],
    };
  }, [graph, graphMode, t, colorOfDomain]);

  // 域名分布：矩形树图（面积 = 页面数）——比单色柱状图信息密度高，
  // 知识库的站点构成一眼可读
  const domainOption = useMemo<EChartsCoreOption>(() => {
    const top = domains.slice(0, 10);
    return {
      tooltip: {
        backgroundColor: t.tooltipBg,
        borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 12 },
        formatter: (p: { name?: string; value?: number }) => `${p.name}: ${p.value} 页`,
      },
      series: [
        {
          type: "treemap",
          data: top.map((d, i) => ({
            name: d.domain,
            value: d.count,
            itemStyle: { color: t.palette[i % t.palette.length], opacity: 0.9 },
          })),
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          top: 4,
          left: 4,
          right: 4,
          bottom: 4,
          itemStyle: { borderRadius: 6, gapWidth: 3, borderColor: "transparent" },
          label: {
            show: true,
            formatter: "{b}\n{c} 页",
            fontSize: 11,
            color: "#fff",
            textShadowColor: "rgba(0,0,0,0.25)",
            textShadowBlur: 3,
          },
        },
      ],
    };
  }, [domains, t]);

  const timeseriesOption = useMemo<EChartsCoreOption>(() => {
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: t.tooltipBg,
        borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 12 },
      },
      legend: {
        data: ["任务量", "成功率 %"],
        textStyle: { color: t.label, fontSize: 11 },
        top: 0,
      },
      grid: { left: 8, right: 8, top: 32, bottom: 8, containLabel: true },
      xAxis: {
        type: "category",
        data: series.map((p) => p.day.slice(5)),
        axisLabel: { color: t.label, fontSize: 11 },
        axisLine: { lineStyle: { color: t.axis } },
        axisTick: { show: false },
      },
      yAxis: [
        {
          type: "value",
          name: "任务",
          nameTextStyle: { color: t.label },
          axisLabel: { color: t.label, fontSize: 11 },
          splitLine: { lineStyle: { color: t.split } },
        },
        {
          type: "value",
          name: "%",
          nameTextStyle: { color: t.label },
          min: 0,
          max: 100,
          axisLabel: { color: t.label, fontSize: 11 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "任务量",
          type: "bar",
          data: series.map((p) => p.total),
          // 垂直渐变柱体：顶部实、底部虚，替代单色平面块
          itemStyle: {
            color: new graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: t.withAlpha(t.brand, 0.95) },
              { offset: 1, color: t.withAlpha(t.brand, 0.3) },
            ]),
            borderRadius: [3, 3, 0, 0],
          },
          barMaxWidth: 18,
        },
        {
          name: "成功率 %",
          type: "line",
          yAxisIndex: 1,
          data: series.map((p) => p.success_rate),
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { color: t.success, width: 2 },
          itemStyle: { color: t.success },
          areaStyle: {
            color: new graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: t.withAlpha(t.success, 0.18) },
              { offset: 1, color: t.withAlpha(t.success, 0) },
            ]),
          },
          // 告警阈值参考线：低于 80% 的时段一眼可辨
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { color: t.destructive, type: "dashed", width: 1, opacity: 0.7 },
            label: { color: t.destructive, fontSize: 10, position: "insideStartTop", formatter: "告警阈值 80%" },
            data: [{ yAxis: 80 }],
          },
        },
      ],
    };
  }, [series, t]);

  // 成本构成环形图：按 Agent 运行的 token 分布（前 6 个任务）
  const costDonutOption = useMemo<EChartsCoreOption>(() => {
    const runs = (cost?.runs ?? []).filter((r) => r.total_tokens > 0).slice(0, 6);
    return {
      tooltip: {
        backgroundColor: t.tooltipBg,
        borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 12 },
        formatter: (p: { name?: string; value?: number; percent?: number }) =>
          `${p.name}: ${(p.value ?? 0).toLocaleString()} tokens（${p.percent ?? 0}%）`,
      },
      series: [
        {
          type: "pie",
          radius: ["62%", "85%"],
          center: ["50%", "50%"],
          data: runs.map((r, i) => ({
            name: (r.goal || r.run_id.slice(0, 8)).slice(0, 10),
            value: r.total_tokens,
            itemStyle: { color: t.palette[i % t.palette.length] },
          })),
          label: { show: false },
          itemStyle: { borderRadius: 4, borderColor: t.tooltipBg, borderWidth: 2 },
        },
      ],
    };
  }, [cost, t]);

  const loading = statsQuery.isLoading;

  // ── 监控大屏模式：forest 暗色全屏仪表盘，答辩投屏用 ──
  const [dashboard, setDashboard] = useState(false);
  const prevThemeRef = useRef<Theme | null>(null);
  const openDashboard = () => {
    prevThemeRef.current = useStore.getState().theme;
    applyTheme("forest"); // 大屏强制暗色（图表主题 token 自动跟随）
    setDashboard(true);
  };
  const closeDashboard = () => {
    if (prevThemeRef.current) applyTheme(prevThemeRef.current);
    setDashboard(false);
  };
  useEffect(() => {
    if (!dashboard) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeDashboard();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dashboard]);

  return (
    <div className="mx-auto max-w-[1440px] p-4 lg:p-8">
      <PageHeader
        icon={Activity}
        eyebrow="系统 · Observability"
        title="任务监控"
        subtitle="系统运行状态与统计图表（每 30 秒自动刷新）"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={openDashboard}>
              <Maximize2 className="h-4 w-4" /> 大屏
            </Button>
            <Button variant="outline" size="sm" onClick={() => { statsQuery.refetch(); domainsQuery.refetch(); tsQuery.refetch(); }}>
              <RefreshCw className="h-4 w-4" /> 刷新
            </Button>
          </>
        }
      />

      {/* 告警横幅 */}
      {alert && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {alert}
        </div>
      )}

      {/* bento 指标行 */}
      {loading ? (
        <div className="mb-6 grid grid-cols-2 gap-4 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-4 xl:grid-cols-4">
            <MetricCard
              icon={ListChecks}
              label="总任务数"
              value={stats?.total_tasks ?? 0}
              sub={`已完成 ${stats?.finished_tasks ?? 0}`}
            />
            <MetricCard
              icon={TrendingUp}
              label="成功率"
              value={(stats?.total_tasks ?? 0) > 0 ? `${stats?.success_rate ?? 0}%` : "—"}
              sub={`阈值 ${80}% 以下告警`}
              tone={(stats?.total_tasks ?? 0) > 0 && (stats?.success_rate ?? 100) < 80 ? "danger" : undefined}
            />
            <MetricCard
              icon={Cpu}
              label="LLM 调用"
              value={stats?.llm_calls ?? 0}
              sub={`平均 ${stats?.avg_llm_time_ms ?? 0}ms`}
            />
            <MetricCard
              icon={Coins}
              label="估算成本"
              value={`¥${(cost?.estimated_cost ?? 0).toFixed(2)}`}
              sub={`${(cost?.total.total_tokens ?? 0).toLocaleString()} tokens`}
            />
          </div>
          <div className="mb-6 flex flex-wrap gap-2 font-mono text-[11px] text-muted-foreground">
            <span className="rounded-full border border-border bg-secondary/50 px-2.5 py-1">
              <Inbox className="mr-1 inline h-3 w-3" /> 队列待处理 {stats?.queue_pending ?? 0}
            </span>
            <span className="rounded-full border border-border bg-secondary/50 px-2.5 py-1">
              <AlertTriangle className="mr-1 inline h-3 w-3" /> 失败 {(stats?.total_tasks ?? 0) - (stats?.finished_tasks ?? 0)}
            </span>
            <span className="rounded-full border border-border bg-secondary/50 px-2.5 py-1">
              <Clock className="mr-1 inline h-3 w-3" /> 平均爬取 {stats?.avg_crawl_time_ms ?? 0}ms
            </span>
          </div>
        </>
      )}

      {/* bento 图表：时间序列(2/3) + 域名分布(1/3) */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-4 lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-foreground">近 14 天任务与成功率</h2>
          {series.length === 0 ? (
            <EmptyState icon={Activity} title="暂无时间序列数据" description="爬取任务完成后这里会出现按天统计的柱状图与成功率曲线。" />
          ) : (
            <Chart option={timeseriesOption} className="h-72 w-full" />
          )}
        </Card>
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold text-foreground">知识库站点构成</h2>
          {domains.length === 0 ? (
            <EmptyState icon={Activity} title="暂无数据" description="爬取到页面后这里会展示真实域名分布。" />
          ) : (
            <Chart option={domainOption} className="h-72 w-full" />
          )}
        </Card>
      </div>

      {/* 爬取图谱(2/3) + 成本明细(1/3) */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Waypoints className="h-4 w-4 text-brand" /> 爬取路径图谱
            </h2>
            <div className="inline-flex rounded-lg border border-border p-0.5">
              {(["domains", "pages"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setGraphMode(m)}
                  className={cn(
                    "rounded-[7px] px-2.5 py-1 text-xs transition",
                    graphMode === m ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {m === "domains" ? "域名级" : "页面级"}
                </button>
              ))}
            </div>
          </div>
          {(graph?.[graphMode].nodes.length ?? 0) === 0 ? (
            <EmptyState icon={Waypoints} title="暂无图谱数据" description="整站爬取（跟随深度 > 0）或 Agent 运行后，这里会展示页面间的链接路径。" />
          ) : (
            <>
              <p className="mb-2 font-mono text-[11px] text-muted-foreground">
                {graph?.[graphMode].nodes.length ?? 0} 节点 · {graph?.[graphMode].links.length ?? 0} 路径
                {graphMode === "pages" && (graph?.pages.links.length ?? 0) === 0 && (
                  <span className="ml-2 text-warning">暂无父子路径：以深度&gt;0 整站爬取或运行 Agent 后生成</span>
                )}
              </p>
              <Chart option={graphOption} className="h-80 w-full" />
            </>
          )}
        </Card>

        <Card className="p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Coins className="h-4 w-4 text-brand" /> Token 成本看板
          </h2>
          {costQuery.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <>
              <p className="text-3xl font-bold tabular-nums text-foreground">
                ¥{(cost?.estimated_cost ?? 0).toFixed(2)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                估算成本 · {(cost?.total.total_tokens ?? 0).toLocaleString()} tokens · {cost?.total.calls ?? 0} 次调用
              </p>
              <p className="mt-1 text-[10px] text-muted-foreground/70">
                单价 ¥{cost?.price_per_m.input ?? 2}/¥{cost?.price_per_m.output ?? 3} 每百万 token（输入/输出，.env 可调）
              </p>
              {(cost?.runs ?? []).filter((r) => r.total_tokens > 0).length >= 2 && (
                <Chart option={costDonutOption} className="mt-2 h-36 w-full" />
              )}
              <div className="mt-3 max-h-56 space-y-1.5 overflow-y-auto">
                {(cost?.runs ?? []).filter((r) => r.total_tokens > 0).slice(0, 8).map((r) => (
                  <div key={r.run_id} className="flex items-baseline justify-between gap-2 rounded-md bg-secondary/60 px-2 py-1.5">
                    <span className="min-w-0 flex-1 truncate text-xs text-foreground/80">{r.goal || r.run_id.slice(0, 8)}</span>
                    <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
                      {r.total_tokens.toLocaleString()} · ¥{r.cost.toFixed(2)}
                    </span>
                  </div>
                ))}
                {(cost?.runs ?? []).filter((r) => r.total_tokens > 0).length === 0 && (
                  <p className="py-4 text-center text-xs text-muted-foreground">Agent 运行后这里会出现按任务的成本明细。</p>
                )}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* 站点变更 */}
      <Card className="mt-4 p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
          <GitCompareArrows className="h-4 w-4 text-brand" /> 最近站点变更（{changes.length}）
        </h2>
        {changes.length === 0 ? (
          <p className="py-4 text-center text-xs text-muted-foreground">
            暂无变更。定时采集或重复爬取同 URL 且内容变化时，这里会出现版本记录。
          </p>
        ) : (
          <div className="space-y-1.5">
            {changes.map((c) => (
              <div key={c.id} className="flex items-center gap-2 rounded-md bg-secondary/60 px-2.5 py-2">
                <Badge variant="warning" className="shrink-0 rounded-full">v{c.version_number}</Badge>
                <a href={c.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-xs text-foreground/80 hover:text-foreground">
                  {c.title || c.url}
                </a>
                <span className="shrink-0 text-[11px] text-muted-foreground">{timeAgo(c.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ── 监控大屏覆盖层：forest 暗色全屏，Esc 退出 ── */}
      {dashboard && (
        <div className="fixed inset-0 z-50 overflow-auto bg-background text-foreground">
          <div className="mx-auto max-w-[1600px] p-6">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h1 className="font-mono text-xl font-bold tracking-wide text-foreground">
                  NIA <span className="text-brand">监控大屏</span>
                </h1>
                <p className="mt-1 text-xs text-muted-foreground">私有化情报系统 · 实时运行态势 · 每 30 秒自动刷新</p>
              </div>
              <div className="flex items-center gap-4">
                <DashboardClock />
                <Button variant="outline" size="sm" onClick={closeDashboard}>
                  <X className="h-4 w-4" /> 退出（Esc）
                </Button>
              </div>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-4 xl:grid-cols-4">
              <MetricCard icon={ListChecks} label="总任务数" value={stats?.total_tasks ?? 0} sub={`已完成 ${stats?.finished_tasks ?? 0}`} />
              <MetricCard
                icon={TrendingUp}
                label="成功率"
                value={(stats?.total_tasks ?? 0) > 0 ? `${stats?.success_rate ?? 0}%` : "—"}
                tone={(stats?.total_tasks ?? 0) > 0 && (stats?.success_rate ?? 100) < 80 ? "danger" : undefined}
              />
              <MetricCard icon={Cpu} label="LLM 调用" value={stats?.llm_calls ?? 0} sub={`平均 ${stats?.avg_llm_time_ms ?? 0}ms`} />
              <MetricCard
                icon={Coins}
                label="估算成本"
                value={`¥${(cost?.estimated_cost ?? 0).toFixed(2)}`}
                sub={`${(cost?.total.total_tokens ?? 0).toLocaleString()} tokens`}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <Card className="p-4 lg:col-span-2">
                <h2 className="mb-3 text-sm font-semibold text-foreground">近 14 天任务与成功率</h2>
                {series.length === 0 ? (
                  <EmptyState icon={Activity} title="暂无时间序列数据" />
                ) : (
                  <Chart option={timeseriesOption} className="h-80 w-full" />
                )}
              </Card>
              <Card className="p-4">
                <h2 className="mb-3 text-sm font-semibold text-foreground">知识库站点构成</h2>
                {domains.length === 0 ? (
                  <EmptyState icon={Activity} title="暂无数据" />
                ) : (
                  <Chart option={domainOption} className="h-80 w-full" />
                )}
              </Card>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              <Card className="p-4 lg:col-span-2">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Waypoints className="h-4 w-4 text-brand" /> 爬取路径图谱
                </h2>
                {(graph?.[graphMode].nodes.length ?? 0) === 0 ? (
                  <EmptyState icon={Waypoints} title="暂无图谱数据" />
                ) : (
                  <Chart option={graphOption} className="h-96 w-full" />
                )}
              </Card>
              <Card className="p-4">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Coins className="h-4 w-4 text-brand" /> Token 构成
                </h2>
                {(cost?.runs ?? []).filter((r) => r.total_tokens > 0).length >= 2 ? (
                  <Chart option={costDonutOption} className="h-56 w-full" />
                ) : (
                  <p className="py-10 text-center text-xs text-muted-foreground">Agent 运行两次后出现构成图</p>
                )}
                <div className="mt-2 max-h-40 space-y-1.5 overflow-y-auto">
                  {(cost?.runs ?? []).filter((r) => r.total_tokens > 0).slice(0, 6).map((r) => (
                    <div key={r.run_id} className="flex items-baseline justify-between gap-2 rounded-md bg-secondary/60 px-2 py-1.5">
                      <span className="min-w-0 flex-1 truncate text-xs text-foreground/80">{r.goal || r.run_id.slice(0, 8)}</span>
                      <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">¥{r.cost.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** 大屏右上角实时时钟 */
function DashboardClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <span className="font-mono text-lg tabular-nums tracking-widest text-foreground">
      {now.toLocaleTimeString("zh-CN", { hour12: false })}
    </span>
  );
}
