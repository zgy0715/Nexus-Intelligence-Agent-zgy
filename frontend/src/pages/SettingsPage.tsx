/**
 * 系统设置页面（v3.1）— 模型角色可视化 + 服务状态 + 配置分组。
 *
 * - 服务状态四卡：Redis / MySQL / 主力模型 / 辅助模型（TanStack Query 60s 刷新）
 * - 模型角色区：主力（推理/工具/报告）与辅助（摘要/查询改写）各自成卡，
 *   把「模型区别开」落到设置页
 * - 配置按分组展示（模型/Embedding/向量/基础设施/爬取与 Agent/RAG 参数）
 */

import { useQuery } from "@tanstack/react-query";
import {
  Settings,
  RefreshCw,
  Cloud,
  Cpu,
  Server,
  Brain,
  Database,
  Boxes,
  SlidersHorizontal,
  Globe,
} from "lucide-react";
import { api } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

function StatusCard({
  name,
  icon: Icon,
  connected,
  detail,
  offlineNote,
}: {
  name: string;
  icon: React.ElementType;
  connected: boolean;
  detail?: string;
  offlineNote?: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="rounded-lg bg-secondary p-2">
            <Icon size={16} className="text-foreground" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">{name}</p>
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              {connected ? detail || "已连接" : offlineNote || "未连接"}
            </p>
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2 py-0.5 text-[10px]",
            connected
              ? "border-success/30 bg-success/10 text-success"
              : "border-destructive/30 bg-destructive/10 text-destructive",
          )}
        >
          {connected ? "在线" : "离线"}
        </span>
      </div>
    </Card>
  );
}

/** 模型角色卡：把主力/辅助模型的分工讲清楚 */
function ModelRoleCard({
  icon: Icon,
  accent,
  roleLabel,
  provider,
  model,
  connected,
  duties,
  note,
}: {
  icon: React.ElementType;
  accent?: boolean;
  roleLabel: string;
  provider: string;
  model: string;
  connected: boolean;
  duties: string[];
  note?: string;
}) {
  return (
    <Card className={cn("p-5", accent && "border-brand/30")}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div
            className={cn(
              "rounded-lg p-2",
              accent ? "bg-brand/10 text-brand" : "bg-secondary text-foreground",
            )}
          >
            <Icon size={18} />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{roleLabel}</p>
            <p className="font-mono text-xs text-muted-foreground">
              {provider} · {model || "未配置"}
            </p>
          </div>
        </div>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[10px]",
            connected
              ? "border-success/30 bg-success/10 text-success"
              : "border-destructive/30 bg-destructive/10 text-destructive",
          )}
        >
          {connected ? "● 在线" : "○ 离线"}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {duties.map((d) => (
          <span key={d} className="rounded-full bg-secondary px-2 py-0.5 text-[11px] text-muted-foreground">
            {d}
          </span>
        ))}
      </div>
      {note && <p className="mt-2.5 text-xs text-muted-foreground">{note}</p>}
    </Card>
  );
}

const CONFIG_GROUPS: { label: string; icon: React.ElementType; match: (k: string) => boolean }[] = [
  { label: "模型", icon: Brain, match: (k) => k.includes("LLM") || k.includes("AUX") },
  { label: "Embedding", icon: Boxes, match: (k) => k.includes("EMBED") },
  { label: "向量存储", icon: Database, match: (k) => k.includes("VECTOR") || k.includes("QDRANT") || k.includes("FAISS") },
  { label: "基础设施", icon: Server, match: (k) => k.includes("REDIS") || k.includes("MYSQL") },
  { label: "爬取 / Agent", icon: Globe, match: (k) => k.includes("CRAWL") || k.includes("MAX_CONCURRENT") },
  {
    label: "RAG 参数",
    icon: SlidersHorizontal,
    match: (k) => k.includes("RAG") || k.includes("RERANK") || k === "AI_CACHE_DAYS" || k === "LOG_LEVEL" || k === "API_AUTH_ENABLED",
  },
];

