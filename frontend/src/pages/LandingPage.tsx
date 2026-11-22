/**
 * LandingPage — 面向评委的滚动式介绍首页（大厂官网式叙事）。
 *
 * 结构：固定顶栏（滚动渐显）→ 阅读进度条 → Hero（价值主张 + 模拟控制台）
 * → 特性 bento → 四步上手（左 sticky 右滚动）→ 技术架构 + 技术栈跑马灯
 * → 三步部署 → 结尾 CTA。全程 motion 滚动揭示 / 视差，锚点平滑滚动。
 * 独立于控制台外壳，使用同一套三主题 design token。
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import {
  motion,
  useScroll,
  useSpring,
  useTransform,
  useMotionValueEvent,
} from "motion/react";
import {
  ArrowRight,
  Bot,
  Globe,
  Database,
  Activity,
  Waypoints,
  Search,
  ChevronDown,
  Sparkles,
  Cloud,
  Server,
  KeyRound,
  Terminal,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

const EASE = [0.22, 1, 0.36, 1] as const;

function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: EASE }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function SectionHead({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: string }) {
  return (
    <Reveal className="mb-10 max-w-2xl">
      <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.22em] text-brand">{eyebrow}</p>
      <h2 className="text-3xl font-bold tracking-tight text-foreground lg:text-4xl">{title}</h2>
      {sub && <p className="mt-3 text-base leading-relaxed text-muted-foreground">{sub}</p>}
    </Reveal>
  );
}

const MOCK_EVENTS = [
  { icon: "🎯", label: "目标", text: "收集 solidot 近期科技资讯的标题与要点" },
  { icon: "🧠", label: "思考", text: "先抓首页理解结构，再跟随资讯链接" },
  { icon: "🔧", label: "动作", text: "fetch_page(url=https://www.solidot.org)" },
  { icon: "💡", label: "发现", text: "3 条资讯 · 附来源链接" },
  { icon: "✅", label: "完成", text: "报告已生成 · 12 页 · 8,432 tokens" },
];

const FEATURES = [
  {
    icon: Bot,
    title: "自主爬取 Agent",
    desc: "原生 tool-calling 多步循环：自主决定爬哪些页、跟随哪些链接、何时停止。上下文滚动压缩让长任务不爆窗口，三维预算与无进展检测保证可控收尾。",
    span: true,
    chips: ["fetch_page", "crawl_links", "extract_data", "finish"],
  },
  {
    icon: Search,
    title: "混合检索 RAG",
    desc: "BM25Plus（jieba 分词）+ FAISS 向量双路召回，RRF 融合排序；流式回答附来源引用，支持多轮追问。",
  },
  {
    icon: Globe,
    title: "并发爬取引擎",
    desc: "异步抓取 + trafilatura 正文密度提取；SSRF 逐跳校验、robots 礼貌限速、HTML 磁盘缓存。",
  },
  {
    icon: Database,
    title: "采集即知识库",
    desc: "抓到的每一页实时入库并建立检索索引，立刻可问答；定时采集 + 内容哈希变更检测，让「变化」本身成为情报。",
    span: true,
    chips: ["实时索引", "变更监控", "版本对比"],
  },
  {
    icon: Activity,
    title: "事件溯源可观测",
    desc: "Agent 事件写入 Redis Stream，SSE 断线续读；历史运行一键回放，任务不再「重启即失忆」。",
  },
  {
    icon: Waypoints,
    title: "图谱与成本看板",
    desc: "爬取路径图谱、域名分布、token 成本估算——运行状态与花费一目了然。",
  },
];

const STEPS = [
  {
    n: "01",
    title: "设定目标与种子",
    desc: "在「自主 Agent」页用一句自然语言描述要收集什么，填入起始 URL，设定页面预算与跟随深度。",
    mock: (
      <div className="space-y-2 rounded-lg border border-border bg-secondary/40 p-3 font-mono text-[11px]">
        <p className="text-muted-foreground">目标 <span className="text-foreground">收集 Anthropic 近期产品公告</span></p>
        <p className="text-muted-foreground">种子 <span className="text-brand">https://www.anthropic.com/news</span></p>
        <p className="text-muted-foreground">预算 <span className="text-foreground">20 页 · 深度 2</span></p>
      </div>
    ),
  },
  {
    n: "02",
    title: "观看自主探索",
    desc: "时间线实时流式呈现思考 / 动作 / 观察 / 发现；预算仪表与上下文压缩全程可视，运行中可随时取消。",
    mock: (
      <div className="space-y-1.5 rounded-lg border border-border bg-secondary/40 p-3 text-[11px]">
        {MOCK_EVENTS.slice(1, 4).map((e) => (
          <p key={e.label} className="flex gap-2 text-muted-foreground">
            <span>{e.icon}</span>
            <span className="text-foreground/80">{e.label}</span>
            <span className="truncate">{e.text}</span>
          </p>
        ))}
      </div>
    ),
  },
  {
    n: "03",
    title: "语义问答",
    desc: "在「语义问答」页对已采集内容提问：流式回答、来源引用可点开原文，支持多轮上下文追问。",
    mock: (
      <div className="space-y-2 rounded-lg border border-border bg-secondary/40 p-3 text-[11px]">
        <p className="ml-auto w-fit rounded-lg bg-brand/15 px-2 py-1 text-foreground">最近有哪些值得关注的动态？</p>
        <p className="w-fit rounded-lg bg-card px-2 py-1 text-muted-foreground">根据采集内容…[来源1][来源2]</p>
      </div>
    ),
  },
  {
    n: "04",
    title: "监控与导出",
    desc: "定时采集自动发现站点变更；情报报告一键导出 Markdown / PDF，知识库数据导出 JSON / CSV。",
    mock: (
      <div className="flex flex-wrap gap-1.5 rounded-lg border border-border bg-secondary/40 p-3">
        {["MD", "PDF", "JSON", "CSV"].map((f) => (
          <span key={f} className="rounded-md border border-border bg-card px-2 py-1 font-mono text-[10px] text-foreground">{f}</span>
        ))}
        <span className="rounded-md border border-success/30 bg-success/10 px-2 py-1 font-mono text-[10px] text-success">变更 ×3</span>
      </div>
    ),
  },
];

const TECH = [
  "React 19", "Vite 8", "Tailwind 4", "FastAPI", "FAISS", "jieba", "BM25Plus",
  "ECharts 6", "SSE", "Redis Stream", "trafilatura", "Pydantic", "MySQL 8", "DeepSeek",
];

export default function LandingPage() {
  const { scrollY, scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, { stiffness: 120, damping: 24 });
  const [scrolled, setScrolled] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setScrolled(v > 12));
  const heroY = useTransform(scrollY, [0, 600], [0, 90]);
  const heroOpacity = useTransform(scrollY, [0, 480], [1, 0.25]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* 阅读进度条 */}
      <motion.div className="fixed inset-x-0 top-0 z-[60] h-0.5 origin-left bg-brand" style={{ scaleX: progress }} />

      {/* 固定顶栏 */}
      <header
        className={cn(
          "fixed inset-x-0 top-0 z-50 transition-all duration-300",
          scrolled ? "border-b border-border bg-card/80 backdrop-blur-md" : "bg-transparent",
        )}
      >
        <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-6 px-4 lg:px-8">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="brand-mark flex h-8 w-8 items-center justify-center rounded-lg">
              <Sparkles size={16} className="text-brand-foreground" />
            </span>
            <span className="text-sm font-bold tracking-tight">NIA</span>
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <a href="#features" className="transition hover:text-foreground">功能特性</a>
            <a href="#how" className="transition hover:text-foreground">使用流程</a>
            <a href="#arch" className="transition hover:text-foreground">技术架构</a>
            <a href="#deploy" className="transition hover:text-foreground">部署</a>
          </nav>
          <Button asChild size="sm" className="ml-auto glow-cta">
            <Link to="/agent">进入控制台 <ArrowRight className="h-3.5 w-3.5" /></Link>
          </Button>
        </div>
      </header>

      {/* Hero */}
      <section className="relative flex min-h-[94vh] flex-col items-center justify-center overflow-hidden px-4 pt-24">
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-40" />
        <div className="pointer-events-none absolute -top-32 left-1/2 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-brand/15 blur-[120px]" />
        <motion.div style={{ y: heroY, opacity: heroOpacity }} className="relative z-10 flex max-w-3xl flex-col items-center text-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/10 px-3 py-1 font-mono text-[11px] tracking-wide text-brand">
              私有化部署 · 数据 100% 本地
            </span>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="mt-6 text-4xl font-bold leading-[1.12] tracking-tight sm:text-6xl lg:text-7xl">
              把互联网，变成
              <br />
              <span className="bg-gradient-to-r from-brand to-glow bg-clip-text text-transparent">你的私有情报库</span>
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              NIA 是一个运行在你自己电脑上的智能爬虫 + 情报分析系统：
              给一个目标，Agent 自主采集；抓到的每一页实时成为可问答的知识库。
              数据全部本地，逻辑全部开源。
            </p>
          </Reveal>
          <Reveal delay={0.24} className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg" className="glow-cta h-12 px-7 text-base">
              <Link to="/agent">进入控制台 <ArrowRight className="h-4 w-4" /></Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-12 px-7 text-base">
              <a href="#how">了解如何使用</a>
            </Button>
          </Reveal>
        </motion.div>

        {/* 模拟控制台 */}
        <Reveal delay={0.3} className="relative z-10 mt-14 w-full max-w-2xl">
          <div className="glass overflow-hidden rounded-2xl shadow-2xl">
            <div className="flex items-center gap-1.5 border-b border-border/60 px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-destructive/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
              <span className="ml-3 font-mono text-[11px] text-muted-foreground">nia · agent run</span>
            </div>
            <div className="space-y-2.5 p-4 text-left">
              {MOCK_EVENTS.map((e, i) => (
                <motion.div
                  key={e.label}
                  initial={{ opacity: 0, x: -14 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.4 + i * 0.18, duration: 0.45, ease: EASE }}
                  className="flex items-baseline gap-2.5 text-[12px]"
                >
                  <span>{e.icon}</span>
                  <span className="w-8 shrink-0 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">{e.label}</span>
                  <span className="truncate text-foreground/85">{e.text}</span>
                </motion.div>
              ))}
            </div>
          </div>
        </Reveal>

        <motion.a
          href="#features"
          aria-label="向下滚动"
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
          className="absolute bottom-6 z-10 text-muted-foreground"
        >
          <ChevronDown className="h-5 w-5" />
        </motion.a>
      </section>

      {/* 特性 bento */}
      <section id="features" className="mx-auto max-w-[1200px] scroll-mt-24 px-4 py-24 lg:px-8">
        <SectionHead
          eyebrow="Features"
          title="一个闭环，六种能力"
          sub="从自主采集到检索问答，再到监控与导出——采集的终点不是文件，而是可追问的知识。"
        />
        <div className="grid gap-4 md:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={i * 0.06} className={cn(f.span && "md:col-span-2")}>
              <motion.div
                whileHover={{ y: -4 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="card-elevated h-full rounded-2xl p-6 transition-colors hover:border-brand/40"
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 text-brand">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-semibold tracking-tight">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
                {f.chips && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {f.chips.map((c) => (
                      <span key={c} className="rounded-md border border-border bg-secondary/60 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">{c}</span>
                    ))}
                  </div>
                )}
              </motion.div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* 四步上手 */}
      <section id="how" className="border-y border-border/60 bg-card/40 scroll-mt-24">
        <div className="mx-auto grid max-w-[1200px] gap-12 px-4 py-24 lg:grid-cols-[380px_minmax(0,1fr)] lg:px-8">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <SectionHead
              eyebrow="How it works"
              title="四步上手"
              sub="从一句目标到一份带来源的情报报告，全程可视、可控、可回放。"
            />
            <Reveal delay={0.1}>
              <Button asChild variant="outline">
                <Link to="/agent">立即体验 <ArrowRight className="h-4 w-4" /></Link>
              </Button>
            </Reveal>
          </div>
          <div className="space-y-12">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 0.05}>
                <div className="flex gap-5">
                  <span className="font-mono text-3xl font-bold tabular-nums text-brand/60">{s.n}</span>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-xl font-semibold tracking-tight">{s.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.desc}</p>
                    <div className="mt-4">{s.mock}</div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* 技术架构 */}
      <section id="arch" className="mx-auto max-w-[1200px] scroll-mt-24 px-4 py-24 lg:px-8">
        <SectionHead
          eyebrow="Architecture"
          title="单进程后端，全本地数据"
          sub="FastAPI 单进程编排 Agent 内核、爬取引擎与混合检索；除 DeepSeek 云 API 外无任何外部服务依赖。"
        />
        <Reveal>
          <div className="card-elevated rounded-2xl p-6 lg:p-8">
            <div className="flex flex-wrap items-center justify-center gap-3 font-mono text-[12px]">
              <span className="rounded-lg border border-border bg-secondary/60 px-3 py-2">浏览器 · React 19</span>
              <span className="text-muted-foreground">→ REST / SSE →</span>
              <span className="rounded-lg border border-brand/40 bg-brand/10 px-3 py-2 text-brand">FastAPI 单进程</span>
            </div>
            <div className="mt-4 flex flex-wrap items-stretch justify-center gap-3 font-mono text-[11px]">
              {[
                { icon: Cloud, t: "DeepSeek 云 API", d: "推理 / 提取 / 问答" },
                { icon: Search, t: "FAISS + BM25", d: "混合检索 RRF" },
                { icon: Server, t: "MySQL + Redis", d: "持久化 / 事件总线" },
              ].map((b) => (
                <div key={b.t} className="flex min-w-[180px] flex-1 flex-col items-center gap-1 rounded-xl border border-border bg-secondary/40 px-4 py-3 text-center">
                  <b.icon className="h-4 w-4 text-brand" />
                  <span className="text-foreground">{b.t}</span>
                  <span className="text-muted-foreground">{b.d}</span>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
        {/* 技术栈跑马灯 */}
        <div className="relative mt-10 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]">
          <motion.div
            animate={{ x: ["0%", "-50%"] }}
            transition={{ duration: 32, repeat: Infinity, ease: "linear" }}
            className="flex w-max gap-3"
          >
            {[...TECH, ...TECH].map((t, i) => (
              <span key={`${t}-${i}`} className="whitespace-nowrap rounded-full border border-border bg-card px-3.5 py-1.5 font-mono text-[11px] text-muted-foreground">
                {t}
              </span>
            ))}
          </motion.div>
        </div>
      </section>

      {/* 部署 */}
      <section id="deploy" className="border-t border-border/60 bg-card/40 scroll-mt-24">
        <div className="mx-auto max-w-[1200px] px-4 py-24 lg:px-8">
          <SectionHead
            eyebrow="Deployment"
            title="三步私有化部署"
            sub="不需要 Docker，不需要本地 GPU / Ollama。Embedding 模型首次自动下载并本地缓存，之后离线可用。"
          />
          <div className="grid gap-4 md:grid-cols-3">
            {[
              { icon: Server, t: "准备基础设施", d: "MySQL 8 + Redis 5+，建库 nia；两条本地服务，无容器编排。" },
              { icon: KeyRound, t: "填一个 API Key", d: "backend/.env 填入 DEEPSEEK_API_KEY；唯一云依赖，成本看板实时估算花费。" },
              { icon: Terminal, t: "两条命令启动", d: "后端 uvicorn 单进程 + 前端 Vite；生产可同端口托管 SPA。" },
            ].map((s, i) => (
              <Reveal key={s.t} delay={i * 0.08}>
                <div className="card-elevated h-full rounded-2xl p-6">
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 text-brand">
                    <s.icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-base font-semibold">{s.t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.d}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal delay={0.15}>
            <pre className="mt-6 overflow-x-auto rounded-xl border border-border bg-secondary/50 p-4 font-mono text-[12px] leading-relaxed text-foreground/85">
{`cd backend  && pip install -r requirements.txt && uvicorn nia.api.app:app --port 8000
cd frontend && npm install && npm run dev   # → http://localhost:5173`}
            </pre>
          </Reveal>
        </div>
      </section>

      {/* 结尾 CTA */}
      <section className="relative overflow-hidden px-4 py-28 text-center">
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[360px] w-[680px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand/12 blur-[110px]" />
        <Reveal className="relative">
          <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
            准备好把互联网变成你的情报库了吗？
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm text-muted-foreground">
            控制台已就绪：自主 Agent、批量爬取、定时监控、语义问答、图谱与成本看板。
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg" className="glow-cta h-12 px-8 text-base">
              <Link to="/agent">进入控制台 <ArrowRight className="h-4 w-4" /></Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-12 px-8 text-base">
              <Link to="/monitor">查看监控看板</Link>
            </Button>
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-border/60 px-4 py-8">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-brand" />
            NIA · Nexus Intelligence Agent — 私有化的智能爬虫与情报分析系统
          </span>
          <span className="font-mono">React 19 · FastAPI · FAISS · BM25 · 全本地数据</span>
        </div>
      </footer>
    </div>
  );
}