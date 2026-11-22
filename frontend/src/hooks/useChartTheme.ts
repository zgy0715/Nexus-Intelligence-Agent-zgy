/**
 * useChartTheme — 读取当前主题下的 CSS 变量色值，供 ECharts option 使用。
 *
 * 注意：zrender 只认逗号语法 hsl(h, s%, l%) / hsla(...)，
 * CSS 新式空格语法（hsl(14 63% 52% / 1)）会解析失败导致系列全透明 ——
 * 所以这里手动重组字符串，而不是把 getComputedStyle 的原值直接透传。
 */

import { useMemo } from "react";
import { useStore } from "@/store";

export function useChartTheme() {
  const theme = useStore((s) => s.theme);
  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string) => style.getPropertyValue(name).trim();
    const hsl = (name: string, alpha = 1) => {
      const [h, s, l] = read(name).split(/\s+/);
      return alpha >= 1 ? `hsl(${h}, ${s}, ${l})` : `hsla(${h}, ${s}, ${l}, ${alpha})`;
    };
    // 把主题 hsl 颜色转为带透明度的 hsla（渐变色 stop 不支持独立 opacity 字段）
    const withAlpha = (color: string, alpha: number) =>
      color.replace(/^hsl\(/, "hsla(").replace(/\)$/, `, ${alpha})`);
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
      // 分类调色板：treemap / 饼图 / 图谱按类别着色用。
      // 取中饱和度的固定色相，明暗三种主题下都可读。
      palette: [
        "#e07a5f", "#3d8a6f", "#4c6fb1", "#a678cf",
        "#d4a04c", "#5aa0c8", "#c05c8e", "#5a8f5a",
      ],
      withAlpha,
    };
  }, [theme]);
}
