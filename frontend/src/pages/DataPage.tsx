/**
 * 数据浏览页面（v3.1）— TanStack Query 数据层 + a11y Dialog 详情。
 *
 * 详情分三个 Tab：结构化数据（JSON 树）/ 正文 / 原始 HTML（sandbox iframe 预览）。
 * 搜索防抖 + placeholderData 保持上一页数据（翻页不闪骨架屏）。
 */

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Database,
  ExternalLink,
  FileCode2,
  FileText,
  Braces,
  Search,
} from "lucide-react";
import { api } from "@/api/client";
import type { CrawlResult } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Dialog } from "@/components/Dialog";
import { useDebounce } from "@/hooks/useDebounce";
import { cn, timeAgo } from "@/lib/utils";

const PAGE_SIZE = 12;

/** 简易 JSON 树（折叠数组/对象，替代一坨 <pre>） */
function JsonNode({ value, depth = 0 }: { value: unknown; depth?: number }) {
  const [open, setOpen] = useState(depth < 1);
  if (value === null || typeof value !== "object") {
    return (
      <span className={cn(typeof value === "string" ? "text-emerald-600 dark:text-emerald-400" : "text-foreground")}>
        {typeof value === "string" ? `"${value}"` : String(value)}
      </span>
    );
  }
  const isArr = Array.isArray(value);
  const entries = isArr ? value.map((v, i) => [String(i), v] as const) : Object.entries(value as object);
  return (
    <div className={depth > 0 ? "ml-3 border-l pl-2" : ""}>
      <button onClick={() => setOpen((v) => !v)} className="font-mono text-xs text-muted-foreground hover:text-foreground">
        {open ? "▾" : "▸"} {isArr ? `[${entries.length}]` : `{${entries.length}}`}
      </button>
      {open && (
        <div>
          {entries.slice(0, 50).map(([k, v]) => (
            <div key={k} className="font-mono text-xs leading-5">
              <span className="text-sky-600 dark:text-sky-400">{k}</span>
              <span className="text-muted-foreground">: </span>
              <JsonNode value={v} depth={depth + 1} />
            </div>
          ))}
          {entries.length > 50 && <p className="font-mono text-xs text-muted-foreground">…共 {entries.length} 项</p>}
        </div>
      )}
    </div>
  );
}

function DetailDialog({ item, onClose }: { item: CrawlResult | null; onClose: () => void }) {
  const [tab, setTab] = useState<"data" | "text" | "html">("data");
  const detailQuery = useQuery({
    queryKey: ["data-item", item?.id],
    queryFn: () => api.getDataItem(item!.id!),
    enabled: !!item?.id,
  });
  const detail = detailQuery.data;

  const tabs = [
    { key: "data" as const, label: "结构化数据", icon: Braces, show: !!detail?.extracted_data && Object.keys(detail.extracted_data).length > 0 },
    { key: "text" as const, label: "正文", icon: FileText, show: !!detail?.content },
    { key: "html" as const, label: "原始 HTML", icon: FileCode2, show: true },
  ];

  return (
    <Dialog
      open={!!item}
      onClose={onClose}
      title={
        <div className="min-w-0">
          <p className="truncate">{item?.title || item?.url}</p>
          <a
            href={item?.url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs font-normal text-muted-foreground hover:text-foreground"
          >
            <ExternalLink className="h-3 w-3 shrink-0" />
            <span className="truncate">{item?.url}</span>
          </a>
        </div>
      }
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {item?.domain && <Badge variant="outline">{item.domain}</Badge>}
        {item?.extraction_method && <Badge variant="secondary">{item.extraction_method}</Badge>}
        {item?.created_at && <span className="text-xs text-muted-foreground">{timeAgo(item.created_at)}</span>}
      </div>

      <div className="mb-3 inline-flex rounded-lg border border-border p-0.5">
        {tabs
          .filter((t) => t.show)
          .map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-1.5 rounded-[7px] px-3 py-1.5 text-xs transition",
                tab === t.key ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <t.icon className="h-3 w-3" />
              {t.label}
            </button>
          ))}
      </div>

      {detailQuery.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : tab === "data" ? (
        <div className="rounded-lg border bg-muted/30 p-3">
          {detail?.extracted_data && Object.keys(detail.extracted_data).length > 0 ? (
            <JsonNode value={detail.extracted_data} />
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">无结构化数据</p>
          )}
        </div>
      ) : tab === "text" ? (
        <pre className="max-h-[46vh] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed">
          {detail?.content || "（无正文）"}
        </pre>
      ) : (
        <iframe
          title="原始 HTML 预览"
          sandbox=""
          srcDoc={detail?.raw_html || "<p>（无原始 HTML）</p>"}
          className="h-[46vh] w-full rounded-lg border bg-white"
        />
      )}
    </Dialog>
  );
}

