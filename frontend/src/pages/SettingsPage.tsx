/**
 * 系统设置页面 — 配置展示 + 服务状态
 */

import { useState, useEffect, useRef } from "react";
import { Settings, RefreshCw, Cpu, Database } from "lucide-react";
import { api } from "@/api/client";
import type { ServiceStatus } from "@/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

function ServiceCard({
  name,
  icon: Icon,
  status,
  extra,
}: {
  name: string;
  icon: React.ElementType;
  status: { connected: boolean; version?: string };
  extra?: React.ReactNode;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-secondary p-2">
            <Icon size={16} className="text-muted-foreground" />
          </div>
          <span className="font-medium text-foreground">{name}</span>
        </div>
        <Badge variant={status.connected ? "success" : "destructive"}>
          <span className={`h-1.5 w-1.5 rounded-full ${status.connected ? "bg-success" : "bg-destructive"}`} />
          {status.connected ? "已连接" : "未连接"}
        </Badge>
      </div>
      {status.version && <p className="mt-2 text-xs text-muted-foreground">版本: {status.version}</p>}
      {extra}
    </Card>
  );
}

export default function SettingsPage() {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [services, setServices] = useState<ServiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadData = async () => {
    try {
      const [c, s] = await Promise.all([api.getConfig(), api.getServiceStatus()]);
      if (mountedRef.current) {
        setConfig(c.config);
        setServices(s);
      }
    } catch {
      /* ignore */
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6 p-6">
        <Skeleton className="h-10 w-48" />
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  const configGroups: Record<string, [string, string][]> = {
    "LLM 配置": Object.entries(config).filter(
      ([k]) => k.includes("LLM") || k.includes("DEEPSEEK") || k.includes("OPENAI") || k.includes("QWEN") || k.includes("OLLAMA"),
    ),
    "Embedding 配置": Object.entries(config).filter(([k]) => k.includes("EMBED")),
    向量存储: Object.entries(config).filter(([k]) => k.includes("VECTOR") || k.includes("QDRANT") || k.includes("FAISS")),
    基础设施: Object.entries(config).filter(([k]) => k.includes("REDIS") || k.includes("MONGO")),
    "爬取 / Agent": Object.entries(config).filter(([k]) => k.includes("CRAWL") || k.includes("AGENT")),
    "AI 参数": Object.entries(config).filter(([k]) => k.includes("CACHE") || k.includes("THRESHOLD") || k.includes("LOG")),
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary">
            <Settings className="text-primary-foreground" size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">系统设置</h1>
            <p className="text-xs text-muted-foreground">查看配置和服务状态</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /> 刷新
        </Button>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">服务状态</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {services && (
            <>
              <ServiceCard name="Redis" icon={Database} status={services.redis} />
              <ServiceCard name="MongoDB" icon={Database} status={services.mongodb} />
              {services.llm_provider && (
                <ServiceCard
                  name={services.llm_provider.provider || "LLM"}
                  icon={Cpu}
                  status={services.llm_provider}
                  extra={
                    services.llm_provider.model && (
                      <p className="mt-2 text-xs text-muted-foreground">模型: {services.llm_provider.model}</p>
                    )
                  }
                />
              )}
            </>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-muted-foreground">配置详情</h2>
        {Object.entries(configGroups).map(
          ([group, entries]) =>
            entries.length > 0 && (
              <Card key={group} className="overflow-hidden">
                <div className="border-b border-border bg-secondary/50 px-5 py-3">
                  <h3 className="text-xs font-medium text-muted-foreground">{group}</h3>
                </div>
                <table className="w-full text-sm">
                  <tbody>
                    {entries.map(([key, value]) => (
                      <tr key={key} className="border-b border-border last:border-0">
                        <td className="px-5 py-2.5 font-mono text-xs text-primary">{key}</td>
                        <td className="px-5 py-2.5 text-xs text-muted-foreground">{value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            ),
        )}
      </div>
    </div>
  );
}
