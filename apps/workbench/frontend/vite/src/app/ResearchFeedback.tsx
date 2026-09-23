import { useEffect, useRef, useState } from "react";
import "./research-feedback.css";
import { PublicActivity } from "./PublicActivity";

type Choice = "keep_pending" | "avoid_inference" | "request_check";
type Issue = { record_id: string; content_digest: string; kind: string; summary: string; next_check: string;
  impact: string; edge_ids: string[]; user_opinion?: { choice: Choice; comment: string };
  evidence: Record<string, { original_read: boolean; preview: Record<string,string>[] }> };
type Orientation = { overview: string; coverage_and_gaps: string;
  findings?: {finding_id:string; judgment:string; unresolved:string; read_refs:string[]}[];
  runtime_provenance?: Record<string,{result:{items:{title?:string;passage?:string;document_id?:string;source_url?:string}[]}}>;
  topics: { topic_id: string; question: string; why_now: string; next_evidence: string; activation: string; depends_on: string[] }[];
  scope_map: { question: string; status: string; reason: string }[] };
type Feedback = { items: Issue[]; orientation?: Orientation | null };
const labels: Record<string,string> = { relation_scope:"关系范围待核", identity:"主体待核", direction:"方向待核", time_status:"时间与状态待核",
  insufficient_evidence:"依据不足", conflicting_evidence:"证据冲突", new_relation:"新关系线索", external_evidence:"外部取证需求" };
const choices: Record<Choice,string> = {keep_pending:"保留待核", avoid_inference:"本次研究暂不据此推断", request_check:"建议补充核查"};

async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {credentials:"same-origin", method: body ? "POST" : "GET",
    headers: {"Content-Type":"application/json", "X-Workbench-Request":"1"}, body:body ? JSON.stringify(body) : undefined});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "反馈暂时无法读取或保存");
  return result;
}

