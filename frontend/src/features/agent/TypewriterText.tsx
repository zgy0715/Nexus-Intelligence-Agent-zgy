/**
 * TypewriterText — 运行中最新「思考」的打字机效果。
 *
 * 后端 thought 事件是整段文本，这里在前端做逐字浮现（间隔 12ms，约 80 字/秒），
 * 只用于正在生成的最后一条；历史回放/已完成事件直接整段渲染。
 */

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface TypewriterTextProps {
  text: string;
  className?: string;
  /** 每字符间隔毫秒 */
  speed?: number;
  enabled?: boolean;
}

export function TypewriterText({ text, className, speed = 12, enabled = true }: TypewriterTextProps) {
  const [shown, setShown] = useState(enabled ? 0 : text.length);

  useEffect(() => {
    if (!enabled) {
      setShown(text.length);
      return;
    }
    setShown(0);
    if (!text) return;
    const timer = setInterval(() => {
      setShown((n) => {
        if (n >= text.length) {
          clearInterval(timer);
          return n;
        }
        return n + 2; // 每跳 2 字符，长文本不至于等太久
      });
    }, speed);
    return () => clearInterval(timer);
  }, [text, speed, enabled]);

  const done = shown >= text.length;
  return (
    <span className={cn("whitespace-pre-wrap", className)}>
      {text.slice(0, shown)}
      {!done && <span className="animate-pulse">▍</span>}
    </span>
  );
}
