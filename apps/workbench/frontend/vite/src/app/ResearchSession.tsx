import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
};
const actorName = (actor: string) => stageName[actor] || (actor.startsWith("author_") ? `${actor.slice(7)} · 责任作者修订` : actor);
const responsibilityName: Record<string, string> = { writer: "报告表达", research: "上游研究", data_tool: "数据 / 工具", human: "人工处理" };
const phaseName: Record<string, string> = {
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

function Markdown({
  text,
  citations = {},
  onCitation,
}: {
  text: string;
  citations?: Record<string, Citation>;
  onCitation: (key: string, citation: Citation) => void;
}) {
  const keys = Object.keys(citations);
  const linked = text.replace(
    /\[((?:P\d{2}:|PASSAGE::|NUMFACT::|CALC::)[^\[\]\s]+)\]/g,
    (original, ref: string) =>
      citations[ref]
        ? `[${keys.indexOf(ref) + 1}](#claim:${encodeURIComponent(ref)})`
        : original,
  );
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        a: ({ href, children }) => {
          if (href?.startsWith("#claim:")) {
            const key = decodeURIComponent(href.slice(7));
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
      {linked}
    </ReactMarkdown>
  );
}

export function ResearchSession() {
  const [configuration, setConfiguration] = useState<ResearchConfiguration | null>(null);
  const [configurationError, setConfigurationError] = useState("");
  const [creating, setCreating] = useState(false);
  const [researchQuestion, setResearchQuestion] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [id, setId] = useState(
    new URLSearchParams(window.location.search).get("thread") || "",
  );
  const [session, setSession] = useState<Session | null>(null);
  const [text, setText] = useState("");
  const [action, setAction] = useState<"ask" | "revise">("ask");
  const [answerMode, setAnswerMode] = useState<"quick" | "deep">("quick");
  const [usageRunId, setUsageRunId] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"report" | "conversation">("report");
  const [inspector, setInspector] = useState<"review" | "activity" | "source">(
    "review",
  );
  const [selected, setSelected] = useState<{
    key: string;
    citation: Citation;
  } | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const sourceWindow = useRef<HTMLDivElement>(null);
  const conversationEnd = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (tab === "conversation") conversationEnd.current?.scrollIntoView({ block: "end" });
  }, [id, tab, session?.conversation?.length]);
  useEffect(() => {
    sourceWindow.current?.scrollIntoView({ block: "nearest" });
  }, [source]);
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
    const update = async () => {
      try {
        const value = await sessionsApi.state(id);
        if (!disposed) setSession(value);
      } catch (e) {
        if (!disposed) setError((e as Error).message);
      }
    };
    update();
    const timer = window.setInterval(update, 2500);
    return () => {
      disposed = true;
      clearInterval(timer);
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
      map.set(`${e.kind}/${e.actor}/${e.call_id}/${e.task_id}/${e.event}/${e.recorded_at}`, e);
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
    return [...map.values()];
  }, [session?.research_tasks, allEvents]);
  const models = useMemo(() => {
    const map = new Map<string, Event>();
    for (const e of allEvents)
      if (e.kind === "model" && e.event === "outcome" && e.call_id)
        map.set(e.call_id, e);
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
  const newSession = async (mode: "review" | "research" = "review") => {
    setSending(true);
    setError("");
    try {
      const made = await sessionsApi.create(mode === "research" ? {
        mode, title: configuration?.title || "Dell · 新研究任务", question: researchQuestion,
      } : { mode });
      choose(made.thread_id);
      if (mode === "research") setInspector("activity");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      await refresh().catch(() => {});
    } finally {
      setSending(false);
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
  const cite = (key: string, citation: Citation) => {
    setSelected({ key, citation });
    setSource(null);
    setInspector("source");
  };
  const findings = session?.report_review?.findings || [];
  return (
    <div className="rs-shell">
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
        <button className="rs-legacy-link" onClick={() => newSession("review")} disabled={sending}>
          <BookOpen size={14} /> 打开已有 Dell 报告审阅
        </button>
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
                      : "已保存"}
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
            研究 / <b>Dell Technologies</b>
          </div>
          <span className="rs-local">
            <span /> LOCAL PILOT
          </span>
        </header>
        {!session || creating ? (
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
            <small>
              {configurationError || (configuration?.fresh_research_enabled
                ? "开始研究会产生真实模型调用；研究过程中可查看任务和费用、停止执行。打开旧报告则不重新研究。"
                : "新研究尚未在当前服务启用，不会拿旧稿冒充新结果。已有报告审阅仍可使用。")}
            </small>
          </section>
        ) : (
          <>
            <section className="rs-heading">
              <div>
                <span className="rs-eyebrow">DELL / AI INFRASTRUCTURE</span>
                <h1>{session.question ? "增长，是否正在兑现？" : "需求如何变成利润与现金？"}</h1>
                <p>
                  {session.question ? "新问题 · 完整研究" : "已有报告审阅"} <span>·</span> 信息截止 {session.research_as_of?.slice(0, 10) || "2026-09-02"} <span>·</span>{" "}
                  报告版本 {session.report_version || "—"}
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
                {busy
                  ? "Agent 正在执行"
                  : session.runs?.[0]?.status === "interrupted"
                    ? "已停止 · 原有结果和记录保留"
                    : session.status === "error"
                    ? "本次执行失败 · 状态已保留"
                    : phaseName[session.phase || ""] || "正在载入"}
              </span>
            </section>
            {session.question && <div className="rs-task-question">{session.question}</div>}
            {session.research_stop_reason && <div className="rs-report-notice">
              <ShieldCheck size={17} /><span>本次仍有未解决问题，已保留成果，不会自动整案重跑。
                {session.research_stop_reason === "material_findings_remain_after_targeted_correction" ? "一轮定向修订后，重大问题仍未关闭。" :
                 session.research_stop_reason === "unresolved_data_or_author_response" ? "数据、工具或责任作者仍有未解决项，请查看审查意见。" : session.research_stop_reason}
              </span></div>}
            {(researchTasks.length > 0 || (session.question && !session.report)) && (
              <details className="rs-task-board" open={!session.report}>
                <summary><Layers size={16} /> 本次研究分工 <span>{researchTasks.length} 个真实任务</span></summary>
                {!researchTasks.length && <p>研究负责人正在读取问题并规划任务。这里不会预先填充虚构的 Agent 活动。</p>}
                <div className="rs-task-grid">{researchTasks.map((task) => (
                  <div className="rs-task-card" key={task.task_id}>
                    <div><strong>{task.owner_role || "研究专家"}</strong><span>{
                      ["submitted", "specialist_submission_accepted"].includes(task.status) ? "已提交底稿" :
                      task.status === "running" ? "研究中" : task.status === "error" ? "执行失败" : task.status === "needs_attention" ? "待处理" : "等待执行"
                    }</span></div>
                    <p>{task.objective}</p>
                    <small>{task.dependency_ids.length ? `依赖：${task.dependency_ids.join("、")}` : "可独立执行"}</small>
                  </div>
                ))}</div>
              </details>
            )}
            <div className="rs-tabs">
              <div>
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
                {Object.keys(session.report?.citations || {}).length}{" "}
                条引用可展开
              </span>
            </div>
            <div className="rs-document" key={tab}>
              {tab === "report" ? (
                <>
                  <div className="rs-report-notice">
                    <ShieldCheck size={17} />
                    <span>
                      {session.report ? "引用可以展开查看依据；报告的实质判断仍需结合来源上下文审阅。" : "研究进行中：底稿、审查与报告会按实际完成情况出现。"}
                    </span>
                  </div>
                  <article className="rs-prose">
                    <h2 className="rs-report-title">{session.report?.title}</h2>
                    <Markdown
                      text={
                        session.report?.narrative_markdown || (session.status === "error" ? "本次尚未取得报告。请查看运行状态；失败记录与已有研究材料均保留。" : "报告正在载入…")
                      }
                      citations={session.report?.citations}
                      onCitation={cite}
                    />
                  </article>
                </>
              ) : (
                <div className="rs-conversation">
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
              )}
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
              <div className="rs-compose-bottom">
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
      <aside className="rs-inspector">
        <header>
          <span>
            <Radio size={16} /> 研究现场
          </span>
          <span className={connected ? "rs-live" : "rs-muted"}>
            {connected ? "实时连接" : "已保存状态"}
          </span>
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
              {busy && <p>运行中：下方是上一轮已保存的审查，本轮复核尚未完成。</p>}
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
                    ? "当前没有已提交的审查问题；仍需人工判断。"
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
                <label htmlFor="usage-run">查看请求用量</label>
                <select id="usage-run" value={usageRun?.run_id || ""} onChange={e => setUsageRunId(e.target.value)}>
                  {session?.runs?.map(r => <option key={r.run_id} value={r.run_id}>
                    {new Date(r.created_at).toLocaleTimeString("zh-CN")} · {r.human_action === "ask" ? (r.answer_mode === "quick" ? "Flash 问答" : "Pro 追问") : r.human_action === "revise" ? "报告修订" : r.human_action === "abandon_failed_question" ? "放弃失败追问" : r.human_action === "return_stopped_question" ? "停止后返回审阅" : "载入 / 审阅"} · {r.status === "interrupted" ? "已停止" : r.status}
                  </option>)}
                </select>
              </div>
              <div className="rs-usage">
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
                本会话当前载入 {models.length} 次模型记录、{format(totals.tokens)} tokens；含失败任务已知用量，不含载入前研究费用。下方为会话事件历史，不是单次问题的调用数。
              </p>
              <div className="rs-agent-cards">
                {[...new Set([...models.map(e => e.actor), ...(session?.responsibility_history || []).map(e => e.actor)])].map((role) => (
                  <div key={role}>
                    <span className="rs-agent-avatar">
                      {role.startsWith("author_") ? "A" : role.charAt(0).toUpperCase()}
                    </span>
                    <span>
                      {actorName(role)}
                      <small>
                        {models.filter((x) => x.actor === role).length}{" "}
                        次已报告调用
                      </small>
                    </span>
                  </div>
                ))}
              </div>
              <div className="rs-event-list">
                {allEvents.map((e, i) => (
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
              {!allEvents.length && (
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
                    onClick={() => {
                      setSelected(null);
                      setSource(null);
                    }}
                  >
                    <PanelRightClose size={16} />
                  </button>
                </div>
                <h3>{selected.key}</h3>
                <p>{selected.citation.claim.statement}</p>
                {selected.citation.sources.map((s) => (
                  <div className="rs-source-card" key={s.source_id}>
                    <span className="rs-source-type">
                      {s.numeric_fact_authority
                        ? "结构化数值"
                        : s.source_id.startsWith("CALC::") || s.result_state === "non_authoritative_metric"
                          ? "本地计算 · 非权威" : "披露 / 外部材料"}
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
                      onClick={() =>
                        sessionsApi
                          .source(id, s.source_id)
                          .then(setSource)
                          .catch((e) => setError(e.message))
                      }
                    >
                      <Search size={13} /> 查看捕获片段与上下文
                    </button>
                  </div>
                ))}
                {source && (
                  <div className="rs-source-window" ref={sourceWindow}>
                    <h4>{source.source_id} · 本地保存的来源窗口</h4>
                    <pre>
                      {source.text || (source.value_decimal !== undefined ? `${source.value_decimal} ${source.unit}` : "此来源没有可显示的捕获片段。")}
                    </pre>
                    {source.next_offset != null && (
                      <button
                        onClick={() =>
                          sessionsApi
                            .source(id, source.source_id, source.next_offset)
                            .then(setSource)
                            .catch((e) => setError(e.message))
                        }
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
