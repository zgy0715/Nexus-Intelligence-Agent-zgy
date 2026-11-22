/**
 * 语义问答 — 居中会话列 + 悬浮输入框（参考现代 AI 对话产品）。
 * 消费 POST /api/query/stream：来源引用先行，答案逐字渲染；
 * 支持停止生成 / 重新生成 / 多轮上下文。历史记录走 TanStack Query。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, RotateCcw, Send, Square, Trash2, Zap } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { ChatMessage, Source } from "@/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn, timeAgo } from "@/lib/utils";

const EXAMPLE_QUESTIONS = [
  "这些网站主要讲了什么？",
  "总结一下最近爬取的内容要点",
  "有哪些和 AI 相关的信息？",
];

/** 消息稳定 id：优先 crypto.randomUUID，不可用（非安全上下文等）时兜底时间戳+随机数。 */
function newMessageId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    /* ignore */
  }
  return `${Date.now()}-${Math.random()}`;
}

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5">
      <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
        <Zap className="h-3 w-3 text-brand" /> 来源
      </span>
      {sources.map((s, i) => (
        <a
          key={`${s.url}-${i}`}
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          title={s.content_snippet || s.title || s.url}
          className="max-w-[260px] truncate rounded-full border border-border bg-secondary/60 px-2 py-0.5 text-[11px] text-muted-foreground transition hover:border-brand hover:text-foreground"
        >
          [{i + 1}] {s.title || s.url}
        </a>
      ))}
    </div>
  );
}

/** 模型链路行：回答所用主力模型 */
function ModelChain({ models }: { models: { answer?: string } | null }) {
  if (!models?.answer) return null;
  return (
    <span className="rounded-full border border-border bg-secondary/60 px-1.5 py-px font-mono text-[10px] text-muted-foreground">
      {models.answer}
    </span>
  );
}

/** 一次检索的调试信息（sources 事件 debug 字段） */
export interface RetrievalDebug {
  debug: Record<string, unknown>;
  relevance: number;
  count: number;
}

/** 检索链路可视化：查询改写 → 向量召回 → BM25 召回 → RRF 融合 → 重排 → 来源。
 *  后端在 sources 事件里本来就带了 debug 计数，这里把它变成可读的管道图 —— 混合检索的实证。 */
function RetrievalPipeline({ data }: { data: RetrievalDebug }) {
  const num = (v: unknown) => (typeof v === "number" ? v : undefined);
  const rewrite = num(data.debug.rewrite);
  const vectorHits = num(data.debug.vector_hits);
  const bm25Hits = num(data.debug.bm25_hits);
  const rerankApplied = data.debug.rerank === true || (typeof data.debug.rerank === "number" && data.debug.rerank > 0);
  const steps: Array<{ label: string; value?: string; tone?: "brand" }> = [];
  if (rewrite != null && rewrite > 0) steps.push({ label: "查询改写", value: `+${rewrite}` });
  if (vectorHits != null) steps.push({ label: "向量召回", value: `${vectorHits}` });
  if (bm25Hits != null) steps.push({ label: "BM25 召回", value: `${bm25Hits}` });
  steps.push({ label: "RRF 融合" });
  if (rerankApplied) steps.push({ label: "重排", value: "开" });
  steps.push({ label: "来源", value: `${data.count}`, tone: "brand" });
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-1 gap-y-1 font-mono text-[10px]">
      {steps.map((s, i) => (
        <span key={s.label} className="flex items-center gap-1">
          {i > 0 && <span className="text-border">→</span>}
          <span
            className={cn(
              "rounded-full border px-1.5 py-px",
              s.tone === "brand"
                ? "border-brand/30 bg-brand/10 text-brand"
                : "border-border bg-secondary/50 text-muted-foreground",
            )}
          >
            {s.label}
            {s.value && <span className="ml-0.5 text-foreground/80">{s.value}</span>}
          </span>
        </span>
      ))}
      <span className="ml-1 rounded-full border border-border bg-secondary/50 px-1.5 py-px text-muted-foreground">
        相关度 <span className="text-foreground/80">{(data.relevance * 100).toFixed(0)}%</span>
      </span>
    </div>
  );
}

