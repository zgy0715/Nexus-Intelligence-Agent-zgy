/**
 * BudgetPanel — 预算仪表盘：页面/步数/token/上下文占用四仪表 + 压缩徽标。
 */

import { motion } from "motion/react";
import { Blocks, FileSearch, Gauge, Footprints } from "lucide-react";
import type { AgentProgress, AgentSnapshot } from "./useAgentRun";
import { cn } from "@/lib/utils";

// 与后端 AGENT_CONTEXT_TOKEN_BUDGET 默认值一致（仅用于可视化占比）
const CONTEXT_TOKEN_BUDGET = 24000;

interface BudgetPanelProps {
  progress: AgentProgress | null;
  usage: AgentSnapshot["usage"];
  estTokens: number;
  compactions: number;
  compactionSaved: number;
}

export function BudgetPanel({ progress, usage, estTokens, compactions, compactionSaved }: BudgetPanelProps) {
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
      budget: 0, // 无预算上限，只展示数值
    },
    {
      icon: <Blocks className="h-3.5 w-3.5" />,
      label: "上下文",
      used: estTokens,
      budget: CONTEXT_TOKEN_BUDGET,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {items.map((item) => {
        const ratio = item.budget > 0 ? Math.min(1, item.used / item.budget) : 0;
        const high = ratio > 0.85;
        return (
          <div key={item.label} className="rounded-lg border bg-card/60 px-3 py-2">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              {item.icon}
              <span>{item.label}</span>
              {item.label === "上下文" && compactions > 0 && (
                <span
                  className="ml-auto rounded-full border border-violet-500/30 bg-violet-500/10 px-1.5 text-[10px] text-violet-500"
                  title={`已压缩 ${compactions} 次，累计释放约 ${compactionSaved.toLocaleString()} tokens`}
                >
                  压缩 ×{compactions}
                </span>
              )}
            </div>
            <div className="mt-1 font-mono text-sm font-medium tabular-nums">
              {item.used.toLocaleString()}
              {item.budget > 0 && (
                <span className="text-xs font-normal text-muted-foreground"> / {item.budget.toLocaleString()}</span>
              )}
            </div>
            {item.budget > 0 && (
              <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted">
                <motion.div
                  className={cn("h-full rounded-full", high ? "bg-destructive" : "bg-primary")}
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
  );
}
