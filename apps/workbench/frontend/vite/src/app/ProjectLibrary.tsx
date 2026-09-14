import { useEffect, useState } from 'react';
import type { Session } from '../api/reportSessions';
import './project-library.css';
import {ProjectSecSource} from './ProjectSecSource';

type Document = {document_id:string;name:string;bytes:number;text_status:string;excerpt:string;sections:number;project_origin?:{research_origin?:{thread_id:string;report_version:number;phase:string;reason:string}}};
type Detail = {name:string;sections:{heading:string;text:string;page:number|null;needs_vision:boolean}[]};
async function readJson(response:Response) {
  const body=await response.json();
  if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'资料操作失败');
  return body;
}

export function ProjectLibrary({project, sessions, navigate, onResearch}:{project:{id:string;name:string};sessions:Session[];navigate:(view:string,id?:string)=>void;onResearch:(documents:{document_id:string;name:string}[],secVersion?:string)=>void}) {
  const base=`/api/v1/projects/${project.id}/documents`;
  const [query,setQuery]=useState(''); const [items,setItems]=useState<Document[]>([]);
  const [detail,setDetail]=useState<Detail|null>(null); const [error,setError]=useState('');
  const [busy,setBusy]=useState(true); const [notice,setNotice]=useState('');
  const [selected,setSelected]=useState<Document[]>([]);
  const load=async()=>{const result=await readJson(await fetch(`${base}?query=${encodeURIComponent(query)}`));setItems(result.items);};
  useEffect(()=>{void load().catch(e=>setError(e.message)).finally(()=>setBusy(false));},[base]);
  const search=async()=>{setBusy(true);setError('');try{await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  return <section className="fs-page fs-project-library"><span className="fs-kicker">项目资料</span><h1>{project.name}</h1>
    <p>项目和资料保存在当前工作台服务。可按文件名或已解析正文查找；上传内容及研究成果仍需核验。历史报告版本分别保留，请明确选择本次需要的版本。</p>
    <div className="fs-project-upload"><label>添加项目资料<input aria-label="添加项目资料" type="file" disabled={busy} accept=".pdf,.docx,.txt,.md,.csv,.html,.htm,.png,.jpg,.jpeg,.webp" onChange={async e=>{
      const file=e.target.files?.[0]; e.target.value=''; if(!file)return;setBusy(true);setError('');setNotice('');
      try{await readJson(await fetch(base,{method:'POST',headers:{'X-Workbench-Request':'1','X-File-Name':encodeURIComponent(file.name)},body:file}));
        setQuery('');const result=await readJson(await fetch(base));setItems(result.items);setNotice(`${file.name} 已保存到项目。`);
      }catch(err){setError((err as Error).message+' 未自动重试，请先重新载入资料列表确认。');}finally{setBusy(false);}
    }}/></label><small>单个文件最多20 MiB；每项目最多12份、合计80 MiB。图片与扫描页暂不提供正文查找。</small></div>
    <form className="fs-search" onSubmit={e=>{e.preventDefault();void search();}}><input aria-label="查找项目资料" placeholder="输入文件名或正文关键词…" value={query} maxLength={200} onChange={e=>setQuery(e.target.value)}/><button disabled={busy}>查找</button></form>
    <button disabled={busy} onClick={()=>void search()}>重新载入资料</button>
    {notice&&<p role="status">{notice}</p>}{busy&&<p role="status">正在处理资料…</p>}{error&&<p role="alert">{error}</p>}
    <p>已选 {selected.length} 份资料。开始研究时保存独立副本，后续项目修改不会自动改变该次研究输入。</p>
    <button disabled={busy||!selected.length} onClick={()=>onResearch(selected)}>用所选资料准备研究</button>
    {!!selected.length&&<button disabled={busy} onClick={()=>setSelected([])}>清空资料选择</button>}
    <div className="fs-project-documents">{items.map(item=><article key={item.document_id}><label><input type="checkbox" aria-label={`选择资料 ${item.name}`} disabled={busy} checked={selected.some(d=>d.document_id===item.document_id)} onChange={e=>setSelected(old=>e.target.checked?[...old,item]:old.filter(d=>d.document_id!==item.document_id))}/>用于研究</label><h2>{item.name}</h2><small>{item.text_status==='searchable'?'正文可查找':'含需识别的图片或扫描页'} · {item.project_origin?.research_origin?'研究成果，须核对原始依据':'用户提供，待核验'}</small><p>{item.excerpt}</p>
      {item.project_origin?.research_origin&&<div><p>研究成果 v{item.project_origin.research_origin.report_version} · {['human_completed','human_reviewed_not_released'].includes(item.project_origin.research_origin.phase)?'用户已确认，仍须核对原始依据':'研究草稿，待审阅'}；{item.project_origin.research_origin.reason}</p><button disabled={busy} onClick={()=>navigate('report',item.project_origin!.research_origin!.thread_id)}>打开原研究与修改记录</button></div>}
      <button disabled={busy} onClick={async()=>{setBusy(true);setError('');try{setDetail(await readJson(await fetch(`${base}/${encodeURIComponent(item.document_id)}`)));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>阅读已保存正文</button>{' '}
      <a href={`${base}/${encodeURIComponent(item.document_id)}/download`}>下载原文件</a>
    </article>)}</div>{!busy&&!items.length&&<p>暂无符合条件的资料。可上传文件或更换关键词。</p>}
    {detail&&<section className="fs-project-document-reader" aria-label="项目资料正文"><button onClick={()=>setDetail(null)}>收起正文</button><h2>{detail.name}</h2>{detail.sections.map((s,i)=><section key={i}><h3>{s.heading}</h3><pre>{s.text||'此页需要图像识别，尚无可查找正文。'}</pre></section>)}</section>}
    <ProjectSecSource key={project.id} projectId={project.id} onResearch={version=>onResearch([],version)}/>
    <h2>项目内的研究与成果</h2><p>所选资料会进入新研究的资料工具，Agent 按需读取；来源绑定不代表内容已核验。已有研究及报告保持原有权限和版本。</p>
    <div className="fs-research-list">{sessions.map(s=><button key={s.thread_id} onClick={()=>navigate('graph',s.thread_id)}>{s.title||'未命名研究'}</button>)}</div>{!sessions.length&&<p>可在“管理项目”中归入已有研究。</p>}
  </section>;
}
