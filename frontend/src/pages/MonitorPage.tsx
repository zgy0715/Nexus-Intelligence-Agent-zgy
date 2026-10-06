/**
 * 监控面板 — 实时指标 + 域名分布图表 (ECharts，适配暗色)
 */

import { useState, useEffect, useCallback, useRef } from "react";
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
import * as echarts from "echarts";
import { api } from "@/api/client";
import { useStore } from "@/store";
import type { MonitorStats } from "@/types";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

interface DomainStat {
  domain: string;
  count: number;
}

function MetricCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{label}</p>
        </div>
        <div className="rounded-xl bg-accent p-2.5 text-accent-foreground">
          <Icon size={18} />
        </div>
      </div>
    </Card>
  );
}

function BarChart({ data, dark }: { data: DomainStat[]; dark: boolean }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    instanceRef.current = echarts.init(chartRef.current);
    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = instanceRef.current;
    if (!chart || data.length === 0) return;
    const axisColor = dark ? "#475569" : "#e5e7eb";
    const labelColor = dark ? "#94a3b8" : "#9ca3af";
    const splitColor = dark ? "#1e293b" : "#f3f4f6";
    chart.setOption({
      tooltip: {
        trigger: "axis",
        backgroundColor: dark ? "#1e293b" : "#fff",
        borderColor: axisColor,
        textStyle: { color: dark ? "#e2e8f0" : "#374151", fontSize: 12 },
      },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        data: data.map((d) => d.domain),
        axisLine: { lineStyle: { color: axisColor } },
        axisLabel: { color: labelColor, fontSize: 11 },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        splitLine: { lineStyle: { color: splitColor } },
        axisLabel: { color: labelColor, fontSize: 11 },
      },
      series: [
        {
          type: "bar",
          data: data.map((d) => d.count),
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "#6366f1" },
              { offset: 1, color: "#818cf8" },
            ]),
            borderRadius: [6, 6, 0, 0],
          },
          barWidth: "50%",
        },
      ],
    });
  }, [data, dark]);

  return <div ref={chartRef} style={{ height: 280, width: "100%" }} />;
}

export default function MonitorPage() {
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [domains, setDomains] = useState<DomainStat[]>([]);
  const [alert, setAlert] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const mountedRef = useRef(true);
  const dark = useStore((s) => s.theme === "dark");

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [s, d, a] = await Promise.all([
        api.getMonitorStats(),
        api.getMonitorDomains(),
        api.getMonitorAlert(),
      ]);
      if (!mountedRef.current) return;
      setStats(s);
      setDomains(d.domains);
      setAlert(a.alert);
      setError(null);
    } catch (e) {
      if (!mountedRef.current) return;
      setError(e instanceof Error ? e.message : "加载监控数据失败");
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 30000);
    return () => clearInterval(interval);
  }, [loadAll]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-12 w-full" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary">
            <Activity className="text-primary-foreground" size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">任务监控</h1>
            <p className="text-xs text-muted-foreground">系统运行状态和任务统计</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadAll}>
          <RefreshCw size={14} /> 刷新
        </Button>
      </div>

      {error ? (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle size={16} />
          {error}
        </div>
      ) : stats?.degraded ? (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
          <AlertTriangle size={16} />
          部分依赖不可用（MongoDB 或 Redis 未连接），统计数据可能不完整
        </div>
      ) : alert ? (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle size={16} />
          {alert}
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">
          <Activity size={16} />
          系统运行正常
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard icon={ListChecks} label="总任务数" value={stats?.total_tasks ?? "-"} />
        <MetricCard icon={TrendingUp} label="成功率" value={stats != null ? `${stats.success_rate}%` : "-"} />
        <MetricCard icon={Cpu} label="LLM 调用" value={stats?.llm_calls ?? "-"} />
        <MetricCard icon={Clock} label="平均 LLM 耗时" value={stats != null ? `${stats.avg_llm_time_ms ?? stats.avg_llm_time ?? 0}ms` : "-"} />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard icon={Inbox} label="队列待处理" value={stats?.queue_pending ?? "-"} />
        <MetricCard icon={AlertTriangle} label="失败任务" value={stats?.dead_letter_count ?? "-"} />
        <MetricCard icon={Clock} label="平均爬取耗时" value={stats != null ? `${stats.avg_crawl_time_ms ?? 0}ms` : "-"} />
        <MetricCard icon={Cpu} label="平均 LLM 调用" value={stats?.avg_llm_calls ?? "-"} />
      </div>

      <Card className="p-5">
        <h2 className="mb-4 text-sm font-medium text-muted-foreground">域名分布</h2>
        {domains.length === 0 ? (
          <div className="py-12 text-center">
            <Activity size={24} className="mx-auto mb-2 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">暂无数据</p>
          </div>
        ) : (
          <BarChart data={domains} dark={dark} />
        )}
      </Card>
    </div>
  );
}
