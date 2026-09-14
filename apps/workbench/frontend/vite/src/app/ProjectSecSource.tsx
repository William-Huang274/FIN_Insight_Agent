import {useEffect,useState} from 'react';

type Version={version:string;ticker:string;cik:string;status:string;company_name?:string;requested_at:string;captured_at?:string;failure_code?:string};
type Concept={taxonomy:string;tag:string;label:string};
type Observation={val:string;unit:string;start?:string;end:string;filed:string;accn:string;form:string;locator:{observation_index:number}};
type Rows={items:Observation[];total:number;next_offset:number|null;notice?:string};
async function json(response:Response){const body=await response.json();if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'数据操作失败');return body;}

export function ProjectSecSource({projectId,onResearch}:{projectId:string;onResearch:(version:string)=>void}){
  const base=`/api/v1/projects/${projectId}/sec`;
  const [ticker,setTicker]=useState('');const [cik,setCik]=useState('');
  const [versions,setVersions]=useState<Version[]>([]);const [version,setVersion]=useState('');
  const [concepts,setConcepts]=useState<Concept[]>([]);const [concept,setConcept]=useState('');
  const [asOf,setAsOf]=useState('');const [rows,setRows]=useState<Rows|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const load=async()=>setVersions((await json(await fetch(base))).items);
  useEffect(()=>{let active=true;void fetch(base).then(json).then(r=>{if(active)setVersions(r.items);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[base]);
  const readVersion=async(id:string)=>{setBusy(true);setError('');setVersion(id);setConcept('');setRows(null);setConcepts([]);
    try{const data=await json(await fetch(`${base}/${id}`));setConcepts(data.concepts);}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const query=async(offset=0)=>{if(!concept)return;setBusy(true);setError('');
    const [taxonomy,tag]=JSON.parse(concept);const params=new URLSearchParams({taxonomy,tag,offset:String(offset)});if(asOf)params.set('as_of',asOf);
    try{setRows(await json(await fetch(`${base}/${version}?${params}`)));}catch(e){setRows(null);setError((e as Error).message);}finally{setBusy(false);}};
  return <section className="fs-project-sec" aria-label="SEC结构化数据"><h2>SEC 结构化披露</h2>
    <p>连接公司公开披露，手动同步为项目内独立版本。可浏览原始指标、期间和单位；选定版本可用于新研究，目前映射收入、营业利润及营业利润率，限定支持的美元口径。</p>
    <form className="fs-sec-fields" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');setNotice('');
      try{const saved=await json(await fetch(base,{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},body:JSON.stringify({version:crypto.randomUUID(),ticker:ticker.trim().toUpperCase(),cik:cik.trim().padStart(10,'0')})}));
        setNotice(saved.status==='complete'?'已保存新的数据版本。请选择版本和指标查看。':`同步未完成：${saved.failure_code||saved.status}。已有版本保留。`);await load();
      }catch(err){setError((err as Error).message+' 未自动重试，请先重新载入版本确认。');}finally{setBusy(false);}
    }}><label>股票代码<input aria-label="SEC股票代码" required maxLength={10} value={ticker} placeholder="例如 MSFT" onChange={e=>setTicker(e.target.value)}/></label>
      <label>SEC CIK<input aria-label="SEC CIK" required pattern="[0-9]{1,10}" maxLength={10} value={cik} placeholder="例如 789019" onChange={e=>setCik(e.target.value)}/></label>
      <button disabled={busy}>连接并保存新版本</button></form>
    <button disabled={busy} onClick={()=>{setBusy(true);setError('');void load().catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>重新载入数据版本</button>
    {busy&&<p role="status">正在处理数据…</p>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
    <ul>{versions.map(v=><li key={v.version}><strong>{v.ticker} · {v.company_name||v.cik}</strong>{' '}
      {v.status==='complete'?'已保存':v.status==='failed'?`同步失败（${v.failure_code}）`:'处理中或已中断，请重新载入确认'} · {new Date(v.captured_at||v.requested_at).toLocaleString()}{' '}
      {v.status==='complete'&&<button disabled={busy} onClick={()=>void readVersion(v.version)}>查看数据版本</button>}</li>)}</ul>
    {!versions.length&&<p>暂无已连接数据。</p>}
    {version&&!!concepts.length&&<><p>当前版本：{version}</p><div className="fs-sec-fields">
      <label>原始指标<select aria-label="SEC原始指标" disabled={busy} value={concept} onChange={e=>{setConcept(e.target.value);setRows(null);}}><option value="">请选择指标</option>{concepts.map(c=><option key={`${c.taxonomy}:${c.tag}`} value={JSON.stringify([c.taxonomy,c.tag])}>{c.label} · {c.taxonomy}:{c.tag}</option>)}</select></label>
      <label>披露日期不晚于<input aria-label="SEC披露截止日期" type="date" value={asOf} onChange={e=>{setAsOf(e.target.value);setRows(null);}}/></label>
      <button disabled={busy||!concept} onClick={()=>void query()}>查询已保存指标</button></div>
      <p><a href={`${base}/${version}/download/sec_companyfacts`}>下载指标原件</a>{' · '}<a href={`${base}/${version}/download/sec_submissions`}>下载披露记录原件</a></p><button disabled={busy} onClick={()=>onResearch(version)}>用此数据版本准备研究</button><p>新研究保存独立原件和指标副本。未映射标签、缺失申报身份和冲突会保留原因，不代表公司未披露。</p></>}
    {rows&&<><p>{rows.notice}</p><p>共 {rows.total} 条原始观测，当前显示 {rows.items.length} 条。多个披露版本分别保留。</p><div className="fs-sec-table"><table><thead><tr><th>期间</th><th>原值</th><th>单位</th><th>披露日期</th><th>表单 / 申报号</th></tr></thead><tbody>{rows.items.map((r,i)=><tr key={i}><td>{r.start?`${r.start} 至 `:'时点 '}{r.end}</td><td>{r.val}</td><td>{r.unit}</td><td>{r.filed}</td><td>{r.form}<br/>{r.accn}</td></tr>)}</tbody></table></div>
      {rows.next_offset!==null&&<button disabled={busy} onClick={()=>void query(rows.next_offset!)}>查看下一页</button>}</>}
  </section>;
}