function MessageBlock({
  msg,
  streaming,
  models,
  retrieval,
  onRegenerate,
}: {
  msg: ChatMessage;
  streaming?: boolean;
  models?: { answer?: string } | null;
  /** 检索链路调试数据：仅最后一条 assistant 消息展示（内存态，刷新后消失） */
  retrieval?: RetrievalDebug | null;
  onRegenerate?: () => void;
}) {
  const isUser = msg.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-secondary px-4 py-2.5 text-sm leading-relaxed text-foreground">
          <p className="whitespace-pre-wrap">{msg.content}</p>
        </div>
      </div>
    );
  }
  return (
    <div className="group">
      <div className="markdown text-sm leading-relaxed">
        <ReactMarkdown>{msg.content || "…"}</ReactMarkdown>
        {streaming && <span className="mr-0.5 inline-block h-4 w-2 animate-pulse bg-brand/70 align-middle" />}
      </div>
      {retrieval && <RetrievalPipeline data={retrieval} />}
      {msg.sources && msg.sources.length > 0 && <SourceList sources={msg.sources} />}
      <div className="mt-2 flex items-center gap-2">
        {!streaming && <ModelChain models={models ?? null} />}
        {!streaming && (msg.created_at || msg.timestamp) && (
          <span className="text-[10px] text-muted-foreground/70">{timeAgo(msg.created_at || msg.timestamp)}</span>
        )}
        {!streaming && onRegenerate && (
          <button
            onClick={onRegenerate}
            className="flex items-center gap-1 text-[11px] text-muted-foreground opacity-0 transition hover:text-foreground group-hover:opacity-100"
          >
            <RotateCcw className="h-3 w-3" /> 重新生成
          </button>
        )}
      </div>
    </div>
  );
}

