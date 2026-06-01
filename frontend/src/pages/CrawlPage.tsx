import { useState, useEffect } from 'react';
import { Globe, Send, ChevronDown, ChevronUp, Loader2, CheckCircle2, Circle } from 'lucide-react';
import { api } from '@/api/client';
import { useStore } from '@/store';
import type { CrawlResult } from '@/types';

const PROGRESS_STEPS = ['添加任务', '启动爬虫', 'AI分析', '数据提取'];

const statusColors: Record<string, string> = {
  completed: 'text-[#00ffa3] bg-[#00ffa3]/10',
  running: 'text-[#3b82f6] bg-[#3b82f6]/10',
  pending: 'text-[#f59e0b] bg-[#f59e0b]/10',
  failed: 'text-[#ef4444] bg-[#ef4444]/10',
};

const statusLabels: Record<string, string> = {
  completed: '已完成',
  running: '运行中',
  pending: '等待中',
  failed: '失败',
};

function ResultCard({ result }: { result: CrawlResult }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-lg border border-[#1e1e2e] bg-[#111118] p-4">
      <div className="flex items-center justify-between">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-gray-300">{result.url}</p>
          <p className="mt-1 text-xs text-gray-500">{result.timestamp}</p>
        </div>
        <div className="ml-3 flex items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs ${statusColors[result.status] || ''}`}>
            {statusLabels[result.status] || result.status}
          </span>
          <button onClick={() => setExpanded(!expanded)} className="text-gray-500 hover:text-gray-300">
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>
      {expanded && result.extracted_data && (
        <div className="mt-3 border-t border-[#1e1e2e] pt-3">
          <pre className="overflow-x-auto text-xs text-gray-400">
            {JSON.stringify(result.extracted_data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function ProgressIndicator({ step }: { step: number }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-[#1e1e2e] bg-[#111118] p-4">
      {PROGRESS_STEPS.map((label, i) => (
        <div key={label} className="flex items-center gap-2">
          <div className="flex flex-col items-center">
            {i < step ? (
              <CheckCircle2 size={20} className="text-[#00ffa3]" />
            ) : i === step ? (
              <Loader2 size={20} className="animate-spin text-[#3b82f6]" />
            ) : (
              <Circle size={20} className="text-gray-600" />
            )}
            <span className={`mt-1 text-xs ${i <= step ? 'text-gray-300' : 'text-gray-600'}`}>{label}</span>
          </div>
          {i < PROGRESS_STEPS.length - 1 && (
            <div className={`mx-2 h-px w-8 ${i < step ? 'bg-[#00ffa3]' : 'bg-gray-700'}`} />
          )}
        </div>
      ))}
    </div>
  );
}

export default function CrawlPage() {
  const [url, setUrl] = useState('');
  const [instruction, setInstruction] = useState('');
  const [useJs, setUseJs] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(-1);
  const [error, setError] = useState('');
  const crawlResults = useStore((s) => s.crawlResults);
  const setCrawlResults = useStore((s) => s.setCrawlResults);
  const addCrawlResult = useStore((s) => s.addCrawlResult);

  useEffect(() => {
    api.getCrawlResults().then((res) => setCrawlResults(res.results)).catch(() => {});
  }, [setCrawlResults]);

  const handleSubmit = async () => {
    if (!url.trim() || !instruction.trim()) return;
    setLoading(true);
    setError('');
    setProgress(0);
    try {
      setProgress(0);
      await new Promise((r) => setTimeout(r, 600));
      setProgress(1);
      const res = await api.crawl(url, instruction, useJs);
      setProgress(2);
      await new Promise((r) => setTimeout(r, 800));
      setProgress(3);
      addCrawlResult(
        { id: res.task_id, url, timestamp: new Date().toISOString(), status: res.status as CrawlResult['status'] },
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : '抓取失败');
    } finally {
      setLoading(false);
      setTimeout(() => setProgress(-1), 1500);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Globe className="text-[#00ffa3]" size={28} />
        <h1 className="text-2xl font-bold text-white">零配置抓取</h1>
      </div>

      <div className="space-y-4 rounded-lg border border-[#1e1e2e] bg-[#111118] p-5">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="输入目标 URL"
          className="w-full rounded-md border border-[#1e1e2e] bg-[#0a0a0f] px-4 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition focus:border-[#00ffa3] focus:shadow-[0_0_8px_rgba(0,255,163,0.3)]"
        />
        <div className="relative">
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="用自然语言描述你想抓取的内容..."
            rows={3}
            className="w-full resize-none rounded-md border border-[#1e1e2e] bg-[#0a0a0f] px-4 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition focus:border-[#00ffa3] focus:shadow-[0_0_8px_rgba(0,255,163,0.3)]"
          />
          <span className="absolute bottom-2 right-3 text-xs text-gray-600">{instruction.length}</span>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-400">
          <input
            type="checkbox"
            checked={useJs}
            onChange={(e) => setUseJs(e.target.checked)}
            className="accent-[#00ffa3]"
          />
          启用 JS 渲染模式
        </label>
        <button
          onClick={handleSubmit}
          disabled={loading || !url.trim() || !instruction.trim()}
          className="flex items-center gap-2 rounded-md bg-[#00ffa3] px-6 py-2.5 text-sm font-semibold text-black transition hover:shadow-[0_0_16px_rgba(0,255,163,0.4)] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:shadow-none"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          开始抓取
        </button>
      </div>

      {error && <p className="rounded-md bg-[#ef4444]/10 px-4 py-2 text-sm text-[#ef4444]">{error}</p>}

      {progress >= 0 && <ProgressIndicator step={progress} />}

      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-300">抓取结果</h2>
        {crawlResults.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-600">暂无抓取结果</p>
        ) : (
          crawlResults.map((r) => <ResultCard key={r.id} result={r} />)
        )}
      </div>
    </div>
  );
}
