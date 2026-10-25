import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import { Skeleton } from "./components/ui/Skeleton";

// 路由级代码分割：首屏只加载 Agent 控制台，其余页面按需拉取
const AgentPage = lazy(() => import("./pages/AgentPage"));
const CrawlPage = lazy(() => import("./pages/CrawlPage"));
const QueryPage = lazy(() => import("./pages/QueryPage"));
const DataPage = lazy(() => import("./pages/DataPage"));
const MonitorPage = lazy(() => import("./pages/MonitorPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

function PageFallback() {
  return (
    <div className="mx-auto max-w-7xl space-y-4 p-6">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-48 w-full" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Skeleton className="h-72 lg:col-span-2" />
        <Skeleton className="h-72" />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<Layout />}>
          <Route
            path="/"
            element={
              <Suspense fallback={<PageFallback />}>
                <AgentPage />
              </Suspense>
            }
          />
          <Route
            path="/crawl"
            element={
              <Suspense fallback={<PageFallback />}>
                <CrawlPage />
              </Suspense>
            }
          />
          <Route
            path="/qa"
            element={
              <Suspense fallback={<PageFallback />}>
                <QueryPage />
              </Suspense>
            }
          />
          <Route
            path="/data"
            element={
              <Suspense fallback={<PageFallback />}>
                <DataPage />
              </Suspense>
            }
          />
          <Route
            path="/monitor"
            element={
              <Suspense fallback={<PageFallback />}>
                <MonitorPage />
              </Suspense>
            }
          />
          <Route
            path="/settings"
            element={
              <Suspense fallback={<PageFallback />}>
                <SettingsPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
