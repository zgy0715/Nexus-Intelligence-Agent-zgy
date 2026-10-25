/**
 * TopProgressBar — 顶部流光进度条（爬取/Agent 运行中常驻）。
 * 运行中：流动光泽的不定进度条；完成：收束到 100% 后淡出。
 */

import { AnimatePresence, motion } from "motion/react";

interface TopProgressBarProps {
  running: boolean;
  /** 0-100 的确定进度；不传则显示流光不定进度 */
  value?: number;
  done?: boolean;
}

export function TopProgressBar({ running, value, done }: TopProgressBarProps) {
  const show = running || (done === true && value !== undefined);
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 3 }}
          exit={{ opacity: 0, height: 0 }}
          className="relative w-full overflow-hidden rounded-full bg-muted"
        >
          {running && value === undefined ? (
            /* 不定进度：光带往复流动 */
            <motion.div
              className="h-full w-2/5 rounded-full bg-gradient-to-r from-brand/40 via-brand to-brand/40"
              animate={{ x: ["-110%", "280%"] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
            />
          ) : (
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-brand/60 via-brand to-brand"
              animate={{ width: `${done ? 100 : Math.min(100, value ?? 0)}%` }}
              transition={{ duration: 0.4, ease: "easeOut" }}
            />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
