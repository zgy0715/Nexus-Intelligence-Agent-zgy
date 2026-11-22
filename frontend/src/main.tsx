import { StrictMode } from "react";
import { BrowserRouter } from "react-router-dom";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { ThemedToaster } from "./components/ThemedToaster";
import { useStore, applyTheme } from "./store";
import "./index.css";

// 启动时应用持久化的主题
applyTheme(useStore.getState().theme);
useStore.subscribe((s) => applyTheme(s.theme));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
        <ThemedToaster />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);