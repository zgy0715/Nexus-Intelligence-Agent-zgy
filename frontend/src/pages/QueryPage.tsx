/**
 * 语义问答页面 — 聊天式交互 + 来源引用 + Markdown 答案
 */

import { useState, useEffect, useRef } from "react";
import { MessageSquare, Send, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { api } from "@/api/client";
import { useStore } from "@/store";
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
      <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">来源引用</p>
      {sources.map((s, i) => (
        <a
          key={`${s.url}-${i}`}
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block truncate py-0.5 text-xs text-primary hover:underline"
        >
          [{i + 1}] {s.title || s.url}
        </a>
      ))}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
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
          <div className="markdown">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        )}
        {!isUser && msg.sources && <SourceList sources={msg.sources} />}
        {(msg.created_at || msg.timestamp) && (
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
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const chatHistory = useStore((s) => s.chatHistory);
  const setChatHistory = useStore((s) => s.setChatHistory);
  const addChatMessage = useStore((s) => s.addChatMessage);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadingHistory(true);
    api
      .getQueryHistory()
      .then((res) => {
        if (!cancelled && mountedRef.current) setChatHistory(res.history);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled && mountedRef.current) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [setChatHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const send = async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || sending) return;
    setInput("");
    setSending(true);
    addChatMessage({ role: "user", content: question });
    try {
      const res = await api.query(question);
      if (mountedRef.current)
        addChatMessage({ role: "assistant", content: res.answer, sources: res.sources });
    } catch {
      if (mountedRef.current)
        addChatMessage({ role: "assistant", content: "抱歉，查询过程中出现错误，请稍后重试。" });
    } finally {
      if (mountedRef.current) setSending(false);
    }
  };

  const handleClear = async () => {
    try {
      await api.clearChatHistory();
      if (mountedRef.current) setChatHistory([]);
      toast.success("聊天记录已清空");
    } catch {
      toast.error("清空失败");
    }
  };

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
            <p className="text-xs text-muted-foreground">基于已爬取数据的智能问答</p>
          </div>
        </div>
        {chatHistory.length > 0 && (
          <Button variant="outline" size="sm" onClick={handleClear}>
            <Trash2 size={14} /> 清空
          </Button>
        )}
      </div>

      {/* 聊天区域 */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loadingHistory ? (
          <div className="space-y-4">
            <Skeleton className="ml-auto h-16 w-2/3" />
            <Skeleton className="h-24 w-3/4" />
            <Skeleton className="ml-auto h-12 w-1/2" />
          </div>
        ) : chatHistory.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="开始提问"
            description="基于已爬取的数据进行语义问答。试试下面的示例问题："
            action={
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
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
            {chatHistory.map((msg, i) => (
              <MessageBubble key={msg.created_at || msg.timestamp || i} msg={msg} />
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-card px-4 py-3 text-sm text-muted-foreground shadow-sm">
                  <span className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
                  </span>
                  思考中…
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
                send();
              }
            }}
            placeholder="输入你的问题…"
            className="h-11"
          />
          <Button size="lg" onClick={() => send()} loading={sending} disabled={!input.trim()}>
            <Send size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
}
