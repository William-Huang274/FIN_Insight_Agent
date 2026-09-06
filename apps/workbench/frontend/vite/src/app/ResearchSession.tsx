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
} from "../api/reportSessions";
import "./research-session.css";

const format = (n: number) => new Intl.NumberFormat("zh-CN").format(n);
const stageName: Record<string, string> = {
  writer: "研究作者",
  verifier: "独立复核",
  quick_writer: "快速问答 · Flash",
};
const phaseName: Record<string, string> = {
  needs_revision: "有问题待修订",
  ready_for_human_review: "等待人工审阅",
  human_reviewed_not_released: "已人工审阅 · 未发布",
  working: "正在研究",
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
    /\[((?:P\d{2}:|NUMFACT::|CALC::)[^\[\]\s]+)\]/g,
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
  const [sessions, setSessions] = useState<Session[]>([]);
  const [id, setId] = useState(
    new URLSearchParams(window.location.search).get("thread") || "",
  );
  const [session, setSession] = useState<Session | null>(null);
  const [text, setText] = useState("");
  const [action, setAction] = useState<"ask" | "revise">("ask");
  const [answerMode, setAnswerMode] = useState<"quick" | "deep">("quick");
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
  }, [refresh]);
  const choose = (next: string) => {
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
            const e = part.data as Event;
            setEvents((old) =>
              old.some(
                (x) =>
                  x.kind === e.kind &&
                  x.call_id === e.call_id &&
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
    for (const e of [...(session?.model_events || []), ...events])
      map.set(`${e.kind}/${e.actor}/${e.call_id}/${e.event}/${e.recorded_at}`, e);
    return [...map.values()].sort(
      (a, b) => (Date.parse(a.recorded_at || "") || 0) - (Date.parse(b.recorded_at || "") || 0),
    );
  }, [session?.model_events, events]);
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
  const newSession = async () => {
    setSending(true);
    setError("");
    try {
      const made = await sessionsApi.create();
      choose(made.thread_id);
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
        <button className="rs-new" onClick={newSession} disabled={sending}>
          <Plus size={16} /> 新建 Dell 审阅会话
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
        {!session ? (
          <section className="rs-empty">
            <span className="rs-eyebrow">从一份研究，到一个可追问的判断</span>
            <h1>让结论经得起追问。</h1>
            <p>
              打开已有的 Dell
              全案研究，在真实来源与独立审查之间来回验证。修订有记录，问题不隐藏，模型按需要调用工具。
            </p>
            <div className="rs-empty-cards">
              <div>
                <BookOpen />
                <h3>读已有研究</h3>
                <p>载入已保存的报告和证据，不重新跑全案。</p>
              </div>
              <div>
                <MessageSquare />
                <h3>问具体问题</h3>
                <p>检查口径、解释推断，或提出定向修改。</p>
              </div>
              <div>
                <ShieldCheck />
                <h3>看独立复核</h3>
                <p>来源绑定不代表结论正确，保留反例与人工判断。</p>
              </div>
            </div>
            <button
              className="rs-primary"
              disabled={sending || !!id}
              onClick={newSession}
            >
              {sending || id ? (
                <LoaderCircle className="rs-spin" size={16} />
              ) : (
                <Plus size={16} />
              )}{" "}
              {id ? "载入会话中" : "开始审阅 Dell 案例"}
            </button>
            <small>
              打开已有报告不调用模型。当前为报告审阅试点，不是任意公司研究入口。
            </small>
          </section>
        ) : (
          <>
            <section className="rs-heading">
              <div>
                <span className="rs-eyebrow">DELL / AI INFRASTRUCTURE</span>
                <h1>需求如何变成利润与现金？</h1>
                <p>
                  全案研究审阅 <span>·</span> 信息截止 2026-09-02 <span>·</span>{" "}
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
                  : session.status === "error"
                    ? "本次执行失败 · 状态已保留"
                    : phaseName[session.phase || ""] || "正在载入"}
              </span>
            </section>
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
                      这份报告保留真实待修订状态。引用证明来源可追溯，不替代对财务含义的判断。
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
              <div className="rs-usage">
                <div>
                  <small>本会话模型调用</small>
                  <strong>{models.length}</strong>
                </div>
                <div>
                  <small>已报告 tokens</small>
                  <strong>{format(totals.tokens)}</strong>
                </div>
              </div>
              <p className="rs-helper">
                输入 {format(totals.input)} · 输出 {format(totals.output)}
                。不含载入前的历史研究费用；失败未知用量不算零。
              </p>
              <div className="rs-agent-cards">
                {["writer", "verifier", "quick_writer"].map((role) => (
                  <div key={role}>
                    <span className="rs-agent-avatar">
                      {role === "writer" ? "W" : role === "verifier" ? "V" : "Q"}
                    </span>
                    <span>
                      {stageName[role]}
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
                      <strong>{stageName[e.actor] || e.actor}</strong>
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
                          : e.status === "handoff"
                            ? "已交接"
                            : e.status === "success"
                              ? "已返回"
                              : e.status || e.event}
                        {e.total_tokens !== undefined &&
                          ` · ${format(e.total_tokens)} tokens`}
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
                <code>{session?.runs?.[0]?.run_id || "尚未创建"}</code>
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
                        : "披露 / 外部材料"}
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
                      {source.text ?? `${source.value_decimal} ${source.unit}`}
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
                      {source.notice ||
                        "数值来自结构化事实库，仍需核对期间与指标含义。"}
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
