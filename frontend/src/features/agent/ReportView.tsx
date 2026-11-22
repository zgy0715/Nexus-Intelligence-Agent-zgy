/**
 * ReportView — 最终 Markdown 情报报告 + 复制 / 导出 MD / 导出 PDF（浏览器打印）。
 */

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Check, Copy, Download, FileText, Printer } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ReportViewProps {
  report: string;
  reason: string;
}

export function ReportView({ report, reason }: ReportViewProps) {
  const [copied, setCopied] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* 剪贴板权限被拒时静默 */
    }
  };

  const downloadMd = () => {
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `nia-report-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // PDF：把已渲染的报告 DOM 放进隐藏 iframe 调起浏览器打印（另存为 PDF）
  const printPdf = () => {
    const html = bodyRef.current?.innerHTML;
    if (!html) return;
    const frame = document.createElement("iframe");
    frame.style.position = "fixed";
    frame.style.right = "100%";
    frame.style.bottom = "100%";
    document.body.appendChild(frame);
    const doc = frame.contentDocument;
    if (!doc) {
      frame.remove();
      return;
    }
    doc.open();
    doc.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>NIA 情报报告</title><style>
      body { font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
             padding: 32px; color: #1a1a1a; line-height: 1.7; font-size: 13px; }
      h1 { font-size: 22px; } h2 { font-size: 17px; margin-top: 20px; } h3 { font-size: 14px; }
      a { color: #b4552d; } code { background: #f2f0eb; padding: 1px 4px; border-radius: 4px; font-size: 12px; }
      pre { background: #f2f0eb; padding: 10px; border-radius: 6px; overflow-x: auto; }
      table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: left; }
      blockquote { border-left: 3px solid #d97757; margin-left: 0; padding-left: 12px; color: #555; }
    </style></head><body>${html}</body></html>`);
    doc.close();
    frame.contentWindow?.focus();
    frame.contentWindow?.print();
    // 打印预览关闭后再移除 iframe；兜底 60s，避免预览还开着就被抽掉内容
    const remove = () => frame.remove();
    frame.contentWindow?.addEventListener("afterprint", remove, { once: true });
    setTimeout(remove, 60_000);
  };

  return (
    <div className="rounded-xl border bg-card/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm font-medium">
          <FileText className="h-4 w-4 text-brand" />
          情报报告
          {reason && <span className="text-xs font-normal text-muted-foreground">· {reason}</span>}
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={downloadMd} title="下载 Markdown 文件">
            <Download className="h-3.5 w-3.5" /> MD
          </Button>
          <Button variant="ghost" size="sm" onClick={printPdf} title="打印 / 另存为 PDF">
            <Printer className="h-3.5 w-3.5" /> PDF
          </Button>
          <Button variant="ghost" size="sm" onClick={copy}>
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "已复制" : "复制"}
          </Button>
        </div>
      </div>
      <div ref={bodyRef} className="markdown max-h-[480px] overflow-y-auto px-4 py-3 text-sm">
        <ReactMarkdown>{report || "（暂无报告）"}</ReactMarkdown>
      </div>
    </div>
  );
}