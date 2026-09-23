import {useEffect,useRef,useState} from 'react';
import {useSearchParams} from 'react-router';
import {ArrowUpRight,FolderOpen,Layers,Plus,RefreshCw} from 'lucide-react';
import {useWorkspaceProjects} from './workspaceProjects';
import {browserOwner} from './IdentityBoundary';
import {ExecutionPicker,executionReady,executionModeName} from './ExecutionPicker';
import type {ExecutionOptions} from '../api/reportSessions';
import {businessRequest,type BusinessTask} from '../api/businessResearch';
import './project-research.css';

type Pending = {key:string; body:{project_id:string;title:string;question:string;document_ids:string[];execution:ExecutionOptions}};
const labels={ready:'尚未提交',unknown:'结果待核对',received:'已确认',rejected:'未能受理'};
const slot=(project:string)=>`finsight.business.pending:${browserOwner}:${project}`;
function saved(project:string):Pending|null {try{return JSON.parse(sessionStorage.getItem(slot(project))||'null');}catch{return null;}}

export default function ProjectResearchWorkspace(){
  const projects=useWorkspaceProjects();
  const [params,setParams]=useSearchParams();
  const project=params.get('project')||'', taskId=params.get('task')||'';
  const selected=projects.index.projects.find(p=>p.id===project);
  const [enabled,setEnabled]=useState<boolean|null>(null),[error,setError]=useState('');
  const [items,setItems]=useState<BusinessTask[]>([]),[detail,setDetail]=useState<BusinessTask|null>(null);
  const [offset,setOffset]=useState(0),[next,setNext]=useState<number|null>(null),[revision,refresh]=useState(0);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),inflight=useRef(false);
  const [title,setTitle]=useState(''),[question,setQuestion]=useState(''),[name,setName]=useState('');
  const [execution,setExecution]=useState<ExecutionOptions>({mode:'auto',model:'default',branch_ids:[]});
  const [docs,setDocs]=useState<{document_id:string;name:string;access_status:string}[]>([]),[docIds,setDocIds]=useState<string[]>([]);
  const [docOffset,setDocOffset]=useState(0),[docNext,setDocNext]=useState<number|null>(null);
  const [pending,setPending]=useState<Pending|null>(null);
  const activeProject=useRef(project);activeProject.current=project;
  useEffect(()=>{let alive=true;businessRequest<{enabled:boolean}>('config').then(v=>alive&&setEnabled(v.enabled)).catch(e=>alive&&setError(e.message));return()=>{alive=false;};},[]);
  useEffect(()=>{setItems([]);setDetail(null);setOffset(0);setDocOffset(0);setDocIds([]);setDocs([]);setError('');setTitle('');setQuestion('');setPending(saved(project));},[project]);
  useEffect(()=>{let alive=true;if(!selected||!enabled){setLoading(false);return;}setLoading(true);
    businessRequest<{items:BusinessTask[];next_offset:number|null}>(`tasks?project_id=${project}&offset=${offset}`)
      .then(v=>{if(alive){setItems(v.items);setNext(v.next_offset);}}).catch(e=>alive&&setError(e.message)).finally(()=>alive&&setLoading(false));
    return()=>{alive=false;};},[project,!!selected,enabled,offset,revision]);
  useEffect(()=>{let alive=true;setDetail(null);if(!taskId||!selected||!enabled)return;
    businessRequest<BusinessTask>(`tasks/${taskId}`).then(v=>{if(alive){if(v.project_id!==project)throw Error('该任务不属于当前项目，请检查链接。');setDetail(v);}}).catch(e=>alive&&setError(e.message));
    return()=>{alive=false;};},[project,!!selected,taskId,enabled,revision]);
  useEffect(()=>{let alive=true;if(!selected)return;fetch(`/api/v1/projects/${project}/documents?offset=${docOffset}&limit=50`,{cache:'no-store'}).then(async r=>{if(!r.ok)throw Error('项目资料读取失败，请刷新。');return r.json();})
    .then(v=>{if(alive){setDocs(v.items);setDocNext(v.next_offset??null);}}).catch(e=>alive&&setError(e.message));return()=>{alive=false;};},[project,!!selected,docOffset,revision]);
  const change=(id:string)=>{setParams(id?{project:id}:{});};
  const work=async(action:()=>Promise<void>)=>{if(inflight.current)return;inflight.current=true;setBusy(true);setError('');try{await action();}catch(e){if(activeProject.current===project)setError((e as Error).message);}finally{inflight.current=false;setBusy(false);}};
  const create=()=>work(async()=>{
    const operation=pending||{key:crypto.randomUUID(),body:{project_id:project,title:title.trim(),question:question.trim(),document_ids:docIds,execution}};
    // Preserve exact input and key BEFORE the network; refresh never creates a new operation.
    sessionStorage.setItem(slot(project),JSON.stringify(operation));setPending(operation);
    const task=await businessRequest<BusinessTask>('tasks','POST',operation.body,operation.key);
    sessionStorage.removeItem(slot(project));
    if(activeProject.current===project){setPending(null);setParams({project,task:task.id});refresh(n=>n+1);setTitle('');setQuestion('');}
  });
  const action=(kind:'prepare'|'start'|'reconcile')=>work(async()=>{if(!detail)return;const task=await businessRequest<BusinessTask>(`tasks/${detail.id}/${kind}`,'POST',{});if(activeProject.current===project){setDetail(task);refresh(n=>n+1);}});
  return <div className="pr-workspace"><aside className="pr-sidebar"><a className="pr-brand" href="/workspace/session"><Layers size={25}/><span>FinSight<small>研究工作区</small></span></a>
    <nav><a aria-current="page" href="/workspace/projects"><FolderOpen size={17}/>项目任务</a><a href="/workspace/session">研究工作台 <ArrowUpRight size={15}/></a><a href="/workspace/assets">资料与资产 <ArrowUpRight size={15}/></a></nav>
    <label>当前项目<select aria-label="切换项目" value={project} disabled={busy||!projects.ready} onChange={e=>change(e.target.value)}><option value="">选择项目</option>{project&&!selected&&<option value={project}>不可访问 · {project.slice(0,8)}</option>}{[...projects.index.projects].sort((a,b)=>a.id.localeCompare(b.id)).map(p=><option key={p.id} value={p.id}>{p.name} · {p.id.slice(0,8)}</option>)}</select></label>
    {selected&&<small className="pr-project-id">项目 ID<br/>{selected.id}</small>}
    <form className="pr-new-project" onSubmit={e=>{e.preventDefault();void work(async()=>{const id=crypto.randomUUID();if(await projects.update({...projects.index,projects:[...projects.index.projects,{id,name:name.trim()}]})){setName('');change(id);}});}}><label>新项目名称<input maxLength={60} value={name} onChange={e=>setName(e.target.value)} placeholder="输入项目名称"/></label><button disabled={!name.trim()||busy||!projects.ready}><Plus size={15}/>创建项目</button></form>
    <p className="pr-sidebar-note">个人项目<br/>研究记录按当前登录身份保存。</p></aside>
    <main><header className="pr-heading"><div><p className="pr-eyebrow">PROJECT RESEARCH</p><h1>{selected?.name||'项目研究任务'}</h1><p>从问题到研究，保留每一次提交与结果的关联。</p></div><button disabled={busy} onClick={()=>{void projects.reload();refresh(n=>n+1);}}><RefreshCw size={16}/>刷新记录</button></header>
      {(error||projects.error)&&<p className="pr-alert" role="alert">{error||projects.error}</p>}
      {enabled===false&&<div className="pr-empty"><h2>研究业务服务尚未启用</h2><p>此部署可继续使用研究工作台。管理员完成业务数据库和研究接入配置后，项目任务入口才会开放。</p><a href="/workspace/session">打开研究工作台 →</a></div>}
      {enabled===null&&!error&&<p role="status">正在检查研究业务服务…</p>}
      {enabled&&(!selected?<div className="pr-empty"><h2>{project?'此项目不存在或不可访问':'选择一个项目开始'}</h2><p>在左侧按项目名称和 ID 切换，也可以创建新项目。同名项目使用不同 ID 区分。</p></div>:<>
      <section className="pr-context"><span><i/>项目上下文已选定</span><code>{selected.id}</code><a href={`/workspace/assets?view=project&project=${project}`}>管理项目资料 <ArrowUpRight size={15}/></a></section>
      <div className="pr-columns"><section className="pr-card"><div className="pr-section-title"><div><h2>研究任务</h2><p>先准备草稿，核对后再启动。</p></div><button disabled={busy} onClick={()=>setParams({project})}><Plus size={16}/>新任务</button></div>
        {loading&&<p role="status">正在读取任务…</p>}{!loading&&!items.length&&<p className="pr-empty-small">这个项目还没有业务研究任务。</p>}
        <div className="pr-task-list">{items.map(t=><button key={t.id} className={taskId===t.id?'selected':''} onClick={()=>setParams({project,task:t.id})}><strong>{t.title}</strong><span>{t.start.status==='received'?'已关联研究运行':t.prepare.status==='received'&&t.start.status==='ready'?'草稿已准备':labels[t.start.status==='ready'?t.prepare.status:t.start.status]}</span><small>{t.id.slice(0,8)} · {new Date(t.created_at).toLocaleString('zh-CN')}</small></button>)}</div>
        <div className="pr-pagination"><button disabled={!offset||loading} onClick={()=>setOffset(Math.max(0,offset-50))}>上一页</button><button disabled={next===null||loading} onClick={()=>next!==null&&setOffset(next)}>下一页</button></div></section>
      <section className="pr-card pr-detail">{taskId?(detail?<><p className="pr-eyebrow">研究任务 · {detail.id.slice(0,8)}</p><h2>{detail.title}</h2><p className="pr-question">{detail.question}</p>
        <ol className="pr-steps"><li><strong>1　准备研究草稿</strong><span>{labels[detail.prepare.status]}</span></li><li><strong>2　启动 Agent 研究</strong><span>{labels[detail.start.status]}</span></li><li><strong>3　查看研究与结果</strong><span>{detail.start.status==='received'?'前往研究工作台查看':'启动后可查看进度与费用'}</span></li></ol>
        <dl><dt>研究截止时点</dt><dd>{detail.binding.research_as_of}</dd><dt>资料发布版本</dt><dd className="pr-hash">{detail.binding.snapshot_ref}</dd><dt>业务任务 ID</dt><dd className="pr-hash">{detail.id}</dd></dl>
        {detail.research_options&&<p className="pr-footnote">提交时研究配置：{executionModeName[detail.research_options.execution?.mode as keyof typeof executionModeName]||'部署默认'} · {detail.research_options.execution?.model==='default'?'按角色配置':detail.research_options.execution?.model||'部署默认'}。项目资料 {detail.research_options.project_materials?.document_ids.length||0} 份。</p>}
        {(detail.prepare.status==='unknown'||detail.start.status==='unknown')&&<p className="pr-alert">提交结果尚未确认。核对会查找原草稿和原运行，不会重新启动研究。</p>}
        {[detail.prepare,detail.start].filter(c=>c.status==='rejected').map(c=><p key={c.operation_id} role="alert" className="pr-alert">{typeof c.result?.detail==='string'?c.result.detail:'原提交未被受理，请核查研究配置和项目资料。'} 原记录已保留。</p>)}
        <div className="pr-actions">{detail.prepare.status==='ready'&&<button disabled={busy} onClick={()=>void action('prepare')}>完成草稿准备</button>}{detail.prepare.status==='received'&&detail.start.status==='ready'&&<button className="pr-primary" disabled={busy} onClick={()=>void action('start')}>确认并启动研究</button>}{(detail.prepare.status==='unknown'||detail.start.status==='unknown')&&<button disabled={busy} onClick={()=>void action('reconcile')}>核对原提交</button>}
          {detail.thread_id&&<a href={`/workspace/session?thread=${detail.thread_id}&view=activity`}>打开原研究 <ArrowUpRight size={15}/></a>}</div>
        {detail.start.status==='ready'&&<p className="pr-footnote">启动后将按部署的研究配置调用模型并产生费用。保存草稿不调用模型。</p>}
        {detail.start.result?.run_id&&<p className="pr-footnote">运行 ID：{detail.start.result.run_id}。此处的已确认仅代表运行受理；完成状态、报告和用量以研究工作台为准。</p>}
      </>:<p role="status">正在读取所选任务…</p>):<form onSubmit={e=>{e.preventDefault();void create();}}><p className="pr-eyebrow">NEW RESEARCH</p><h2>准备一项研究</h2>{pending&&<div className="pr-alert"><strong>上次提交尚待核对</strong><p>{pending.body.title} · {pending.key.slice(0,8)}</p><p>继续使用原提交凭证读取或完成受理；不会创建第二项任务。</p></div>}
        <fieldset disabled={busy||!!pending}><label>研究标题<input value={title} maxLength={120} required onChange={e=>setTitle(e.target.value)} placeholder="例如：算力资本开支与现金流研究"/></label><label>研究问题<textarea value={question} minLength={10} maxLength={16000} required rows={5} onChange={e=>setQuestion(e.target.value)} placeholder="说明研究对象、期间和要回答的问题…"/></label>
          <ExecutionPicker value={execution} onChange={setExecution}/><div className="pr-docs"><h3>项目资料 <small>已选 {docIds.length}/12 · 可不选</small></h3>{docs.map(d=><label key={d.document_id}><input type="checkbox" disabled={d.access_status!=='active'||(!docIds.includes(d.document_id)&&docIds.length>=12)} checked={docIds.includes(d.document_id)} onChange={e=>setDocIds(e.target.checked?[...docIds,d.document_id]:docIds.filter(id=>id!==d.document_id))}/><span>{d.name}{d.access_status!=='active'?' · 不可用':''}</span></label>)}{!docs.length&&<p>暂无项目资料，研究将使用部署已发布的公共资料库。</p>}<div className="pr-pagination"><button type="button" disabled={!docOffset} onClick={()=>setDocOffset(Math.max(0,docOffset-50))}>上一页资料</button><button type="button" disabled={docNext===null} onClick={()=>docNext!==null&&setDocOffset(docNext)}>下一页资料</button></div></div></fieldset>
          <button className="pr-primary" disabled={busy||(!pending&&(!title.trim()||question.trim().length<10||!executionReady(execution)))}>{busy?'正在保存…':pending?'核对并恢复原提交':'保存并准备草稿'}</button><p className="pr-footnote">保存项目、问题、所选资料和研究配置。准备完成后会显示资料版本与截止时点，供你确认启动。</p>
      </form>}</section></div></>)}
    </main></div>;
}
