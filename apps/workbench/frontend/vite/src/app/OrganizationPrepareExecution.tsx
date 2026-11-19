import {useEffect,useRef,useState} from 'react';
import {ArrowRight} from 'lucide-react';
import {useSearchParams} from 'react-router';
import {assetRequest} from '../api/assetWorkspace';
import {browserOwner} from './IdentityBoundary';
import {OrganizationSourceSearch} from './OrganizationSourceSearch';

export function OrganizationPrepareExecution({project,draft,digest}:{project:string;draft:string;digest:string}){
  const [,setParams]=useSearchParams();const [rows,setRows]=useState<{execution_id:string;closed:boolean;preparation:string}[]>([]);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[mode,setMode]=useState('auto');
  const [continuous,setContinuous]=useState(false),[capabilitiesLoaded,setCapabilitiesLoaded]=useState(false),[delivery,setDelivery]=useState('answer');
  const [review,setReview]=useState(false);
  type ModelProfile = {execution_id: string; runtime_profile: string};
  const [profiles,setProfiles]=useState<ModelProfile[]>([]);
  const [selectedProfile,setSelectedProfile]=useState('');
  const [revision,refresh]=useState(0),[loaded,setLoaded]=useState(false);const operation=useRef(false),generation=useRef(0);
  const base=`organization-projects/${project}/research-drafts/${draft}`;
  const slot=`finsight:org-prepare:${browserOwner}:${project}:${draft}`;
  useEffect(()=>{
    let alive=true;
    setCapabilitiesLoaded(false);setSelectedProfile('');setProfiles([]);
    assetRequest<{on_demand:boolean; model_profiles?:boolean}>('organization-research-capabilities').then(async v=>{
      const available=v.on_demand && v.model_profiles ? await assetRequest<ModelProfile[]>(`${base}/model-profiles`) : [];
      if(alive){setContinuous(v.on_demand);setProfiles(available);setCapabilitiesLoaded(true);}
    }).catch(e=>alive&&setError(e.message));
    return()=>{alive=false;};
  },[base]);
  useEffect(()=>{let alive=true;++generation.current;setLoaded(false);setRows([]);setError('');assetRequest<typeof rows>(`${base}/executions`).then(v=>{if(alive){setRows(v);setLoaded(true);}}).catch(e=>alive&&setError(e.message));return()=>{alive=false;++generation.current;};},[base,revision]);
  function open(id:string){setParams(p=>{p.set('execution',id);p.set('view','research');p.delete('draft');return p;});}
  async function reconcile(id:string){if(operation.current)return;operation.current=true;setBusy(true);const current=generation.current;try{const v=await assetRequest<{status:string}>(`organization-projects/${project}/research/${id}/reconcile/preparation`,'POST',{});if(current!==generation.current)return;if(v.status==='received')open(id);else setError('准备结果仍待核对；不会创建第二项执行。');}catch(e){if(current===generation.current)setError((e as Error).message);}finally{operation.current=false;setBusy(false);}}
  async function prepare(existing?:string){if(operation.current)return;operation.current=true;setBusy(true);setError('');const current=generation.current;
    try{const prior=sessionStorage.getItem(slot);const body=prior?JSON.parse(prior):{execution_id:existing||profiles.find(p=>p.runtime_profile===selectedProfile)?.execution_id||crypto.randomUUID(),manifest_digest:digest,execution:{mode,model:'default',branch_ids:[],...(selectedProfile?{runtime_profile:selectedProfile}:{}),...(continuous?{delivery_intent:delivery,require_report_review:delivery==='report'&&review}:{})}};
      sessionStorage.setItem(slot,JSON.stringify(body));const result=await assetRequest<{status:string}>(`${base}/prepare`,'POST',body);
      if(current===generation.current){if(result.status==='received')open(body.execution_id);else{setRows([{execution_id:body.execution_id,closed:false,preparation:result.status}]);setError('准备结果尚未确认，请核对原准备结果。');}}
    }catch(e){if(current===generation.current)setError((e as Error).message+' 原执行标识已保留，请读取已有执行或用原内容核对准备。');}
    finally{operation.current=false;setBusy(false);}}
  return <section className="org-actions" aria-label="准备执行"><h4>准备执行</h4><p>固定研究方式并创建执行记录，此步骤不调用模型。随后在同一研究页确认启动。</p>
    {error&&<p role="alert">{error}</p>}
    {rows.filter(row=>!row.closed && row.preparation==='received').map(row=>
      <OrganizationSourceSearch key={row.execution_id} project={project} draft={draft} execution={row.execution_id}/>)}
    {rows.map(row=><p key={row.execution_id}>{row.closed?'已有一项关闭的执行':row.preparation==='received'?<button disabled={busy} onClick={()=>open(row.execution_id)}>查看已有研究执行 →</button>:row.preparation==='absent'?<button disabled={busy} onClick={()=>void prepare(row.execution_id)}>完成已有执行的准备</button>:<button disabled={busy} onClick={()=>void reconcile(row.execution_id)}>核对原准备结果</button>}</p>)}
    <div className="pw-toolbar">{continuous?<label>希望得到的成果<select aria-label="希望得到的成果" disabled={busy||!!sessionStorage.getItem(slot)} value={delivery} onChange={e=>setDelivery(e.target.value)}><option value="answer">回答与解释</option><option value="workpaper">工作底稿</option><option value="report">完整报告</option></select></label>:<label>研究方式 <select disabled={busy||!!sessionStorage.getItem(slot)} value={mode} onChange={e=>setMode(e.target.value)}><option value="auto">自由调度</option><option value="standard">标准协作</option></select></label>}
    {profiles.length>0 && <label>模型组合<select aria-label="模型组合" value={selectedProfile}
      disabled={busy||!!sessionStorage.getItem(slot)} onChange={e=>{setSelectedProfile(e.target.value);setReview(false);}}>
      <option value="">部署默认</option>{profiles.map(p=><option key={p.execution_id} value={p.runtime_profile}>
        GPT-6.2 Sol high 主持 · DeepSeek Flash 调查（{p.execution_id.slice(0,8)}）</option>)}</select></label>}
    {continuous&&delivery==='report'&&!selectedProfile&&<label><input type="checkbox" checked={review} disabled={busy||!!sessionStorage.getItem(slot)} onChange={e=>setReview(e.target.checked)}/>交付前完成独立报告核查</label>}
    {!rows.length&&<button className="pw-primary" disabled={busy||!loaded||!capabilitiesLoaded} onClick={()=>void prepare()}>{sessionStorage.getItem(slot)?'核对原准备请求':'准备研究执行'}<ArrowRight size={15}/></button>}<button disabled={busy} onClick={()=>refresh(n=>n+1)}>读取已有执行</button></div>
  </section>;
}
