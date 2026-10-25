/**
 * 语义问答页面 — 流式输出聊天（v3）。
 *
 * 消费 POST /api/query/stream：来源引用先行，答案逐字渲染；
 * 支持停止生成 / 重新生成。历史记录走 TanStack Query。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, RotateCcw, Send, Square, Trash2, Zap } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { ChatMessage, Source } from "@/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn, timeAgo } from "@/lib/utils";

const EXAMPLE_QUESTIONS = [
  "这些网站主要讲了什么？",
  "总结一下最近爬取的内容要点",
  "有哪些和 AI 相关的信息？",
];

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="mt-2 border-t border-border pt-2">
      <p className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        <Zap className="h-3 w-3" /> 来源引用（混合检索）
      </p>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((s, i) => (
          <a
            key={`${s.url}-${i}`}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            title={s.content_snippet || s.title || s.url}
            className="max-w-[280px] truncate rounded-full border border-border bg-secondary px-2 py-0.5 text-[11px] text-muted-foreground transition hover:border-brand hover:text-foreground"
          >
            [{i + 1}] {s.title || s.url}
          </a>
        ))}
      </div>
    </div>
  );
}

/** 模型链路行：改写（辅助模型）→ 回答（主力模型） */
function ModelChain({ models }: { models: { answer?: string; rewrite?: string | null } | null }) {
  if (!models?.answer) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[10px] text-muted-foreground">
      {models.rewrite && (
        <>
          <span className="rounded-full border border-brand/40 bg-brand/10 px-1.5 py-px font-mono text-brand">
            改写 · {models.rewrite}
          </span>
          <span>→</span>
        </>
      )}
      <span className="rounded-full border border-border bg-secondary px-1.5 py-px font-mono">
        回答 · {models.answer}
      </span>
    </div>
  );
}

function MessageBubble({
  msg,
  streaming,
  models,
  onRegenerate,
}: {
  msg: ChatMessage;
  streaming?: boolean;
  models?: { answer?: string; rewrite?: string | null } | null;
  onRegenerate?: () => void;
}) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md border border-border bg-card text-card-foreground",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <>
            <div className="markdown">
              <ReactMarkdown>{msg.content || "…"}</ReactMarkdown>
            </div>
            {streaming && <span className="mr-0.5 inline-block h-4 w-2 animate-pulse bg-foreground/60 align-middle" />}
            {msg.sources && msg.sources.length > 0 && <SourceList sources={msg.sources} />}
            {!streaming && <ModelChain models={models ?? null} />}
            {!streaming && onRegenerate && (
              <button
                onClick={onRegenerate}
                className="mt-1.5 flex items-center gap-1 text-[11px] text-muted-foreground transition hover:text-foreground"
              >
                <RotateCcw className="h-3 w-3" /> 重新生成
              </button>
            )}
          </>
        )}
        {!streaming && (msg.created_at || msg.timestamp) && (
          <div className={cn("mt-1.5 text-[10px]", isUser ? "text-primary-foreground/70" : "text-muted-foreground")}>
            {timeAgo(msg.created_at || msg.timestamp)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function QueryPage() {
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [pending, setPending] = useState<ChatMessage | null>(null);
  const [pendingModels, setPendingModels] = useState<{ answer?: string; rewrite?: string | null } | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const queryClient = useQueryClient();

  const historyQuery = useQuery({
    queryKey: ["chat-history"],
    queryFn: () => api.getQueryHistory(50),
  });
  const history: ChatMessage[] = historyQuery.data?.history ?? [];

  useEffect(() => () => abortRef.current?.(), []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length, pending?.content]);

  const doSend = useCallback(
    (text?: string) => {
      const question = (text ?? input).trim();
      if (!question || streaming) return;
      setInput("");
      setLastQuestion(question);
      setStreaming(true);
      setPending({ role: "assistant", content: "" });
      setPendingModels(null);

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

  const handleStop = () => {
    abortRef.current?.();
    finishStream();
  };

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
      {/* 标题栏 */}
      <div className="flex items-center justify-between border-b border-border bg-card px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary">
            <MessageSquare className="text-primary-foreground" size={20} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground">语义问答</h1>
            <p className="text-xs text-muted-foreground">流式输出 · BM25+向量混合检索 · 本地辅助模型改写查询</p>
          </div>
        </div>
        {history.length > 0 && (
          <Button variant="outline" size="sm" onClick={handleClear}>
            <Trash2 size={14} /> 清空
          </Button>
        )}
      </div>

      {/* 聊天区域 */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {historyQuery.isLoading ? (
          <div className="space-y-4">
            <Skeleton className="ml-auto h-16 w-2/3" />
            <Skeleton className="h-24 w-3/4" />
            <Skeleton className="ml-auto h-12 w-1/2" />
          </div>
        ) : showExamples && !streaming ? (
          <EmptyState
            icon={MessageSquare}
            title="开始提问"
            description="基于已爬取的数据进行语义问答。试试下面的示例问题："
            action={
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => doSend(q)}
                    className="rounded-full bg-secondary px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                  >
                    {q}
                  </button>
                ))}
              </div>
            }
          />
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {history.map((msg, i) => (
              <MessageBubble
                key={msg.created_at || msg.timestamp || i}
                msg={msg}
                onRegenerate={
                  msg.role === "assistant" && i === history.length - 1 && lastQuestion
                    ? () => doSend(lastQuestion)
                    : undefined
                }
              />
            ))}
            {lastQuestion && !history.some((m) => m.role === "user" && m.content === lastQuestion) && (
              <MessageBubble msg={{ role: "user", content: lastQuestion }} />
            )}
            {pending && (
              <MessageBubble msg={pending} streaming={streaming} models={pendingModels} />
            )}
            {!pending && streaming && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-card px-4 py-3 text-sm text-muted-foreground shadow-sm">
                  <span className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
                  </span>
                  检索中…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* 输入框 */}
      <div className="border-t border-border bg-card px-6 py-4">
        <div className="mx-auto flex max-w-3xl gap-3">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                doSend();
              }
            }}
            placeholder={streaming ? "正在生成回答…" : "输入你的问题…"}
            className="h-11"
            disabled={streaming}
          />
          {streaming ? (
            <Button size="lg" variant="destructive" onClick={handleStop}>
              <Square size={16} />
            </Button>
          ) : (
            <Button size="lg" onClick={() => doSend()} disabled={!input.trim()}>
              <Send size={16} />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