/** Nonblocking questions. User opinions are distinct from source evidence and execution approval. */
export function ResearchFeedback({threadId, runId, live}: {threadId:string; runId?:string; live:boolean}) {
  const [data,setData]=useState<Feedback>({items:[]}); const [error,setError]=useState("");
  const [selected,setSelected]=useState<Issue|null>(null); const [choice,setChoice]=useState<Choice>("keep_pending");
  const [comment,setComment]=useState(""); const [saving,setSaving]=useState(false); const [notice,setNotice]=useState("");
  const [revision,setRevision]=useState(0); const generation=useRef(0);
  const dialog=useRef<HTMLDialogElement>(null); const attempt=useRef<{key:string; id:string}|null>(null);
  const base=`/api/v1/research-sessions/${encodeURIComponent(threadId)}/research-feedback`;
  useEffect(()=>{
    const current=++generation.current; let disposed=false; let timer: ReturnType<typeof setTimeout> | undefined;
    setData({items:[]}); setSelected(null); setNotice(""); setError("");
    async function load() {
      try { const result=await request<Feedback>(base+(runId ? `?run_id=${encodeURIComponent(runId)}` : ""));
        if (!Array.isArray(result.items)) throw new Error("反馈接口未返回有效记录，请检查服务版本");
        if (!disposed) {setData(result); setError("");} }
      catch(e) {if (!disposed) setError((e as Error).message);}
      finally {if (!disposed && live && current===generation.current) timer=setTimeout(load,6000);}
    }
    void load(); return ()=>{disposed=true; clearTimeout(timer);};
  },[base,runId,live,revision]);
  useEffect(()=>{ if (selected) dialog.current?.showModal(); else dialog.current?.close(); },[selected]);
  function open(issue:Issue) { setSelected(issue); setChoice(issue.user_opinion?.choice || "keep_pending"); setComment(issue.user_opinion?.comment || ""); attempt.current=null; setNotice(""); }
  async function save() {
    if (!selected) return;
    const current=generation.current;
    const payload={content_digest:selected.content_digest,choice,comment}; const key=JSON.stringify([selected.record_id,payload]);
    if (attempt.current?.key!==key) attempt.current={key,id:crypto.randomUUID()};
    setSaving(true);
    try { await request(`${base}/${encodeURIComponent(selected.record_id)}`,{...payload,submission_id:attempt.current.id});
      if (current===generation.current) {setData(d=>({...d,items:d.items.map(i=>i.record_id===selected.record_id ? {...i,user_opinion:{choice,comment}} : i)})); setSelected(null); setNotice("意见已保存；Lead 后续调用可读取。本次操作不会自动补查或改写关系库。");} }
    catch(e) {if (current===generation.current) setNotice((e as Error).message);}
    finally {setSaving(false);}
  }
  if (!data.items.length && !data.orientation && !error) return null;
  return <section className="fs-research-feedback" aria-label="研究规划与待核线索">
    {data.orientation && <details className="fs-orientation" open><summary>Lead 议题规划与依据</summary><details><summary>回看总体认识</summary><PublicActivity text={data.orientation.overview}/></details>
      <details><summary>查看初步判断与原文依据 · 尚未独立复核</summary>{data.orientation.findings?.map(f=><article key={f.finding_id}><p>{f.judgment}</p><p><strong>尚待核实：</strong>{f.unresolved}</p><details><summary>依据 {f.read_refs.join("、")}</summary>{f.read_refs.map(ref=><div key={ref}><strong>{ref}</strong>{data.orientation?.runtime_provenance?.[ref]?.result.items.filter(i=>i.passage).map((i,n)=><div key={n}><small>{i.title || i.document_id}</small><blockquote style={{whiteSpace:"pre-wrap"}}>{i.passage}</blockquote></div>)}</div>)}</details></article>)}</details>
      <div className="fs-orientation-topics">{data.orientation.topics.map(t=><article key={t.topic_id}><small>{t.activation==="deferred" ? "后续议题" : "优先研究"}{t.depends_on.length ? ` · 依赖 ${t.depends_on.join("、")}` : ""}</small><h4>{t.question}</h4><p>{t.why_now}</p><p><strong>下一步依据：</strong>{t.next_evidence}</p></article>)}</div>
      <details><summary>范围与待发现的问题</summary>{data.orientation.scope_map.map((s,i)=><p key={i}><strong>{s.question}</strong> · {s.reason}</p>)}</details><PublicActivity text={data.orientation.coverage_and_gaps}/>
    </details>}
    {!!data.items.length && <><header><h3>待核线索与取证需求 <span>{data.items.length}</span></h3><p>不打断当前研究。可以留下意见；反馈本身尚不是核实结论。</p></header>
      <div className="fs-feedback-cards">{data.items.map(issue=><button key={issue.record_id} onClick={()=>open(issue)}><small>{labels[issue.kind] || "待核线索"} · {issue.user_opinion ? choices[issue.user_opinion.choice] : "待核查"}</small><strong>{issue.summary}</strong><span>查看依据与给出意见 →</span></button>)}</div></>}
    {error && <p role="alert">{error} <button onClick={()=>setRevision(r=>r+1)}>重新读取</button></p>}
    {notice && !selected && <p role="status">{notice}</p>}
    <dialog className="fs-feedback-dialog" ref={dialog} aria-labelledby="feedback-title" onCancel={e=>{if(saving)e.preventDefault(); else setSelected(null);}} onClose={()=>setSelected(null)}>
      {selected && <><header><h3 id="feedback-title">{labels[selected.kind] || "待核线索"}</h3><button aria-label="关闭反馈" disabled={saving} onClick={()=>setSelected(null)}>关闭</button></header>
        <div className="fs-feedback-body"><p>{selected.summary}</p><p><strong>建议核查：</strong>{selected.next_check}</p>
          <p>对当前研究的影响：{({not_used:"尚未据此推断",independent_search:"已改用独立检索",plan_changed:"影响研究安排",no_current_impact:"暂无影响"} as Record<string,string>)[selected.impact]}</p>
          {!!selected.edge_ids.length && <small>关联记录：{selected.edge_ids.join("、")}</small>}
          <details><summary>查看本次工具依据</summary>{Object.entries(selected.evidence).map(([ref,e])=><article key={ref}><strong>{ref} · {e.original_read ? "已读取原文" : "仅目录或检索线索，未据此判定原文错误"}</strong>{e.preview?.map((p,i)=><dl key={i}>{Object.entries(p).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>)}</article>)}</details>
          <fieldset disabled={saving}><legend>你的意见</legend>{(Object.keys(choices) as Choice[]).map(c=><label key={c}><input type="radio" name="feedback-choice" value={c} checked={choice===c} onChange={()=>setChoice(c)}/>{choices[c]}</label>)}<label htmlFor="feedback-comment">补充说明（可选）</label><textarea id="feedback-comment" maxLength={3000} value={comment} onChange={e=>setComment(e.target.value)}/></fieldset>
          <p className="fs-feedback-note">意见会供 Lead 后续调用参考。补查需另行安排；不会因选择意见而自动改图或启动模型。</p>{notice && <p role="alert">{notice}</p>}
        </div><footer><button disabled={saving} onClick={()=>setSelected(null)}>暂不处理</button><button disabled={saving} onClick={()=>void save()}>{saving ? "正在保存…" : "保存意见"}</button></footer></>}
    </dialog>
  </section>;
}
