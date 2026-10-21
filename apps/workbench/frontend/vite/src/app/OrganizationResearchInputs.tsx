import {useEffect,useRef,useState} from 'react';
import {useSearchParams} from 'react-router';
import {businessRequest} from '../api/businessResearch';
import {assetRequest} from '../api/assetWorkspace';
import {browserOwner} from './IdentityBoundary';
import './organization-research-inputs.css';
import {OrganizationPrepareExecution} from './OrganizationPrepareExecution';

type Resource={id:string;title:string;resource_type:string;space_name:string};
type Input={resource_id:string;title:string;resource_type:string;ref:{version_id:string;digest:string}};
type Release={release_id:string;model:string;index_digest:string;published_at:string;resource_ids:string[]};
type Draft={id:string;title:string;question:string;created_at:string;manifest_digest:string;manifest:{research_as_of:string;inputs:Input[];input_selection?:{selected_resource_ids:string[];retrieval_resource_ids:string[]};retrieval_index?:Pick<Release,'release_id'|'model'|'index_digest'>}};
type Body={id:string;title:string;question:string;research_as_of:string;resource_ids:string[];retrieval_release_id?:string;retrieval_resource_ids?:string[]};
export function OrganizationResearchInputs({project}:{project:{id:string;role:string;archived:boolean}}){
  const [params,setParams]=useSearchParams(),id=params.get('draft')||'';
  const base=`workspaces/projects/${project.id}/research-drafts`,slot=`finsight.organization-inputs:${browserOwner}:${project.id}`;
  const allowed=['manager','researcher'].includes(project.role)&&!project.archived;
  const [rows,setRows]=useState<Draft[]>([]),[detail,setDetail]=useState<Draft|null>(null),[docs,setDocs]=useState<Resource[]>([]);
  const [offset,setOffset]=useState(0),[next,setNext]=useState<number|null>(null),[docOffset,setDocOffset]=useState(0),[docNext,setDocNext]=useState<number|null>(null);
  const [title,setTitle]=useState(''),[question,setQuestion]=useState(''),[asOf,setAsOf]=useState(''),[selected,setSelected]=useState<string[]>([]);
  const [copiedFrom,setCopiedFrom]=useState<Draft|null>(null);
  const [releases,setReleases]=useState<Release[]>([]),[releaseId,setReleaseId]=useState('');
  const [pending,setPending]=useState<Body|null>(()=>{try{return JSON.parse(sessionStorage.getItem(slot)||'null');}catch{return null;}});
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[revision,refresh]=useState(0);
  const generation=useRef(0),operation=useRef(false);
  useEffect(()=>{let alive=true;++generation.current;setRows([]);setDetail(null);setError('');setNotice('');setLoading(true);
    (async()=>{const list=await businessRequest<{items:Draft[];next_offset:number|null}>(`${base}?offset=${offset}`);const item=id?await businessRequest<Draft>(`${base}/${id}`):null;if(alive){setRows(list.items);setNext(list.next_offset);setDetail(item);if(item){setPending(previous=>{if(previous?.id!==item.id)return previous;sessionStorage.removeItem(slot);return null;});}}})().catch(e=>{if(alive){setRows([]);setDetail(null);setError(e.message);}}).finally(()=>alive&&setLoading(false));return()=>{alive=false;++generation.current;};
  },[base,id,offset,revision]);
  useEffect(()=>{let alive=true;setDocs([]);setDocNext(null);if(allowed)businessRequest<{items:Resource[];next_offset:number|null}>(`workspaces/projects/${project.id}/resources?offset=${docOffset}`).then(v=>{if(alive){setDocs(v.items);setDocNext(v.next_offset);}}).catch(e=>alive&&setError(e.message));return()=>{alive=false;};},[project.id,allowed,docOffset,revision]);
  useEffect(()=>{let alive=true;setReleases([]);if(allowed)businessRequest<{items:Release[]}>(`workspaces/projects/${project.id}/retrieval-releases`).then(v=>{if(alive)setReleases(v.items);}).catch(e=>alive&&setError(e.message));return()=>{alive=false;};},[project.id,allowed,revision]);
  function choose(value:string){setParams(p=>{if(value)p.set('draft',value);else p.delete('draft');return p;});}
  function newDraft(){if(!pending){setCopiedFrom(null);setTitle('');setQuestion('');setAsOf('');setSelected([]);setReleaseId('');}choose('');}
  function selectResources(values:string[]){setSelected(values);if(releaseId){setReleaseId('');setNotice('资料选择已变化，请重新选择匹配的检索版本。');}}
  async function copyDraft(){
    if(!detail||!allowed||pending||operation.current)return;
    operation.current=true;setBusy(true);setError('');setNotice('');const current=++generation.current,original=detail;
    try{
      // A loaded detail is not a continuing permission grant. Re-read before
      // copying; saving still performs the authoritative transactional checks.
      const source=await businessRequest<Draft>(`${base}/${original.id}`);
      if(current!==generation.current)return;
      if(source.id!==original.id||source.manifest_digest!==original.manifest_digest)throw Error('原准备单版本不匹配，请刷新核对');
      setCopiedFrom(source);setTitle(source.title);setQuestion(source.question);setAsOf(source.manifest.research_as_of);
      setReleaseId(source.manifest.retrieval_index?.release_id||'');
      setSelected(source.manifest.input_selection?.selected_resource_ids||source.manifest.inputs.map(i=>i.resource_id));setDocOffset(0);choose('');
    }catch(e){if(current===generation.current){setDetail(null);setRows([]);setDocs([]);setSelected([]);setCopiedFrom(null);setTitle('');setQuestion('');setAsOf('');setError((e as Error).message);}}
    finally{operation.current=false;setBusy(false);}
  }
  function abandonPending(){if(!window.confirm('仅清除本浏览器的待核对内容。服务器可能已经保存原准备单，请先核对；此操作不会删除服务器记录。'))return;sessionStorage.removeItem(slot);setPending(null);setReleaseId('');setTitle('');setQuestion('');setAsOf('');setSelected([]);setError('');setNotice('本地待核对内容已清除；服务器原记录保留。');}
  async function save(){if(operation.current)return;operation.current=true;setBusy(true);setError('');const current=++generation.current;
    const retrievalResources=releaseId?(releases.find(r=>r.release_id===releaseId)?.resource_ids||copiedFrom?.manifest.inputs.map(i=>i.resource_id)):copiedFrom?.manifest.input_selection?.retrieval_resource_ids;
    const body=pending||{id:crypto.randomUUID(),title:title.trim(),question:question.trim(),research_as_of:asOf,resource_ids:selected,...(releaseId?{retrieval_release_id:releaseId}:{}),...(retrievalResources?{retrieval_resource_ids:[...new Set([...retrievalResources,...selected])]}:{})};
    try{sessionStorage.setItem(slot,JSON.stringify(body));setPending(body);const result=await businessRequest<Draft>(base,'POST',body);sessionStorage.removeItem(slot);if(current===generation.current){setPending(null);choose(result.id);refresh(n=>n+1);}}
    catch(e){if(current===generation.current)setError((e as Error).message+' 原准备内容和凭证已保留；可核对原单，或以原内容重试。');}
    finally{operation.current=false;setBusy(false);}}
  async function verify(){if(!detail||operation.current)return;operation.current=true;setBusy(true);setNotice('');setError('');const current=++generation.current;
    try{const v=await assetRequest<{manifest_digest:string;notice:string}>(`asset-workspace/organization-projects/${project.id}/research-drafts/${detail.id}/verify`,'POST',{});
      if(current===generation.current){if(v.manifest_digest!==detail.manifest_digest)throw Error('校验结果与原准备单不匹配');setNotice(v.notice);}}
    catch(e){if(current===generation.current){setDetail(null);setRows([]);setDocs([]);setSelected([]);setNotice('');setError((e as Error).message);}}
    finally{operation.current=false;setBusy(false);}}
  return <section className="org-inputs" aria-label="组织研究输入准备"><header className="pw-title"><div><h2>研究准备</h2><p>先确定问题、截止日期和资料版本。保存后固定执行配置，再确认开始预研究。</p></div><button disabled={busy} onClick={()=>refresh(n=>n+1)}>刷新准备单</button></header>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{loading&&<p role="status">正在读取准备单…</p>}
    {pending&&allowed&&<button disabled={busy} onClick={abandonPending}>清除本地待核对内容</button>}
    <div className="org-research-layout"><section className="pw-card"><h3>已保存的准备单</h3>{rows.map(r=><button className="pw-row" aria-current={r.id===id?'true':undefined} key={r.id} onClick={()=>choose(r.id)}><span>{r.title}<small>输入已保存 · {r.manifest.research_as_of}</small></span></button>)}{!loading&&!error&&!rows.length&&<p>暂无当前有权读取的准备单。</p>}<div className="pw-toolbar"><button disabled={!offset||busy} onClick={()=>setOffset(Math.max(0,offset-30))}>上一页准备单</button><button disabled={next===null||busy} onClick={()=>next!==null&&setOffset(next)}>下一页准备单</button>{allowed&&<button disabled={busy} onClick={newDraft}>新建准备单</button>}</div></section>
    <section className="pw-card">{id?(detail?<><h3>{detail.title}</h3><p>{detail.question}</p><p>研究截止日期：{detail.manifest.research_as_of}</p>{detail.manifest.retrieval_index&&<p>检索版本已固定：{detail.manifest.retrieval_index.release_id.slice(0,8)}。后续发布不会替换本次版本。</p>}<h4>重点资料</h4>{detail.manifest.inputs.filter(i=>!detail.manifest.input_selection||detail.manifest.input_selection.selected_resource_ids.includes(i.resource_id)).map(i=><p key={i.resource_id}>{i.title}<small> · {{files:'文件资料',knowledge:'知识库选取',database:'数据库快照'}[i.resource_type]}</small></p>)}{detail.manifest.input_selection&&<p>可检索资料范围：{detail.manifest.input_selection.retrieval_resource_ids.length} 份固定版本。检索、引用和成果读取仍检查全部资料的当前权限。</p>}<details><summary>全部固定版本与核对信息</summary><p style={{overflowWrap:'anywhere'}}>准备单摘要：{detail.manifest_digest}</p>{detail.manifest.inputs.map(i=><p key={i.resource_id} style={{overflowWrap:'anywhere'}}>{i.title}：{i.ref.version_id} · {i.ref.digest}</p>)}</details>{allowed&&<div className="pw-toolbar"><button disabled={busy} onClick={()=>void verify()}>重新校验权限与原件</button><button disabled={busy||!!pending} onClick={()=>void copyDraft()}>复制为新准备单</button></div>}<p className="pw-muted">校验仅反映本次请求时的状态，不是未来启动许可。没有创建研究运行，也没有调用模型。</p>{allowed&&<OrganizationPrepareExecution key={detail.id} project={project.id} draft={detail.id} digest={detail.manifest_digest}/>}</>:!loading&&<p>准备单不可读取；请刷新核对当前权限。</p>):allowed?<form className="pw-settings" onSubmit={e=>{e.preventDefault();void save();}}><h3>准备研究输入</h3>{copiedFrom&&!pending&&<aside aria-label="复制的研究输入"><p>基于「{copiedFrom.title}」创建新准备单。请核对问题与截止日期；原记录保留，保存时重新检查资料权限。</p><p>沿用原单的固定资料版本，不自动替换为最新版本。</p>{copiedFrom.manifest.inputs.filter(i=>selected.includes(i.resource_id)).map(i=><p key={i.resource_id}>{i.title} <button type="button" disabled={busy} onClick={()=>selectResources(selected.filter(id=>id!==i.resource_id))}>移除 {i.title}</button></p>)}</aside>}{pending&&<div role="status"><p>上次提交待核对：{pending.title}</p><button type="button" onClick={()=>choose(pending.id)}>核对原准备单</button><p>原内容已固定；以相同凭证重试不会创建第二份。</p></div>}
      <fieldset disabled={busy||!!pending}><label>准备单标题<input required maxLength={120} value={title} onChange={e=>setTitle(e.target.value)}/></label><label>研究问题<textarea required minLength={10} maxLength={16000} rows={4} value={question} onChange={e=>setQuestion(e.target.value)}/></label><label>研究截止日期<input required type="date" value={asOf} onChange={e=>setAsOf(e.target.value)}/></label>{releases.length>0&&<label>检索版本<select aria-label="检索版本" value={releaseId} onChange={e=>setReleaseId(e.target.value)}><option value="">暂不绑定检索索引</option>{releases.map(r=><option key={r.release_id} value={r.release_id} disabled={selected.some(id=>!r.resource_ids.includes(id))}>{r.published_at.slice(0,16)} · {r.resource_ids.length} 份可检索资料</option>)}</select><small>选择覆盖重点资料的已发布检索范围。保存后固定全部候选版本，旧研究不跟随新发布。</small></label>}<p>从已关联且可读取的项目资料中选择重点资料，已选 {selected.length}/12。</p>{docs.map(d=><label key={d.id}><input type="checkbox" checked={selected.includes(d.id)} disabled={!selected.includes(d.id)&&selected.length>=12} onChange={e=>selectResources(e.target.checked?[...selected,d.id]:selected.filter(v=>v!==d.id))}/>{d.title} · {d.space_name}</label>)}<div className="pw-toolbar"><button type="button" disabled={!docOffset} onClick={()=>setDocOffset(Math.max(0,docOffset-30))}>上一页可选资料</button><button type="button" disabled={docNext===null} onClick={()=>docNext!==null&&setDocOffset(docNext)}>下一页可选资料</button></div></fieldset>
      <p className="pw-muted">准备单归项目管理；阅读它仍需要重点资料及检索范围内全部资料的当前权限。保存不确认原件可用，请在详情中执行校验。</p><button className="pw-primary" disabled={busy||(!pending&&(!title.trim()||question.trim().length<10||!asOf||!selected.length))}>{pending?'以原内容重试保存':'保存输入准备单'}</button></form>:<p>只读成员可以查看有权读取的准备单；归档项目不能创建或校验研究输入。</p>}</section></div>
  </section>;
}
