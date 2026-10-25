/**
 * AnimatedNumber — 数字滚动（motion spring，爬取计数用）。
 */

import { useEffect, useRef } from "react";
import { useMotionValue, useSpring, useTransform, motion } from "motion/react";

export function AnimatedNumber({ value, className }: { value: number; className?: string }) {
  const mv = useMotionValue(value);
  const spring = useSpring(mv, { stiffness: 120, damping: 20 });
  const display = useTransform(spring, (v) => Math.round(v).toLocaleString());
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      // 首次直接到位，避免从 0 飞入的噪音
      mv.set(value);
      first.current = false;
    } else {
      mv.set(value);
    }
  }, [value, mv]);

  return <motion.span className={className}>{display}</motion.span>;
}
