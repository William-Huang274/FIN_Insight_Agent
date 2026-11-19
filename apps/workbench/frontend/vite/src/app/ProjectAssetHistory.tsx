import {useEffect,useState} from 'react';

type Version={document_id?:string;version?:string;name?:string;ticker?:string;created_at?:string;requested_at?:string;captured_at?:string;status?:string;access_status:string;digest?:string;version_info?:{sequence:number;change_kind:string;note:string};project_origin?:{research_origin?:unknown}};
type Impact={tasks:{thread_id:string}[];reports:{document_id:string;name:string;report_version:number;access_status:string}[];unknown_tasks:number;unknown_reports:number;notice:string};
type Comparison={kind:string;raw_equal:boolean;before_digest:string;after_digest:string;lines?:string[];truncated?:boolean;unread_pages?:boolean;notice:string;added?:number;removed?:number;total?:number;next_offset?:number|null;items?:{change:string;count:number;taxonomy:string;tag:string;unit:string;observation:{val:string;start?:string;end?:string;filed?:string;accn?:string;form?:string}}[]};
const idOf=(v:Version)=>v.document_id||v.version!;
const labels:Record<string,string>={original:'初版',correction:'原资料修订',new_period:'新增期间披露',report:'研究成果'};
async function json(response:Response){const body=await response.json();if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'资料版本操作失败');return body;}

