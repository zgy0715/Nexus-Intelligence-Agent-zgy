/**
 * usePageTitle — 路由级页面标题（浏览器标签页）。
 *
 * 统一格式 `{页面名} · Nexus Intelligence Agent`；
 * 不传或传空时回退默认标题（Landing 首页）。
 */

import { useEffect } from "react";

const BASE_TITLE = "Nexus Intelligence Agent";

export function usePageTitle(title?: string | null) {
  useEffect(() => {
    document.title = title ? `${title} · ${BASE_TITLE}` : BASE_TITLE;
  }, [title]);
}
