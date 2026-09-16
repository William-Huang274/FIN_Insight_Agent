import {useEffect,useRef,useState} from 'react';
import {X} from 'lucide-react';
import {assetRequest as request} from '../api/assetWorkspace';

export type CaptureSelection={kind:'library';document_id:string;snapshot:string;section_ids:string[]}|{kind:'financial';query:Record<string,unknown>;snapshot:string;row_ids:string[]};

export function AssetCaptureDialog({selection,initialTitle,summary,onClose}:{selection:CaptureSelection;initialTitle:string;summary:string;onClose:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [projects,setProjects]=useState<{id:string;name:string}[]>([]),[project,setProject]=useState('');
  const [title,setTitle]=useState(initialTitle.slice(0,120)),[note,setNote]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState('');
  useEffect(()=>{dialog.current?.showModal();let alive=true;void request<{projects:{id:string;name:string}[]}>('projects').then(r=>{if(alive){setProjects(r.projects);setProject(r.projects[0]?.id||'');}}).catch(e=>{if(alive)setError(e.message);});return()=>{alive=false;};},[]);
  async function save(){setBusy(true);setError('');try{const result=await request<{document_id:string}>('asset-workspace/captures','POST',{project_id:project,title,note,selection});setSaved(result.document_id);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <dialog ref={dialog} className="dl-capture-dialog" aria-label="保存来源到项目" onCancel={e=>{if(busy)e.preventDefault();else onClose();}}>
    <header><h2>{saved?'已保存到项目':'加入项目'}</h2><button disabled={busy} aria-label="关闭保存来源" onClick={onClose}><X size={18}/></button></header>
    <p>{summary}</p><p className="dl-capture-hint">保存所选内容的固定版本。批注属于你的判断，原文与财务原值保持不变。</p>
    {error&&<p role="alert">{error}</p>}
    {saved?<div role="status"><p>来源与批注已保存，可在研究侧栏阅读或用于新研究。</p><a href={`/workspace/assets?view=project&project=${project}&asset=${encodeURIComponent(saved)}`}>打开已保存资产 →</a><button onClick={onClose}>继续浏览</button></div>:<form onSubmit={e=>{e.preventDefault();void save();}}>
      <label>保存到项目<select aria-label="来源目标项目" disabled={busy} value={project} onChange={e=>setProject(e.target.value)}><option value="">选择项目</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      {!projects.length&&<p>先在<a href="/workspace/session">研究工作台</a>创建一个项目，再保存资料。</p>}
      <label>资产名称<input aria-label="来源资产名称" disabled={busy} maxLength={120} value={title} onChange={e=>setTitle(e.target.value)}/></label>
      <label>我的批注<textarea aria-label="来源批注" disabled={busy} maxLength={10000} value={note} onChange={e=>setNote(e.target.value)} placeholder="为什么保存这份资料？有哪些需要继续核验的判断？"/></label>
      <footer><button type="button" disabled={busy} onClick={onClose}>取消</button><button disabled={busy||!project||!title.trim()} type="submit">{busy?'正在保存…':'保存到项目'}</button></footer>
    </form>}
  </dialog>;
}
