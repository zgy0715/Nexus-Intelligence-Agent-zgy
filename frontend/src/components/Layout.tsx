/**
 * 布局组件 — 侧边栏 + 顶栏 + 内容区（含暗色切换）
 */

import { NavLink, Outlet } from "react-router-dom";
import {
  Bot,
  Globe,
  MessageSquare,
  Database,
  Activity,
  Settings,
  Menu,
  X,
  Sun,
  Moon,
  Sparkles,
} from "lucide-react";
import { useStore } from "../store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

const navItems = [
  { to: "/", icon: Bot, label: "自主 Agent", end: true },
  { to: "/crawl", icon: Globe, label: "批量爬取" },
  { to: "/qa", icon: MessageSquare, label: "语义问答" },
  { to: "/data", icon: Database, label: "数据浏览" },
  { to: "/monitor", icon: Activity, label: "任务监控" },
  { to: "/settings", icon: Settings, label: "系统设置" },
];

export default function Layout() {
  const { sidebarOpen, toggleSidebar, setSidebarOpen, theme, toggleTheme } = useStore();

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* 移动端遮罩 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <aside
        className={cn(
          "fixed z-40 flex h-full flex-col border-r border-border bg-card transition-all duration-300 lg:relative",
          sidebarOpen ? "w-60" : "w-0 lg:w-16",
        )}
      >
        {/* Logo */}
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-border px-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary shadow-sm">
            <Sparkles size={18} className="text-primary-foreground" />
          </div>
          {sidebarOpen && (
            <div className="flex flex-col overflow-hidden">
              <span className="whitespace-nowrap text-sm font-bold text-foreground">NIA</span>
              <span className="whitespace-nowrap text-[10px] text-muted-foreground">
                Nexus Intelligence Agent
              </span>
            </div>
          )}
        </div>

        {/* 导航 */}
        <nav className="flex flex-1 flex-col gap-1 px-2 py-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => {
                if (window.innerWidth < 1024) setSidebarOpen(false);
              }}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all duration-200",
                  !sidebarOpen && "justify-center",
                  isActive
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                )
              }
            >
              <item.icon size={18} className="shrink-0" />
              {sidebarOpen && <span className="whitespace-nowrap text-sm">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* 底部状态 */}
        <div className="shrink-0 border-t border-border px-4 py-3">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success/60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
              </span>
              <span className="text-[11px] text-muted-foreground">系统就绪</span>
            </div>
          )}
        </div>
      </aside>

      {/* 主内容区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 顶栏 */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
          <Button variant="ghost" size="icon" onClick={toggleSidebar} aria-label="切换侧边栏">
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </Button>
          <div className="h-4 w-px bg-border" />
          <span className="text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
            Nexus Intelligence
          </span>
          <div className="ml-auto">
            <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="切换主题">
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
          </div>
        </header>

        {/* 内容 */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
