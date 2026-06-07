import { type ReactNode } from "react";
import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-16 text-center", className)}>
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
        <Icon className="h-7 w-7" />
      </div>
      <h3 className="mb-1 text-base font-semibold text-foreground">{title}</h3>
      {description && <p className="mb-5 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}
