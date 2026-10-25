/**
 * 监控面板 — 实时指标 + 时间序列 + 域名分布（ECharts，随主题变色）。
 *
 * v3：数据层迁移 TanStack Query（refetchInterval 替代手写 setInterval），
 * 图表走 <Chart> 封装（echarts/core 按需 + CSS token 取色），
 * 新增 14 天任务量/成功率时间序列图。
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  Activity,
  ListChecks,
  TrendingUp,
  Cpu,
  Clock,
  Inbox,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { api } from "@/api/client";
import type { EChartsCoreOption } from "echarts/core";
import { Chart, useChartTheme } from "@/components/Chart";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";

function MetricCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  tone?: "danger";
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-2xl font-bold ${tone === "danger" ? "text-destructive" : "text-foreground"}`}>
            {value}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{label}</p>
        </div>
        <div className="rounded-xl bg-accent p-2.5 text-accent-foreground">
          <Icon size={18} />
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
    queryFn: api.getMonitorDomains,
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

  const stats = statsQuery.data;
  const domains = domainsQuery.data?.domains ?? [];
  const series = tsQuery.data?.series ?? [];
  const alert = alertQuery.data?.alert;

  const domainOption = useMemo<EChartsCoreOption>(() => {
    const top = domains.slice(0, 10);
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: t.tooltipBg,
        borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 12 },
      },
      grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
      xAxis: {
        type: "category",
        data: top.map((d) => d.domain),
        axisLabel: { color: t.label, fontSize: 11, rotate: 24, truncate: { width: 90 } },
        axisLine: { lineStyle: { color: t.axis } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: t.label, fontSize: 11 },
        splitLine: { lineStyle: { color: t.split } },
      },
      series: [
        {
          type: "bar",
          data: top.map((d) => d.count),
          itemStyle: { color: t.brand, borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 28,
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
          axisLabel: { color: t.label, fontSize: 11 },
          splitLine: { lineStyle: { color: t.split } },
        },
        {
          type: "value",
          name: "%",
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
          itemStyle: { color: t.brand, borderRadius: [3, 3, 0, 0] },
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
        },
      ],
    };
  }, [series, t]);

  const loading = statsQuery.isLoading;

  return (
    <div className="mx-auto max-w-7xl p-4 lg:p-6">
      {/* 标题 */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary shadow-sm">
          <Activity className="h-6 w-6 text-primary-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold text-foreground">任务监控</h1>
          <p className="text-sm text-muted-foreground">系统运行状态与统计图表（每 30 秒自动刷新）</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { statsQuery.refetch(); domainsQuery.refetch(); tsQuery.refetch(); }}>
          <RefreshCw className="h-4 w-4" /> 刷新
        </Button>
      </div>

      {/* 告警横幅 */}
      {alert && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {alert}
        </div>
      )}

      {/* 指标卡 */}
      {loading ? (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard icon={ListChecks} label="总任务数" value={stats?.total_tasks ?? 0} />
          <MetricCard
            icon={TrendingUp}
            label="成功率"
            value={`${stats?.success_rate ?? 0}%`}
            tone={(stats?.success_rate ?? 100) < 80 ? "danger" : undefined}
          />
          <MetricCard icon={Cpu} label="LLM 调用" value={stats?.llm_calls ?? 0} />
          <MetricCard icon={Clock} label="平均 LLM 耗时" value={`${stats?.avg_llm_time_ms ?? 0}ms`} />
          <MetricCard icon={Inbox} label="队列待处理" value={stats?.queue_pending ?? 0} />
          <MetricCard icon={AlertTriangle} label="失败任务" value={(stats?.total_tasks ?? 0) - (stats?.finished_tasks ?? 0)} />
        </div>
      )}

      {/* 图表：时间序列 + 域名分布 */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold text-foreground">近 14 天任务与成功率</h2>
          {series.length === 0 ? (
            <EmptyState icon={Activity} title="暂无时间序列数据" description="爬取任务完成后这里会出现按天统计的柱状图与成功率曲线。" />
          ) : (
            <Chart option={timeseriesOption} className="h-72 w-full" />
          )}
        </Card>
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold text-foreground">域名分布 TOP10</h2>
          {domains.length === 0 ? (
            <EmptyState icon={Activity} title="暂无数据" description="爬取到页面后这里会展示真实域名分布。" />
          ) : (
            <Chart option={domainOption} className="h-72 w-full" />
          )}
        </Card>
      </div>
    </div>
  );
}
