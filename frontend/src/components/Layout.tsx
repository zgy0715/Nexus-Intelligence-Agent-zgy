/**
 * 布局组件 — 侧边栏（分组导航 + 模型状态卡）+ 顶栏 + 内容区。
 *
 * v3.1：导航按「采集 / 情报 / 系统」三组分区（功能一目了然），
 * 底部常驻模型状态卡（主力模型 vs 辅助模型，绿点在线/红点离线）。
 */

import { NavLink, Outlet } from "react-router-dom";
import { CommandPalette } from "./CommandPalette";
import { ModelStatusCard, ModelStatusDots } from "./ModelStatusCard";
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

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
  end?: boolean;
}

/** 导航分组：采集 → 情报 → 系统 */
const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "采集",
    items: [
      { to: "/", icon: Bot, label: "自主 Agent", end: true },
      { to: "/crawl", icon: Globe, label: "批量爬取" },
    ],
  },
  {
    label: "情报",
    items: [
      { to: "/qa", icon: MessageSquare, label: "语义问答" },
      { to: "/data", icon: Database, label: "数据浏览" },
    ],
  },
  {
    label: "系统",
    items: [
      { to: "/monitor", icon: Activity, label: "任务监控" },
      { to: "/settings", icon: Settings, label: "系统设置" },
    ],
  },
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

        {/* 分组导航 */}
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-3">
              {sidebarOpen ? (
                <p className="mb-1 px-3 text-[10px] font-medium uppercase tracking-widest text-muted-foreground/70">
                  {group.label}
                </p>
              ) : (
                <div className="mx-auto mb-2 h-px w-6 bg-border" />
              )}
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={() => {
                      if (window.innerWidth < 1024) setSidebarOpen(false);
                    }}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-200",
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
              </div>
            </div>
          ))}
        </nav>

        {/* 底部：常驻模型状态卡（主力 vs 辅助，在线/离线） */}
        <div className="shrink-0 border-t border-border p-2.5">
          {sidebarOpen ? <ModelStatusCard /> : <ModelStatusDots />}
        </div>
      </aside>

      <CommandPalette />

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
