import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, CheckCircle2, ChevronDown, FileText, LoaderCircle, Radio, Square, Terminal, TriangleAlert } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { sessionsApi, type Event, type Session } from "../api/reportSessions";
import { branchName, claimLabel } from "./researchLabels";
import { executionModeName } from "./ExecutionPicker";
import { useSearchParams } from "react-router";
import { ContextUsage } from "./ContextUsage";

const statusName = (s: string) => ({running:"执行中", pending:"等待执行", success:"运行完成", interrupted:"已停止 / 到达等待点", error:"执行失败", submitted:"底稿已提交", handoff:"已交接结果"} as Record<string,string>)[s] || s;
const needsAttention = (phase?: string) => phase === "research_needs_attention";
const actionName = (s?: string) => ({ask:"追问", revise:"修订", research:"新研究", continue_remaining:"继续研究", abandon_failed_question:"结束失败追问", return_stopped_question:"返回审阅"} as Record<string,string>)[s || ""] || "任务操作";
const nodeName = (s: string) => branchName[s.replace(/^specialist:/, "").split("_")[0]] || ({research:"研究流程",writer:"报告写作与修订", quick_writer:"追问研究者", specialist:"研究者", lead:"研究负责人", research_configuration:"研究配置", verifier:"底稿核验", report_verifier:"报告复核", counter:"反证审查", synthesis:"综合研究", research_verifier:"判断复核", human_guidance:"用户补充意见", responsibility_router:"责任分派"} as Record<string,string>)[s] || `研究节点 ${s}`;
const toolName = (s: string) => ({read_current_source:"读取引用来源", read_current_report:"阅读当前报告", read_current_workpaper:"阅读研究底稿", research_artifact_catalog:"查看资料目录", read_source_document:"检索和阅读文献", query_company_financial_facts:"查询财务数据", calculate_research_metric:"核算研究指标", report_research_progress:"更新研究进展", submit_answer:"提交回答", submit_case_report:"提交报告", submit_report_edits:"提交报告修改"} as Record<string,string>)[s] || `调用工具 ${s}`;