export default function QueryPage() {
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [pending, setPending] = useState<ChatMessage | null>(null);
  const [pendingModels, setPendingModels] = useState<{ answer?: string } | null>(null);
  /** 刚发出、还没出现在后端历史里的用户消息（带稳定 id）；历史 refetch 落地后清除 */
  const [pendingUserMsg, setPendingUserMsg] = useState<ChatMessage | null>(null);
  /** 最近一次检索的链路数据（sources 事件携带；仅内存态，用于检索链路可视化） */
  const [lastRetrieval, setLastRetrieval] = useState<RetrievalDebug | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const queryClient = useQueryClient();

  const historyQuery = useQuery({
    queryKey: ["chat-history"],
    queryFn: () => api.getQueryHistory(50),
  });
  // 用 useMemo 保证引用稳定（data 未就绪时也返回同一个空数组），供下方 decoratedHistory 依赖
  const history = useMemo<ChatMessage[]>(() => historyQuery.data?.history ?? [], [historyQuery.data]);

  /** 给历史消息补齐稳定 id；assistant 消息挂上产生它的问题（取其前面最近一条 user 消息），
   * 这样刷新后“重新生成”依然可用，不再依赖 lastQuestion 字符串匹配。 */
  const decoratedHistory: ChatMessage[] = useMemo(() => {
    let currentQuestion = "";
    return history.map((m) => {
      const base: ChatMessage = { ...m, id: m.id ?? newMessageId() };
      if (base.role === "user") {
        currentQuestion = base.content;
        return base;
      }
      return { ...base, question: base.question ?? currentQuestion };
    });
  }, [history]);

  useEffect(() => () => abortRef.current?.(), []);

  // 历史数据更新（发送完成后的 refetch 落地）时，移除临时的“刚发出”用户消息
  const historyUpdatedAt = historyQuery.dataUpdatedAt;
  useEffect(() => {
    setPendingUserMsg(null);
  }, [historyUpdatedAt]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length, pending?.content]);

  const doSend = useCallback(
    (text?: string) => {
      const question = (text ?? input).trim();
      if (!question || streaming) return;
      setInput("");
      setPendingUserMsg({ id: newMessageId(), role: "user", content: question });
      setStreaming(true);
      setPending({ id: newMessageId(), role: "assistant", content: "", question });
      setPendingModels(null);
      setLastRetrieval(null);

      let finished = false;
      const finish = () => {
        if (finished) return;
        finished = true;
        setPending((p) => {
          if (p) {
            queryClient.invalidateQueries({ queryKey: ["chat-history"] });
          }
          return null;
        });
        setStreaming(false);
        abortRef.current = null;
      };

      const cancel = api.streamQuery(
        question,
        (e) => {
          if (e.type === "sources") {
            setPending((p) => (p ? { ...p, sources: e.sources } : p));
            setPendingModels(e.models ?? null);
            setLastRetrieval({ debug: e.debug ?? {}, relevance: e.relevance, count: e.sources.length });
          } else if (e.type === "delta") {
            setPending((p) => (p ? { ...p, content: p.content + e.text } : p));
          } else if (e.type === "done") {
            finish();
          } else if (e.type === "error") {
            setPending((p) =>
              p ? { ...p, content: p.content || `（出错：${e.message}）` } : p,
            );
            finish();
          }
        },
      );
      abortRef.current = cancel;
    },
    [input, streaming, queryClient],
  );

  const finishStream = () => {
    setPending((p) => {
      if (p && p.content.trim()) {
        queryClient.invalidateQueries({ queryKey: ["chat-history"] });
      }
      return null;
    });
    setStreaming(false);
    abortRef.current = null;
  };

  const handleStop = () => {
    abortRef.current?.();
    finishStream();
  };

  const handleClear = async () => {
    try {
      await api.clearChatHistory();
      queryClient.invalidateQueries({ queryKey: ["chat-history"] });
      toast.success("聊天记录已清空");
    } catch {
      toast.error("清空失败");
    }
  };

  const showExamples = history.length === 0 && !pending;

  return (
    <div className="flex h-full flex-col">
      {/*  slim 标题栏 */}
      <div className="shrink-0 border-b border-border/60">
        <div className="mx-auto flex max-w-3xl items-center gap-2.5 px-4 py-3">
          <MessageSquare className="h-4 w-4 text-brand" />
          <h1 className="text-sm font-semibold text-foreground">语义问答</h1>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            混合检索 · 多轮上下文 · 流式输出
          </span>
          {history.length > 0 && (
            <Button variant="ghost" size="sm" className="ml-auto" onClick={handleClear}>
              <Trash2 size={14} /> 清空
            </Button>
          )}
        </div>
      </div>

      {/* 会话列 */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
          {historyQuery.isLoading ? (
            <div className="space-y-4">
              <Skeleton className="ml-auto h-10 w-2/3" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="ml-auto h-10 w-1/2" />
            </div>
          ) : showExamples && !streaming ? (
            <div className="flex flex-col items-center justify-center gap-5 py-20 text-center">
              <div className="brand-mark flex h-12 w-12 items-center justify-center rounded-2xl">
                <MessageSquare className="h-6 w-6 text-brand-foreground" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">基于已采集内容提问</h2>
                <p className="mt-1 text-sm text-muted-foreground">BM25 + 向量混合检索，回答附来源引用</p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => doSend(q)}
                    className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {decoratedHistory.map((msg, i) => {
                const isLastAssistant = msg.role === "assistant" && i === decoratedHistory.length - 1;
                const regenerateQuestion = isLastAssistant ? msg.question : undefined;
                return (
                  <MessageBlock
                    key={msg.id}
                    msg={msg}
                    retrieval={isLastAssistant ? lastRetrieval : undefined}
                    onRegenerate={regenerateQuestion ? () => doSend(regenerateQuestion) : undefined}
                  />
                );
              })}
              {pendingUserMsg && <MessageBlock msg={pendingUserMsg} />}
              {pending && (
                <MessageBlock msg={pending} streaming={streaming} models={pendingModels} retrieval={lastRetrieval} />
              )}
              {!pending && streaming && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand/70 [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand/70 [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand/70" />
                  </span>
                  检索中…
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* 悬浮输入框 */}
      <div className="shrink-0 bg-gradient-to-t from-background via-background to-transparent px-4 pb-5 pt-2">
        <div className="composer-focus mx-auto flex max-w-3xl items-center gap-2 rounded-2xl border border-border bg-card p-2 shadow-lg transition-all">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                doSend();
              }
            }}
            placeholder={streaming ? "正在生成回答…" : "输入你的问题，Enter 发送…"}
            className="h-10 border-0 bg-transparent focus-visible:ring-0"
            disabled={streaming}
          />
          {streaming ? (
            <Button size="icon" variant="destructive" className="h-10 w-10 shrink-0 rounded-xl" onClick={handleStop} aria-label="停止生成">
              <Square size={15} />
            </Button>
          ) : (
            <Button size="icon" className={cn("h-10 w-10 shrink-0 rounded-xl", input.trim() && "glow-cta")} onClick={() => doSend()} disabled={!input.trim()} aria-label="发送">
              <Send size={15} />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}