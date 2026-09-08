import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { remarkBoundCitations } from "./remarkBoundCitations";
import { remarkReportHeadings } from "./remarkReportHeadings";
import { sourceCalculation } from "./sourceCalculation";
import { ReportVersions } from "./ReportVersions";
import { ResearchGraph } from "./ResearchGraph";
import type { ReportSnapshot } from "../api/reportSessions";
import {
  ArrowUp,
  BookOpen,
  Check,
  ChevronRight,
  Circle,
  FileText,
  Layers,
  LoaderCircle,
  MessageSquare,
  PanelRightClose,
  Plus,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  Square,
  X,
} from "lucide-react";
import {
  sessionsApi,
  streamClient,
  type Citation,
  type Event,
  type Session,
  type Source,
  type ResearchConfiguration,
} from "../api/reportSessions";
import "./research-session.css";

const format = (n: number) => new Intl.NumberFormat("zh-CN").format(n);
const stageName: Record<string, string> = {
  lead: "研究负责人",
  counter: "反证审查",
  case_review: "跨稿独立审查",
  convergence: "责任修订与报告交付",
  report_verifier: "报告终审",
  synthesis: "Lead · 综合研究判断",
  research_verifier: "研究判断复核",
  responsibility_router: "按问题责任回派",
  writer: "报告写作",
  verifier: "独立复核",
  quick_writer: "快速问答 · Flash",
  human_guidance: "用户补充意见",
  issuer_truth_specialist: "收入、利润与现金",
  demand_quality_specialist: "客户需求质量",
  architecture_ramp_specialist: "架构更新与交付",
  units_asp_pvm_specialist: "数量、价格与产品组合",
  model_compute_specialist: "模型与算力需求",
  supply_price_specialist: "供应链与成本传导",
  competition_specialist: "同行竞争与议价",
  export_control_specialist: "出口管制与区域风险",
  counterevidence_specialist: "反证与替代解释",
  counterevidence_synthesis_specialist: "反证与替代解释",
};
const branchName: Record<string, string> = { Q1: "收入、利润与现金", Q2: "客户需求质量", Q3: "量价与产品组合",
  Q4: "架构更新与交付", Q5: "供应链与成本", Q6: "模型与算力需求", Q7: "出口管制", Q8: "同行竞争", Q9: "反证与替代解释" };
const actorName = (actor: string) => {
  if (actor.startsWith("lead:")) return "Lead · 研究任务规划";
  const branch = actor.match(/^specialist:(Q\d+)_/)?.[1];
  if (branch && branchName[branch]) return `${branch} · ${branchName[branch]}`;
  return stageName[actor] || (actor.startsWith("author_") ? `${actor.slice(7)} · 责任作者修订` : actor);
};
const responsibilityName: Record<string, string> = { writer: "报告表达", research: "上游研究", data_tool: "数据 / 工具", human: "人工处理" };
const phaseName: Record<string, string> = {
  draft: "资料准备中 · 未调用模型",
  needs_revision: "有问题待修订",
  ready_for_human_review: "等待人工审阅",
  human_reviewed_not_released: "已人工审阅 · 未发布",
  working: "正在研究",
  research_reviewing: "专家底稿已提交 · 跨稿审查中",
  research_writing: "整合判断与撰写报告",
  research_needs_attention: "研究尚未完成 · 需要处理",
  research_incomplete_acknowledged: "已查看未完成研究",
};
function validLink(url?: string) {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return ["http:", "https:"].includes(u.protocol) ? u.href : undefined;
  } catch {
    return undefined;
  }
}

function chartSourceLinks(value: unknown): string[] {
  if (Array.isArray(value)) return [...new Set(value.flatMap(chartSourceLinks))];
  if (value && typeof value === "object") return [...new Set(Object.entries(value).flatMap(([key, item]) =>
    ["source_url", "url"].includes(key) && typeof item === "string" ? (validLink(item) ? [item] : []) :
    key === "citation_urls" && Array.isArray(item) ? item.filter((url): url is string => typeof url === "string" && !!validLink(url)) : chartSourceLinks(item)))];
  return [];
}

