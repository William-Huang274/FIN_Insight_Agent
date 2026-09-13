import {useRef,useState} from 'react';
import {FilePenLine,X} from 'lucide-react';
import {createPatch} from 'diff';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {ReportDiffView} from './ReportDiffView';
import {roleName} from './researchLabels';
import type {Session} from '../api/reportSessions';
type Paper={paper_id:string;branch_id:string;thesis:string;body:string};
type Draft={base_version:number;report_markdown:string;papers:Paper[];charts?:{chart_index:number;title:string;interpretation:string}[];review:Session['report_review']};
const paperTitle=(body:string,fallback:string)=>body.match(/^#{1,3}\s+(.+)$/m)?.[1]||fallback;

export function ManualReview({session,onSaved}:{session:Session;onSaved:()=>Promise<void>}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [draft,setDraft]=useState<Draft|null>(null),[original,setOriginal]=useState<Draft|null>(null);
  const [reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [memoryNotice,setMemoryNotice]=useState('');
  const changed=!!draft&&JSON.stringify(draft)!==JSON.stringify(original);
  const dirty=changed||!!reason;
  function close(){if(dirty){setError('修改尚未提交，请先保存，或放弃本次修改。');return;}dialog.current?.close();}
  async function open(){dialog.current?.showModal();setBusy(true);setError('');
    try{const r=await fetch(`/api/v1/research-sessions/${session.thread_id}/manual-review`);const d=await r.json();if(!r.ok)throw Error(d.detail||'暂不可修改');setDraft(d);setOriginal(d);setReason('');setConfirmed(false);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function save(){if(!draft)return;setBusy(true);setError('');
    try{const r=await fetch(`/api/v1/research-sessions/${session.thread_id}/actions`,{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},body:JSON.stringify({action:'manual_complete',manual_review:{base_version:draft.base_version,report_markdown:draft.report_markdown,reason,confirmed,chart_edits:(draft.charts||[]).filter((c,i)=>c.interpretation!==original?.charts?.[i].interpretation).map(c=>({chart_index:c.chart_index,interpretation:c.interpretation})),paper_edits:draft.papers.filter((p,i)=>p.body!==original?.papers[i].body).map(p=>({paper_id:p.paper_id,body:p.body}))}})});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'保存未完成');setOriginal(draft);setReason('');dialog.current?.close();await onSaved();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <>{session.can_manual_complete&&<button className="fs-context-menu-button" onClick={()=>void open()}><FilePenLine size={16}/>人工修改与确认</button>}
    {['human_completed','human_reviewed_not_released'].includes(session.phase||'')&&<button className="fs-context-menu-button" disabled={busy} onClick={async()=>{setBusy(true);try{const r=await fetch(`/api/v1/research-sessions/${session.thread_id}/remember`,{method:'POST',headers:{'X-Workbench-Request':'1'}});const d=await r.json();if(!r.ok)throw Error(d.detail||'未能保存');setMemoryNotice('已保存此版本；新对话可从个人研究记忆回读。');}catch(e){setMemoryNotice((e as Error).message);}finally{setBusy(false);}}}>保存到个人研究记忆</button>}
    {memoryNotice&&<p role="status">{memoryNotice}</p>}
    {!!session.human_edits?.length&&<details className="fs-human-history"><summary>人工修改 {session.human_edits.length} 次 · 查看角色与底稿</summary>{session.human_edits.map(h=><section key={h.number}><h3>第 {h.number} 次 · {h.reason}</h3><p>{new Date(h.recorded_at).toLocaleString()} · {h.owner}</p>{[...h.papers,...(h.charts||[]).map(c=>({paper_id:`chart-${c.chart_index}`,actor:'writer',title:`图表说明 · ${c.title}`,before:c.before,after:c.after})),...(h.report_before||h.report_after?[{paper_id:'report',actor:'writer',title:'最终报告',before:h.report_before,after:h.report_after}]:[])].map(p=><details key={p.paper_id}><summary>{roleName(p.actor)} — {p.paper_id==='report'?'最终报告':paperTitle(p.after,p.title)}</summary><ReportDiffView proseOnly value={{before_version:h.base_version,after_version:h.base_version+1,reason:h.reason,diff:createPatch('正文',p.before,p.after),citations_changed:false,charts_changed:false}}/><details><summary>查看修改后完整正文</summary><ReactMarkdown remarkPlugins={[remarkGfm]}>{p.after}</ReactMarkdown></details></details>)}</section>)}</details>}
    <dialog ref={dialog} className="fs-working-notes fs-human-editor" aria-label="人工修改与确认" onCancel={e=>{if(dirty){e.preventDefault();close();}}}>
      <header><div><h2>人工修改与确认</h2><p>按角色修订底稿，再确认报告。保存会保留原版，不调用模型；原审查意见不会被删除。</p></div><button aria-label="关闭人工修改" onClick={close}><X size={20}/></button></header>
      {draft&&<><details><summary>查看模型留下的审查意见</summary><p>{draft.review?.summary}</p>{draft.review?.findings.map(f=><p key={f.finding_id}>{f.report_quote}：{f.diagnosis} — {f.requested_change}</p>)}</details>
        {draft.papers.map((p,i)=><details key={p.paper_id}><summary>{roleName(p.branch_id)} — {p.thesis}</summary><textarea aria-label={`修改底稿 ${p.paper_id}`} value={p.body} onChange={e=>setDraft({...draft,papers:draft.papers.map((v,j)=>i===j?{...v,body:e.target.value}:v)})}/></details>)}
        <label>报告正文<textarea aria-label="人工修改报告正文" value={draft.report_markdown} onChange={e=>setDraft({...draft,report_markdown:e.target.value})}/></label>
        {draft.charts?.map((c,i)=><label key={c.chart_index}>图表说明 · {c.title}<textarea aria-label={`修改图表说明 ${c.chart_index+1}`} value={c.interpretation} onChange={e=>setDraft({...draft,charts:draft.charts?.map((v,j)=>i===j?{...v,interpretation:e.target.value}:v)})}/><small>只修改说明；数值、单位和来源仍使用已保存的计算结果。</small></label>)}
        <label>修改说明<textarea aria-label="人工修改说明" maxLength={4000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
        <label className="fs-human-confirm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我已检查底稿、报告、原有图表及剩余意见，确认修改后的内容可作为本次研究结果；这不代表模型自动核验通过。</label>
        <button disabled={busy||!changed||!reason.trim()||!confirmed} onClick={()=>void save()}>保存修改并确认完成</button><button disabled={busy} onClick={()=>{setDraft(original);setReason('');setConfirmed(false);setError('');}}>放弃本次修改</button></>}
      {error&&<p role="alert">{error}</p>}
    </dialog></>;
}
