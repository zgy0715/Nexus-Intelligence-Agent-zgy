import { create } from "zustand";
import { persist } from "zustand/middleware";

/** 三套设计语言：暖纸人文 / 极简终端 / 森林暗色 */
export type Theme = "paper" | "mono" | "forest";

export const THEMES: { key: Theme; label: string; hint: string }[] = [
  { key: "paper", label: "暖纸", hint: "象牙白 · 陶土橙 · 衬线" },
  { key: "mono", label: "极简", hint: "纯黑白 · 等宽 · 锐角" },
  { key: "forest", label: "森林", hint: "深绿 · 翡翠发光" },
];

function isTheme(v: unknown): v is Theme {
  return v === "paper" || v === "mono" || v === "forest";
}

interface AppState {
  theme: Theme;
  setTheme: (t: Theme) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      theme: "paper",
      setTheme: (t) => set({ theme: t }),
    }),
    {
      name: "nia-ui-v4",
      partialize: (s) => ({ theme: s.theme }),
      // 只取持久化数据中的 theme 合并回初始 state。
      // 旧版本 localStorage（nia-ui-v4）残留的 sidebarOpen 等脏键一律忽略，不进 state。
      merge: (persisted, current) => {
        const theme = (persisted as { theme?: unknown } | null)?.theme;
        return { ...current, theme: isTheme(theme) ? theme : current.theme };
      },
    },
  ),
);

let _themeTransitionTimer: ReturnType<typeof setTimeout> | null = null;

/** 把主题应用到 <html data-theme>；forest 同时挂 .dark 以兼容 dark: 变体。
 * 切换瞬间给全站施加统一颜色过渡，之后移除（不干扰 motion 的 transform 动画）。 */
export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.classList.toggle("dark", theme === "forest");
  root.classList.add("theme-transitioning");
  if (_themeTransitionTimer) clearTimeout(_themeTransitionTimer);
  _themeTransitionTimer = setTimeout(() => {
    root.classList.remove("theme-transitioning");
    _themeTransitionTimer = null;
  }, 320);
}
