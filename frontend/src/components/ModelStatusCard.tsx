/**
 * ModelStatusCard — 常驻模型状态卡（侧边栏底部）。
 *
 * 把「模型区别开」落在全局 UI：主力模型（DeepSeek 等，推理/报告）与
 * 辅助模型（本地 Ollama，摘要/改写）各占一行，绿点=在线、红点=离线。
 * 数据来自 GET /api/settings/status（TanStack Query，60s 自动刷新）。
 */

import { useQuery } from "@tanstack/react-query";
import { Cloud, Cpu } from "lucide-react";
import { api } from "@/api/client";
import { cn } from "@/lib/utils";

export function useServiceStatus() {
  return useQuery({
    queryKey: ["service-status"],
    queryFn: api.getServiceStatus,
    refetchInterval: 60_000,
  });
}

function Dot({ ok }: { ok: boolean }) {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      {ok && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success/50" />}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", ok ? "bg-success" : "bg-destructive")} />
    </span>
  );
}

export function ModelStatusCard() {
  const { data } = useServiceStatus();
  const main = data?.llm_provider;
  const aux = data?.aux_llm;

  return (
    <div className="space-y-1.5 rounded-lg border border-border/70 bg-card/60 p-2.5" data-testid="model-status">
      {/* 主力模型 */}
      <div className="flex items-center gap-2" title={`主力模型 · 推理/工具/报告${main?.error ? `（${main.error}）` : ""}`}>
        <Cloud className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <Dot ok={!!main?.connected} />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate font-mono text-[11px] text-foreground">{main?.model || "未配置"}</p>
          <p className="text-[10px] text-muted-foreground">主力 · 推理/报告</p>
        </div>
      </div>
      {/* 辅助模型（本地） */}
      <div
        className="flex items-center gap-2"
        title={`辅助模型 · 摘要/查询改写${aux && !aux.enabled ? "（未启用，回退主模型）" : aux?.error ? `（${aux.error}）` : ""}`}
      >
        <Cpu className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <Dot ok={aux ? aux.connected : false} />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate font-mono text-[11px] text-foreground">
            {aux?.enabled ? `${aux.model}（本地）` : "未启用"}
          </p>
          <p className="text-[10px] text-muted-foreground">辅助 · 摘要/改写</p>
        </div>
      </div>
    </div>
  );
}

/** 折叠态：只显示两个状态点 */
export function ModelStatusDots() {
  const { data } = useServiceStatus();
  return (
    <div className="flex flex-col items-center gap-1.5 py-1" title="模型状态（展开侧边栏查看详情）">
      <Dot ok={!!data?.llm_provider?.connected} />
      <Dot ok={!!data?.aux_llm?.connected} />
    </div>
  );
}
