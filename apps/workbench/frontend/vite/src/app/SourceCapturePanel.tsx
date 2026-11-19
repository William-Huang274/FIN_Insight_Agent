import {useEffect,useState} from 'react';
import {assetRequest as request,type AssetRef,type SourceCapture,type CapturedFinancialRow} from '../api/assetWorkspace';

export function CapturedFinancialTable({rows}:{rows:CapturedFinancialRow[]}){
  const metricRows=rows.filter(r=>'id' in r);
  const factRows=rows.filter(r=>'selection_id' in r);
  return <div className="aw-captured-table">
    <p>仅包含明确选择的记录，各披露版本分别保留。</p>
    {metricRows.map(r=>'id' in r&&<section className="aw-metric-snapshot" key={r.id} aria-label="已保存指标数据卡">
      <h3>{r.company_name} · {r.label}</h3>
      <p className="aw-metric-value">{r.value===null?(r.text_value||'缺少数值'):<>
        {({gt:'>',ge:'≥',lt:'<',le:'≤',approx:'约 '} as Record<string,string>)[r.comparator||'']||''}{r.value} {r.unit}
      </>}</p>
      <dl>
        <dt>财务期间</dt><dd>{r.period_label} · {r.period_start||(r.period_kind==='instant'?'时点':'起始日未提供')} — {r.period_end||'结束日未提供'}</dd>
        <dt>可获知日</dt><dd>{r.available_at}</dd>
        <dt>数值性质</dt><dd>{{actual:'实际',plan:'计划',guidance:'指引'}[r.value_state]||r.value_state}</dd>
        <dt>业务口径</dt><dd>{r.business_scope||'见原始依据'}</dd>
      </dl>
      {r.evidence_quote&&<details><summary>查看保存的披露依据</summary><blockquote>{r.evidence_quote}</blockquote><small>{r.evidence_locator}</small></details>}
      {!!r.inputs?.length&&<details><summary>计算输入与公式</summary><code>{r.formula}</code>
        {r.inputs?.map((v,i)=><p key={v.id||i}>{v.display_label||v.role}：{v.value} {v.unit} · {v.period_start} — {v.period_end}</p>)}
      </details>}
      {r.sources?.map(s=><p key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · {s.published_at}</p>)}
      <details><summary>记录与版本</summary><p>{r.id}</p><p>{r.formula_version||'原始披露'}</p></details>
    </section>)}
    {!!factRows.length&&<table><thead><tr><th>公司 / 指标</th><th>来源原值 / 单位</th><th>期间</th><th>披露与出处</th></tr></thead>
      <tbody>{factRows.map(r=>'selection_id' in r&&<tr key={r.selection_id}>
        <td>{r.ticker}<br/>{r.metric_id}</td><td>{r.value_decimal}<br/>{r.unit}</td>
        <td>{r.period_start||'时点'} — {r.period_end}<br/>FY{r.fiscal_year} {r.fiscal_period}</td>
        <td>{r.filed_at}<br/><a href={r.citation_url} target="_blank" rel="noreferrer">原始披露 {r.form}</a></td>
      </tr>)}</tbody>
    </table>}
  </div>;
}

export function SourceCapturePanel({capture,reference,onSaved,onEditing}:{capture:SourceCapture;reference:AssetRef;onSaved:(id:string)=>Promise<void>;onEditing:(value:boolean)=>void}){
  const [editing,setEditing]=useState(false),[note,setNote]=useState(capture.note||''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{setEditing(false);setNote(capture.note||'');setError('');},[reference.version_id]);
  const query=new URLSearchParams({view:capture.kind==='library'?'library':'financial-data'});
  if(capture.origin)query.set('source',capture.origin.document_id);
  const metricCapture=capture.query?.kind==='metric_cards';
  for(const [k,v] of Object.entries(capture.query||{}))if(v!==null&&v!==''&&!['limit','offset'].includes(k))query.set(k,String(v));
  async function save(){setBusy(true);setError('');try{const r=await request<{document_id:string}>('asset-workspace/captures/note','PUT',{base_ref:reference,note});await onSaved(r.document_id);setEditing(false);onEditing(false);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <section className="aw-capture" aria-label="固定来源与批注"><strong>{capture.kind==='library'?`固定原文 · ${capture.section_ids?.length} 个章节`:`固定财务记录 · ${capture.selected_count} 条`}</strong>
    <p>来源内容保持原样；用户批注独立标记。新的披露或查询结果需重新选择保存。</p>
    <div className="aw-actions"><a href={metricCapture?`/workspace/assets?view=financial-data&company=${encodeURIComponent(String((capture.query?.entity_ids as string[])?.[0]||''))}`:`/workspace/assets?${query}`}>浏览当前来源</a><a href={`/api/v1/projects/${reference.project_id}/documents/${encodeURIComponent(reference.version_id)}/download`}>下载此版本</a>{!editing&&<button onClick={()=>{setEditing(true);onEditing(true);}}>编辑批注</button>}</div>
    {error&&<p role="alert">{error}</p>}
    {editing?<><label>我的批注<textarea aria-label="编辑来源批注" disabled={busy} maxLength={10000} value={note} onChange={e=>setNote(e.target.value)}/></label><div className="aw-actions"><button disabled={busy} onClick={()=>void save()}>保存批注版本</button><button disabled={busy} onClick={()=>{setNote(capture.note||'');setEditing(false);onEditing(false);}}>放弃批注修改</button></div></>:<p className="aw-capture-note">{capture.note||'尚未添加批注。'}</p>}
  </section>;
}
