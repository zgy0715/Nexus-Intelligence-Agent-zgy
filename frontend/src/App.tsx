import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import CrawlPage from "./pages/CrawlPage";
import QueryPage from "./pages/QueryPage";
import DataPage from "./pages/DataPage";
import MonitorPage from "./pages/MonitorPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<CrawlPage />} />
        <Route path="/qa" element={<QueryPage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="/monitor" element={<MonitorPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