/** Native events rendered as a conversation; public commentary is distinct from private reasoning. */
export function RunWorkspace({ session, events, connected, refresh, onReport }: { session: Session; events: Event[]; connected: boolean; refresh:()=>Promise<void>; onReport:()=>void }) {
  const [, setParams] = useSearchParams();
  const [chosenRun, setChosenRun] = useState(""); const [actor, setActor] = useState("");
  const [query, setQuery] = useState(""); const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false); const [notice, setNotice] = useState("");
  const [follow, setFollow] = useState(true); const [newEvents, setNewEvents] = useState(false);
  const history = useRef<HTMLDetailsElement>(null); const feed = useRef<HTMLDivElement>(null);
  const run = session.runs?.find(r => r.run_id === chosenRun) || session.runs?.[0];
  const live = run?.status === "running" || run?.status === "pending";
  const recorded = useMemo(() => events.filter(e => !run || e.run_id === run.run_id).sort((a,b) => (a.recorded_at || "").localeCompare(b.recorded_at || "")), [events, run?.run_id]);
  const actors = [...new Set(recorded.map(e => e.actor))];
  const visible = actor ? recorded.filter(e => e.actor === actor) : recorded;
  const groups = useMemo(() => {
    const rows: { kind: "message" | "calls"; actor: string; events: Event[] }[] = [];
    for (const event of visible) {
      const kind = event.kind === "tool" || event.kind === "model" ? "calls" : "message";
      const previous = rows.at(-1);
      if (kind === "calls" && previous?.kind === kind && previous.actor === event.actor) previous.events.push(event);
      else rows.push({ kind, actor: event.actor, events: [event] });
    }
    return rows;
  }, [visible]);
  useEffect(() => { setActor(""); setFollow(true); setNewEvents(false); }, [run?.run_id]);
  useEffect(() => { if (follow && feed.current) { feed.current.scrollTop = feed.current.scrollHeight; setNewEvents(false); } else setNewEvents(true); }, [recorded.length, follow]);
  const describe = (e: Event) => e.objective || (e.kind === "task" ? `${e.event === "started" ? "开始研究" : "研究状态更新"}：${e.task_id || nodeName(e.actor)}` : e.event === "started" ? "开始处理本阶段。" : e.event === "outcome" ? `本阶段已返回结果${e.status ? `：${statusName(e.status)}` : ""}。` : e.event === "applied" ? "已读取本次运行配置。" : `阶段记录：${e.event}`);
  return <section className="fs-run-workspace fs-run-conversation">
    <div className="fs-run-heading"><div><span className="fs-kicker"><Radio size={15}/> RESEARCH IN MOTION</span><h2>研究现场</h2><p>{run ? statusName(run.status) : "尚无运行"} · {live ? connected ? "活动实时更新" : "正在连接活动流" : "历史运行记录"}</p></div><button onClick={refresh}>刷新状态</button>{session.report && <button onClick={onReport}><FileText size={15}/>阅读当前报告</button>}</div>
    <details ref={history} className="fs-run-history"><summary>{actionName(run?.human_action)} · {run?.created_at ? new Date(run.created_at).toLocaleString("zh-CN") : "选择运行"}<ChevronDown size={15}/></summary><div><input aria-label="搜索运行记录" value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索追问、修订或日期…"/>{session.runs?.filter(r => `${actionName(r.human_action)} ${r.created_at} ${r.run_id}`.includes(query)).map(r => <button key={r.run_id} aria-pressed={run?.run_id === r.run_id} onClick={() => { setChosenRun(r.run_id); if (history.current) history.current.open = false; }}>{actionName(r.human_action)} · {new Date(r.created_at).toLocaleString("zh-CN")} · {statusName(r.status)}</button>)}</div></details>
    {run?.human_action === "ask" && <button onClick={() => setParams(p => { p.set("view", "conversation"); return p; })}>查看追问与回答</button>}
    {run?.execution && <p className="fs-run-config">{executionModeName[run.execution.mode]} · {run.execution.model === "default" ? "模型按角色配置" : run.execution.model} · 本次运行已固定</p>}
    {run?.revision_target && <p className="fs-run-target">{claimLabel(run.revision_target.citation_id, session.report?.citations || {})} · 基线 v{run.revision_target.base_version}</p>}
    <ContextUsage usage={run?.context_usage} nodeName={nodeName}/>
    <div className="fs-live-layout"><div className="fs-live-main"><div className="fs-live-feed" ref={feed} role="log" aria-label="Agent 活动流" aria-live="polite" onScroll={() => { const el = feed.current!; setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 70); }}>
      <div className="fs-live-request"><small>{actionName(run?.human_action)}</small><p>{run?.request_message || (run?.human_action === "research" ? session.question : run?.revision_target ? claimLabel(run.revision_target.citation_id, session.report?.citations || {}) : "本次请求的执行活动")}</p></div>
      {groups.map((g,i) => <article className={`fs-live-entry ${g.kind}`} key={`${g.events[0].recorded_at}:${i}`}><header><span className="fs-live-avatar">{g.kind === "calls" ? <Terminal size={17}/> : <Radio size={17}/>}</span><strong>{nodeName(g.actor)}</strong><time>{g.events[0].recorded_at ? new Date(g.events[0].recorded_at).toLocaleTimeString("zh-CN") : ""}</time></header>
        {g.kind === "message" ? <div className="fs-live-prose">{g.events[0].event === "output" && <strong className="fs-live-output-label">{g.events[0].status === "recovered_candidate" ? "从历史提交记录恢复的候选输出" : "模型输出 · 候选内容"}</strong>}<ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{a:({children})=><span>{children}</span>,img:()=>null}}>{describe(g.events[0])}</ReactMarkdown>{g.events[0].status === "planned" && <small>计划中的动作，执行结果见后续工具记录</small>}{g.events[0].event === "output" && <small>保留模型原文；提交校验与独立复核结果以对应阶段为准。</small>}</div> : <details className="fs-live-calls"><summary>模型与工具活动 · {g.events.length} 条记录</summary>{g.events.map((e,j) => <div key={j}>{e.status === "error" || e.status === "provider_failed" ? <TriangleAlert size={15}/> : e.event === "outcome" ? <CheckCircle2 size={15}/> : <Terminal size={15}/>}<span>{e.kind === "model" ? `模型 ${e.model || "已配置模型"}` : toolName(e.tool || "")} · {e.event === "outcome" ? e.status === "success" ? "已返回" : statusName(e.status || "结果已记录") : "已发起"}{e.total_tokens != null ? ` · ${e.total_tokens.toLocaleString()} tokens` : ""}</span></div>)}</details>}
      </article>)}
      {!groups.length && <p>{live ? "等待 Agent 发出首条活动…" : "本次运行未保存公开活动；不能从耗时重建过程。"}</p>}
      {run?.status === "error" && <section className="fs-live-failure" aria-label="失败说明"><strong>运行未完成 · 已产生的输出保留在上方</strong><p>{recorded.filter(e => e.error_type).at(-1)?.error_type ? `系统记录：${recorded.filter(e => e.error_type).at(-1)?.error_type}。` : "本次历史记录没有保存可展示的详细系统错误。"} {run.run_id === session.runs?.[0]?.run_id && session.research_stop_reason}</p><p>模型候选输出不代表提交已通过校验。已执行活动和候选结果可继续查看；未收到模型的失败说明时，不推测模型理由。</p></section>}
      {live && <div className="fs-live-working"><LoaderCircle className="rs-spin" size={17}/><span>Agent 正在工作，新的进展会追加在这里。</span></div>}
      {!live && !!groups.length && <p className="fs-live-end">本次运行{run?.status === "success" ? needsAttention(session.phase) && run.run_id === session.runs?.[0]?.run_id ? "已停止在需要处理的研究问题，尚未形成可审阅报告" : "已结束，结果仍需审阅" : statusName(run?.status || "")}。{!recorded.some(e => e.event === "progress") && "这条历史记录未保存文字进展，仅列示实际阶段和调用。"}</p>}
    </div>{newEvents && <button className="fs-jump-latest" onClick={() => setFollow(true)}><ArrowDown size={15}/>查看最新活动</button>}
    <div className="fs-live-composer"><label htmlFor="run-guidance">参与这次研究</label><textarea id="run-guidance" value={message} onChange={e => setMessage(e.target.value)} placeholder="补充需要核实的范围、来源或假设…" disabled={!live || !session.question || sending}/><footer><span>意见在后续阶段读取</span><button disabled={!live || !session.question || !message.trim() || sending} onClick={async () => { setSending(true); try { await sessionsApi.guidance(session.thread_id, message); setMessage(""); setNotice("意见已保存，等待后续阶段读取。"); await refresh(); } catch(e) { setNotice((e as Error).message); } finally { setSending(false); } }}>发送补充</button><button disabled={!live || sending} onClick={async () => { if (!run) return; setSending(true); try { await sessionsApi.cancel(session.thread_id, run.run_id); setNotice("已请求停止，已产生结果保留。"); await refresh(); } catch(e) { setNotice((e as Error).message); } finally { setSending(false); } }}><Square size={12}/>停止</button></footer>{notice && <p role="status">{notice}</p>}</div></div>
    <aside className="fs-live-context"><h3>研究中的节点</h3><button aria-pressed={!actor} onClick={() => setActor("")}>全部活动</button>{actors.map(a => <button key={a} aria-pressed={actor === a} onClick={() => setActor(a)}>{nodeName(a)}</button>)}<details><summary>本次任务分工</summary>{recorded.filter(e => e.kind === "task" && e.event === "started").map(e => <p key={e.task_id}>{e.objective}</p>)}</details><div className="fs-live-cost"><h3>本次用量</h3><strong>{run?.cost_estimate ? `¥${run.cost_estimate.known_cny.toFixed(4)}` : "未记录"}</strong><p>{run?.usage?.total_tokens?.toLocaleString() ?? "未记录"} tokens</p><small>未知或待计价请求：{run?.cost_estimate?.unknown_or_pending_requests ?? "未记录"}</small></div><small>展示公开进展、工具与结果；原始私有推理不进入页面。</small></aside></div>
  </section>;
}
