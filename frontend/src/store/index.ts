import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, CrawlResult } from "../types";

type Theme = "light" | "dark";

interface AppState {
  // 主题
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;

  // 布局
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  // 业务状态
  crawlResults: CrawlResult[];
  chatHistory: ChatMessage[];
  setCrawlResults: (results: CrawlResult[]) => void;
  addCrawlResult: (result: CrawlResult) => void;
  removeCrawlResult: (id: string) => void;
  setChatHistory: (history: ChatMessage[]) => void;
  addChatMessage: (message: ChatMessage) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      theme: "dark",
      toggleTheme: () => set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),
      setTheme: (t) => set({ theme: t }),

      sidebarOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      crawlResults: [],
      chatHistory: [],
      setCrawlResults: (results) => set({ crawlResults: results }),
      addCrawlResult: (result) => set((s) => ({ crawlResults: [result, ...s.crawlResults] })),
      removeCrawlResult: (id) =>
        set((s) => ({ crawlResults: s.crawlResults.filter((r) => (r.task_id || r.id) !== id) })),
      setChatHistory: (history) => set({ chatHistory: history }),
      addChatMessage: (message) => set((s) => ({ chatHistory: [...s.chatHistory, message] })),
    }),
    {
      name: "nia-ui-v2",
      partialize: (s) => ({ theme: s.theme, sidebarOpen: s.sidebarOpen }),
    },
  ),
);

/** 把主题 class 应用到 <html>，在 store 变化时调用。 */
export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
}
