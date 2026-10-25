/**
 * FindingsPanel — 结构化发现侧栏。
 *
 * 替换旧版 JSON.stringify 进 <pre> 的展示：标题/来源链接/摘 要为主体，
 * 结构化数据（extract_data 的 JSON）折叠在「查看数据」里。
 */

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, ExternalLink, Lightbulb } from "lucide-react";
import type { AgentFinding } from "@/types";
import { cn } from "@/lib/utils";

interface FindingCardProps {
  finding: AgentFinding;
  index: number;
}

function FindingCard({ finding, index }: FindingCardProps) {
  const [openData, setOpenData] = useState(false);
  const hasData = finding.data && Object.keys(finding.data).length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500/15 font-mono text-[10px] font-medium text-amber-600 dark:text-amber-400">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-snug">{finding.title || "（无标题）"}</p>
          {finding.url && (
            <a
              href={finding.url}
              target="_blank"
              rel="noreferrer"
              className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground"
            >
              <ExternalLink className="h-3 w-3 shrink-0" />
              <span className="truncate">{finding.url}</span>
            </a>
          )}
          {finding.content && (
            <p className="mt-1.5 whitespace-pre-wrap text-xs leading-relaxed text-foreground/80">
              {finding.content.length > 400 ? finding.content.slice(0, 400) + "…" : finding.content}
            </p>
          )}
          {hasData && (
            <>
              <button
                onClick={() => setOpenData((v) => !v)}
                className="mt-1.5 flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground"
              >
                <ChevronDown className={cn("h-3 w-3 transition-transform", openData && "rotate-180")} />
                查看结构化数据
              </button>
              <AnimatePresence initial={false}>
                {openData && (
                  <motion.pre
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="mt-1 max-h-56 overflow-auto rounded-md border bg-muted/40 p-2 font-mono text-[11px] leading-relaxed"
                  >
                    {JSON.stringify(finding.data, null, 2)}
                  </motion.pre>
                )}
              </AnimatePresence>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function FindingsPanel({ findings }: { findings: AgentFinding[] }) {
  return (
    <div className="space-y-2.5 overflow-y-auto pr-1">
      {findings.length === 0 ? (
        <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Lightbulb className="h-6 w-6 opacity-30" />
          <p className="text-sm">尚无发现</p>
        </div>
      ) : (
        findings.map((f, i) => <FindingCard key={`${f.url}-${f.title}-${i}`} finding={f} index={i} />)
      )}
    </div>
  );
}
