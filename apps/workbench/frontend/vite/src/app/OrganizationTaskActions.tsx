import {useEffect,useRef,useState} from 'react';
import {assetRequest} from '../api/assetWorkspace';
import {browserOwner} from './IdentityBoundary';

type Baseline={previous_run_id:string;checkpoint_id:string;state_digest:string};
type Commands={enabled:boolean;items:{id:string;status:string}[]};

export function OrganizationTaskActions({base,busyRun,onChanged}:{base:string;busyRun:boolean;onChanged:()=>void}){
  const [commands,setCommands]=useState<Commands|null>(null),[message,setMessage]=useState('');
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[revision,refresh]=useState(0);
  const [baseline,setBaseline]=useState<Baseline|null>(null),[closing,setClosing]=useState(false);
  const [delivery,setDelivery]=useState('answer'),[review,setReview]=useState(false);
  const [recover,setRecover]=useState(false);
  const guard=useRef(false),generation=useRef(0);
  const slot=`finsight:org-task:${browserOwner}:${base}`;
  useEffect(()=>{let alive=true;++generation.current;setCommands(null);setBaseline(null);
    assetRequest<Commands>(`${base}/task-commands`).then(value=>alive&&setCommands(value)).catch(e=>alive&&setError(e.message));
    return()=>{alive=false;++generation.current;};
  },[base,revision]);
  async function act(action:'preview'|'recover'|'submit'|'reconcile'|'stop',id?:string){
    if(guard.current)return;guard.current=true;setBusy(true);setError('');const current=generation.current;
    try{
      if(action==='preview'||action==='recover'){
        const value=await assetRequest<Baseline>(`${base}/task-action-preview?action=${action==='recover'?'recover':'continue'}`);
        if(current===generation.current){setBaseline(value);setRecover(action==='recover');}
      }else{
        let suffix=action==='stop'?'stop':action==='reconcile'?`task-commands/${id}/reconcile`:'task-commands';
        let body:unknown={};
        if(action==='submit'){
          body={...baseline,id:crypto.randomUUID(),action:recover?'recover':'continue',message:recover?'恢复原任务；允许本次重试失败的检索请求，保留失败用量及原预算。':message.trim(),delivery_intent:delivery,require_report_review:delivery==='report'&&review};
          sessionStorage.setItem(slot,JSON.stringify(body));
        }
        await assetRequest(`${base}/${suffix}`,'POST',body);
        if(current===generation.current){sessionStorage.removeItem(slot);setBaseline(null);setClosing(false);setMessage('');refresh(v=>v+1);onChanged();}
      }
    }catch(e){if(current===generation.current){setBaseline(null);setError((e as Error).message+' 请核对原操作记录；不会自动重新调用模型。');refresh(v=>v+1);}}
    finally{guard.current=false;setBusy(false);}
  }
  const uncertain=commands?.items.find(item=>['ready','dispatching','unknown'].includes(item.status));
  const stored=sessionStorage.getItem(slot);
  const pendingId=uncertain?.id||(stored?JSON.parse(stored).id:undefined);
  return <section aria-label="继续当前任务">
    <h4>继续当前任务</h4>{error&&<p role="alert">{error}</p>}
    {pendingId?<><p>上一条操作尚待核对，保留原请求。</p><button disabled={busy} onClick={()=>void act('reconcile',pendingId)}>核对原任务操作</button></>
      :commands?.enabled?<><label>这一步的成果<select aria-label="这一步的成果" disabled={busy||!!baseline} value={delivery} onChange={e=>setDelivery(e.target.value)}><option value="answer">回答与解释</option><option value="workpaper">工作底稿</option><option value="report">完整报告</option></select></label>
        {delivery==='report'&&<label><input type="checkbox" checked={review} disabled={busy||!!baseline} onChange={e=>setReview(e.target.checked)}/>交付前完成独立报告核查</label>}
        <label>继续提问或交代下一步<textarea aria-label="继续提问或交代下一步" rows={3} maxLength={16000} disabled={busy||!!baseline} value={message} onChange={e=>setMessage(e.target.value)}/></label>
        {baseline?<><p>{recover?'将从失败停点恢复原任务，保留成功结果和失败用量。允许本次重试失败的检索请求，沿用原预算，可能产生费用。':'将沿用当前成果和授权资料开始一次新运行，可能产生模型费用。'}</p><button disabled={busy||busyRun} onClick={()=>void act('submit')}>{recover?'确认恢复失败运行':'确认继续任务'}</button><button disabled={busy} onClick={()=>setBaseline(null)}>返回编辑</button></>
          :<><button disabled={busy||busyRun||!message.trim()} onClick={()=>void act('preview')}>准备继续任务</button><button disabled={busy||busyRun} onClick={()=>void act('recover')}>恢复失败运行</button></>}</>:<p>当前环境未启用任务接续。</p>}
    {busyRun&&<p>当前任务正在执行，结束后可以继续提问。</p>}
    {closing?<><p>结束后将停止本任务及其委派工作，保留已保存成果；本执行不能再接续。</p><button disabled={busy} onClick={()=>void act('stop')}>确认结束本次执行</button><button disabled={busy} onClick={()=>setClosing(false)}>返回</button></>:<button disabled={busy} onClick={()=>setClosing(true)}>结束本次执行</button>}
  </section>;
}
