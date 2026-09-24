import {useEffect,useRef,useState} from 'react';
import {useSearchParams} from 'react-router';
import {businessRequest} from '../api/businessResearch';
import {ProjectNavigation,projectUrl} from './ProjectNavigation';
import {intentId,finishIntent} from './ResourceWorkspace';

type Organization={id:string;name:string;role:string};
type Project={id:string;organization_id:string;organization_name:string;name:string;description:string;archived:boolean;revision:number;role:string;can_manage:boolean;research_enabled?:boolean};
type Member={subject:string;display_name:string;role:string;organization_admin?:boolean;active?:boolean};
const roles:Record<string,string>={manager:'项目管理员',researcher:'研究成员',viewer:'只读成员'};
const path=(id='')=>'workspaces/projects'+(id?'/'+id:'');
const url=(id:string,view='overview')=>projectUrl(id,view,'organization');

export function OrganizationProjectHub(){
  const [enabled,setEnabled]=useState(false),[organizations,setOrganizations]=useState<Organization[]>([]),[rows,setRows]=useState<Project[]>([]);
  const [org,setOrg]=useState(''),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[archived,setArchived]=useState(false),[offset,setOffset]=useState(0),[next,setNext]=useState<number|null>(null);
  const [error,setError]=useState(''),[loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[revision,refresh]=useState(0);
  const [name,setName]=useState(''),[description,setDescription]=useState(''),[target,setTarget]=useState(''),[createError,setCreateError]=useState('');
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{let alive=true;businessRequest<{organization_projects?:boolean}>('config').then(async c=>{if(!alive)return;setEnabled(!!c.organization_projects);if(c.organization_projects){const v=await businessRequest<{organizations:Organization[]}>('workspaces');if(alive)setOrganizations(v.organizations);}}).catch(e=>alive&&setError(e.message));return()=>{alive=false;};},[revision]);
  useEffect(()=>{let alive=true;if(!enabled)return;setRows([]);setNext(null);setError('');setLoading(true);const q=new URLSearchParams({query,archived:String(archived),offset:String(offset)});if(org)q.set('organization_id',org);
    businessRequest<{items:Project[];next_offset:number|null}>(path()+'?'+q).then(v=>{if(alive){setRows(v.items);setNext(v.next_offset);}}).catch(e=>alive&&setError(e.message)).finally(()=>alive&&setLoading(false));return()=>{alive=false;};
  },[enabled,org,query,archived,offset,revision]);
  const admins=organizations.filter(o=>o.role==='admin');
  async function create(){setBusy(true);setCreateError('');try{const body={organization_id:target,name:name.trim(),description:description.trim()};const id=intentId('create-organization-project',body);const p=await businessRequest<Project>(path(),'POST',{...body,id});finishIntent('create-organization-project');window.location.assign(url(p.id));}catch(e){setCreateError((e as Error).message+' 可保留相同内容重试，或关闭后刷新列表核对。');}finally{setBusy(false);}}
  if(!enabled&&!error)return null;
  return <section aria-label="组织项目"><header className="pw-title"><div><h2>组织项目</h2><p>按组织归属管理项目和成员。</p></div>{admins.length>0&&<button onClick={()=>{setName('');setDescription('');setCreateError('');setTarget(admins.find(o=>o.id===org)?.id||admins[0].id);dialog.current?.showModal();}}>新建组织项目</button>}</header>
    {error&&<p role="alert">{error} <button onClick={()=>refresh(n=>n+1)}>重新读取组织项目</button></p>}
    <form className="pw-toolbar" onSubmit={e=>{e.preventDefault();setQuery(search);setOffset(0);}}><select aria-label="按组织筛选项目" value={org} onChange={e=>{setOrg(e.target.value);setOffset(0);}}><option value="">全部组织</option>{organizations.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select><input aria-label="搜索组织项目" maxLength={200} placeholder="搜索项目名称或说明" value={search} onChange={e=>setSearch(e.target.value)}/><button>搜索组织项目</button><select aria-label="组织项目状态" value={archived?'archived':'active'} onChange={e=>{setArchived(e.target.value==='archived');setOffset(0);}}><option value="active">进行中</option><option value="archived">已归档</option></select></form>
    {loading&&<p role="status">正在读取组织项目…</p>}<div className="pw-grid">{rows.map(p=><article className="pw-card" key={p.id}><small>{p.organization_name} · {roles[p.role]}</small><h2><a href={url(p.id)}>{p.name}</a></h2><p>{p.description||'尚未填写项目说明'}</p><footer><a href={url(p.id)}>进入项目 →</a><a href={url(p.id,'settings')}>项目与成员</a></footer></article>)}</div>
    {!loading&&!error&&!rows.length&&<p className="pw-empty">当前范围内没有可访问的组织项目。</p>}<div className="pw-toolbar"><button disabled={!offset||loading} onClick={()=>setOffset(Math.max(0,offset-30))}>上一页组织项目</button><button disabled={next===null||loading} onClick={()=>next!==null&&setOffset(next)}>下一页组织项目</button><a href="/workspace/assets?view=all-resources">组织与空间管理</a></div>
    <dialog ref={dialog} className="pw-dialog" aria-label="新建组织项目"><h2>新建组织项目</h2><form className="pw-settings" onSubmit={e=>{e.preventDefault();void create();}}><label>所属组织<select required value={target} onChange={e=>setTarget(e.target.value)}>{admins.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label><label>组织项目名称<input required maxLength={60} value={name} onChange={e=>setName(e.target.value)}/></label><label>组织项目说明<textarea maxLength={500} value={description} onChange={e=>setDescription(e.target.value)}/></label><p className="pw-muted">项目归所选组织管理。成员由项目管理员添加；现有个人项目与资料不会自动转入。</p>{createError&&<p role="alert">{createError}</p>}<div className="pw-toolbar"><button disabled={busy||!target||!name.trim()}>创建组织项目</button><button type="button" disabled={busy} onClick={()=>dialog.current?.close()}>取消</button></div></form></dialog>
  </section>;
}

export function OrganizationProjectPage(){
  const [params]=useSearchParams(),id=params.get('project')||'',view=params.get('view')||'overview';
  const [project,setProject]=useState<Project|null>(null),[members,setMembers]=useState<Member[]>([]),[candidates,setCandidates]=useState<Member[]>([]);
  const [error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[revision,refresh]=useState(0);
  const [name,setName]=useState(''),[description,setDescription]=useState(''),[subject,setSubject]=useState(''),[role,setRole]=useState('viewer');
  const generation=useRef(0),operation=useRef(false);
  useEffect(()=>{let alive=true;const current=++generation.current;setLoading(true);setError('');setProject(null);setMembers([]);setCandidates([]);
    (async()=>{if(!id)throw Error('请选择一个组织项目。');const config=await businessRequest<{organization_projects?:boolean}>('config');if(!config.organization_projects)throw Error('当前部署尚未启用组织项目。');
      const p=await businessRequest<Project>(path(id));
      const [m,c]=await Promise.all([businessRequest<Member[]>(path(id)+'/members'),p.can_manage?businessRequest<Member[]>(`workspaces/organizations/${p.organization_id}/members`):Promise.resolve([])]);
      if(alive&&generation.current===current){setProject(p);setMembers(m);setCandidates(c.filter(x=>x.active&&x.role!=='admin'));setName(p.name);setDescription(p.description);setSubject('');}
    })().catch(e=>alive&&setError(e.message)).finally(()=>alive&&setLoading(false));return()=>{alive=false;};
  },[id,revision]);
  async function mutate(suffix:string,body:unknown){if(operation.current)return;operation.current=true;setBusy(true);setMessage('');setError('');try{await businessRequest(path(id)+suffix,'POST',body);setMessage('已保存。');refresh(n=>n+1);}catch(e){setError((e as Error).message+' 请先重新读取，核对后再提交。');}finally{operation.current=false;setBusy(false);}}
  const pending=!['overview','settings'].includes(view);
  return <div className="fs-workspace pw-shell" data-theme={localStorage.getItem('finsight.theme')||'system'}><ProjectNavigation project={project||undefined} projects={project?[project]:[]} view={view} scope="organization"/><main className="pw-main"><header className="pw-top"><a href="/workspace/projects">所有项目</a>{project&&<><span>/</span><span>{project.organization_name}</span><span>/</span><a href={url(id)}>{project.name}</a></>}</header><div className="pw-content">
    {loading&&<p role="status">正在读取组织项目…</p>}{error&&<p role="alert">{error} <button disabled={busy} onClick={()=>refresh(n=>n+1)}>重新读取项目</button></p>}{message&&<p role="status">{message}</p>}
    {project&&<><header className="pw-title"><div><h1>{view==='settings'?'项目管理':project.name}</h1><p>{project.organization_name} · {roles[project.role]}{project.archived?' · 已归档':''}</p></div><button disabled={busy} onClick={()=>refresh(n=>n+1)}>刷新项目</button></header>
      {pending?<section className="pw-card"><h2>{{files:'项目资料关联',research:'团队研究',results:'项目成果'}[view]||'后续项目功能'}</h2><p>此组织项目尚未开放这项功能。项目资料关联、研究使用权限与成果范围将在后续阶段接入。</p><a href={url(id)}>返回项目概览</a></section>:view==='overview'?<div className="pw-grid"><section className="pw-card"><h2>项目目标</h2><p>{project.description||'尚未填写项目说明'}</p><a href={url(id,'settings')}>查看项目与成员 →</a></section><section className="pw-card"><h2>协作范围</h2><p>当前可查看项目的成员：{members.length} 人。</p><p>项目成员资格不自动授予团队空间或个人资料权限。</p><p>研究与资料接入将在后续阶段开放。</p></section></div>:<>
        <section className="pw-card"><h2>项目信息</h2>{project.can_manage?<form className="pw-settings" onSubmit={e=>{e.preventDefault();void mutate('',{revision:project.revision,name:name.trim(),description:description.trim(),archived:project.archived});}}><label>项目名称<input required maxLength={60} value={name} onChange={e=>setName(e.target.value)}/></label><label>项目说明<textarea maxLength={500} value={description} onChange={e=>setDescription(e.target.value)}/></label><div className="pw-toolbar"><button disabled={busy||!name.trim()} className="pw-primary">保存修改</button><button type="button" disabled={busy} onClick={()=>{if(window.confirm(project.archived?'恢复这个项目？':'归档这个项目？成员权限和项目记录会保留。'))void mutate('',{revision:project.revision,name:project.name,description:project.description,archived:!project.archived});}}>{project.archived?'恢复项目':'归档项目'}</button></div></form>:<><p>{project.name}</p><p>{project.description||'尚未填写项目说明'}</p><p>项目信息和成员由项目管理员维护。</p></>}</section>
        <section className="pw-panel op-members"><header><h2>项目成员</h2></header>{members.map(m=><div className="pw-row" key={m.subject}><span><strong>{m.display_name}</strong><small>{roles[m.role]}{m.organization_admin?' · 组织管理员':''}</small></span>{project.can_manage&&!m.organization_admin&&<button disabled={busy} onClick={()=>{if(window.confirm(`将 ${m.display_name} 移出项目？其项目访问权限将失效。`))void mutate('/members',{revision:project.revision,subject:m.subject,role:'remove'});}}>移出项目</button>}</div>)}</section>
        {project.can_manage&&<section className="pw-card"><h2>添加或调整成员</h2><form className="pw-toolbar" onSubmit={e=>{e.preventDefault();void mutate('/members',{revision:project.revision,subject,role});}}><select required aria-label="选择项目成员" value={subject} onChange={e=>{setSubject(e.target.value);setRole(members.find(m=>m.subject===e.target.value)?.role||'viewer');}}><option value="">选择当前组织成员</option>{candidates.map(m=><option key={m.subject} value={m.subject}>{m.display_name}</option>)}</select><select aria-label="项目成员角色" value={role} onChange={e=>setRole(e.target.value)}>{Object.entries(roles).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select><button disabled={busy||!subject}>保存成员权限</button></form><p className="pw-muted">项目管理员维护信息与成员；研究成员预留研究操作资格，只读成员预留阅读资格。本阶段三种角色均不开放团队研究。组织管理员保留管理权限。</p></section>}
      </>}
    </>}{!loading&&!project&&<a href="/workspace/projects">返回项目列表</a>}
  </div></main></div>;
}
