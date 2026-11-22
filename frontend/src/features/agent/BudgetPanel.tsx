/**
 * BudgetPanel — 右轨竖排预算仪表：页面/步数/token/上下文 + 压缩徽标
 * + 每步 token 消耗折线（上下文压缩拐点可见，上下文工程的实证可视化）。
 */

import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useMemo } from "react";
import { Blocks, FileSearch, Gauge, Footprints } from "lucide-react";
import { api } from "@/api/client";
import type { EChartsCoreOption } from "echarts/core";
import { Chart } from "@/components/Chart";
import { useChartTheme } from "@/hooks/useChartTheme";
import type { AgentProgress, AgentSnapshot } from "./useAgentRun";
import { cn } from "@/lib/utils";

// 与后端 AGENT_CONTEXT_TOKEN_BUDGET 默认值一致（仅用于可视化占比）。
// GET /api/settings/config 目前未暴露该字段，取不到真实值时回退此默认。
const DEFAULT_CONTEXT_TOKEN_BUDGET = 24000;

/** 配置值可能是字符串或数字；缺失/非法返回 null（调用方回退默认值） */
function parseTokenBudget(raw: string | number | undefined): number | null {
  if (raw == null) return null;
  const n = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}

interface BudgetPanelProps {
  progress: AgentProgress | null;
  usage: AgentSnapshot["usage"];
  estTokens: number;
  compactions: number;
  compactionSaved: number;
  tokenSeries: AgentSnapshot["tokenSeries"];
  compactionSteps: AgentSnapshot["compactionSteps"];
}

export function BudgetPanel({
  progress,
  usage,
  estTokens,
  compactions,
  compactionSaved,
  tokenSeries,
  compactionSteps,
}: BudgetPanelProps) {
  const t = useChartTheme();
  // 与 SettingsPage 共用同一 queryKey，共享缓存；staleTime 拉长避免频繁请求
  const configQuery = useQuery({
    queryKey: ["settings-config"],
    queryFn: () => api.getConfig(),
    staleTime: 5 * 60 * 1000,
  });
  const contextBudget =
    parseTokenBudget(configQuery.data?.config?.AGENT_CONTEXT_TOKEN_BUDGET) ?? DEFAULT_CONTEXT_TOKEN_BUDGET;

  // 每步 token 折线：上下文占用（实线，压缩后应回落）+ 累计消耗（虚线，单调增）
  const tokenOption = useMemo<EChartsCoreOption>(() => {
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: t.tooltipBg,
        borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 11 },
      },
      legend: {
        data: ["上下文估算", "累计消耗"],
        bottom: 0,
        itemWidth: 10,
        itemHeight: 2,
        textStyle: { color: t.label, fontSize: 9 },
      },
      grid: { left: 2, right: 6, top: 6, bottom: 22, containLabel: true },
      xAxis: {
        type: "category",
        data: tokenSeries.map((p) => `S${p.step}`),
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: t.axis } },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: t.label,
          fontSize: 9,
          formatter: (v: number) => (v >= 1000 ? `${Math.round(v / 100) / 10}k` : `${v}`),
        },
        splitLine: { lineStyle: { color: t.split } },
      },
      series: [
        {
          name: "上下文估算",
          type: "line",
          data: tokenSeries.map((p) => p.est),
          smooth: true,
          symbol: "circle",
          symbolSize: 3,
          lineStyle: { color: t.brand, width: 2 },
          itemStyle: { color: t.brand },
          areaStyle: { color: t.brand, opacity: 0.1 },
          // 压缩发生步：紫色虚线竖标 —— 拐点与压缩对齐，压缩效果一眼可见
          markLine:
            compactionSteps.length > 0
              ? {
                  silent: true,
                  symbol: "none",
                  lineStyle: { color: "#8b5cf6", type: "dashed", width: 1 },
                  label: { show: false },
                  data: compactionSteps.map((step) => ({ xAxis: `S${step}` })),
                }
              : undefined,
        },
        {
          name: "累计消耗",
          type: "line",
          data: tokenSeries.map((p) => p.total),
          smooth: true,
          symbol: "none",
          lineStyle: { color: t.label, width: 1, opacity: 0.55, type: "dashed" },
        },
      ],
    };
  }, [tokenSeries, compactionSteps, t]);

  const items = [
    {
      icon: <FileSearch className="h-3.5 w-3.5" />,
      label: "页面",
      used: progress?.pages_used ?? 0,
      budget: progress?.budget_pages ?? 0,
    },
    {
      icon: <Footprints className="h-3.5 w-3.5" />,
      label: "步数",
      used: progress?.steps_used ?? 0,
      budget: progress?.budget_steps ?? 0,
    },
    {
      icon: <Gauge className="h-3.5 w-3.5" />,
      label: "Tokens",
      used: usage?.total_tokens ?? 0,
      budget: 0,
    },
    {
      icon: <Blocks className="h-3.5 w-3.5" />,
      label: "上下文",
      used: estTokens,
      budget: contextBudget,
    },
  ];

  return (
    <div className="rounded-xl border bg-card/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">预算仪表</span>
        {compactions > 0 && (
          <span
            className="rounded-full border border-violet-500/30 bg-violet-500/10 px-1.5 text-[10px] text-violet-500"
            title={`已压缩 ${compactions} 次，累计释放约 ${compactionSaved.toLocaleString()} tokens`}
          >
            压缩 ×{compactions}
          </span>
        )}
      </div>
      <div className="space-y-3">
        {items.map((item) => {
          const ratio = item.budget > 0 ? Math.min(1, item.used / item.budget) : 0;
          const high = ratio > 0.85;
          return (
            <div key={item.label}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  {item.icon}
                  {item.label}
                </span>
                <span className="font-mono text-xs tabular-nums text-foreground">
                  {item.used.toLocaleString()}
                  {item.budget > 0 && (
                    <span className="text-muted-foreground"> / {item.budget.toLocaleString()}</span>
                  )}
                </span>
              </div>
              {item.budget > 0 && (
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted">
                  <motion.div
                    className={cn("h-full rounded-full", high ? "bg-destructive" : "bg-brand")}
                    initial={{ width: 0 }}
                    animate={{ width: `${ratio * 100}%` }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
      {tokenSeries.length >= 2 && (
        <Chart option={tokenOption} className="mt-3 h-32 w-full" />
      )}
    </div>
  );
}
