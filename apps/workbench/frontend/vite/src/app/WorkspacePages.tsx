import { useEffect, useMemo, useState } from "react";
import { ArrowRight, FileClock, Files, FolderOpen, Search, ShieldCheck } from "lucide-react";
import { sessionsApi, type Session, type Source, type ReportDiff } from "../api/reportSessions";
import { ReportDiffView } from "./ReportDiffView";
import { SourceReader } from "./SourceReader";
import { pageTitles, sessionStatus, isResearchComplete } from "./WorkspaceNavigation";
import { reportTopics } from "./reportTopics";
import { claimLabel, claimTitle, sourceKind, sourceTitle } from "./researchLabels";
import { useSearchParams } from "react-router";

export function GlobalWorkspacePage({ page, sessions, navigate, query, onQuery, filter, onFilter, theme, onTheme, motion, onMotion }: {
  page: string; sessions: Session[]; navigate: (page: string, id?: string) => void; query: string; onQuery: (value: string) => void;
  filter: string; onFilter: (value: string) => void; theme: string; onTheme: (value: string) => void; motion: boolean; onMotion: (value: boolean) => void;
}) {
  const pending = sessions.filter(s => s.status === "interrupted" && !isResearchComplete(s) && s.phase !== "human_reviewed_not_released" && s.phase !== "research_needs_attention");
  const matching = (page === "inbox" ? pending : page === "completed" ? sessions.filter(isResearchComplete) : sessions).filter(s => `${s.title} ${s.question || ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()) && (!filter || s.status === filter));
  if (page === "preferences") return <section className="fs-page"><span className="fs-kicker">YOUR WORKSPACE</span><h1>外观与偏好</h1><p>偏好保存在此浏览器，不影响研究运行。</p><div className="fs-setting"><div><h3>界面外观</h3><p>研究蓝与中性色，阅读和图谱使用同一套视觉。</p></div><select aria-label="界面外观" value={theme} onChange={e => onTheme(e.target.value)}><option value="system">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></div><div className="fs-setting"><div><h3>减少动态效果</h3><p>系统减少动态效果偏好始终优先。</p></div><input type="checkbox" aria-label="减少动态效果" checked={motion} onChange={e => onMotion(e.target.checked)} /></div></section>;
  return <section className="fs-page"><div className="fs-page-title"><div><span className="fs-kicker">RESEARCH WORKSPACE</span><h1>{page === "home" ? "从上次的判断，继续研究。" : pageTitles[page]}</h1><p>{page === "inbox" ? "回到保存的审阅点，核对依据与修订结果。" : "报告、来源与研究过程，在一个工作空间中连续展开。"}</p></div><button className="fs-primary" onClick={() => navigate("new")}>新建研究 <ArrowRight size={16} /></button></div>
    {page === "home" && <div className="fs-metrics">{[{ title: "已保存研究", value: sessions.length, icon: FolderOpen, view: "all" }, { title: "等待审阅", value: pending.length, icon: ShieldCheck, view: "inbox" }, { title: "正在运行", value: sessions.filter(s => s.status === "busy").length, icon: FileClock, view: "all" }].map(m => <button key={m.title} onClick={() => { onFilter(m.title === "正在运行" ? "busy" : ""); navigate(m.view); }}><m.icon size={21} /><strong>{m.value}</strong><span>{m.title}<ArrowRight size={14} /></span></button>)}</div>}
    <div className="fs-list-heading"><h2>{page === "home" ? "最近工作" : "研究任务"}</h2><span>{matching.length} 项研究</span></div>
    <div className="fs-search"><Search size={18} /><input aria-label="搜索研究" value={query} placeholder="搜索题目或研究问题…" onChange={e => onQuery(e.target.value)} /><select aria-label="研究状态" value={filter} onChange={e => onFilter(e.target.value)}><option value="">全部状态</option><option value="busy">运行中</option><option value="interrupted">等待审阅</option><option value="error">执行失败</option><option value="idle">已保存</option></select></div>
    <div className="fs-research-list">{matching.map(s => <button key={s.thread_id} onClick={() => navigate(page === "inbox" ? "review" : "graph", s.thread_id)}><span className="fs-file-icon"><Files size={23} /></span><span className="fs-task-summary"><strong>{s.title || "未命名研究"}</strong><small>{s.updated_at ? new Date(s.updated_at).toLocaleString("zh-CN") : "更新时间未记录"} · {s.thread_id.slice(-6)}</small></span><span className="fs-status">{sessionStatus(s)}</span><ArrowRight size={18} /></button>)}{!matching.length && <div className="fs-empty"><Search size={28} /><h3>{sessions.length ? "没有符合条件的研究" : "第一份研究，从一个问题开始"}</h3><p>{sessions.length ? "试试其他关键词或清除状态过滤。" : "可以先准备问题和资料，再明确开始研究。"}</p></div>}</div>
  </section>;
}

export function SessionLibrary({ session, checkpoint, report, view }: { session: Session; checkpoint?: string; report: NonNullable<Session["report"]>; view: "sources" | "revisions" }) {
  const [query, setQuery] = useState(""); const [reader, setReader] = useState<Source | null>(null); const [pinned, setPinned] = useState(checkpoint || ""); const [error, setError] = useState(""); const [loading, setLoading] = useState(""); const [diff, setDiff] = useState<{id: string; value: ReportDiff} | null>(null);
  const topics = useMemo(() => reportTopics(report), [report]);
  const [params, setParams] = useSearchParams();
  const chosenTopic = params.get("topic") || "";
  const visibleTopics = topics.filter(t => !chosenTopic || t.id === chosenTopic);
  const matches = (id: string, s: Source) => `${claimTitle(id, report.citations)} ${sourceTitle(s)} ${s.period_end || ""} ${s.source_id}`.toLowerCase().includes(query.toLowerCase());
  useEffect(() => { let live = true; if (!checkpoint) sessionsApi.versions(session.thread_id).then(result => { if (live) { const v = result.versions.find(v => v.version === session.report_version); if (!v) throw new Error("无法定位此报告的来源版本"); setPinned(v.checkpoint_id); } }).catch(e => live && setError(e.message)); return () => { live = false; }; }, [checkpoint, session.thread_id, session.report_version]);
  const open = async (s: Source) => { setLoading(s.source_id); setError(""); try { setReader(await sessionsApi.source(session.thread_id, s.source_id, 0, pinned)); } catch (e) { setError((e as Error).message); } finally { setLoading(""); } };
  const revisions = (session.runs || []).filter(r => r.human_action === "revise" || r.revision_target);
  return <section className="fs-page"><span className="fs-kicker">{view === "sources" ? "EVIDENCE LIBRARY" : "REVISION HISTORY"}</span><h1>{pageTitles[view]}</h1><p>{view === "sources" ? "此报告实际引用的来源与计算。原文按需读取，固定在当前所阅报告版本。" : "每次修订保留基线和运行结果，运行完成后仍需人工审阅。未提交草稿保留在对应判断中。"}</p>
    {error && <p role="alert">{error}</p>}
    {view === "sources" ? <>
      <div className="fs-search"><Search size={18}/><input aria-label="搜索来源" placeholder="搜索专题、研究判断、来源或期间…" value={query} onChange={e => setQuery(e.target.value)}/></div>
      <nav className="fs-library-topics" aria-label="按研究地图专题筛选"><button aria-pressed={!chosenTopic} onClick={() => setParams(p => { p.delete("topic"); return p; })}>全部专题</button>{topics.map(t => <button key={t.id} aria-pressed={chosenTopic === t.id} onClick={() => setParams(p => { p.set("topic", t.id); return p; })}>{t.title}</button>)}</nav>
      <div className="fs-evidence-paths">{visibleTopics.map(t => {
        const claims = t.claimIds.filter(id => report.citations[id].sources.some(s => matches(id, s)));
        return claims.length > 0 && <section key={t.id} className="fs-evidence-topic"><header><h2>{t.title}</h2><button onClick={() => setParams(p => { p.set("view", "graph"); p.set("topic", t.id); p.set("level", "topic"); return p; })}>在研究地图中打开 <ArrowRight size={15}/></button></header>
          {claims.map(id => <details key={id} className="fs-evidence-claim" open={!!query || undefined}><summary><span>{claimLabel(id, report.citations)}</span><small>{report.citations[id].sources.length} 条依据</small></summary><div className="fs-evidence-context"><span>引用编号 {id} · 来自当前报告绑定</span><button onClick={() => setParams(p => { p.set("view", "graph"); p.set("topic", t.id); p.set("level", "claim"); p.set("claim", id); return p; })}>判断与依据 →</button></div><div className="fs-source-grid">{report.citations[id].sources.filter(s => matches(id, s)).map(s => <button key={s.source_id} onClick={() => void open(s)} disabled={!pinned || !!loading}><Files size={20}/><small>{sourceKind(s)} · {s.period_end || "期间见原文"}</small><h3>{sourceTitle(s)}</h3><span>{loading === s.source_id ? "正在读取…" : "扩展上下文 / 阅读原文"}<ArrowRight size={15}/></span></button>)}</div></details>)}
        </section>;
      })}{!visibleTopics.some(t => t.claimIds.some(id => report.citations[id].sources.some(s => matches(id, s)))) && <p>没有符合条件的资料；可以清除搜索或切回全部专题。</p>}</div>
    </> : <div className="fs-revision-list">{!revisions.length && <div className="fs-empty"><FileClock size={28}/><h3>尚无已提交的修订</h3><p>在研究地图中选择判断，核对来源后提交具体意见。</p></div>}{revisions.map(r => <article key={r.run_id}><small>{r.created_at ? new Date(r.created_at).toLocaleString("zh-CN") : "时间未记录"}</small><h3>{r.revision_target ? claimLabel(r.revision_target.citation_id, report.citations) : "报告修订"}</h3>{r.revision_target && <small>引用编号 {r.revision_target.citation_id} · 基线 v{r.revision_target.base_version} · 名称按当前所阅版本显示</small>}<p>{({ success: "运行完成，待审阅", running: "正在执行", pending: "等待执行", interrupted: "已到达等待点 / 已停止", error: "执行失败，历史保留" } as Record<string,string>)[r.status] || r.status}</p><details><summary>运行标识</summary><code>{r.run_id}</code></details>{r.revision_target && <button onClick={async () => { if (diff?.id === r.run_id) { setDiff(null); return; } try { const d = await sessionsApi.diff(session.thread_id, r.revision_target!.base_checkpoint); setDiff({id:r.run_id, value:d}); } catch (e) { setError((e as Error).message); } }}>{diff?.id === r.run_id ? "收起报告变化" : "比较基线与当前报告"}</button>}{diff?.id === r.run_id && <ReportDiffView value={diff.value}/>}</article>)}</div>}
    {reader && <SourceReader id={session.thread_id} checkpoint={pinned} source={reader} context={Object.values(report.citations).filter(c => c.sources.some(s => s.source_id === reader.source_id)).map(c => c.claim.statement).join("\n\n")} onClose={() => setReader(null)} />}
  </section>;
}
