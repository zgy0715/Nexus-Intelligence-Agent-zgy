import { NavLink, Outlet } from "react-router-dom";
import { Globe, MessageSquare, Database, Activity, Settings, Menu, X, Bug } from "lucide-react";
import { useStore } from "../store";

const navItems = [
  { to: "/", icon: Globe, label: "零配置抓取" },
  { to: "/qa", icon: MessageSquare, label: "语义问答" },
  { to: "/data", icon: Database, label: "数据浏览" },
  { to: "/monitor", icon: Activity, label: "任务监控" },
  { to: "/settings", icon: Settings, label: "系统设置" },
];

export default function Layout() {
  const { sidebarOpen, toggleSidebar, setSidebarOpen } = useStore();

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-primary)" }}>
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed lg:relative z-40 h-full flex flex-col transition-all duration-300 border-r ${
          sidebarOpen ? "w-60" : "w-0 lg:w-16"
        }`}
        style={{
          background: "var(--bg-secondary)",
          borderColor: "var(--border)",
          overflow: "hidden",
        }}
      >
        <div className="flex items-center gap-3 px-4 h-16 border-b shrink-0" style={{ borderColor: "var(--border)" }}>
          <Bug
            size={24}
            style={{ color: "var(--accent)", minWidth: 24 }}
            className="shrink-0"
          />
          {sidebarOpen && (
            <div className="flex flex-col overflow-hidden">
              <span
                className="text-sm font-bold tracking-wider neon-text whitespace-nowrap"
                style={{ color: "var(--accent)", fontFamily: "var(--font-heading)" }}
              >
                NIA
              </span>
              <span
                className="text-[10px] whitespace-nowrap"
                style={{ color: "var(--text-muted)" }}
              >
                Nexus Intelligence Agent
              </span>
            </div>
          )}
        </div>

        <nav className="flex-1 py-4 flex flex-col gap-1 px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={() => {
                if (window.innerWidth < 1024) setSidebarOpen(false);
              }}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded transition-all duration-200 group ${
                  sidebarOpen ? "" : "justify-center"
                } ${
                  isActive
                    ? "neon-glow"
                    : "hover:bg-[var(--bg-card)]"
                }`
              }
              style={({ isActive }) => ({
                color: isActive ? "var(--accent)" : "var(--text-secondary)",
                borderLeft: isActive ? "3px solid var(--accent)" : "3px solid transparent",
                fontFamily: isActive ? "var(--font-heading)" : "var(--font-body)",
                fontWeight: isActive ? 600 : 400,
              })}
            >
              <item.icon size={20} className="shrink-0" />
              {sidebarOpen && (
                <span className="text-sm whitespace-nowrap">{item.label}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-3 border-t shrink-0" style={{ borderColor: "var(--border)" }}>
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full"
                style={{
                  background: "var(--accent)",
                  animation: "pulse-glow 2s ease-in-out infinite",
                }}
              />
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                系统就绪
              </span>
            </div>
          )}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header
          className="h-14 flex items-center px-4 border-b shrink-0 gap-3"
          style={{
            background: "var(--bg-secondary)",
            borderColor: "var(--border)",
          }}
        >
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded transition-colors duration-200 hover:bg-[var(--bg-card)]"
            style={{ color: "var(--text-secondary)" }}
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div
            className="h-5 w-px"
            style={{ background: "var(--border)" }}
          />
          <span
            className="text-xs tracking-widest uppercase"
            style={{ color: "var(--text-muted)", fontFamily: "var(--font-heading)" }}
          >
            NEXUS INTELLIGENCE
          </span>
        </header>

        <main
          className="flex-1 overflow-auto p-6 scan-line"
          style={{ background: "var(--bg-primary)" }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
