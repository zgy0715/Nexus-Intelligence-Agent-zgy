import { BrowserRouter } from "react-router-dom";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import App from "./App";
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

// 不用 StrictMode，避免和 echarts/lucide 等库冲突导致 insertBefore 错误
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <App />
      <Toaster position="top-right" richColors closeButton theme={useStore.getState().theme} />
    </BrowserRouter>
  </QueryClientProvider>,
);
