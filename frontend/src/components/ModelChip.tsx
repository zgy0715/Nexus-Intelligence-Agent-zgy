/**
 * 顶栏模型状态芯片：主力 + 辅助各一枚，绿点=在线 / 红点=离线，悬停显示错误原因。
 */

import { cn } from "@/lib/utils";
import { useServiceStatus } from "@/hooks/useServiceStatus";

function Chip({
  label,
  model,
  ok,
  title,
}: {
  label: string;
  model?: string;
  ok: boolean;
  title: string;
}) {
  return (
    <div
      className="hidden items-center gap-2 rounded-full border border-border bg-secondary/50 px-3 py-1.5 sm:flex"
      title={title}
    >
      <span className="relative flex h-1.5 w-1.5">
        {ok && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success/60" />}
        <span className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", ok ? "bg-success" : "bg-destructive")} />
      </span>
      <span className="font-mono text-[11px] text-muted-foreground">
        <span className="text-foreground/70">{label}</span> {model || "未配置"}
      </span>
    </div>
  );
}

export function ModelChip() {
  const { data } = useServiceStatus();
  const main = data?.llm_provider;
  const aux = data?.aux_llm;
  return (
    <div className="hidden items-center gap-2 sm:flex">
      <Chip
        label="主"
        model={main?.model}
        ok={!!main?.connected}
        title={`主力模型 · 推理/工具/报告${main?.error ? `（${main.error}）` : ""}`}
      />
      {aux?.enabled && (
        <Chip
          label="辅"
          model={`${aux.model}（本地）`}
          ok={!!aux.connected}
          title={`辅助模型 · 摘要/查询改写（本地 Ollama，零 token 成本）${aux.error ? `（${aux.error}）` : ""}`}
        />
      )}
    </div>
  );
}
