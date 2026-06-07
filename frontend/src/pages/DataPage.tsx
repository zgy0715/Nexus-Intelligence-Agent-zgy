/**
 * 数据浏览页面 — 分页表格 + 搜索
 */

import { useState, useEffect, useRef } from "react";
import { Database, Search, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { api } from "@/api/client";
import type { CrawlResult } from "@/types";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { timeAgo } from "@/lib/utils";

const PAGE_SIZE = 12;

function TableSkeleton() {
  return (
    <div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 border-b border-border px-4 py-3.5">
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
}

export default function DataPage() {
  const [data, setData] = useState<CrawlResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [firstLoad, setFirstLoad] = useState(true);
  const mountedRef = useRef(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    api
      .getData(page, PAGE_SIZE, debouncedSearch || undefined)
      .then((res) => {
        if (!controller.signal.aborted && mountedRef.current) {
          setData(res.data);
          setTotal(res.total);
        }
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!controller.signal.aborted && mountedRef.current) setData([]);
      })
      .finally(() => {
        if (!controller.signal.aborted && mountedRef.current) {
          setLoading(false);
          setFirstLoad(false);
        }
      });
    return () => controller.abort();
  }, [page, debouncedSearch]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary">
          <Database className="text-primary-foreground" size={22} />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">数据浏览</h1>
          <p className="text-xs text-muted-foreground">浏览和搜索已爬取的结构化数据</p>
        </div>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索 URL、域名或标题…"
          className="pl-10"
        />
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-secondary/50">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">URL</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">域名</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">标题</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">提取方法</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">创建时间</th>
            </tr>
          </thead>
          <tbody>
            {loading && firstLoad ? (
              <tr>
                <td colSpan={5}>
                  <TableSkeleton />
                </td>
              </tr>
            ) : loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center">
                  <Loader2 size={20} className="mx-auto animate-spin text-muted-foreground" />
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <EmptyState icon={Database} title="暂无数据" description="去「批量爬取」或「自主 Agent」采集一些数据吧。" />
                </td>
              </tr>
            ) : (
              data.map((item) => (
                <tr key={item.id} className="border-b border-border transition-colors last:border-0 hover:bg-secondary/40">
                  <td className="max-w-[240px] truncate px-4 py-3">
                    <a href={item.url} target="_blank" rel="noreferrer" className="text-foreground hover:text-primary hover:underline" title={item.url}>
                      {item.url}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{item.domain || "-"}</td>
                  <td className="max-w-[180px] truncate px-4 py-3 text-muted-foreground" title={item.title}>
                    {item.title || "-"}
                  </td>
                  <td className="px-4 py-3">
                    {item.extraction_method && <Badge variant="secondary">{item.extraction_method}</Badge>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                    {timeAgo(item.created_at || item.timestamp) || "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          共 {total} 条 · 第 {page}/{totalPages || 1} 页
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
            <ChevronLeft size={16} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
}