export default function SettingsPage() {
  const configQuery = useQuery({ queryKey: ["settings-config"], queryFn: api.getConfig });
  const statusQuery = useQuery({
    queryKey: ["service-status"],
    queryFn: api.getServiceStatus,
    refetchInterval: 60_000,
  });

  const config = configQuery.data?.config ?? {};
  const status = statusQuery.data;
  const main = status?.llm_provider;
  const aux = status?.aux_llm;

  return (
    <div className="mx-auto max-w-5xl p-4 lg:p-6">
      <PageHeader
        icon={Settings}
        title="系统设置"
        subtitle="服务状态 · 模型角色 · 生效配置"
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              configQuery.refetch();
              statusQuery.refetch();
            }}
          >
            <RefreshCw className="h-4 w-4" /> 刷新
          </Button>
        }
      />

      {/* 服务状态四卡 */}
      {statusQuery.isLoading ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[72px]" />
          ))}
        </div>
      ) : (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatusCard
            name="Redis"
            icon={Server}
            connected={!!status?.redis?.connected}
            detail={status?.redis?.version ? `v${status.redis.version}` : undefined}
          />
          <StatusCard
            name="MySQL"
            icon={Database}
            connected={!!status?.mysql?.connected}
            detail={status?.mysql?.version ? `v${status.mysql.version.split("-")[0]}` : undefined}
          />
          <StatusCard
            name={`主力模型（${main?.provider ?? "?"}）`}
            icon={Cloud}
            connected={!!main?.connected}
            detail={main?.model}
          />
          <StatusCard
            name={`辅助模型（${aux?.provider ?? "未启用"}）`}
            icon={Cpu}
            connected={!!aux?.connected}
            detail={aux?.enabled ? aux.model : undefined}
            offlineNote={aux?.enabled ? "离线 · 回退主模型" : "未启用"}
          />
        </div>
      )}

      {/* 模型角色区 */}
      <h2 className="mb-3 text-sm font-semibold text-foreground">模型分工</h2>
      <div className="mb-6 grid gap-3 md:grid-cols-2">
        <ModelRoleCard
          icon={Cloud}
          roleLabel="主力模型"
          provider={main?.provider ?? config.LLM_PROVIDER ?? "—"}
          model={main?.model || config.LLM_MODEL || ""}
          connected={!!main?.connected}
          duties={["Agent 推理与工具调用", "结构化提取", "RAG 回答", "报告生成"]}
          note="所有关键路径都由主力模型承担；辅助模型不可用时自动回退到这里。"
        />
        <ModelRoleCard
          icon={Cpu}
          accent
          roleLabel="辅助模型（本地）"
          provider={aux?.provider ?? config.AUX_LLM_PROVIDER ?? "—"}
          model={aux?.model || config.AUX_LLM_MODEL || ""}
          connected={!!aux?.connected}
          duties={["上下文压缩摘要", "RAG 查询改写"]}
          note={
            aux && !aux.enabled
              ? "未启用：设置 AUX_LLM_PROVIDER 后生效（本地 Ollama，零 token 成本）。"
              : "本地运行零 token 成本；离线时相关后台任务自动回退主模型，功能不缺失。"
          }
        />
      </div>

      {/* 配置分组 */}
      <h2 className="mb-3 text-sm font-semibold text-foreground">生效配置</h2>
      {configQuery.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {CONFIG_GROUPS.map((group) => {
            const entries = Object.entries(config).filter(([k]) => group.match(k));
            if (entries.length === 0) return null;
            return (
              <Card key={group.label} className="overflow-hidden">
                <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
                  <group.icon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-sm font-medium text-foreground">{group.label}</span>
                  <span className="ml-auto text-[10px] text-muted-foreground">{entries.length} 项</span>
                </div>
                <div className="px-4 py-2">
                  {entries.map(([k, v]) => (
                    <div key={k} className="flex items-baseline justify-between gap-3 border-b border-border/40 py-1.5 last:border-0">
                      <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{k}</span>
                      <span className="truncate text-right font-mono text-xs text-foreground">
                        {typeof v === "boolean" ? (v ? "启用" : "关闭") : String(v) || "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