function Markdown({
  text,
  citations = {},
  onCitation,
  reportHeadings = false,
}: {
  text: string;
  citations?: Record<string, Citation>;
  onCitation: (key: string, citation: Citation) => void;
  reportHeadings?: boolean;
}) {
  const keys = Object.keys(citations);
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, [remarkBoundCitations, { ids: keys }], [remarkReportHeadings, { enabled: reportHeadings }]]}
      skipHtml
      components={{
        a: ({ href, children }) => {
          if (href?.startsWith("#claim:")) {
            let key: string;
            try { key = decodeURIComponent(href.slice(7)); }
            catch { return <span>{children}</span>; }
            if (!citations[key]) return <span>{children}</span>;
            return (
              <button
                className="rs-cite"
                onClick={() => onCitation(key, citations[key])}
              >
                {children}
              </button>
            );
          }
          const url = validLink(href);
          return url ? (
            <a href={url} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ) : (
            <span>{children}</span>
          );
        },
        img: ({ alt }) => (
          <span className="rs-image-note">
            [图示：{alt || "未自动加载外部图片"}]
          </span>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

export function ResearchSession() {
  const [configuration, setConfiguration] = useState<ResearchConfiguration | null>(null);
  const [configurationError, setConfigurationError] = useState("");
  const [creating, setCreating] = useState(false);
  const [researchQuestion, setResearchQuestion] = useState("");
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [id, setId] = useState(
    new URLSearchParams(window.location.search).get("thread") || "",
  );
  const [session, setSession] = useState<Session | null>(null);
  const [historicalReport, setHistoricalReport] = useState<ReportSnapshot | null>(null);
  const displayedReport = historicalReport?.report || session?.report;
  const reportQuery = historicalReport ? `?checkpoint_id=${encodeURIComponent(historicalReport.checkpoint_id)}` : "";
  const [text, setText] = useState("");
  const [action, setAction] = useState<"ask" | "revise">("ask");
  const [answerMode, setAnswerMode] = useState<"quick" | "deep">("quick");
  const [usageRunId, setUsageRunId] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"graph" | "report" | "conversation">("graph");
  useEffect(() => { if (session && !session.report && tab === "graph") setTab("report"); }, [session, tab]);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [taskDetails, setTaskDetails] = useState(false);
  const [outline, setOutline] = useState<{ id: string; label: string }[]>([]);
  const [activeHeading, setActiveHeading] = useState("");
  const reportArticle = useRef<HTMLElement>(null);
  const documentWindow = useRef<HTMLDivElement>(null);
  const reportScroll = useRef(0);
  const sourceReturnFocus = useRef<HTMLElement | null>(null);
  const sourceReturnLocation = useRef<{ area: string; index: number } | null>(null);
  const inspectorClose = useRef<HTMLButtonElement>(null);
  const sourceRequest = useRef(0);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState("");
  const [sourceHistory, setSourceHistory] = useState<Source[]>([]);
  const [inspector, setInspector] = useState<"review" | "activity" | "source">(
    "review",
  );
  const [selected, setSelected] = useState<{
    key: string;
    citation: Citation;
    checkpoint?: string;
  } | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const calculation = useMemo(() => sourceCalculation(source), [source]);
  const sourceWindow = useRef<HTMLDivElement>(null);
  useEffect(() => { setHistoricalReport(null); setSelected(null); setSource(null); setSourceHistory([]);
    setInspectorOpen(false); setTaskDetails(false); reportScroll.current = 0; sourceRequest.current += 1;
  }, [id]);
  useEffect(() => {
    setOutline(Array.from(reportArticle.current?.querySelectorAll<HTMLElement>("[id^='report-section-']") || [])
      .map(h => ({ id: h.id, label: h.textContent || "章节" })));
    setActiveHeading("");
  }, [displayedReport?.narrative_markdown]);
  useEffect(() => {
    reportScroll.current = 0;
    if (documentWindow.current) documentWindow.current.scrollTop = 0;
    setSelected(null); setSource(null); setSourceHistory([]); setSourceError(""); setSourceLoading(false);
    setInspectorOpen(false); sourceRequest.current += 1;
  }, [id, historicalReport?.checkpoint_id, session?.report_version]);
  useEffect(() => { if (tab === "report" && documentWindow.current) documentWindow.current.scrollTop = reportScroll.current; }, [tab]);
  const closeInspector = useCallback(() => {
    setInspectorOpen(false); sourceRequest.current += 1; setSourceLoading(false);
    requestAnimationFrame(() => {
      const origin = sourceReturnFocus.current;
      const location = sourceReturnLocation.current;
      const target = origin?.isConnected ? origin : location
        ? document.querySelectorAll<HTMLElement>(`${location.area} .rs-cite`)[location.index] : null;
      target?.focus({ preventScroll: true });
      if (tab === "report" && documentWindow.current) documentWindow.current.scrollTop = reportScroll.current;
    });
  }, [tab]);
  useEffect(() => {
    if (!inspectorOpen) return;
    inspectorClose.current?.focus({ preventScroll: true });
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") closeInspector(); };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [inspectorOpen, closeInspector]);
  const conversationEnd = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (tab === "conversation") conversationEnd.current?.scrollIntoView({ block: "end" });
  }, [id, tab, session?.conversation?.length]);
  useEffect(() => { if (source) sourceWindow.current?.scrollIntoView({ block: "nearest" }); }, [source]);
  const [events, setEvents] = useState<Event[]>([]);
  const [connected, setConnected] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const streamKey = useRef("");
  const [reconnect, setReconnect] = useState(0);
  const refresh = useCallback(async () => {
    setSessions(await sessionsApi.list());
  }, []);
  useEffect(() => {
    refresh().catch((e) => setError(String(e.message)));
    sessionsApi.config().then((value) => {
      setConfiguration(value);
      setResearchQuestion((current) => current || value.default_question || "");
    }).catch((e) => setConfigurationError(`无法读取当前服务的新研究配置：${String(e.message)}。新研究不会启动；请完成后台版本部署后再试。`));
  }, [refresh]);
  const choose = (next: string) => {
    setCreating(false);
    setUsageRunId("");
    setId(next);
    setSession(null);
    setEvents([]);
    setSelected(null);
    setSource(null);
    setError("");
    window.history.replaceState(
      {},
      "",
      `/workspace/session?thread=${encodeURIComponent(next)}`,
    );
  };
  useEffect(() => {
    if (!id) return;
    let disposed = false;
    let firstSnapshot = true;
    let timer: number | undefined;
    const update = async () => {
      let nextPollMs = 15000;
      try {
        const value = await sessionsApi.state(id);
        nextPollMs = value.status === "busy" ? 5000 : 15000;
        if (!disposed) {
          setSession(value);
          if (firstSnapshot) {
            setInspector(value.status === "busy" ? "activity" : "review");
            firstSnapshot = false;
          }
        }
      } catch (e) {
        if (!disposed) setError((e as Error).message);
      } finally {
        // Streaming carries live events; snapshots must not pile up when a
        // checkpoint read is slow, or poll an idle report at active-run speed.
        if (!disposed) timer = window.setTimeout(update, nextPollMs);
      }
    };
    update();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      abort.current?.abort();
      streamKey.current = "";
    };
  }, [id]);
  const activeRun = session?.runs?.find(
    (r) => r.status === "running" || r.status === "pending",
  );
  const busy = sending || !!activeRun || session?.status === "busy";
  useEffect(() => {
    if (!id || !activeRun) return;
    const key = `${id}/${activeRun.run_id}/${reconnect}`;
    if (streamKey.current === key) return;
    streamKey.current = key;
    abort.current?.abort();
    const control = new AbortController();
    abort.current = control;
    (async () => {
      try {
        setConnected(true);
        for await (const part of streamClient.runs.joinStream(
          id,
          activeRun.run_id,
          { signal: control.signal },
        )) {
          if (control.signal.aborted) break;
          if (
            part.event === "custom" &&
            part.data &&
            typeof part.data === "object"
          ) {
            const e = {...part.data, run_id: activeRun.run_id} as Event;
            setEvents((old) =>
              old.some(
                (x) =>
                  x.kind === e.kind &&
                  x.call_id === e.call_id &&
                  x.task_id === e.task_id &&
                  x.actor === e.actor &&
                  x.event === e.event &&
                  x.recorded_at === e.recorded_at,
              )
                ? old
                : [...old, e],
            );
          }
        }
      } catch (e) {
        if (!control.signal.aborted)
          setError(`事件流断开，任务未被重启：${(e as Error).message}`);
      } finally {
        if (!control.signal.aborted) {
          setConnected(false);
          sessionsApi
            .state(id)
            .then(setSession)
            .catch(() => {});
          refresh().catch(() => {});
        }
      }
    })();
    return () => {
      control.abort();
      setConnected(false);
    };
  }, [id, activeRun?.run_id, reconnect, refresh]);
  const allEvents = useMemo(() => {
    const map = new Map<string, Event>();
    for (const e of [...events, ...(session?.model_events || [])])
      map.set(`${e.run_id}/${e.kind}/${e.actor}/${e.call_id}/${e.task_id}/${e.event}/${e.recorded_at}`, e);
    return [...map.values()].sort(
      (a, b) => (Date.parse(a.recorded_at || "") || 0) - (Date.parse(b.recorded_at || "") || 0),
    );
  }, [session?.model_events, events]);
  const researchTasks = useMemo(() => {
    const map = new Map((session?.research_tasks || []).map((task) => [task.task_id, task]));
    for (const e of allEvents) if (e.kind === "task" && e.task_id) {
      map.set(e.task_id, { task_id: e.task_id, owner_role: e.actor, objective: e.objective || "",
        dependency_ids: e.dependency_ids || [], status: e.status || e.event });
    }
    // Final native outcomes win over a partial retained stream after refresh.
    for (const task of session?.research_tasks || [])
      if (!["planned", "ready"].includes(task.status)) map.set(task.task_id, task);
    return [...map.values()];
  }, [session?.research_tasks, allEvents]);
  const models = useMemo(() => {
    const map = new Map<string, Event>();
    for (const e of allEvents)
      if (e.kind === "model" && e.event === "outcome" && e.call_id)
        map.set(`${e.run_id}/${e.call_id}`, e);
    return [...map.values()];
  }, [allEvents]);
  const totals = models.reduce(
    (a, e) => ({
      tokens: a.tokens + (e.total_tokens || 0),
      input: a.input + (e.input_tokens || 0),
      output: a.output + (e.output_tokens || 0),
    }),
    { tokens: 0, input: 0, output: 0 },
  );
  const usageRun = session?.runs?.find(r => r.run_id === usageRunId) || session?.runs?.[0];
  const cumulative = session?.cumulative_usage;
  const visibleEvents = usageRun ? allEvents.filter(e => e.run_id === usageRun.run_id) : allEvents;
  const visibleModels = visibleEvents.filter(e => e.kind === "model" && e.event === "outcome");
  const newSession = async (mode: "review" | "research" = "review") => {
    setSending(true);
    setError("");
    try {
      const made = await sessionsApi.create(mode === "research" ? {
        mode, title: configuration?.title || "Dell · 新研究任务", question: researchQuestion, defer_start: uploadFiles.length > 0,
      } : { mode });
      choose(made.thread_id);
      if (mode === "research" && uploadFiles.length) {
        for (const file of uploadFiles) {
          setUploadStatus(`正在解析 ${file.name}，尚未启动研究模型`);
          await sessionsApi.upload(made.thread_id, file);
        }
        setUploadFiles([]);
        setUploadStatus("");
        await sessionsApi.start(made.thread_id);
      }
      if (mode === "research") setInspector("activity");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      await refresh().catch(() => {});
    } finally {
      setSending(false);
      setUploadStatus("");
    }
  };
  const send = async (
    selectedAction: "ask" | "revise" | "accept" = action,
    message = text,
  ) => {
    if (!id) return;
    setSending(true);
    setError("");
    try {
      await sessionsApi.action(id, selectedAction, message, selectedAction === "ask" ? answerMode : "deep");
      setUsageRunId("");
      setText("");
      setInspector("activity");
      if (selectedAction === "ask") setTab("conversation");
      setSession(await sessionsApi.state(id));
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };
  const cite = (key: string, citation: Citation, checkpoint?: string) => {
    sourceReturnFocus.current = document.activeElement as HTMLElement;
    const area = sourceReturnFocus.current.closest(".rs-report-pane") ? ".rs-report-pane" : ".rs-conversation";
    sourceReturnLocation.current = { area, index: Array.from(document.querySelectorAll(`${area} .rs-cite`)).indexOf(sourceReturnFocus.current) };
    if (tab === "report") reportScroll.current = documentWindow.current?.scrollTop || 0;
    sourceRequest.current += 1;
    setSelected({ key, citation, checkpoint });
    setSource(null);
    setSourceHistory([]); setSourceError(""); setSourceLoading(false);
    setInspector("source");
    setInspectorOpen(true);
  };
  const readSource = async (sourceId: string, offset = 0, keepHistory = false) => {
    const request = ++sourceRequest.current;
    setSourceLoading(true); setSourceError("");
    try {
      const result = await sessionsApi.source(id, sourceId, offset, selected?.checkpoint);
      if (request !== sourceRequest.current) return;
      setSourceHistory(history => keepHistory && source ? [...history, source] : []);
      setSource(result);
    } catch (e) { if (request === sourceRequest.current) setSourceError((e as Error).message); }
    finally { if (request === sourceRequest.current) setSourceLoading(false); }
  };
  const findings = session?.report_review?.findings || [];
  return (
    <div className={`rs-shell ${inspectorOpen ? "rs-has-inspector" : ""}`}>
      <aside className="rs-sidebar">
        <a className="rs-brand" href="/workspace/session">
          <span className="rs-brand-mark">
            <Layers size={20} />
          </span>
          <strong>
            FinSight<span>RESEARCH WORKSPACE</span>
          </strong>
        </a>
        <button className="rs-new" onClick={() => setCreating(true)} disabled={sending}>
          <Plus size={16} /> 新建研究任务
        </button>
        {configuration?.legacy_review_enabled && <button className="rs-legacy-link" onClick={() => newSession("review")} disabled={sending}>
          <BookOpen size={14} /> 打开已有 Dell 报告审阅
        </button>}
        <div className="rs-side-label">
          研究会话{" "}
          <button
            aria-label="刷新会话"
            onClick={() => refresh().catch((e) => setError(e.message))}
          >
            <RefreshCw size={13} />
          </button>
        </div>
        <nav className="rs-session-list">
          {sessions.map((s) => (
            <button
              key={s.thread_id}
              className={s.thread_id === id ? "selected" : ""}
              onClick={() => choose(s.thread_id)}
            >
              <FileText size={15} />
              <span>
                {s.title}
                <small>
                  {s.status === "busy"
                    ? "运行中"
                    : s.status === "interrupted"
                      ? "等待审阅"
                    : "已保存"} · {s.thread_id.slice(-6)}
                </small>
              </span>
            </button>
          ))}
        </nav>
        <div className="rs-sidebar-bottom">
          <ShieldCheck size={17} />
          <div>
            本地研究环境<small>来源只读 · 密钥留在服务端</small>
          </div>
        </div>
      </aside>
      <main className="rs-main">
        <header className="rs-top">
          <div className="rs-breadcrumb">
            <a href="/workspace/session">研究列表</a> / <b>研究工作台</b>
          </div>
          <span className="rs-local">
            <span /> LOCAL PILOT
          </span>
          <div className="rs-detail-actions">
            <button onClick={(e) => { sourceReturnFocus.current = e.currentTarget; setInspector("review"); setInspectorOpen(true); }}>审查意见</button>
            <button onClick={(e) => { sourceReturnFocus.current = e.currentTarget; setInspector("activity"); setInspectorOpen(true); }}>运行与费用</button>
          </div>
        </header>
        {id && !session && !creating ? <section className="rs-empty" role="status"><LoaderCircle className="rs-spin" /><h1>正在读取已保存研究…</h1><p>读取报告不会发起新的模型调用。</p></section> : !session || creating ? (
          <section className="rs-empty">
            <span className="rs-eyebrow">从一份研究，到一个可追问的判断</span>
            <h1>让结论经得起追问。</h1>
            <p>
              提出一个有分量的问题，让研究 Agent 自主拆解、查资料、核算与交叉质疑。
              当前围绕 Dell 案例运行，原始资料可以复用，旧报告不会被当成新研究答案。
            </p>
            <div className="rs-empty-cards">
              <div>
                <BookOpen />
                <h3>自主拆题与研究</h3>
                <p>Lead 动态分工，专家按需调用内外源工具。</p>
              </div>
              <div>
                <MessageSquare />
                <h3>有依据的判断</h3>
                <p>把业务机制连到利润和现金，保留真正的反证。</p>
              </div>
              <div>
                <ShieldCheck />
                <h3>看独立复核</h3>
                <p>来源绑定不代表结论正确，保留反例与人工判断。</p>
              </div>
            </div>
            <div className="rs-research-prompt">
              <label htmlFor="new-research-question">这次你想研究什么？</label>
              <textarea id="new-research-question" value={researchQuestion} maxLength={16000}
                onChange={(e) => setResearchQuestion(e.target.value)} rows={7}
                placeholder="例如：判断 Dell 的增长质量、盈利兑现和未来执行压力，并说明什么证据会改变判断。" />
              <div><span>案例资料时点：{configuration?.research_as_of?.slice(0, 10) || "待配置"}</span>
                {configuration?.cost_expectation_cny && <span>完整研究规划估费约 ¥{configuration.cost_expectation_cny.rough_low}–{configuration.cost_expectation_cny.rough_high}，非固定价格</span>}</div>
            </div>
            <button
              className="rs-primary"
              disabled={sending || !configuration?.fresh_research_enabled || researchQuestion.trim().length < 10}
              onClick={() => newSession("research")}
            >
              {sending ? (
                <LoaderCircle className="rs-spin" size={16} />
              ) : (
                <Plus size={16} />
              )}{" "}
              {sending ? "正在创建任务" : "开始全新研究"}
            </button>
            <label className="rs-upload-label">补充本次研究资料（可选）
              <input type="file" multiple accept=".pdf,.docx,.md,.txt,.csv,.html,.htm,.png,.jpg,.jpeg,.webp"
                disabled={sending} onChange={(e) => { const files = Array.from(e.target.files || []); if (files.length > 12) { setError("一次最多12份资料，请重新选择；没有静默丢弃文件。"); e.target.value = ""; setUploadFiles([]); } else setUploadFiles(files); }} />
              <small>PDF、Word、Markdown、文本、CSV、HTML 或图片；每份最多20MiB。仅当前任务可用，不写入共享知识库。图片识别按需调用视觉模型。</small>
            </label>
            {uploadFiles.length > 0 && <p>{uploadFiles.map((file) => file.name).join("、")}</p>}
            <small>
              {configurationError || (configuration?.fresh_research_enabled
                ? "开始研究会产生真实模型调用；研究过程中可查看任务和费用、停止执行。打开旧报告则不重新研究。"
                : configuration?.legacy_review_enabled ? "新研究尚未启用；可打开已有报告审阅。" : "连接研究运行服务并启用新研究后即可开始；此部署没有预装旧报告。")}
            </small>
          </section>
        ) : (
          <>
            <section className="rs-heading">
              <div>
                <h1>{session.title || sessions.find(s => s.thread_id === id)?.title || "研究报告"}</h1>
                <p>
                  信息截止 {session.research_as_of?.slice(0, 10) || "未提供"} <span>·</span>{" "}
                  {historicalReport ? `正在阅读历史 v${historicalReport.report_version}` : `当前报告 v${session.report_version || "—"}`}
                  <button className="rs-task-toggle" aria-expanded={taskDetails} onClick={() => setTaskDetails(v => !v)}>任务说明与资料</button>
                </p>
              </div>
              <span
                className={`rs-status ${busy ? "running" : session.phase === "needs_revision" ? "warning" : ""}`}
              >
                {busy ? (
                  <LoaderCircle size={14} className="rs-spin" />
                ) : (
                  <Circle size={8} />
                )}{" "}
                {session.is_draft ? (uploadStatus ? "正在解析资料 · 未调用模型" : "资料准备中 · 未调用模型") : busy
                  ? "Agent 正在执行"
                  : session.runs?.[0]?.status === "interrupted"
                    ? "已停止 · 原有结果和记录保留"
                    : session.status === "error"
                    ? "本次执行失败 · 状态已保留"
                    : phaseName[session.phase || ""] || "正在载入"}
              </span>
            </section>
            <div className="rs-task-details" hidden={!taskDetails && !!session.report}>
            {session.question && <div className="rs-task-question">{session.question}</div>}
            {uploadStatus && <div className="rs-report-notice">{uploadStatus}</div>}
            {!busy && (session.is_draft || (session.case_profile === "dell_growth_quality" && session.can_respond)) &&
              <label className="rs-upload-label">补充本任务资料
                <input type="file" aria-label="补充本任务资料" accept=".pdf,.docx,.md,.txt,.csv,.html,.htm,.png,.jpg,.jpeg,.webp"
                  disabled={sending} onChange={async (e) => { const file = e.target.files?.[0]; if (!file) return;
                    setSending(true); setUploadStatus(`正在解析：${file.name}`); try { await sessionsApi.upload(id, file); setSession(await sessionsApi.state(id)); }
                    catch (err) { setError((err as Error).message); } finally { setSending(false); setUploadStatus(""); e.target.value = ""; }
                  }} />
              </label>}
            {!!session.attachments?.length && <details className="rs-task-board"><summary>本任务资料 · {session.attachments.length} 份</summary>
              {session.attachments.map((file) => <p key={file.document_id}><a href={`/api/v1/research-sessions/${id}/attachments/${encodeURIComponent(file.document_id)}`}>{file.name}</a>
                {" · "}{file.sections} 个页面/章节{file.needs_vision ? " · 可按需视觉识别" : " · 已解析，可检索"}</p>)}
            </details>}
            {session.is_draft && <div className="rs-report-notice"><span>资料准备任务已保存，尚未调用研究模型。</span>
              <button disabled={busy} onClick={async () => { setSending(true); try { await sessionsApi.start(id); setSession(await sessionsApi.state(id)); }
                catch (e) { setError((e as Error).message); } finally { setSending(false); } }}>开始已准备的研究</button></div>}
            {session.research_stop_reason && <div className="rs-report-notice">
              <ShieldCheck size={17} /><span>本次仍有未解决问题，已保留成果，不会自动整案重跑。
                {session.research_stop_reason === "material_findings_remain_after_targeted_correction" ? "一轮定向修订后，重大问题仍未关闭。" :
                 session.research_stop_reason === "unresolved_data_or_author_response" ? "数据、工具或责任作者仍有未解决项，请查看审查意见。" : session.research_stop_reason}
              </span></div>}
            {(researchTasks.length > 0 || (session.question && !session.report)) && (
              <details className="rs-task-board" open={!session.report}>
                <summary><Layers size={16} /> 本次研究分工 <span>{researchTasks.length ? `当前任务视图 ${researchTasks.length} 项` : "任务摘要待同步"} · 并发上限 2</span></summary>
                {!researchTasks.length && <p>任务摘要尚未同步，请在右侧“运行”查看实际模型调用；这不表示研究尚未开始，也不会因此重新启动任务。</p>}
                <div className="rs-task-grid">{researchTasks.map((task) => (
                  <div className="rs-task-card" key={task.task_id}>
                    <div><strong>{actorName(task.owner_role || "研究专家")}</strong><span>{
                      ["submitted", "specialist_submission_accepted"].includes(task.status) ? "已提交底稿" :
                      task.status === "running" ? "研究中" : task.status === "error" ? "执行失败" :
                      ["needs_attention", "specialist_human_review_handoff_emitted", "human_review_required"].includes(task.status) ? "未完成 · 待处理" :
                      ["planned", "ready"].includes(task.status) ? "等待执行" : "状态待核实"
                    }</span></div>
                    <p>{task.objective}</p>
                    <small>{task.dependency_ids.length ? `依赖：${task.dependency_ids.join("、")}` : "可独立执行"}</small>
                  </div>
                ))}</div>
                {!!session.research_attempt_history?.length && <details><summary>本任务各次研究尝试（保留未完成记录）</summary>
                  {session.research_attempt_history.map((attempt, i) => <p key={i}>第 {i + 1} 次 · {attempt.outcomes.filter(t => t.status === "submitted").length} 份新底稿 · {attempt.outcomes.filter(t => t.status !== "submitted").map(t => `${t.task_id} 未完成`).join("、") || "无未完成结果"}</p>)}
                </details>}
              </details>
            )}
            </div>
            {session.report && session.research_stop_reason && !taskDetails && <div className="rs-report-notice">
              <ShieldCheck size={16} /><span>本次研究仍有未解决问题，已保存报告供审阅，不会自动重跑。</span>
              <button onClick={(e) => { sourceReturnFocus.current = e.currentTarget; setInspector("review"); setInspectorOpen(true); }}>查看未决审查</button>
            </div>}
            <div className="rs-tabs">
              <div>
                {displayedReport && <button className={tab === "graph" ? "active" : ""} onClick={() => { setInspectorOpen(false); setTab("graph"); }}><Layers size={15} /> 研究图</button>}
                <button
                  className={tab === "report" ? "active" : ""}
                  onClick={() => setTab("report")}
                >
                  <FileText size={15} /> 研究报告
                </button>
                <button
                  className={tab === "conversation" ? "active" : ""}
                  onClick={() => setTab("conversation")}
                >
                  <MessageSquare size={15} /> 追问与反馈{" "}
                  <small>{session.conversation?.length || 0}</small>
                </button>
              </div>
              <span>
                {Object.keys(displayedReport?.citations || {}).length}{" "}
                条引用可展开
              </span>
            </div>
            <div className="rs-content-shell" data-tab={tab}>
            {displayedReport && <ResearchGraph key={`${id}:${historicalReport?.checkpoint_id || session.report_version}`} id={id}
              version={historicalReport?.report_version || session.report_version || 1} checkpoint={historicalReport?.checkpoint_id}
              report={displayedReport} digest={historicalReport?.report_digest || session.report_digest} canRevise={!historicalReport && !!session.can_respond}
              runs={session.runs || []} onRefresh={async () => { setSession(await sessionsApi.state(id)); await refresh(); }} active={tab === "graph"} onReport={() => setTab("report")} />}
            {tab === "report" && !!outline.length && <nav className="rs-outline" aria-label="报告目录">
              <label htmlFor="report-section-picker">报告目录</label>
              <select id="report-section-picker" value={activeHeading} onChange={e => { setActiveHeading(e.target.value); document.getElementById(e.target.value)?.scrollIntoView({ block: "start" }); }}>
                <option value="">选择章节</option>{outline.map(h => <option key={h.id} value={h.id}>{h.label}</option>)}
              </select>
              <div>{outline.map(h => <button key={h.id} aria-current={activeHeading === h.id ? "location" : undefined}
                onClick={() => { setActiveHeading(h.id); document.getElementById(h.id)?.scrollIntoView({ block: "start" }); }}>{h.label}</button>)}</div>
            </nav>}
            <div className={`rs-document rs-active-${tab}`} ref={documentWindow} onScroll={e => { if (tab === "report" && !inspectorOpen) reportScroll.current = e.currentTarget.scrollTop; }}>
                <section className="rs-report-pane" aria-label="研究报告">
                  {session.report && <ReportVersions key={id} id={id} currentVersion={session.report_version || 1} onSelect={setHistoricalReport} />}
                  <div className="rs-report-notice">
                    <ShieldCheck size={17} />
                    <span>
                      {session.report ? "引用可以展开查看依据；报告的实质判断仍需结合来源上下文审阅。" : session.is_draft ? "资料上传与解析不启动研究模型。确认材料后点击开始。" : "研究进行中：底稿、审查与报告会按实际完成情况出现。"}
                    </span>
                  </div>
                  <article className="rs-prose" ref={reportArticle}>
                    <h2 className="rs-report-title">{displayedReport?.title}</h2>
                    {displayedReport && <div className="rs-export-actions"><span>导出这版报告</span>
                      {([['md', 'Markdown'], ['pdf', 'PDF'], ['docx', 'Word'], ['pptx', 'PowerPoint']] as const).map(([format, label]) =>
                        <a key={format} href={`/api/v1/research-sessions/${id}/report/export/${format}${reportQuery}`} download>{label}</a>)}
                      {!!displayedReport.charts?.length && <a href="#report-charts">查看 {displayedReport.charts.length} 幅图表</a>}
                    </div>}
                    <Markdown
                      reportHeadings
                      text={
                        displayedReport?.narrative_markdown || (session.is_draft ? "研究尚未启动。这里将在研究完成后显示报告。" : session.status === "error" ? "本次尚未取得报告。请查看运行状态；失败记录与已有研究材料均保留。" : "报告尚未生成；请在研究现场查看真实任务进度。")
                      }
                      citations={displayedReport?.citations}
                      onCitation={(key, citation) => cite(key, citation, historicalReport?.checkpoint_id)}
                    />
                    {!!displayedReport?.charts?.length && <h3 id="report-charts">图表与出处</h3>}
                    {displayedReport?.charts?.map((chart, index) => <figure className="rs-research-chart" key={`${historicalReport?.report_version || session.report_version}-${index}`}>
                      <img src={`/api/v1/research-sessions/${id}/report/charts/${index}.png${reportQuery || `?v=${session.report_version}`}`} alt={chart.title} />
                      <figcaption>{chart.interpretation}</figcaption>
                      <details><summary>图表数值与来源（{chart.unit}）</summary><table><thead><tr><th>项目</th><th>系列</th><th>数值</th><th>来源</th></tr></thead>
                        <tbody>{chart.points.map((point, p) => <tr key={p}><td>{point.label}</td><td>{point.series}</td><td>{point.value.toLocaleString()}</td>
                          <td>{chartSourceLinks(point.provenance).map((url, n) => <a key={url} href={url} target="_blank" rel="noopener noreferrer">原始来源 {n + 1} </a>)}
                            <details><summary>定位与计算明细</summary><small>{point.source_id}</small><pre>{JSON.stringify(point.provenance, null, 2)}</pre></details></td></tr>)}</tbody></table></details>
                    </figure>)}
                  </article>
                </section>
                <div className="rs-conversation" aria-label="研究对话">
                  {!session.conversation?.length && (
                    <div className="rs-conversation-empty">
                      <MessageSquare size={28} />
                      <h3>从一个具体问题开始</h3>
                      <p>
                        例如：融资应收加回变小，为什么不一定代表现金流变差？
                      </p>
                    </div>
                  )}
                  {session.conversation?.map((m, i) => (
                    <div key={i} className={`rs-message ${m.role}`}>
                      <span className="rs-message-label">
                        {m.role === "user"
                          ? "你 · 公开反馈"
                          : m.role === "system" ? "运行提示 · 不是模型回答" : "研究 Agent · 来源绑定回答"}
                      </span>
                      <div className="rs-prose">
                        <Markdown
                          text={m.content}
                          citations={m.citations}
                          onCitation={cite}
                        />
                      </div>
                    </div>
                  ))}
                  {busy && (
                    <div className="rs-working">
                      <LoaderCircle size={16} className="rs-spin" />{" "}
                      正在按需读取材料与工具反馈。可在右侧查看真实运行事件。
                    </div>
                  )}
                  <div ref={conversationEnd} />
                </div>
            </div>
            <footer className="rs-compose">
              <div className="rs-compose-tools">
                <div>
                  <button
                    className={action === "ask" ? "active" : ""}
                    onClick={() => setAction("ask")}
                  >
                    <MessageSquare size={14} /> 追问
                  </button>
                  <button
                    className={action === "revise" ? "active" : ""}
                    onClick={() => setAction("revise")}
                  >
                    <FileText size={14} /> 定向修订
                  </button>
                </div>
                <span>
                  {action === "ask"
                    ? "回答问题，不自动重写报告"
                    : "Writer 修订后交独立 Verifier"}
                </span>
              </div>
              {action === "ask" && (
                <div className="rs-answer-mode">
                  <label htmlFor="answer-mode">处理模式</label>
                  <select id="answer-mode" value={answerMode}
                    disabled={busy || sending}
                    onChange={(e) => setAnswerMode(e.target.value as "quick" | "deep")}>
                    <option value="quick">快速问答 · Flash</option>
                    <option value="deep">深度追问 · Pro</option>
                  </select>
                  <small>{answerMode === "quick" ? "查数、出处与简短解释；资料按需读取" : "复杂推断与多来源分析；通常耗时更长"}</small>
                </div>
              )}
              <textarea
                aria-label="问题或修订意见"
                value={text}
                onChange={(e) => setText(e.target.value)}
                maxLength={16000}
                placeholder={
                  action === "ask"
                    ? "追问这个判断的依据、口径或其他解释…"
                    : "说明哪一处需要修订，以及你希望核实的问题…"
                }
                onKeyDown={(e) => {
                  if (
                    (e.ctrlKey || e.metaKey) &&
                    e.key === "Enter" &&
                    !busy &&
                    session.can_respond &&
                    text.trim()
                  ) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              {session.research_guidance?.length ? <details><summary>已保存的运行中意见（{session.research_guidance.length}）</summary>
                {session.research_guidance.map((g, i) => <p key={i}>{g.message}</p>)}
                <small>在后续阶段交接时读取。以运行记录中的“用户补充意见”事件确认是否已送达。</small></details> : null}
              <div className="rs-compose-bottom">
                {!busy && session.can_continue_remaining && <button disabled={sending} onClick={async () => {
                  setSending(true); try { await sessionsApi.continueRemaining(id); setSession(await sessionsApi.state(id)); }
                  catch (e) { setError((e as Error).message); } finally { setSending(false); }
                }}>继续未完成主题 · 保留已交稿</button>}
                {busy && session.question && <button disabled={sending || !text.trim()} onClick={async () => {
                  setSending(true); try { await sessionsApi.guidance(id, text); setText(""); setSession(await sessionsApi.state(id)); }
                  catch (e) { setError((e as Error).message); } finally { setSending(false); }
                }}>补充意见 · 下阶段读取</button>}
                {!busy && session.phase === "research_needs_attention" && <button onClick={async () => {
                  try { await sessionsApi.acknowledgeIncomplete(id); setSession(await sessionsApi.state(id)); }
                  catch (e) { setError((e as Error).message); }
                }}>确认已查看 · 不重跑</button>}
                <small>
                  {session.can_respond
                    ? "模型可按需读取资料 · Ctrl / ⌘ + Enter 发送"
                    : busy
                      ? "运行中可停止；不会自动重发未知结果的调用"
                      : "当前不在可继续的人工审阅点"}
                </small>
                {busy && activeRun ? (
                  <button
                    className="rs-stop"
                    onClick={async () => {
                      try {
                        await sessionsApi.cancel(id, activeRun.run_id);
                        setSession(await sessionsApi.state(id));
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    <Square size={12} /> 停止
                  </button>
                ) : session.can_abandon_question ? (
                  <button className="rs-stop" disabled={sending} onClick={async () => {
                    setSending(true);
                    try {
                      await sessionsApi.abandonQuestion(id);
                      setTab("conversation");
                      setSession(await sessionsApi.state(id));
                    } catch (e) { setError((e as Error).message); }
                    finally { setSending(false); }
                  }}>
                    返回审阅 · 不重试
                  </button>
                ) : (
                  <button
                    className="rs-send"
                    aria-label="发送"
                    disabled={!text.trim() || !session.can_respond || busy}
                    onClick={() => send()}
                  >
                    <ArrowUp size={19} />
                  </button>
                )}
              </div>
            </footer>
            </div>
          </>
        )}
        {error && (
          <div className="rs-error" role="alert">
            <span>{error}</span>
            <button aria-label="关闭提示" onClick={() => setError("")}>
              <X size={15} />
            </button>
          </div>
        )}
      </main>
      <aside className={`rs-inspector ${inspectorOpen ? "rs-inspector-open" : ""}`} aria-label="审查与运行详情" hidden={!inspectorOpen}>
        <header>
          <span>
            <Radio size={16} /> {inspector === "source" ? "来源与计算" : inspector === "review" ? "审查意见" : "运行与费用"}
          </span>
          <span className={connected ? "rs-live" : "rs-muted"}>
            {connected ? "实时连接" : "已保存状态"}
          </span>
          <button ref={inspectorClose} aria-label="关闭详情" onClick={closeInspector}><span className="rs-return-label">返回阅读</span><X size={16} /></button>
        </header>
        <div className="rs-inspector-tabs">
          <button
            className={inspector === "review" ? "active" : ""}
            onClick={() => setInspector("review")}
          >
            审查 {findings.length > 0 && <b>{findings.length}</b>}
          </button>
          <button
            className={inspector === "activity" ? "active" : ""}
            onClick={() => setInspector("activity")}
          >
            运行
          </button>
          <button
            className={inspector === "source" ? "active" : ""}
            onClick={() => setInspector("source")}
          >
            来源
          </button>
        </div>
        <div className="rs-inspector-content">
          {inspector === "review" && (
            <>
              <h3>需要核实的判断</h3>
              {busy && <p>{session?.report_review ? "运行中：下方是上一轮已保存的审查，本轮复核尚未完成。" : session?.workpaper_reviews?.length ? "底稿审查已提交，下方保留原始发现；责任修订与报告终审仍在继续。" : "研究正在进行，独立审查尚未交稿。可切换到“运行”查看当前活动。"}</p>}
              <p className="rs-helper">
                这是模型审查意见，不是标准答案。可以展开原文、提出异议，再交给作者处理。
              </p>
              {findings.map((f, i) => (
                <details
                  className="rs-finding"
                  key={f.finding_id}
                  open={i === 0}
                >
                  <summary>
                    <span className={`rs-severity ${f.severity}`}>
                      {f.severity === "material" ? "重大" : "建议"}
                    </span>
                    <span>
                      {f.finding_id.replace(/^R\d+_/, "").replaceAll("_", " ")}
                    </span>
                    <ChevronRight size={15} />
                  </summary>
                  <blockquote>{f.report_quote}</blockquote>
                  <p>{f.diagnosis}</p>
                  {f.responsibility && <p className="rs-helper">责任：{responsibilityName[f.responsibility]}
                    {!!f.paper_ids?.length && ` · ${f.paper_ids.join("、")}`}</p>}
                  <div className="rs-recommendation">{f.requested_change}</div>
                  <button
                    onClick={() => {
                      setAction("revise");
                      setText(
                        `请核查下面这条审查意见，原始资料优先于审查者意见。若成立，修订对应内容与重复结论；若不成立，保留有来源支撑的判断。\n原文：${f.report_quote}\n问题：${f.diagnosis}\n建议：${f.requested_change}`,
                      );
                    }}
                  >
                    作为修订反馈 <ChevronRight size={13} />
                  </button>
                </details>
              ))}
              {!findings.length && (
                <p className="rs-muted">
                  {session
                    ? session.report_review ? "最终报告审查未列出问题；仍需人工判断。" : "最终报告审查尚未提交；已完成的研究阶段审查见下方。"
                    : "打开研究会话后显示真实审查结果。"}
                </p>
              )}
              {session?.report_review && (
                <details className="rs-review-summary">
                  <summary>阅读完整审查摘要</summary>
                  <p>{session.report_review.summary}</p>
                  {session.report_review.unresolved_data_requests.map(
                    (x, i) => (
                      <p key={i}>{x}</p>
                    ),
                  )}
                </details>
              )}
              {session?.synthesis_review && <details className="rs-review-summary">
                <summary>Lead 综合判断的独立复核</summary>
                <p>{session.synthesis_review.summary}</p>
                {session.synthesis_review.findings.map(f => <div key={f.finding_id}>
                  <strong>{f.severity === "material" ? "重大" : "建议"} · {responsibilityName[f.responsibility || ""] || "待定位"} {f.paper_ids?.join("、")}</strong>
                  <p>{f.diagnosis}</p><p>{f.requested_change}</p>
                </div>)}
                {session.synthesis_review.unresolved_data_requests.map((item, i) => <p key={i}>{item}</p>)}
              </details>}
              {session?.workpaper_reviews?.map(review => <details className="rs-review-summary" key={review.actor}>
                <summary>{actorName(review.actor)} · 原始底稿审查（{review.findings.length} 条）</summary>
                <p className="rs-helper">这是研究中途的原始发现，是否已修正以随后综合复核和报告终审为准。</p>
                <p>{review.summary}</p>
                {review.findings.map(f => <div key={f.finding_id}>
                  <strong>{f.paper_id} · {f.severity === "material" ? "重大" : "建议"}</strong>
                  <blockquote>{f.problematic_quote}</blockquote><p>{f.diagnosis}</p><p>{f.requested_change}</p>
                </div>)}
              </details>)}
              {session?.can_accept && (
                <button
                  className="rs-accept"
                  onClick={() => send("accept", "")}
                >
                  <Check size={15} /> 人工确认本版 · 不发布
                </button>
              )}
            </>
          )}
          {inspector === "activity" && (
            <>
              <h3>真实调用，不是模拟进度</h3>
              <div className="rs-answer-mode">
                <label htmlFor="usage-run">查看请求用量与活动</label>
                <select id="usage-run" value={usageRun?.run_id || ""} onChange={e => setUsageRunId(e.target.value)}>
                  {session?.runs?.map(r => <option key={r.run_id} value={r.run_id}>
                    {new Date(r.created_at).toLocaleTimeString("zh-CN")} · {r.human_action === "research" ? "完整新研究" : r.human_action === "continue_remaining" ? "接续同任务余下流程" : r.human_action === "ask" ? (r.answer_mode === "quick" ? "Flash 问答" : "Pro 追问") : r.human_action === "revise" ? "报告修订" : r.human_action === "abandon_failed_question" ? "放弃失败追问" : r.human_action === "return_stopped_question" ? "停止后返回审阅" : "载入 / 审阅"} · {r.status === "interrupted" ? "已停止" : r.status}
                  </option>)}
                </select>
              </div>
              <div className="rs-usage">
                <div><small>已知部分估费 · 非账单</small><strong>{usageRun?.cost_estimate ? `¥${usageRun.cost_estimate.known_cny.toFixed(3)}` : "—"}</strong>
                  <small>未计入进行中 / 缺失用量；单价 {usageRun?.cost_estimate?.price_as_of || "待确认"}</small></div>
                <div>
                  <small>所选请求 · 已记录调用</small>
                  <strong>{usageRun?.usage?.recorded_requests ?? "—"}</strong>
                </div>
                <div>
                  <small>所选请求 · 已报告 tokens</small>
                  <strong>{usageRun?.usage ? format(usageRun.usage.total_tokens) : "—"}</strong>
                </div>
              </div>
              <p className="rs-helper">
                {usageRun?.usage ? <>输入 {format(usageRun.usage.input_tokens)} · 输出 {format(usageRun.usage.output_tokens)} · {usageRun.usage.unknown_or_pending_requests} 次用量待定 / 未知。{usageRun.usage.partial_audit && "审计记录尚不完整。"}</> : "没有本次模型用量记录；载入报告或放弃追问不会发起模型调用。"}
              </p>
              <p className="rs-helper">
                {usageRun?.usage && <>所选请求缓存：已知命中 {format(usageRun.usage.cache_hit_tokens || 0)} / 未命中 {format(usageRun.usage.cache_miss_tokens || 0)} tokens；{usageRun.usage.unknown_cache_requests ?? "未知"} 次缓存明细待定。</>}
                {usageRun?.elapsed_ms !== undefined && <> 执行耗时 {(usageRun.elapsed_ms / 1000).toFixed(1)} 秒（含调度与工具）。</>}
              </p>
              {cumulative && <>
                <h4>本任务累计 · 全部 {cumulative.native_runs} 次原生运行</h4>
                <div className="rs-usage">
                  <div><small>已知部分估费 · 非账单</small><strong>¥{cumulative.known_cny.toFixed(3)}</strong></div>
                  <div><small>已记录模型调用</small><strong>{cumulative.recorded_requests}</strong></div>
                  <div><small>已报告 tokens</small><strong>{format(cumulative.total_tokens)}</strong></div>
                </div>
                <p className="rs-helper">输入 {format(cumulative.input_tokens)} · 输出 {format(cumulative.output_tokens)}；缓存已知命中 {format(cumulative.cache_hit_tokens)} / 未命中 {format(cumulative.cache_miss_tokens)}，{cumulative.unknown_cache_requests} 次缓存明细未知。已记录模型耗时合计 {(cumulative.elapsed_ms / 1000).toFixed(1)} 秒，{cumulative.unknown_elapsed_requests} 次耗时未知。</p>
                <p className="rs-helper">{cumulative.unknown_or_pending_requests} 次用量待定 / 未知，{cumulative.unpriced_requests} 次未计价，{cumulative.missing_audit_runs} 次运行缺少用量记录。{cumulative.partial_audit && "存在未完整读取的审计记录。"}{cumulative.notice}</p>
              </>}
              <p className="rs-helper">
                活动视图当前载入 {models.length} 次模型结果记录、{format(totals.tokens)} 个已报告 tokens。下方仅显示所选请求，最新事件在前；可在上方切换查看历史请求。
              </p>
              <div className="rs-agent-cards">
                {[...new Set(visibleEvents.filter(e => e.kind === "model").map(e => e.actor))].map((role) => (
                  <div key={role}>
                    <span className="rs-agent-avatar">
                      {role.startsWith("author_") ? "A" : role.charAt(0).toUpperCase()}
                    </span>
                    <span>
                      {actorName(role)}
                      <small>
                        {visibleModels.filter((x) => x.actor === role).length}{" "}
                        次已报告调用
                      </small>
                    </span>
                  </div>
                ))}
              </div>
              <div className="rs-event-list">
                {[...visibleEvents].reverse().map((e, i) => (
                  <div key={i}>
                    <span
                      className={`rs-event-dot ${e.status === "error" || e.status === "provider_failed" ? "error" : ""}`}
                    />
                    <div>
                      <strong>{actorName(e.actor)}</strong>
                      <span>
                        {e.kind === "tool"
                          ? e.tool
                          : e.kind === "model"
                            ? e.model || "模型"
                            : "任务节点"}
                      </span>
                      <small>
                        {e.event === "started"
                          ? "开始"
                          : e.error_type === "CancelledError"
                            ? "已中断 · 用量未知"
                          : e.status === "handoff"
                            ? "已交接"
                            : e.status === "success"
                              ? "已返回"
                              : e.status || e.event}
                        {e.total_tokens !== undefined &&
                          ` · ${format(e.total_tokens)} tokens`}
                        {e.correction_round !== undefined && ` · ${e.correction_round ? "定向修订轮" : "首次执行"}`}
                        {!!e.responsible_paper_ids?.length && ` · 回派 ${e.responsible_paper_ids.join("、")}`}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
              {!visibleEvents.length && (
                <p className="rs-muted">
                  提交追问或修订后，这里展示原生子 Agent
                  的模型与工具事件。已保存用量来自后端，不模拟动画。
                </p>
              )}
              <button
                className="rs-reconnect"
                disabled={!activeRun}
                onClick={() => setReconnect((n) => n + 1)}
              >
                <RefreshCw size={13} /> 重新连接事件流
              </button>
              <div className="rs-trace-note">
                LangSmith + PostgreSQL
                <br />
                原生运行 ID{" "}
                <code>{usageRun?.run_id || "尚未创建"}</code>
              </div>
            </>
          )}
          {inspector === "source" &&
            (selected ? (
              <>
                <div className="rs-source-heading">
                  <span className="rs-eyebrow">CITATION DETAIL</span>
                  <button
                    aria-label="关闭引用"
                    onClick={closeInspector}
                  >
                    <PanelRightClose size={16} />
                  </button>
                </div>
                <h3>引用依据</h3>
                <details className="rs-source-id"><summary>引用标识</summary><code>{selected.key}</code></details>
                <small>引用记录中的原始主张</small>
                <p>{selected.citation.claim.statement}</p>
                {selected.citation.sources.map((s) => (
                  <div className="rs-source-card" key={s.source_id}>
                    <span className="rs-source-type">
                      {s.numeric_fact_authority
                        ? "结构化数值"
                        : s.source_id.startsWith("CALC::") || s.result_state === "non_authoritative_metric"
                          ? "本地计算 · 非权威" : s.result_state === "query_gap_receipt"
                            ? "本地查询边界 · 非事实证据" : "披露 / 外部材料"}
                    </span>
                    <h4>
                      {s.title ||
                        [s.ticker, s.metric_id, s.period_end]
                          .filter(Boolean)
                          .join(" · ") ||
                        s.source_id}
                    </h4>
                    {[s.source_url, ...(s.citation_urls || [])]
                      .filter(Boolean)
                      .map(
                        (u, i) =>
                          validLink(u) && (
                            <a
                              key={i}
                              href={validLink(u)}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              打开原始链接 ↗
                            </a>
                          ),
                      )}
                    {selected.citation.claim.citation_quotes?.[s.source_id] && (
                      <blockquote>
                        {Array.isArray(
                          selected.citation.claim.citation_quotes[s.source_id],
                        )
                          ? (
                              selected.citation.claim.citation_quotes[
                                s.source_id
                              ] as string[]
                            ).join("\n\n")
                          : selected.citation.claim.citation_quotes[
                              s.source_id
                            ]}
                      </blockquote>
                    )}
                    <button
                      onClick={() => readSource(s.source_id)}
                    >
                      <Search size={13} /> {s.result_state === "query_gap_receipt" ? "查看查询条件与回执" : "查看捕获片段与上下文"}
                    </button>
                  </div>
                ))}
                {sourceLoading && <p role="status">正在读取来源…</p>}
                {sourceError && <p role="alert">来源读取失败：{sourceError}。可再次点击来源读取；报告仍保留。</p>}
                {source && !sourceLoading && (
                  <div className="rs-source-window" ref={sourceWindow}>
                    {!!sourceHistory.length && <button onClick={() => { sourceRequest.current += 1; setSourceError(""); setSource(sourceHistory[sourceHistory.length - 1]); setSourceHistory(v => v.slice(0, -1)); }}>← 返回上一级来源 / 计算</button>}
                    <h4>{source.title || (source.result_state === "query_gap_receipt" ? "本地查询回执，非事实证据" : "本地保存的来源窗口")}</h4>
                    {calculation && <div className="rs-calculation" aria-label="计算与操作数">
                      <h4>计算过程</h4><p><code>{calculation.expression}</code> = {calculation.value_decimal || source.value_decimal} {calculation.result_unit || source.unit}</p>
                      <p>{calculation.rationale}</p>
                      {Object.entries(calculation.operands).map(([name, operand]) => <div className="rs-operand" key={name}>
                        <strong>{name} · {operand.metric_id || "输入"}</strong><p>{operand.value_decimal ?? "未提供数值"} {operand.unit}</p>
                        <small>{[operand.ticker || operand.source_provenance?.ticker, operand.period_start, operand.period_end || operand.source_provenance?.fiscal_period, operand.unit || operand.source_provenance?.unit || "单位未单列"].filter(Boolean).join(" · ")} · {operand.authority || "权威状态未提供"}</small>
                        {operand.quote && <blockquote>{operand.quote}</blockquote>}
                        {operand.source_id && <button onClick={() => readSource(calculation.operand_source_aliases?.[operand.source_id!] || operand.source_id!, 0, true)}>查看操作数 {name} 来源</button>}
                      </div>)}
                      <p>算术核验：{calculation.arithmetic_verified === true ? "通过" : calculation.arithmetic_verified === false ? "未通过或未核验" : "未提供"}；金融语义：{calculation.financial_semantics_verified === true ? "已核验" : "未确认"}。</p>
                    </div>}
                    {calculation ? <details><summary>原始计算记录</summary><pre>{source.text}</pre></details> : <pre>
                      {source.text || (source.value_decimal !== undefined ? `${source.value_decimal} ${source.unit}` : "此来源没有可显示的捕获片段。")}
                    </pre>}
                    <details><summary>来源标识</summary><code>{source.source_id}</code></details>
                    {source.next_offset != null && (
                      <button
                        onClick={() => readSource(source.source_id, source.next_offset, true)}
                      >
                        下一段原文 →
                      </button>
                    )}
                    <p>
                      {source.notice || source.authority_note || (source.source_id.startsWith("CALC::") || source.result_state === "non_authoritative_metric"
                        ? "这是由绑定输入计算的结果，不是发行人直接披露值。公式正确仍不等于财务解释正确。"
                        : source.numeric_fact_authority
                          ? "数值来自结构化事实库，仍需核对期间与指标含义。"
                          : "这是来源原文片段，不是 S2 结构化财务事实。请结合来源性质、日期及上下文理解。")}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="rs-source-empty">
                <BookOpen size={25} />
                <h3>从结论回到来源</h3>
                <p>
                  点击报告或回答中的编号，查看对应主张、原文引句和捕获上下文。
                </p>
              </div>
            ))}
        </div>
        <footer className="rs-inspector-footer">
          <ShieldCheck size={14} /> 展示公开依据，不展示私有思维链
        </footer>
      </aside>
    </div>
  );
}
