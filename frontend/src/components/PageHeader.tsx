/**
 * PageHeader — 产品级页头：mono 眉题 + 大号展示标题 + 描述 + 右侧动作槽。
 * 去掉旧版图标方块，留白与字阶建立层级（参考 Vercel / Linear 文档页）。
 */

import type { LucideIcon } from "lucide-react";

interface PageHeaderProps {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: React.ReactNode;
}

export function PageHeader({ icon: Icon, title, subtitle, eyebrow, actions }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <div className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          <Icon className="h-3.5 w-3.5 text-brand" />
          <span>{eyebrow ?? "NIA Console"}</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground lg:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 pb-0.5">{actions}</div>}
    </div>
  );
}