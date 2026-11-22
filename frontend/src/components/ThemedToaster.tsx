/**
 * ThemedToaster — sonner 通知的主题跟随封装（forest 主题下用暗色面板）。
 */

import { Toaster } from "sonner";
import { useStore } from "@/store";

export function ThemedToaster() {
  const theme = useStore((s) => s.theme);
  return (
    <Toaster
      position="top-right"
      richColors
      closeButton
      theme={theme === "forest" ? "dark" : "light"}
    />
  );
}
