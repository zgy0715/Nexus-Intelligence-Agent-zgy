import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 Tailwind 类名，解决冲突（如 px-2 + px-4 → px-4）。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 相对时间格式化（如 "3 分钟前"）。 */
export function timeAgo(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const diff = Date.now() - d.getTime();
  if (Number.isNaN(diff)) return "";
  const s = Math.floor(diff / 1000);
  if (s < 60) return "刚刚";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  const day = Math.floor(h / 24);
  if (day < 30) return `${day} 天前`;
  return d.toLocaleDateString("zh-CN");
}

/** 截断长字符串。 */
export function truncate(s: string, n = 80): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
