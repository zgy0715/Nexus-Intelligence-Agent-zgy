/**
 * CommandPalette — Ctrl+K 全局命令面板（导航 + 快捷动作）。
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  Activity,
  Bot,
  CornerDownLeft,
  Database,
  Globe,
  MessageSquare,
  Search,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandItem {
  label: string;
  hint: string;
  to: string;
  icon: React.ElementType;
  keywords: string;
}

const COMMANDS: CommandItem[] = [
  { label: "自主 Agent", hint: "核心控制台", to: "/", icon: Bot, keywords: "agent 爬取 自主" },
  { label: "批量爬取", hint: "整站 / 批量抓取", to: "/crawl", icon: Globe, keywords: "crawl batch 爬取 整站" },
  { label: "语义问答", hint: "流式 RAG 问答", to: "/qa", icon: MessageSquare, keywords: "qa query 问答 检索" },
  { label: "数据浏览", hint: "已爬取数据", to: "/data", icon: Database, keywords: "data 数据 浏览" },
  { label: "任务监控", hint: "统计图表", to: "/monitor", icon: Activity, keywords: "monitor 监控 统计 图表" },
  { label: "系统设置", hint: "服务状态与配置", to: "/settings", icon: Settings, keywords: "settings 设置 配置 状态" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
        setQuery("");
        setIndex(0);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COMMANDS;
    return COMMANDS.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.hint.toLowerCase().includes(q) ||
        c.keywords.includes(q),
    );
  }, [query]);

  const go = (to: string) => {
    setOpen(false);
    navigate(to);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[12vh] backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="w-[560px] max-w-[92vw] overflow-hidden rounded-xl border bg-popover shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2.5 border-b px-4">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setIndex(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setIndex((i) => Math.min(i + 1, items.length - 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setIndex((i) => Math.max(i - 1, 0));
                  } else if (e.key === "Enter" && items[index]) {
                    go(items[index].to);
                  }
                }}
                placeholder="跳转到…（↑↓ 选择，Enter 确认）"
                className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="rounded border bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                ESC
              </kbd>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              {items.length === 0 && (
                <p className="px-3 py-6 text-center text-sm text-muted-foreground">没有匹配的命令</p>
              )}
              {items.map((item, i) => (
                <button
                  key={item.to}
                  onClick={() => go(item.to)}
                  onMouseEnter={() => setIndex(i)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition",
                    i === index ? "bg-accent text-accent-foreground" : "text-foreground",
                  )}
                >
                  <item.icon className="h-4 w-4 text-muted-foreground" />
                  <span className="flex-1 text-sm">{item.label}</span>
                  <span className="text-xs text-muted-foreground">{item.hint}</span>
                  {i === index && <CornerDownLeft className="h-3 w-3 text-muted-foreground" />}
                </button>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
