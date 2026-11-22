/**
 * 产品级外壳 — 顶部品牌栏（命令搜索 + 模型状态 + 主题切换）+ 水平导航标签。
 * 参考 Vercel / Linear 的顶栏式信息架构：内容区全宽、导航一眼可见、
 * 键盘优先（Ctrl+K）。路由切换带轻量过渡。
 */

import { NavLink, Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  Bot,
  Globe,
  MessageSquare,
  Database,
  Activity,
  Settings,
  Sparkles,
  CalendarClock,
  Home,
} from "lucide-react";
import { CommandPalette } from "./CommandPalette";
import { ModelChip } from "./ModelChip";
import { useStore, THEMES } from "../store";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/utils";

// 路由 → 标签页标题（LandingPage 不经过 Layout，标题保持默认）
const PAGE_TITLES: Record<string, string> = {
  "/agent": "自主 Agent",
  "/crawl": "批量爬取",
  "/schedules": "定时采集",
  "/qa": "语义问答",
  "/data": "数据浏览",
  "/monitor": "任务监控",
  "/settings": "系统设置",
};

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", icon: Home, label: "首页", end: true },
  { to: "/agent", icon: Bot, label: "自主 Agent", end: true },
  { to: "/crawl", icon: Globe, label: "批量爬取" },
  { to: "/schedules", icon: CalendarClock, label: "定时采集" },
  { to: "/qa", icon: MessageSquare, label: "语义问答" },
  { to: "/data", icon: Database, label: "数据浏览" },
  { to: "/monitor", icon: Activity, label: "任务监控" },
  { to: "/settings", icon: Settings, label: "系统设置" },
];

function ThemeSwitcher() {
  const theme = useStore((s) => s.theme);
  const setTheme = useStore((s) => s.setTheme);
  return (
    <div
      className="inline-flex items-center rounded-full border border-border bg-secondary/60 p-0.5"
      role="radiogroup"
      aria-label="设计主题"
    >
      {THEMES.map((t) => (
        <button
          key={t.key}
          role="radio"
          aria-checked={theme === t.key}
          title={`${t.label} · ${t.hint}`}
          onClick={() => setTheme(t.key)}
          className={cn(
            "rounded-full px-2.5 py-1 text-[11px] font-medium transition-all duration-200",
            theme === t.key
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export default function Layout() {
  const location = useLocation();

  // 路由级标签页标题；旧 store 字段仅剩兼容持久化的用途，不再使用
  usePageTitle(PAGE_TITLES[location.pathname]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* 顶栏：品牌 + 命令搜索 + 状态 + 主题 */}
      <header className="shrink-0 border-b border-border bg-card/70 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-3 px-4 lg:px-8">
          <NavLink to="/" className="flex items-center gap-2.5">
            <span className="brand-mark flex h-8 w-8 items-center justify-center rounded-lg">
              <Sparkles size={16} className="text-brand-foreground" />
            </span>
            <span className="hidden flex-col leading-tight md:flex">
              <span className="text-sm font-bold tracking-tight text-foreground">NIA</span>
              <span className="text-[10px] text-muted-foreground">Nexus Intelligence Agent</span>
            </span>
          </NavLink>

          <div className="ml-auto flex items-center gap-2">
            <ModelChip />
            <ThemeSwitcher />
          </div>
        </div>

        {/* 水平导航标签 */}
        <nav className="mx-auto max-w-[1440px] px-4 lg:px-8">
          <div className="-mb-px flex gap-1 overflow-x-auto no-scrollbar">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2.5 text-[13px] transition-colors duration-150",
                    isActive
                      ? "border-brand font-medium text-foreground"
                      : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                  )
                }
              >
                <item.icon size={15} className="shrink-0" />
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </header>

      <CommandPalette />

      {/* 内容区：路由过渡 */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="flex-1 overflow-auto"
        >
          <Outlet />
        </motion.main>
      </AnimatePresence>
    </div>
  );
}