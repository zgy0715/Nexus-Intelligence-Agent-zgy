import { StrictMode } from "react";
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

// v3：React 19 + StrictMode 回归（echarts 双挂载问题由 <Chart> 封装的
// 正确 dispose 生命周期解决，不再靠禁用 StrictMode 掩盖）
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
        <Toaster position="top-right" richColors closeButton theme={useStore.getState().theme} />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
