import {useEffect,useRef,useState} from 'react';
import {ArrowUpRight,FileText,FolderOpen,RefreshCw,X} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {assetRequest as request,type Asset,type AssetVersion,type SourceCapture} from '../api/assetWorkspace';
import './project-assets-panel.css';
import {CapturedFinancialTable} from './SourceCapturePanel';
import {TaskAssetUpdates} from './TaskAssetUpdates';

export function ProjectAssetsPanel({projects,initialProject,thread,onClose}:{projects:{id:string;name:string}[];initialProject:string;thread:string;onClose:()=>void}){
  const [project,setProject]=useState(initialProject||projects[0]?.id||'');
  const [assets,setAssets]=useState<Asset[]>([]),[selected,setSelected]=useState<AssetVersion|null>(null);
  const [reading,setReading]=useState<{capture?:SourceCapture;text:string;editable:boolean;truncated:boolean;concepts?:{label:string;tag:string}[]}|null>(null);
  const [error,setError]=useState(''),[loading,setLoading]=useState(false),[revision,refresh]=useState(0);
  const close=useRef<HTMLButtonElement>(null);
  const lastSelection=useRef<{project:string;asset:string}|null>(null);
  if(selected)lastSelection.current={project,asset:selected.ref.asset_id};
  useEffect(()=>{close.current?.focus();const escape=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose();};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape);},[onClose]);
  useEffect(()=>{const focus=()=>refresh(n=>n+1);window.addEventListener('focus',focus);return()=>window.removeEventListener('focus',focus);},[]);
  useEffect(()=>{let alive=true;setLoading(true);setError('');setReading(null);setSelected(null);
    if(!project){setAssets([]);setLoading(false);return;}
    void request<{items:Asset[]}>(`asset-workspace/projects/${project}`).then(r=>{if(alive){setAssets(r.items);const previous=lastSelection.current;setSelected((previous?.project===project?r.items.find(a=>a.asset_id===previous.asset):undefined)?.current||r.items[0]?.current||null);}}).catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};
  },[project,revision]);
  useEffect(()=>{let alive=true;setReading(null);if(!selected)return;setLoading(true);setError('');void request<NonNullable<typeof reading>>('asset-workspace/read','POST',selected.ref).then(r=>{if(alive)setReading(r);}).catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};},[selected]);
  const group=assets.find(a=>a.asset_id===selected?.ref.asset_id&&a.kind===selected?.ref.kind);
  const editor=new URLSearchParams({view:'project',project,...(selected?{asset:selected.ref.version_id}:{}),...(thread?{return_thread:thread}:{})});
  return <aside className="fa-project-panel" aria-label="项目资料侧栏"><header><div><FolderOpen size={18}/><strong>项目资料</strong></div><button ref={close} aria-label="关闭项目资料侧栏" onClick={onClose}><X size={18}/></button></header>
    <div className="fp-controls"><select aria-label="侧栏项目" value={project} onChange={e=>setProject(e.target.value)}><option value="">选择项目</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><button aria-label="重新读取项目资料" onClick={()=>refresh(n=>n+1)}><RefreshCw size={16}/></button></div>
    <div className="fp-links"><a href={`/workspace/assets?${editor}`}>在资产区打开与编辑 <ArrowUpRight size={14}/></a>{project&&<a href={`/workspace/session?view=project&project=${project}`}>导入与管理</a>}</div>
    {error&&<p className="fp-error" role="alert">{error}</p>}{loading&&<p className="fp-status" role="status">正在读取项目资料…</p>}
    <div className="fp-list" aria-label="项目文件列表">{assets.map(a=><button key={`${a.kind}:${a.asset_id}`} aria-pressed={a.asset_id===selected?.ref.asset_id} onClick={()=>setSelected(a.current)}><FileText size={15}/><span>{a.current.title}<small>v{a.current.sequence}{a.current.access_status!=='active'?' · 使用受限':''}</small></span></button>)}{!assets.length&&!loading&&<p>此项目暂无保存资料。可在管理页导入或到资产区新建笔记。</p>}</div>
    {thread&&<TaskAssetUpdates thread={thread} selected={selected} refreshKey={revision}/>}
    {selected&&<><div className="fp-reading-title"><strong>{selected.title}</strong><select aria-label="侧栏资料版本" value={selected.ref.version_id} onChange={e=>setSelected(group?.versions.find(v=>v.ref.version_id===e.target.value)||null)}>{group?.versions.map(v=><option key={v.ref.version_id} value={v.ref.version_id}>v{v.sequence}{v===group.current?' · 当前':''}</option>)}</select></div>
      <article className="fp-reading" aria-label="侧栏资料正文">{reading?.truncated&&<p>仅显示部分正文，请到完整页面查看原件。</p>}{reading?.capture&&<p className="fp-capture-note">用户批注（非来源事实）：{reading.capture.note||'暂无批注'}</p>}{reading?.capture?.rows?<CapturedFinancialTable rows={reading.capture.rows}/>:reading?.concepts?<><p>已保存的 SEC 指标目录</p>{reading.concepts.map(c=><p key={c.tag}>{c.label} · {c.tag}</p>)}</>:<ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{img:()=>null}}>{reading?.text||''}</ReactMarkdown>}</article>
      <footer>浏览项目资料不会更改当前研究绑定的版本。</footer></>}
  </aside>;
}
