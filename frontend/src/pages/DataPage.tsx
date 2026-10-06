/**
 * 数据浏览页面 — 分页表格 + 搜索
 */

import { useState, useEffect, useRef } from "react";
import { Database, Search, ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { toast } from "sonner";
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
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<CrawlResult | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
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
    setError("");
    api
      .getData(page, PAGE_SIZE, debouncedSearch || undefined, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted && mountedRef.current) {
          setData(res.data);
          setTotal(res.total);
        }
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!controller.signal.aborted && mountedRef.current) {
          const msg = err instanceof Error ? err.message : String(err);
          setData([]);
          setTotal(0);
          setError(msg);
          toast.error("加载数据失败", { description: msg });
        }
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

  const openDetail = async (item: CrawlResult) => {
    // 列表接口不返回 raw_html，详情单独按 id 拉取完整文档
    const id = item.id;
    setDetail(item);
    if (!id) return;
    setDetailLoading(true);
    try {
      const full = await api.getDataItem(id);
      if (mountedRef.current) setDetail(full);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error("加载详情失败", { description: msg });
    } finally {
      if (mountedRef.current) setDetailLoading(false);
    }
  };

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
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && firstLoad ? (
              <tr>
                <td colSpan={6}>
                  <TableSkeleton />
                </td>
              </tr>
            ) : loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center">
                  <Loader2 size={20} className="mx-auto animate-spin text-muted-foreground" />
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  {error ? (
                    <div className="px-4 py-10 text-center text-sm text-destructive">{error}</div>
                  ) : (
                    <EmptyState icon={Database} title="暂无数据" description="去「批量爬取」或「自主 Agent」采集一些数据吧。" />
                  )}
                </td>
              </tr>
            ) : (
              data.map((item, i) => (
                <tr key={item.id ?? `${item.url}-${i}`} className="border-b border-border transition-colors last:border-0 hover:bg-secondary/40">
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
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <Button variant="ghost" size="sm" onClick={() => void openDetail(item)}>
                      查看
                    </Button>
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

      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setDetail(null)}
        >
          <Card
            className="max-h-[85vh] w-full max-w-3xl overflow-auto p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="truncate text-base font-semibold text-foreground">
                  {detail.title || detail.url}
                </h2>
                <a
                  href={detail.url}
                  target="_blank"
                  rel="noreferrer"
                  className="line-clamp-1 text-xs text-primary hover:underline"
                >
                  {detail.url}
                </a>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setDetail(null)} aria-label="关闭">
                <X size={16} />
              </Button>
            </div>

            {detailLoading && (
              <div className="flex items-center gap-2 py-4 text-xs text-muted-foreground">
                <Loader2 size={14} className="animate-spin" /> 加载完整数据…
              </div>
            )}

            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              {detail.domain && <Badge variant="secondary">{detail.domain}</Badge>}
              {detail.extraction_method && <Badge variant="outline">{detail.extraction_method}</Badge>}
              {detail.created_at && (
                <Badge variant="outline">{new Date(detail.created_at).toLocaleString()}</Badge>
              )}
            </div>

            {detail.extracted_data && Object.keys(detail.extracted_data).length > 0 && (
              <div className="mb-4">
                <div className="mb-1.5 text-xs font-medium text-muted-foreground">结构化字段</div>
                <div className="space-y-1 rounded-lg border border-border bg-secondary/40 p-3">
                  {Object.entries(detail.extracted_data).map(([k, v]) => (
                    <div key={k} className="flex gap-2 text-xs">
                      <span className="shrink-0 font-medium text-foreground">{k}</span>
                      <span className="min-w-0 break-words text-muted-foreground">
                        {typeof v === "string" ? v : JSON.stringify(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="text-xs font-medium text-muted-foreground">正文</div>
            <pre className="mt-1.5 max-h-[45vh] overflow-auto whitespace-pre-wrap rounded-lg bg-secondary p-3 text-xs text-muted-foreground">
              {detail.content || "（无正文内容）"}
            </pre>
          </Card>
        </div>
      )}
    </div>
  );
}
