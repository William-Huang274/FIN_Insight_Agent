import {useEffect,useState} from 'react';

/** EventSource reconnects only reads. Close on failure; never retry a command. */
export function OrganizationResearchEvents({base,run,verifyAccess}:{base:string;run?:string|null;verifyAccess:()=>Promise<boolean>}){
  const [events,setEvents]=useState<{id:string;text:string}[]>([]),[status,setStatus]=useState(''),[revision,refresh]=useState(0);
  useEffect(()=>{
    setEvents([]);setStatus('');if(!run)return;
    const stream=new EventSource(`/api/v1/${base}/runs/${run}/events`);let alive=true;
    setStatus('正在读取运行动态');
    stream.addEventListener('custom',(raw)=>{const e=raw as MessageEvent;try{
      const value=JSON.parse(e.data),text=[value.actor,value.objective||value.summary||value.event].filter(v=>typeof v==='string').join(' · ');
      if(text&&alive)setEvents(rows=>[...rows.filter(r=>r.id!==e.lastEventId),{id:e.lastEventId||crypto.randomUUID(),text}].slice(-80));
    }catch{/* Never render unparsed transport data. */}});
    stream.onopen=()=>alive&&setStatus('运行动态已连接');
    stream.onerror=()=>{stream.close();if(alive){setStatus('正在核对动态读取权限');void verifyAccess().then(allowed=>{if(alive){if(!allowed)setEvents([]);setStatus(allowed?'动态连接已结束；已核对当前读取权限。':'无法核对读取权限，已清空动态。');}});}};
    return()=>{alive=false;stream.close();};
  },[base,run,revision]);
  if(!run)return null;
  return <details className="org-events"><summary>运行动态 <span>{status}</span></summary><ol>{events.map(e=><li key={e.id}>{e.text}</li>)}</ol><button onClick={()=>refresh(n=>n+1)}>重新连接动态</button><p className="pw-muted">动态只展示执行进展；研究是否完成以保存的研究状态为准。</p></details>;
}
