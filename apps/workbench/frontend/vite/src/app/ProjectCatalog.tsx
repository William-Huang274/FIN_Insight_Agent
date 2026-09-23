import {useEffect,useState} from 'react';
import {useSearchParams} from 'react-router';
import {ArrowLeft,FileText,FolderOpen,Plus} from 'lucide-react';
import {assetRequest,type AssetVersion} from '../api/assetWorkspace';
import ProjectAssetWorkspace from './ProjectAssetWorkspace';
import {projectUrl} from './ProjectNavigation';
import {useWorkspaceProjects,type WorkspaceProject} from './workspaceProjects';

type Row={project_id:string;project_name:string;project_archived:boolean;kind:string;asset_id:string;current:AssetVersion;version_count:number};
export function ProjectCatalog({project,role=''}:{project?:WorkspaceProject;role?:string}){
  const [params,setParams]=useSearchParams(),projects=useWorkspaceProjects();
  const scope=project?.id||params.get('scope')||'',query=params.get('q')||'',kind=role||params.get('kind')||'';
  const offset=Math.max(0,Number(params.get('offset'))||0),reader=params.get('asset'),readerProject=project?.id||params.get('project');
  const [rows,setRows]=useState<Row[]>([]),[next,setNext]=useState<number|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [search,setSearch]=useState(query),[revision,refresh]=useState(0);
  useEffect(()=>setSearch(query),[query]);
  useEffect(()=>{let alive=true;setRows([]);setNext(null);setError('');if(reader)return;setBusy(true);
    const queryParams=new URLSearchParams({query,role:kind,offset:String(offset),limit:'30'});if(scope)queryParams.set('project_id',scope);
    assetRequest<{items:Row[];next_offset:number|null}>(`asset-workspace/catalog?${queryParams}`).then(v=>{if(alive){setRows(v.items);setNext(v.next_offset);}}).catch(e=>alive&&setError(e.message)).finally(()=>alive&&setBusy(false));return()=>{alive=false;};
  },[scope,query,kind,offset,reader,revision]);
  const filter=(key:string,value:string)=>setParams(p=>{value?p.set(key,value):p.delete(key);p.delete('offset');return p;});
  const back=()=>setParams(p=>{p.delete('asset');p.delete('context');p.delete('assistant');if(!project)p.delete('project');return p;});
  if(reader&&readerProject)return <><div className="pw-reader-back"><button onClick={back}><ArrowLeft size={16}/>{project?'返回项目资料':'返回资料库'}</button></div><ProjectAssetWorkspace key={readerProject} projectLocked/></>;
  return <section className="pw-catalog">
    <form className="pw-toolbar" onSubmit={e=>{e.preventDefault();filter('q',search);}}>
      {!project&&<select aria-label="按项目筛选资料" value={scope} onChange={e=>filter('scope',e.target.value)}><option value="">全部项目</option>{projects.index.projects.map(p=><option key={p.id} value={p.id}>{p.name}{p.archived?'（已归档）':''}</option>)}</select>}
      <input aria-label="搜索资料名称" placeholder="搜索当前范围内的资料" maxLength={200} value={search} onChange={e=>setSearch(e.target.value)}/><button>搜索</button>
      {!role&&<select aria-label="资料类型" value={kind} onChange={e=>filter('kind',e.target.value)}><option value="">全部类型</option><option value="document">资料与笔记</option><option value="report">研究成果</option><option value="database">数据快照</option></select>}
      {(query||(!project&&scope)||(!role&&kind))&&<button type="button" onClick={()=>setParams(p=>{['scope','q','kind','offset'].forEach(k=>p.delete(k));return p;})}>清除筛选</button>}
    </form>
    {(error||projects.error)&&<p role="alert">{error||projects.error} <button onClick={()=>{void projects.reload();refresh(n=>n+1);}}>重新读取</button></p>}
    {busy?<p role="status">正在读取资料目录…</p>:<div className="pw-panel">{rows.map(row=><a className="pw-row" key={`${row.project_id}:${row.kind}:${row.asset_id}`} href={(()=>{const p=new URLSearchParams(params);p.set('project',row.project_id);p.set('asset',row.current.ref.version_id);return `${location.pathname}?${p}`;})()}><FileText size={19}/><span><strong>{row.current.title}</strong><small>{row.project_name}{row.project_archived?' · 已归档':''} · v{row.current.sequence} · {new Date(row.current.created_at).toLocaleDateString('zh-CN')}{row.current.access_status!=='active'?' · 使用受限':''}</small></span><span>阅读 →</span></a>)}{!rows.length&&!error&&<p className="pw-empty">当前范围内没有匹配的资料。</p>}</div>}
    <div className="pw-toolbar"><button disabled={!offset||busy} onClick={()=>setParams(p=>{p.set('offset',String(Math.max(0,offset-30)));return p;})}>上一页</button><span className="pw-muted">第 {Math.floor(offset/30)+1} 页</span><button disabled={next===null||busy} onClick={()=>setParams(p=>{p.set('offset',String(next));return p;})}>下一页</button></div>
    {project?<div className="pw-toolbar"><a href={`/workspace/session?view=project&project=${project.id}`}><Plus size={15}/>上传与管理资料</a><a href={`/workspace/assets?view=files&scope=${project.id}&return_project=${project.id}`}><FolderOpen size={15}/>在全局资料库中查看</a></div>:<p className="pw-muted">按原项目归属展示资料，阅读与编辑沿用原文件版本。{params.get('return_project')&&<a href={projectUrl(params.get('return_project')!,'files')}> 返回原项目</a>}</p>}
  </section>;
}
