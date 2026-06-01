import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Send, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '@/api/client';
import { useStore } from '@/store';
import type { ChatMessage, Source } from '@/types';

function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-[#3b82f6] hover:underline"
      >
        来源引用 ({sources.length})
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {open && (
        <div className="mt-2 space-y-1">
          {sources.map((s, i) => (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block truncate rounded px-2 py-1 text-xs text-[#3b82f6] hover:bg-[#1e1e2e]"
            >
              {s.title || s.url}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-lg px-4 py-2.5 text-sm ${
          isUser ? 'bg-[#3b82f6] text-white' : 'border border-[#1e1e2e] bg-[#111118] text-gray-300'
        }`}
      >
        <p className="whitespace-pre-wrap">{msg.content}</p>
        {!isUser && msg.sources && <SourceList sources={msg.sources} />}
      </div>
    </div>
  );
}

export default function QueryPage() {
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const chatHistory = useStore((s) => s.chatHistory);
  const setChatHistory = useStore((s) => s.setChatHistory);
  const addChatMessage = useStore((s) => s.addChatMessage);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getQueryHistory().then((res) => setChatHistory(res.history)).catch(() => {});
  }, [setChatHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || sending) return;
    setInput('');
    setSending(true);
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    };
    addChatMessage(userMsg);
    try {
      const res = await api.query(question);
      addChatMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
        timestamp: new Date().toISOString(),
      });
    } catch {
      addChatMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '抱歉，查询过程中出现错误，请稍后重试。',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-[#1e1e2e] px-6 py-4">
        <MessageSquare className="text-[#00ffa3]" size={24} />
        <h1 className="text-xl font-bold text-white">语义问答</h1>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {chatHistory.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-gray-600">输入问题开始对话</p>
          </div>
        ) : (
          <div className="space-y-4">
            {chatHistory.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-lg border border-[#1e1e2e] bg-[#111118] px-4 py-3 text-sm text-gray-500">
                  <Loader2 size={14} className="animate-spin" />
                  思考中...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="border-t border-[#1e1e2e] px-6 py-4">
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题..."
            className="flex-1 rounded-md border border-[#1e1e2e] bg-[#0a0a0f] px-4 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition focus:border-[#00ffa3] focus:shadow-[0_0_8px_rgba(0,255,163,0.3)]"
          />
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            className="flex items-center gap-2 rounded-md bg-[#00ffa3] px-5 py-2.5 text-sm font-semibold text-black transition hover:shadow-[0_0_16px_rgba(0,255,163,0.4)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
