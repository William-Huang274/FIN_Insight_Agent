import {useEffect,useState} from 'react';
import {assetRequest,type AssetRef,type AssetVersion} from '../api/assetWorkspace';

type Status={supported:boolean;revision:number;active_revision:number;pending:boolean;notice:string;
  items:{ref:AssetRef;title:string;current:AssetVersion|null;has_newer:boolean}[];
  history:{revision:number;state:string;created_at:string}[];
  adoptions:{run:string;revision:number;recorded_at:string}[]};

export function TaskAssetUpdates({thread,selected,refreshKey,surface='research-sessions'}:{thread:string;selected:AssetVersion|null;refreshKey:number;surface?:'research-sessions'|'conversations'}){
  const [status,setStatus]=useState<Status|null>(null),[error,setError]=useState(''),[saving,setSaving]=useState(false),[version,setVersion]=useState(0);
  useEffect(()=>{let alive=true;const read=()=>void assetRequest<Status>(`${surface}/${thread}/asset-updates`)
    .then(r=>{if(alive){setStatus(r);setError('');}}).catch(e=>{if(alive)setError(e.message);});
    read();const timer=setInterval(read,10000);window.addEventListener('focus',read);
    return()=>{alive=false;clearInterval(timer);window.removeEventListener('focus',read);};
  },[thread,refreshKey,version,surface]);
  const target=status?.items?.find(r=>selected&&r.ref.project_id===selected.ref.project_id&&r.ref.kind===selected.ref.kind&&r.ref.asset_id===selected.ref.asset_id);
  const changed=target&&selected&&target.ref.version_id!==selected.ref.version_id;
  async function apply(){if(!status||!selected||saving)return;setSaving(true);setError('');
    try{await assetRequest(`${surface}/${thread}/asset-updates`,'POST',{request_id:crypto.randomUUID(),base_revision:status.revision,ref:selected.ref});setVersion(n=>n+1);}
    catch(e){setError(e instanceof Error?e.message:'提交未确认，请刷新查看记录');}finally{setSaving(false);}}
  async function abandon(revision:number){setSaving(true);setError('');
    try{await assetRequest(`${surface}/${thread}/asset-updates/${revision}/abandon`,'POST');setVersion(n=>n+1);}
    catch(e){setError(e instanceof Error?e.message:'未能放弃准备，请刷新检查');}finally{setSaving(false);}}
  if(!status?.supported&&!error)return null;
  return <section className="fp-update" aria-label="任务资料更新">
    {error&&<p role="alert">{error}</p>}
    {status?.supported&&<><strong>{status.pending?`输入 r${status.revision} 已保存，待下次运行采用`:`当前任务输入 r${status.active_revision}`}</strong>
      {status.items.some(r=>r.has_newer)&&<p>项目资料有新版本。选择并阅读后，可明确提交给此任务。</p>}
      {changed&&<button disabled={saving||selected?.access_status!=='active'} onClick={()=>void apply()}>{saving?'正在保存…':`下次运行采用所选 v${selected?.sequence}`}</button>}
      {status.revision>0&&<p>旧结果保留；采用资料不代表已完成影响复核。</p>}
      <details><summary>采用规则与记录</summary><p>{status.notice}</p>
        {status.items.map(r=><p key={`${r.ref.kind}:${r.ref.asset_id}`}>{r.title} · 已选版本 {r.ref.version_id.slice(-8)}</p>)}
        {status.history.map(r=><div key={r.revision}><p>输入 r{r.revision} · {({ready:'准备完成',preparing:'准备中',failed:'准备失败',abandoned:'已放弃准备'} as Record<string,string>)[r.state]||r.state}</p>{r.state==='preparing'&&<button disabled={saving} onClick={()=>void abandon(r.revision)}>放弃未完成的准备 r{r.revision}</button>}</div>)}
        {status.adoptions.filter(r=>r.revision>0).map(r=><p key={r.run}>已采用 r{r.revision} · {new Date(r.recorded_at).toLocaleString()} · 运行 {r.run.slice(-8)}</p>)}
      </details></>}
  </section>;
}
