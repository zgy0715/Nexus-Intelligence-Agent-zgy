import { useState, useEffect, useCallback } from 'react';
import { Database, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '@/api/client';
import type { CrawlResult } from '@/types';

const PAGE_SIZE = 10;

export default function DataPage() {
  const [data, setData] = useState<CrawlResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchData = useCallback(async (fetchPage: number) => {
    setLoading(true);
    try {
      const res = await api.getData(fetchPage, PAGE_SIZE, debouncedSearch || undefined);
      setData(res.data);
      setTotal(res.total);
    } catch {
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch]);

  useEffect(() => {
    fetchData(page);
  }, [page, fetchData]);

  useEffect(() => {
    setPage(1);
    fetchData(1);
  }, [debouncedSearch, fetchData]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Database className="text-[#00ffa3]" size={28} />
        <h1 className="text-2xl font-bold text-white">数据浏览</h1>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索 URL、域名或标题..."
          className="w-full rounded-md border border-[#1e1e2e] bg-[#111118] py-2.5 pl-9 pr-4 text-sm text-white placeholder-gray-500 outline-none transition focus:border-[#00ffa3] focus:shadow-[0_0_8px_rgba(0,255,163,0.3)]"
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-[#1e1e2e]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2e] bg-[#111118]">
              <th className="px-4 py-3 text-left font-medium text-gray-400">URL</th>
              <th className="px-4 py-3 text-left font-medium text-gray-400">域名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-400">标题</th>
              <th className="px-4 py-3 text-left font-medium text-gray-400">提取方法</th>
              <th className="px-4 py-3 text-left font-medium text-gray-400">创建时间</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">加载中...</td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-600">暂无数据</td>
              </tr>
            ) : (
              data.map((item, i) => (
                <tr
                  key={item.id}
                  className={`border-b border-[#1e1e2e] transition hover:bg-[#1e1e2e]/50 ${i % 2 === 1 ? 'bg-[#0d0d14]' : ''}`}
                >
                  <td className="max-w-[200px] truncate px-4 py-3 text-gray-300">{item.url}</td>
                  <td className="px-4 py-3 text-gray-400">{item.domain || '-'}</td>
                  <td className="max-w-[150px] truncate px-4 py-3 text-gray-400">{item.title || '-'}</td>
                  <td className="px-4 py-3 text-gray-400">{item.method || '-'}</td>
                  <td className="px-4 py-3 text-gray-500">{item.timestamp}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-400">
        <span>共 {total} 条 · 第 {page}/{totalPages || 1} 页</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded border border-[#1e1e2e] p-1.5 transition hover:border-[#00ffa3] disabled:cursor-not-allowed disabled:opacity-30"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded border border-[#1e1e2e] p-1.5 transition hover:border-[#00ffa3] disabled:cursor-not-allowed disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