export function ProjectAssetHistory({projectId,kind,asset,onClose,onChanged,onSelect,navigate}:{projectId:string;kind:'document'|'sec';asset:string;onClose:()=>void;onChanged:()=>Promise<void>;onSelect:(id:string)=>Promise<void>;navigate?:(view:string,id?:string)=>void}){
  const base=`/api/v1/projects/${projectId}`;
  const route=(id:string)=>`${base}/assets/${kind}/${encodeURIComponent(id)}`;
  const [versions,setVersions]=useState<Version[]>([]);const [before,setBefore]=useState(asset);const [after,setAfter]=useState('');
  const [diff,setDiff]=useState<Comparison|null>(null);const [impact,setImpact]=useState<Impact|null>(null);
  const [busy,setBusy]=useState(true);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [changeKind,setChangeKind]=useState('correction');const [note,setNote]=useState('');
  const load=async()=>{const data=await json(await fetch(`${route(asset)}/history`));setVersions(data.items);return data.items as Version[];};
  useEffect(()=>{let alive=true;void fetch(`${route(asset)}/history`).then(json).then(data=>{if(!alive)return;const vs=data.items as Version[];setVersions(vs);setAfter(vs.length>1?idOf(vs[vs.length-1])===asset?idOf(vs[vs.length-2]):idOf(vs[vs.length-1]):'');}).catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setBusy(false);});return()=>{alive=false;};},[base,asset,kind]);
  const available=(v:Version)=>v.access_status==='active'&&(kind==='document'||v.status==='complete');
  const label=(v:Version,i:number)=>`v${v.version_info?.sequence??i+1} · ${v.name||v.ticker} · ${new Date(v.created_at||v.captured_at||v.requested_at!).toLocaleString()}`;
  const compare=async(offset=0)=>{setBusy(true);setError('');setDiff(null);try{setDiff(await json(await fetch(`${route(before)}/compare?${new URLSearchParams({other:after,offset:String(offset)})}`)));}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const inspectImpact=async()=>{setBusy(true);setError('');setImpact(null);try{setImpact(await json(await fetch(`${route(before)}/dependencies`)));}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const latest=versions[versions.length-1];
  return <section className="fs-asset-history" aria-label="资料版本与关联成果">
    <div className="fs-version-heading"><h2>资料版本与关联成果</h2><button onClick={onClose} disabled={busy}>收起版本记录</button></div>
    <p>保存时间表示进入项目的时间，不等于披露时间。请选择具体版本；新版本不会覆盖旧任务、旧资料或已确认报告。</p>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{busy&&<p role="status">正在读取或保存版本…</p>}
    <ol>{versions.map((v,i)=><li key={idOf(v)}><strong>{label(v,i)}</strong><p>{v.version_info?labels[v.version_info.change_kind]:v.status==='complete'?'已保存快照':v.status==='failed'?'同步失败':'处理中或中断'} · {v.access_status==='active'?'允许使用':v.access_status==='revoked'?'已撤销使用':'依赖不可用'}</p>{v.version_info?.note&&<p>{v.version_info.note}</p>}
      <small>版本标识：{idOf(v)}</small><br/><button disabled={busy||!available(v)} onClick={async()=>{setBusy(true);setNotice('');setError('');try{await onSelect(idOf(v));setNotice('已明确选择此版本。准备新任务前仍可核对选择；历史任务保持原版。');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>选择此版本用于新研究</button>
    </li>)}</ol>
    <div className="fs-sec-fields"><label>基准版本<select aria-label="基准版本" disabled={busy} value={before} onChange={e=>{setBefore(e.target.value);setDiff(null);setImpact(null);}}>{versions.map((v,i)=><option key={idOf(v)} value={idOf(v)}>{label(v,i)}</option>)}</select></label>
      <label>对照版本<select aria-label="对照版本" disabled={busy} value={after} onChange={e=>{setAfter(e.target.value);setDiff(null);}}><option value="">请选择另一版本</option>{versions.filter(v=>available(v)).map((v,i)=><option key={idOf(v)} value={idOf(v)}>{label(v,versions.indexOf(v))}</option>)}</select></label>
      <button disabled={busy||!after||before===after||!versions.some(v=>idOf(v)===before&&available(v))} onClick={()=>void compare()}>比较所选版本</button>
      <button disabled={busy||!before} onClick={()=>void inspectImpact()}>查基准版本的关联任务与成果</button></div>
    {diff&&<section aria-label="版本差异"><h3>版本差异</h3><p>{diff.raw_equal?'原件校验值相同。':'原件校验值不同。'}{diff.notice}</p>
      <details><summary>原件校验记录</summary><p>基准：{diff.before_digest}</p><p>对照：{diff.after_digest}</p></details>
      {diff.truncated&&<p role="status">内容较大，差异未完整展示。请下载两个版本原件核对，不要据此判断完整变化。</p>}
      {diff.unread_pages&&<p role="status">含未识别图片或扫描页，这部分尚未比较。</p>}
      {diff.kind==='document'&&<pre className="fs-source-diff">{diff.lines?.length?diff.lines.map((line,i)=><span className={line.startsWith('+')?'fs-diff-added':line.startsWith('-')?'fs-diff-removed':''} key={i}>{line}{'\n'}</span>):'已解析正文未显示差异；请同时核对原件与未比较部分。'}</pre>}
      {diff.kind==='sec'&&<><p>新增 {diff.added} 条；移除 {diff.removed} 条原始观测。数值改变分别列出旧值和新值。</p><div className="fs-sec-table"><table><thead><tr><th>变化 / 次数</th><th>指标</th><th>期间</th><th>原值 / 单位</th><th>披露 / 申报</th></tr></thead><tbody>{diff.items?.map((r,i)=><tr key={i}><td>{r.change==='added'?'新增':'移除'} ×{r.count}</td><td>{r.taxonomy}:{r.tag}</td><td>{r.observation.start||'时点'} → {r.observation.end}</td><td>{r.observation.val} {r.unit}</td><td>{r.observation.filed}<br/>{r.observation.form} / {r.observation.accn}</td></tr>)}</tbody></table></div>{diff.next_offset!=null&&<button disabled={busy} onClick={()=>void compare(diff.next_offset!)}>下一页差异</button>}</>}
    </section>}
    {impact&&<section aria-label="已记录的来源依赖"><h3>基准版本的已记录依赖</h3><p>{impact.notice}</p><p>任务 {impact.tasks.length} 个；项目成果 {impact.reports.length} 份。另有 {impact.unknown_tasks} 个任务、{impact.unknown_reports} 份成果的记录不完整或不可核实。</p>
      {impact.tasks.map(t=><p key={t.thread_id}><button onClick={()=>navigate?.('graph',t.thread_id)} disabled={!navigate}>打开关联任务 {t.thread_id}</button></p>)}
      {impact.reports.map(r=><p key={r.document_id}>{r.name} · v{r.report_version} · {r.access_status==='active'?<a href={`${base}/documents/${encodeURIComponent(r.document_id)}/download`}>下载已保存成果</a>:'使用受限，保留历史记录'}</p>)}
      <p>这些任务和成果仍绑定原版本。如需使用更新资料，请明确选版并准备新任务。</p></section>}
    {kind==='document'&&latest&&!latest.project_origin?.research_origin&&<fieldset disabled={busy||!available(latest)}><legend>在最新版本后添加资料</legend><p>新文件作为 v{(latest.version_info?.sequence||1)+1} 保存，前序版本保留。每个版本计入项目的 12 份 / 80 MiB 上限。</p>
      <div className="fs-sec-fields"><label>更新性质<select aria-label="更新性质" value={changeKind} onChange={e=>setChangeKind(e.target.value)}><option value="correction">原资料修订</option><option value="new_period">新增期间披露</option></select></label>
      <label>更新说明<input aria-label="更新说明" maxLength={500} value={note} onChange={e=>setNote(e.target.value)} placeholder="例如更正单位，或新增第三季度材料"/></label>
      <label>上传新版本<input aria-label="上传新版本" type="file" accept=".pdf,.docx,.txt,.md,.csv,.html,.htm,.png,.jpg,.jpeg,.webp" onChange={async e=>{const file=e.target.files?.[0];e.target.value='';if(!file)return;setBusy(true);setError('');setNotice('');setDiff(null);setImpact(null);
        try{const saved=await json(await fetch(`${base}/documents?${new URLSearchParams({parent:idOf(latest),change_kind:changeKind,note})}`,{method:'POST',headers:{'X-Workbench-Request':'1','X-File-Name':encodeURIComponent(file.name)},body:file}));await load();await onChanged();setBefore(idOf(latest));setAfter(saved.document_id);setNote('');setNotice('新版本已保存。请比较差异并明确选版；原选择和历史任务未被替换。');}
        catch(e){setError((e as Error).message+' 未自动重试。请收起并重新打开版本记录确认保存结果。');}finally{setBusy(false);}
      }}/></label></div></fieldset>}
  </section>;
}
