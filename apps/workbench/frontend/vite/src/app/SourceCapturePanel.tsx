import {useEffect,useState} from 'react';
import {assetRequest as request,type AssetRef,type SourceCapture,type CapturedFinancialRow} from '../api/assetWorkspace';

export function CapturedFinancialTable({rows}:{rows:CapturedFinancialRow[]}){
  return <div className="aw-captured-table"><p>仅包含明确选择的记录，各披露版本分别保留。</p><table><thead><tr><th>公司 / 指标</th><th>来源原值 / 单位</th><th>期间</th><th>披露与出处</th></tr></thead><tbody>{rows.map(r=><tr key={r.selection_id}><td>{r.ticker}<br/>{r.metric_id}</td><td>{r.value_decimal}<br/>{r.unit}</td><td>{r.period_start||'时点'} — {r.period_end}<br/>FY{r.fiscal_year} {r.fiscal_period}</td><td>{r.filed_at}<br/><a href={r.citation_url} target="_blank" rel="noreferrer">原始披露 {r.form}</a></td></tr>)}</tbody></table></div>;
}

export function SourceCapturePanel({capture,reference,onSaved,onEditing}:{capture:SourceCapture;reference:AssetRef;onSaved:(id:string)=>Promise<void>;onEditing:(value:boolean)=>void}){
  const [editing,setEditing]=useState(false),[note,setNote]=useState(capture.note||''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{setEditing(false);setNote(capture.note||'');setError('');},[reference.version_id]);
  const query=new URLSearchParams({view:capture.kind==='library'?'library':'financial-data'});
  if(capture.origin)query.set('source',capture.origin.document_id);
  for(const [k,v] of Object.entries(capture.query||{}))if(v!==null&&v!==''&&!['limit','offset'].includes(k))query.set(k,String(v));
  async function save(){setBusy(true);setError('');try{const r=await request<{document_id:string}>('asset-workspace/captures/note','PUT',{base_ref:reference,note});await onSaved(r.document_id);setEditing(false);onEditing(false);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <section className="aw-capture" aria-label="固定来源与批注"><strong>{capture.kind==='library'?`固定原文 · ${capture.section_ids?.length} 个章节`:`固定财务记录 · ${capture.selected_count} 条`}</strong>
    <p>来源内容保持原样；用户批注独立标记。新的披露或查询结果需重新选择保存。</p>
    <div className="aw-actions"><a href={`/workspace/assets?${query}`}>浏览当前来源</a><a href={`/api/v1/projects/${reference.project_id}/documents/${encodeURIComponent(reference.version_id)}/download`}>下载此版本</a>{!editing&&<button onClick={()=>{setEditing(true);onEditing(true);}}>编辑批注</button>}</div>
    {error&&<p role="alert">{error}</p>}
    {editing?<><label>我的批注<textarea aria-label="编辑来源批注" disabled={busy} maxLength={10000} value={note} onChange={e=>setNote(e.target.value)}/></label><div className="aw-actions"><button disabled={busy} onClick={()=>void save()}>保存批注版本</button><button disabled={busy} onClick={()=>{setNote(capture.note||'');setEditing(false);onEditing(false);}}>放弃批注修改</button></div></>:<p className="aw-capture-note">{capture.note||'尚未添加批注。'}</p>}
  </section>;
}
