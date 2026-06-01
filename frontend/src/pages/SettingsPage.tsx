import { useState, useEffect } from 'react';
import { Settings, RefreshCw, Server } from 'lucide-react';
import { api } from '@/api/client';
import type { ServiceStatus } from '@/types';

function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
      connected ? 'bg-[#00ffa3]/10 text-[#00ffa3]' : 'bg-[#ef4444]/10 text-[#ef4444]'
    }`}>
      <span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-[#00ffa3]' : 'bg-[#ef4444]'}`} />
      {connected ? '已连接' : '未连接'}
    </span>
  );
}

function ServiceCard({ name, status }: { name: string; status: { connected: boolean; version?: string } }) {
  return (
    <div className="rounded-lg border border-[#1e1e2e] bg-[#111118] p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server size={18} className="text-[#3b82f6]" />
          <span className="font-medium text-white">{name}</span>
        </div>
        <StatusBadge connected={status.connected} />
      </div>
      {status.version && (
        <p className="mt-2 text-xs text-gray-500">版本: {status.version}</p>
      )}
    </div>
  );
}

function OllamaServiceCard({ name, status }: { name: string; status: ServiceStatus['ollama'] }) {
  return (
    <div className="rounded-lg border border-[#1e1e2e] bg-[#111118] p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server size={18} className="text-[#3b82f6]" />
          <span className="font-medium text-white">{name}</span>
        </div>
        <StatusBadge connected={status.connected} />
      </div>
      {status.version && (
        <p className="mt-2 text-xs text-gray-500">版本: {status.version}</p>
      )}
      {status.models && status.models.length > 0 && (
        <div className="mt-3 border-t border-[#1e1e2e] pt-3">
          <p className="mb-1.5 text-xs text-gray-500">可用模型</p>
          <div className="flex flex-wrap gap-1.5">
            {status.models.map((m) => (
              <span key={m} className="rounded bg-[#1e1e2e] px-2 py-0.5 text-xs text-[#00ffa3]">{m}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [services, setServices] = useState<ServiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [c, s] = await Promise.all([api.getConfig(), api.getServiceStatus()]);
      setConfig(c.config);
      setServices(s);
    } catch (_e) {
      console.error(_e);
    } finally {
      setLoading(false);
      setRefreshing(false);
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
    return <div className="flex h-full items-center justify-center text-gray-500">加载中...</div>;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings className="text-[#00ffa3]" size={28} />
          <h1 className="text-2xl font-bold text-white">系统设置</h1>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-md border border-[#1e1e2e] px-3 py-2 text-sm text-gray-400 transition hover:border-[#00ffa3] hover:text-[#00ffa3] disabled:opacity-40"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      <div className="rounded-lg border border-[#1e1e2e] bg-[#111118]">
        <div className="border-b border-[#1e1e2e] px-5 py-3">
          <h2 className="text-sm font-medium text-gray-300">配置项</h2>
        </div>
        {Object.keys(config).length === 0 ? (
          <p className="px-5 py-6 text-center text-sm text-gray-600">暂无配置</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(config).map(([key, value], i) => (
                <tr key={key} className={`border-b border-[#1e1e2e] last:border-0 ${i % 2 === 1 ? 'bg-[#0d0d14]' : ''}`}>
                  <td className="px-5 py-2.5 font-mono text-[#00ffa3]">{key}</td>
                  <td className="px-5 py-2.5 text-gray-400">{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-gray-300">服务状态</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {services && (
            <>
              <ServiceCard name="Redis" status={services.redis} />
              <ServiceCard name="MongoDB" status={services.mongodb} />
              <OllamaServiceCard name="Ollama" status={services.ollama} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
