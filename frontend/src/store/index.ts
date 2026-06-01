import { create } from "zustand";
import type { ChatMessage, CrawlResult } from "../types";

interface AppState {
  crawlResults: CrawlResult[];
  chatHistory: ChatMessage[];
  sidebarOpen: boolean;
  setCrawlResults: (results: CrawlResult[]) => void;
  addCrawlResult: (result: CrawlResult) => void;
  setChatHistory: (history: ChatMessage[]) => void;
  addChatMessage: (message: ChatMessage) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useStore = create<AppState>()((set) => ({
  crawlResults: [],
  chatHistory: [],
  sidebarOpen: true,
  setCrawlResults: (results) => set({ crawlResults: results }),
  addCrawlResult: (result) =>
    set((s) => ({ crawlResults: [result, ...s.crawlResults] })),
  setChatHistory: (history) => set({ chatHistory: history }),
  addChatMessage: (message) =>
    set((s) => ({ chatHistory: [...s.chatHistory, message] })),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
