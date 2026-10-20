import {useEffect,useRef,useState} from 'react';
import {assetRequest} from '../api/assetWorkspace';

type Baseline={previous_run_id:string;checkpoint_id:string;state_digest:string;report_version:number;report_digest:string};
type CommandRow={id:string;status:string;action:'ask'|'revise';report_version:number;run_id?:string};
type Commands={enabled:boolean;items:CommandRow[]};

export function OrganizationReportActions({base,busyRun,citations=[],onChanged}:{base:string;busyRun:boolean;citations?:string[];onChanged:()=>void}){
  const [commands,setCommands]=useState<Commands|null>(null),[message,setMessage]=useState('');
  const [action,setAction]=useState<'ask'|'revise'>('ask'),[preview,setPreview]=useState<Baseline|null>(null);
  const [target,setTarget]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[revision,refresh]=useState(0);
  const guard=useRef(false),generation=useRef(0);
  useEffect(()=>{let alive=true;++generation.current;setCommands(null);setPreview(null);
    assetRequest<Commands>(`${base}/report-commands`).then(v=>alive&&setCommands(v)).catch(e=>alive&&setError(e.message));
    return()=>{alive=false;++generation.current;};
  },[base,revision]);
  async function perform(kind:'preview'|'submit'|'reconcile',id?:string){
    if(guard.current)return;guard.current=true;setBusy(true);setError('');const current=generation.current;
    try{
      if(kind==='preview'){
        const value=await assetRequest<Baseline>(`${base}/report-action-preview`);
        if(current===generation.current)setPreview(value);
      }else{
        const suffix=kind==='reconcile'?`report-commands/${id}/reconcile`:'report-commands';
        const requestId=crypto.randomUUID();
        const body=kind==='reconcile'?{}:{...preview,id:requestId,action,message:message.trim(),answer_mode:action==='ask'?'quick':'deep',
          target:action==='revise'&&target&&preview?{request_id:requestId,citation_id:target,base_version:preview.report_version,base_digest:preview.report_digest,base_checkpoint:preview.checkpoint_id}:null};
        await assetRequest(`${base}/${suffix}`,'POST',body);
        if(current===generation.current){setPreview(null);setMessage('');refresh(n=>n+1);onChanged();}
      }
    }catch(e){if(current===generation.current){setPreview(null);setError((e as Error).message+' 请核对操作记录，不会自动重发。');refresh(n=>n+1);}}
    finally{guard.current=false;setBusy(false);}
  }
  const uncertain=commands?.items.find(c=>['ready','unknown','dispatching'].includes(c.status));
  return <section className="org-report-actions" aria-label="报告追问与修订">
    <h4>继续这份研究</h4>
    {error&&<p role="alert">{error}</p>}
    {uncertain?<div role="status"><p>上一条{uncertain.action==='ask'?'追问':'修订'}的回执待核对。先找回原操作，再继续。</p><button disabled={busy} onClick={()=>void perform('reconcile',uncertain.id)}>核对报告操作</button></div>
    :commands?.enabled?<><div className="pw-toolbar" role="group" aria-label="报告操作类型">
      <button aria-pressed={action==='ask'} disabled={busy||!!preview} onClick={()=>setAction('ask')}>追问解释</button>
      <button aria-pressed={action==='revise'} disabled={busy||!!preview} onClick={()=>setAction('revise')}>提出修订</button>
    </div>{action==='revise'&&citations.length>0&&<label>修订关注范围<select aria-label="修订关注范围" value={target} disabled={busy||!!preview} onChange={e=>setTarget(e.target.value)}><option value="">整份报告</option>{citations.map(id=><option key={id} value={id}>围绕引用 {id} 核查</option>)}</select></label>}
      <label>问题或修订意见<textarea aria-label="问题或修订意见" rows={3} maxLength={16000} value={message} disabled={busy||!!preview} onChange={e=>setMessage(e.target.value)}/></label>
      <p className="pw-muted">{action==='ask'?'围绕当前报告与来源解释问题，保留已有报告。':'沿用本次研究的资料和配置核查意见，修订后重新复核。用户意见不作为事实证据。'}</p>
      {preview?<div className="org-confirm"><p>已核对报告 v{preview.report_version}。确认{action==='ask'?'提交追问':'提交修订'}会启动一次新的模型运行。</p><div className="pw-toolbar"><button className="pw-primary" disabled={busy||busyRun} onClick={()=>void perform('submit')}>确认{action==='ask'?'提交追问':'提交修订'}</button><button disabled={busy} onClick={()=>setPreview(null)}>返回编辑</button></div></div>
      :<button className="pw-primary" disabled={busy||busyRun||!message.trim()} onClick={()=>void perform('preview')}>核对并准备{action==='ask'?'追问':'修订'}</button>}
      {busyRun&&<p role="status">当前研究仍在运行，完成后可继续提交。</p>}
    </>:commands&&<p className="pw-muted">此环境尚未启用组织报告交互。</p>}
    {!!commands?.items.length&&<details><summary>最近报告操作（{commands.items.length}）</summary><ul>{commands.items.map(c=><li key={c.id}>报告 v{c.report_version} · {c.action==='ask'?'追问':'修订'} · {c.status==='received'?'已受理，请查看运行结果':c.status==='rejected'?'未受理，请核对报告基线':'待核对'}</li>)}</ul></details>}
  </section>;
}
