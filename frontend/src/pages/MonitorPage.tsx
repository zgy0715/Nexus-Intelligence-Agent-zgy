import { useState, useEffect, useCallback } from 'react';
import { Activity, ListChecks, TrendingUp, Cpu, Clock, Inbox, AlertTriangle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '@/api/client';
import type { MonitorStats } from '@/types';

interface DomainStat {
  domain: string;
  count: number;
}

function MetricCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string | number; color: string }) {
  return (
    <div className="rounded-lg border border-[#1e1e2e] bg-[#111118] p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-2xl font-bold text-white">{value}</p>
          <p className="mt-1 text-xs text-gray-500">{label}</p>
        </div>
        <div className={`rounded-lg p-2.5 ${color}`}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}

export default function MonitorPage() {
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [domains, setDomains] = useState<DomainStat[]>([]);
  const [alert, setAlert] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    try {
      const [s, d, a] = await Promise.all([api.getMonitorStats(), api.getMonitorDomains(), api.getMonitorAlert()]);
      setStats(s);
      setDomains(d.domains);
      setAlert(a.alert);
    } catch (_e) {
      console.error(_e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 30000);
    return () => clearInterval(interval);
  }, [loadAll]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-gray-500">加载中...</div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Activity className="text-[#00ffa3]" size={28} />
        <h1 className="text-2xl font-bold text-white">任务监控</h1>
      </div>

      {alert ? (
        <div className="flex items-center gap-2 rounded-lg border border-[#ef4444]/30 bg-[#ef4444]/10 px-4 py-3 text-sm text-[#ef4444]">
          <AlertTriangle size={16} />
          {alert}
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-lg border border-[#00ffa3]/30 bg-[#00ffa3]/10 px-4 py-3 text-sm text-[#00ffa3]">
          <Activity size={16} />
          系统运行正常
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard icon={ListChecks} label="总任务数" value={stats?.total_tasks ?? '-'} color="bg-[#3b82f6]/10 text-[#3b82f6]" />
        <MetricCard icon={TrendingUp} label="成功率" value={stats ? `${stats.success_rate}%` : '-'} color="bg-[#00ffa3]/10 text-[#00ffa3]" />
        <MetricCard icon={Cpu} label="LLM调用次数" value={stats?.llm_calls ?? '-'} color="bg-[#f59e0b]/10 text-[#f59e0b]" />
        <MetricCard icon={Clock} label="平均LLM耗时" value={stats ? `${stats.avg_llm_time}ms` : '-'} color="bg-[#a855f7]/10 text-[#a855f7]" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <MetricCard icon={Inbox} label="队列中待抓取" value={stats?.queue_pending ?? '-'} color="bg-[#3b82f6]/10 text-[#3b82f6]" />
        <MetricCard icon={AlertTriangle} label="死信队列" value={stats?.dead_letter_count ?? '-'} color="bg-[#ef4444]/10 text-[#ef4444]" />
      </div>

      <div className="rounded-lg border border-[#1e1e2e] bg-[#111118] p-5">
        <h2 className="mb-4 text-sm font-medium text-gray-400">域名分布</h2>
        {domains.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-600">暂无数据</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={domains}>
              <XAxis dataKey="domain" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#1e1e2e' }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#1e1e2e' }} />
              <Tooltip
                contentStyle={{ background: '#111118', border: '1px solid #1e1e2e', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Bar dataKey="count" fill="#00ffa3" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
