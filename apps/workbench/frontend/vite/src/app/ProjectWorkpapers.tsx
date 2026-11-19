import {useEffect,useState} from 'react';
import {assetRequest} from '../api/assetWorkspace';
import {WorkingNotes} from './WorkingNotes';

type Task={thread_id:string;title:string;available:boolean;status?:string;surface?:string;notice?:string};
export function ProjectWorkpapers({project}:{project:string}){
  const [items,setItems]=useState<Task[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false),[next,setNext]=useState<number|null>(null);
  async function load(offset=0){setBusy(true);setError('');try{const result=await assetRequest<{items:Task[];next_offset:number|null}>(`asset-workspace/projects/${project}/tasks?offset=${offset}`);setItems(old=>offset?[...old,...result.items]:result.items);setNext(result.next_offset);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  useEffect(()=>{void load();},[project]);
  return <section className="aw-project-papers" aria-label="项目任务底稿"><header><h2>任务底稿</h2><button disabled={busy} onClick={()=>void load()}>刷新底稿目录</button></header><p>这里编辑原任务的同一份底稿。旧版本保留，正式报告仍须完成研究复核。</p>{error&&<p role="alert">{error}</p>}{!items.length&&!busy&&<p>项目还没有关联任务；可先从资料发起对话或研究。</p>}{items.map(task=><article key={task.thread_id}><strong>{task.title}</strong>{task.available?<><a href={task.surface==='conversations'?`/workspace/assistant?thread=${task.thread_id}`:`/workspace/session?thread=${task.thread_id}&view=graph`}>打开任务</a><WorkingNotes endpoint={`/api/v1/${task.surface}/${task.thread_id}/working-notes`}/>{task.status==='busy'&&<small>任务运行中。保存后下一次模型调用会收到回读提醒；已发出的调用与正式报告保留原状态。</small>}</>:<p>{task.notice}</p>}</article>)}{next!==null&&<button disabled={busy} onClick={()=>void load(next)}>更多关联任务</button>}</section>;
}
