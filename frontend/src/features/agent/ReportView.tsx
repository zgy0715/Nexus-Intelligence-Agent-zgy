/**
 * ReportView — 最终 Markdown 情报报告 + 一键复制。
 */

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Check, Copy, FileText } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ReportViewProps {
  report: string;
  reason: string;
}

export function ReportView({ report, reason }: ReportViewProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* 剪贴板权限被拒时静默 */
    }
  };

  return (
    <div className="rounded-xl border bg-card/60">
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm font-medium">
          <FileText className="h-4 w-4 text-primary" />
          情报报告
          {reason && <span className="text-xs font-normal text-muted-foreground">· {reason}</span>}
        </div>
        <Button variant="ghost" size="sm" onClick={copy}>
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "已复制" : "复制"}
        </Button>
      </div>
      <div className="markdown max-h-[480px] overflow-y-auto px-4 py-3 text-sm">
        <ReactMarkdown>{report || "（暂无报告）"}</ReactMarkdown>
      </div>
    </div>
  );
}
