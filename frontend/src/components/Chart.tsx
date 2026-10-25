/**
 * Chart — ECharts 统一封装（v3）。
 *
 - echarts/core 按需注册（bundle 从全量 ~1MB 降到 ~40%）；
 - init/dispose/resize 生命周期集中处理，StrictMode 双挂载安全；
 - 颜色从 CSS 设计 token 读取（getComputedStyle），主题切换自动跟随，
   不再像旧版硬编码 indigo 色值。
 */

import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { useStore } from "@/store";

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);

/** 读取当前主题下的 CSS 变量色值 */
export function useChartTheme() {
  const theme = useStore((s) => s.theme);
  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string) => style.getPropertyValue(name).trim();
    const hsl = (name: string, alpha = 1) =>
      `hsl(${read(name)} / ${alpha})`;
    return {
      theme,
      label: hsl("--muted-foreground", 0.9),
      axis: hsl("--border"),
      split: hsl("--border", 0.5),
      tooltipBg: hsl("--popover"),
      tooltipBorder: hsl("--border"),
      tooltipText: hsl("--popover-foreground"),
      brand: hsl("--brand"),
      success: hsl("--success"),
      warning: hsl("--warning"),
      destructive: hsl("--destructive"),
      foreground: hsl("--foreground"),
      muted: hsl("--muted"),
    };
  }, [theme]);
}

interface ChartProps {
  option: EChartsCoreOption;
  className?: string;
  style?: React.CSSProperties;
}

export function Chart({ option, className, style }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const chartTheme = useChartTheme();

  // 初始化 / 销毁（StrictMode 双挂载下 dispose 保证不泄漏）
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = echarts.init(el);
    chartRef.current = chart;
    const onResize = () => chart.resize();
    const observer = new ResizeObserver(onResize);
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  // option / 主题变化时重建 option
  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option, chartTheme]);

  return <div ref={containerRef} className={className} style={style} />;
}
