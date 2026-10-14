import {useEffect,useRef,useState} from 'react';
import {ArrowRight,RefreshCw,Play,ShieldCheck} from 'lucide-react';
import {assetRequest} from '../api/assetWorkspace';

type Stage='preparation'|'start'|'continuation';
type Control={can_operate:boolean;enabled?:boolean;preparation?:string;start?:string;continuation?:string};
type Preview={previous_run_id:string;checkpoint_id:string;state_digest:string};
const names:Record<Stage,string>={preparation:'准备研究',start:'首次启动',continuation:'正式研究'};

export function OrganizationResearchActions({base,phase,onChanged}:{base:string;phase?:string;onChanged:()=>void}){
  const [control,setControl]=useState<Control|null>(null),[preview,setPreview]=useState<Preview|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[revision,refresh]=useState(0);
  const guard=useRef(false),generation=useRef(0);
  useEffect(()=>{let alive=true;++generation.current;setControl(null);setPreview(null);setError('');
    assetRequest<Control>(`${base}/control`).then(v=>alive&&setControl(v)).catch(e=>alive&&setError(e.message));
    return()=>{alive=false;++generation.current;};
  },[base,phase,revision]);
  async function act(suffix:string,body:unknown={},get=false){
    if(guard.current)return;guard.current=true;setBusy(true);setError('');const current=generation.current;
    try{const value=await assetRequest<Preview>(`${base}/${suffix}`,get?'GET':'POST',get?undefined:body);
      if(current!==generation.current)return;
      if(get)setPreview(value);else{setPreview(null);refresh(n=>n+1);onChanged();}
    }catch(e){if(current===generation.current){setPreview(null);setControl(null);setError((e as Error).message+' 请重新读取命令状态；页面不会自动重发。');}}
    finally{guard.current=false;setBusy(false);}
  }
  const uncertain=(['preparation','start','continuation'] as Stage[]).filter(s=>control?.[s]==='unknown'||control?.[s]==='ready');
  return <section className="org-actions" aria-label="研究操作">
    <div className="org-action-heading"><ShieldCheck size={18}/><strong>下一步</strong><button className="pw-quiet" disabled={busy} onClick={()=>refresh(n=>n+1)}><RefreshCw size={14}/>核对操作状态</button></div>
    {error&&<p role="alert">{error}</p>}
    {control&&!control.can_operate&&<p>你可以阅读这项研究；启动和接续由原发起人操作。</p>}
    {control?.can_operate&&<>
      {uncertain.map(stage=><div key={stage}><p>{names[stage]}的提交结果待核对。核对只读取原命令，不会新建运行。</p><button disabled={busy} onClick={()=>void act(`reconcile/${stage}`)}><RefreshCw size={15}/>核对{names[stage]}结果</button></div>)}
      {!control.enabled&&<p>此环境尚未启用组织研究执行。</p>}
      {control.enabled&&!uncertain.length&&control.preparation==='received'&&control.start==='absent'&&<><p>资料版本与执行配置已固定。先进行预研究，查看方向后再确认正式研究。</p><button className="pw-primary" disabled={busy} onClick={()=>void act('start')}><Play size={15}/>开始预研究</button><small>本次动作会调用已配置的研究模型；截止日按 UTC 当日结束计算。</small></>}
      {control.enabled&&!uncertain.length&&control.start==='received'&&control.continuation==='absent'&&phase==='research_orientation_submitted'&&!preview&&<><p>预研究已保存。核对原运行和用量后，可以沿用当前问题与资料进入正式研究。</p><button className="pw-primary" disabled={busy} onClick={()=>void act('continuation-preview',undefined,true)}>准备正式研究<ArrowRight size={15}/></button></>}
      {preview&&<div className="org-confirm" role="group" aria-label="确认正式研究"><h4>沿用当前预研究，开始正式研究？</h4><p>问题、资料版本、模型配置保持冻结。正式研究会重新取证与核查，可能产生新的模型费用。</p><div className="pw-toolbar"><button className="pw-primary" disabled={busy} onClick={()=>void act('continue',preview)}>确认接续研究</button><button disabled={busy} onClick={()=>setPreview(null)}>暂不开始</button></div></div>}
      {(['preparation','start','continuation'] as Stage[]).some(s=>control[s]==='rejected')&&<p>原命令已拒绝。请保留记录排查原因，不能从此页面重试运行。</p>}
      {control.continuation==='received'&&<p>正式研究已受理。可查看运行动态与保存内容；刷新不会重复执行。</p>}
      {control.start==='received'&&control.continuation==='absent'&&phase!=='research_orientation_submitted'&&<p>预研究已受理。查看运行动态或刷新保存内容；只有前序预研究成功结束且用量可核对，才能确认接续。</p>}
    </>}
  </section>;
}
