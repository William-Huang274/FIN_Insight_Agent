import {useEffect,useRef,useState} from 'react';
import {useSearchParams} from 'react-router';
import {FolderOpen,Plus,RefreshCw} from 'lucide-react';
import {sessionsApi,type Session} from '../api/reportSessions';
import {businessRequest,type BusinessTask} from '../api/businessResearch';
import {useWorkspaceProjects} from './workspaceProjects';
import {ProjectNavigation,projectUrl} from './ProjectNavigation';
import {ProjectCatalog} from './ProjectCatalog';
import ProjectResearchWorkspace from './ProjectResearchWorkspace';
import {isResearchComplete,sessionStatus} from './WorkspaceNavigation';
import {OrganizationProjectPage,OrganizationProjectHub} from './OrganizationProjects';
import './research-session.css';
import './workspace-design.css';

export default function ProjectWorkspace(){
  const [params]=useSearchParams();
  return params.get('scope')==='organization'?<OrganizationProjectPage key={params.get('project')||''}/>:<PersonalProjectWorkspace/>;
}

function PersonalProjectWorkspace(){
  const projects=useWorkspaceProjects(),[params,setParams]=useSearchParams();
  const id=params.get('project')||'',view=params.get('task')?'intake':params.get('view')||'overview';
  const selected=projects.index.projects.find(p=>p.id===id);
  const [query,setQuery]=useState(''),[sort,setSort]=useState('name'),[archived,setArchived]=useState(false);
  const [name,setName]=useState(''),[description,setDescription]=useState(''),[message,setMessage]=useState('');
  const [sessions,setSessions]=useState<Session[]>([]),[nativeError,setNativeError]=useState('');
  const [business,setBusiness]=useState<BusinessTask[]>([]),[businessError,setBusinessError]=useState(''),[enabled,setEnabled]=useState<boolean|null>(null);
  const [configError,setConfigError]=useState('');
  const [loading,setLoading]=useState(false),[revision,refresh]=useState(0),[offset,setOffset]=useState(0),[next,setNext]=useState<number|null>(null);
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{setName(selected?.name||'');setDescription(selected?.description||'');},[id,selected?.name,selected?.description]);
  useEffect(()=>{setMessage('');setOffset(0);},[id]);
  useEffect(()=>{let alive=true;setNativeError('');sessionsApi.list().then(s=>alive&&setSessions(s)).catch(e=>alive&&setNativeError(e.message));return()=>{alive=false;};},[revision]);
  useEffect(()=>{let alive=true;setConfigError('');businessRequest<{enabled:boolean}>('config').then(c=>alive&&setEnabled(c.enabled)).catch(e=>alive&&setConfigError(e.message));return()=>{alive=false;};},[revision]);
  useEffect(()=>{let alive=true;setBusiness([]);setNext(null);setBusinessError('');setLoading(false);if(!selected||!enabled)return;setLoading(true);
    businessRequest<{items:BusinessTask[];next_offset:number|null}>(`tasks?project_id=${id}&offset=${offset}`).then(v=>{if(alive){setBusiness(v.items);setNext(v.next_offset);}}).catch(e=>alive&&setBusinessError(e.message)).finally(()=>alive&&setLoading(false));return()=>{alive=false;};
  },[id,!!selected,enabled,offset,revision]);
  const native=sessions.filter(s=>projects.index.assignments[s.thread_id]===id);
  const nativeById=new Map(sessions.map(s=>[s.thread_id,s]));
  const businessThreads=new Set([...business.map(t=>t.thread_id),...native.filter(s=>s.business_task_id&&enabled).map(s=>s.thread_id)]);
  const complete=native.filter(isResearchComplete);
  const href=(s:Session)=>`/workspace/session?${new URLSearchParams({thread:s.thread_id,view:isResearchComplete(s)?'report':'activity',project:id})}`;
  const save=async()=>{if(!selected||!name.trim())return;const ok=await projects.update({...projects.index,projects:projects.index.projects.map(p=>p.id===id?{...p,name:name.trim(),description:description.trim()}:p)});if(ok)setMessage('项目设置已保存。');};
  const create=async()=>{if(!name.trim())return;const key=crypto.randomUUID();if(await projects.update({...projects.index,projects:[...projects.index.projects,{id:key,name:name.trim(),description:description.trim(),archived:false}]})){dialog.current?.close();setParams({project:key});}};
  const archive=async()=>{if(!selected)return;if(await projects.update({...projects.index,projects:projects.index.projects.map(p=>p.id===id?{...p,archived:!p.archived}:p)}))setMessage(selected.archived?'项目已恢复。':'项目已归档，资料和研究仍然保留。');};
  const newResearch=enabled===false?`/workspace/session?view=project&project=${id}`:projectUrl(id,'intake');
  const researchRows=<>{business.map(t=>{const s=t.thread_id?nativeById.get(t.thread_id):undefined;const settled=t.start.status==='received';return <a className="pw-row" key={t.id} href={s&&settled?href(s):`${projectUrl(id,'intake')}&task=${t.id}`}><span><strong>{t.title}</strong><small>{new Date(t.created_at).toLocaleString('zh-CN')}</small></span><span>{s&&settled?sessionStatus(s):t.start.status==='unknown'||t.prepare.status==='unknown'?'提交结果待核对':settled?'运行已受理':t.prepare.status==='received'?'待确认启动':'草稿准备'}</span></a>;})}{offset===0&&native.filter(s=>!businessThreads.has(s.thread_id)).map(s=><a key={s.thread_id} className="pw-row" href={href(s)}><span><strong>{s.title}</strong><small>{s.updated_at?new Date(s.updated_at).toLocaleString('zh-CN'):'更新时间未记录'}</small></span><span>{sessionStatus(s)}</span></a>)}{!loading&&!business.length&&!native.length&&!nativeError&&!businessError&&<p className="pw-empty">这个项目还没有研究。</p>}</>;
  const visible=projects.index.projects.filter(p=>!!p.archived===archived&&`${p.name} ${p.description||''}`.toLowerCase().includes(query.toLowerCase()));
  if(sort==='name')visible.sort((a,b)=>a.name.localeCompare(b.name,'zh-CN'));else visible.reverse();
  return <div className="fs-workspace pw-shell" data-theme={localStorage.getItem('finsight.theme')||'system'}><ProjectNavigation project={selected} projects={projects.index.projects} view={view==='intake'?'research':view}/><main className="pw-main"><header className="pw-top"><a href="/workspace/projects">所有项目</a>{selected&&<><span>/</span><a href={projectUrl(id)}>{selected.name}</a><span>/</span><span>{{overview:'项目概览',research:'研究',files:'资料',results:'成果',settings:'项目管理',intake:'准备研究'}[view]}</span></>}</header><div className="pw-content">
    {projects.error&&<p role="alert">{projects.error} <button onClick={()=>void projects.reload()}>重新载入项目</button></p>}{message&&<p role="status">{message}</p>}
    {!projects.ready?<p role="status">正在读取项目…</p>:id&&!selected?<section><h1>此项目不存在或不可访问</h1><a href="/workspace/projects">返回项目列表</a></section>:!selected?<>
      <header className="pw-title"><div><h1>项目</h1><p>集中管理研究、资料与成果。</p></div><button className="pw-primary" onClick={()=>{setName('');setDescription('');dialog.current?.showModal();}}><Plus size={17}/>新建项目</button></header>
      <OrganizationProjectHub/>
      <h2>个人项目</h2><p className="pw-muted">现有个人项目保持原来的资料与研究访问范围。</p>
      <div className="pw-toolbar"><input aria-label="搜索项目" placeholder="搜索项目名称或说明" value={query} onChange={e=>setQuery(e.target.value)}/><select aria-label="项目状态" value={archived?'archived':'active'} onChange={e=>setArchived(e.target.value==='archived')}><option value="active">进行中的项目</option><option value="archived">已归档项目</option></select><select aria-label="项目排序" value={sort} onChange={e=>setSort(e.target.value)}><option value="name">按项目名称</option><option value="created">最近添加</option></select></div>
      <div className="pw-grid">{visible.map(p=><article className="pw-card" key={p.id}><FolderOpen size={22}/><h2><a href={projectUrl(p.id)}>{p.name}</a></h2><p>{p.description||'尚未填写项目说明'}</p><footer><a href={projectUrl(p.id,'research')}>研究</a><a href={projectUrl(p.id,'files')}>资料</a><a href={projectUrl(p.id,'results')}>成果</a><a href={projectUrl(p.id)}>进入项目 →</a></footer></article>)}</div>{!visible.length&&<p className="pw-empty">{projects.index.projects.length?'没有符合条件的项目。':'创建一个项目，开始整理研究与资料。'}</p>}
    </>:<>
      <header className="pw-title"><div><h1>{view==='overview'?selected.name:{research:'项目研究',files:'项目资料',results:'项目成果',settings:'项目管理',intake:'准备一项研究'}[view]||selected.name}</h1><p>{selected.archived?'已归档 · 研究与资料仍然保留':view==='overview'?selected.description||'围绕项目目标推进研究。':selected.name}</p></div>{view!=='settings'&&view!=='intake'&&!selected.archived&&<a className="pw-primary" href={newResearch}><Plus size={17}/>新建研究</a>}</header>
      {view==='intake'?<ProjectResearchWorkspace embedded/>:view==='files'?<ProjectCatalog project={selected}/>:view==='settings'?<div className="pw-card"><form className="pw-settings" onSubmit={e=>{e.preventDefault();void save();}}><label>项目名称<input maxLength={60} required value={name} onChange={e=>setName(e.target.value)}/></label><label>项目说明<textarea maxLength={500} value={description} onChange={e=>setDescription(e.target.value)}/></label><div className="pw-toolbar"><button className="pw-primary" disabled={projects.saving||!name.trim()}>保存修改</button><button type="button" disabled={projects.saving} onClick={()=>void archive()}>{selected.archived?'恢复项目':'归档项目'}</button></div></form><p className="pw-muted">归档用于整理项目，不删除资料、不停止已有研究，也不改变访问权限。成员分工与报告审批将在后续阶段接入。</p></div>:<>
        {(nativeError||businessError||configError)&&<p role="alert">部分研究记录读取失败：{nativeError||businessError||configError} <button onClick={()=>refresh(n=>n+1)}>重新读取</button></p>}
        <p className="pw-muted">原有研究按最近 50 条记录显示；业务提交记录可翻页查看。</p>
        {view==='results'?<><section className="pw-panel"><header><h2>已完成研究</h2></header>{complete.map(s=><a key={s.thread_id} className="pw-row" href={href(s)}><span>{s.title}</span><span>打开报告 →</span></a>)}{!complete.length&&!nativeError&&<p className="pw-empty">暂无已完成研究。</p>}</section><h2>保存的研究成果</h2><ProjectCatalog project={selected} role="report"/></>:<><section className="pw-panel"><header><h2>{view==='overview'?'继续推进':'研究记录'}</h2><button onClick={()=>refresh(n=>n+1)}><RefreshCw size={15}/>刷新</button></header>{loading&&<p role="status">正在读取研究…</p>}{researchRows}</section>{enabled&&<div className="pw-toolbar"><button disabled={!offset||loading} onClick={()=>setOffset(Math.max(0,offset-50))}>上一页研究</button><button disabled={next===null||loading} onClick={()=>next!==null&&setOffset(next)}>下一页研究</button></div>}{view==='overview'&&<><h2>项目资料</h2><ProjectCatalog project={selected}/></>}</>}
      </>}
    </>}
    <dialog ref={dialog} className="pw-dialog" aria-label="新建项目"><h2>新建项目</h2><form className="pw-settings" onSubmit={e=>{e.preventDefault();void create();}}><label>项目名称<input autoFocus required maxLength={60} value={name} onChange={e=>setName(e.target.value)}/></label><label>项目说明<textarea maxLength={500} value={description} onChange={e=>setDescription(e.target.value)}/></label>{projects.error&&<p role="alert">{projects.error}</p>}<div className="pw-toolbar"><button disabled={projects.saving||!name.trim()} className="pw-primary">创建项目</button><button type="button" disabled={projects.saving} onClick={()=>dialog.current?.close()}>取消</button></div></form></dialog>
  </div></main></div>;
}
