/**
 * PageHeader — 统一页头：图标方块 + 标题 + 副标题 + 右侧动作槽位。
 * 六页共用，保证信息架构一致（页头永远回答「这是哪、能干什么、主操作在哪」）。
 */

import type { LucideIcon } from "lucide-react";

interface PageHeaderProps {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function PageHeader({ icon: Icon, title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex items-center gap-3">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary shadow-sm">
        <Icon className="h-6 w-6 text-primary-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-bold tracking-tight text-foreground">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