export default function DataPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<CrawlResult | null>(null);
  const queryClient = useQueryClient();
  const debouncedSearch = useDebounce(search, 300);

  // 搜索词变化时回到第 1 页
  const [lastSearch, setLastSearch] = useState(debouncedSearch);
  if (debouncedSearch !== lastSearch) {
    setLastSearch(debouncedSearch);
    setPage(1);
  }

  const dataQuery = useQuery({
    queryKey: ["data", page, debouncedSearch],
    queryFn: () => api.getData(page, PAGE_SIZE, debouncedSearch || undefined),
    placeholderData: (prev) => prev, // 翻页/搜索时保持上一页数据，不闪骨架
  });

  const rows = dataQuery.data?.data ?? [];
  const total = dataQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-7xl p-4 lg:p-6">
      <PageHeader
        icon={Database}
        title="数据浏览"
        subtitle={`已爬取的结构化数据（共 ${total} 条）`}
        actions={
          <Button variant="outline" size="sm" onClick={() => queryClient.invalidateQueries({ queryKey: ["data"] })}>
            <Search className="h-4 w-4" /> 刷新
          </Button>
        }
      />

      {/* 搜索 */}
      <div className="relative mb-4 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="按 URL / 域名 / 标题搜索…"
          className="h-10 pl-9"
        />
      </div>

      {/* 表格 */}
      <Card className="overflow-hidden">
        {dataQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={Database}
            title="没有数据"
            description={debouncedSearch ? "换个搜索词试试，或先去爬取一些页面。" : "先用 Agent 或批量爬取采集一些页面。"}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="px-4 py-3 font-medium">标题 / URL</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">域名</th>
                  <th className="hidden px-4 py-3 font-medium sm:table-cell">提取方式</th>
                  <th className="hidden px-4 py-3 font-medium lg:table-cell">时间</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id || row.url} className="border-b border-border/60 transition hover:bg-accent/40">
                    <td className="max-w-[380px] px-4 py-2.5">
                      <p className="truncate font-medium text-foreground">{row.title || "（无标题）"}</p>
                      <a href={row.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 truncate text-xs text-muted-foreground hover:text-foreground">
                        {row.url}
                      </a>
                    </td>
                    <td className="hidden px-4 py-2.5 md:table-cell">
                      <span className="font-mono text-xs text-muted-foreground">{row.domain}</span>
                    </td>
                    <td className="hidden px-4 py-2.5 sm:table-cell">
                      <Badge variant="secondary">{row.extraction_method || "text"}</Badge>
                    </td>
                    <td className="hidden whitespace-nowrap px-4 py-2.5 text-xs text-muted-foreground lg:table-cell">
                      {row.created_at ? timeAgo(row.created_at) : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Button variant="outline" size="sm" onClick={() => setSelected(row)}>
                        查看
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 分页 */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
            <span>
              共 {total} 条 · 第 {page}/{totalPages} 页
            </span>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="上一页">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} aria-label="下一页">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      <DetailDialog item={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
