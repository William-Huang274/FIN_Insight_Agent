import {useEffect,useState} from 'react';
type Usage={versions:number;original_bytes:number;max_versions:number;max_original_bytes:number};
const size=(n:number)=>n>=1024**3?`${(n/1024**3).toFixed(1)} GiB`:n>=1024**2?`${(n/1024**2).toFixed(1)} MiB`:n>=1024?`${(n/1024).toFixed(1)} KiB`:`${n} B`;
export function ProjectStorageUsage({project,revision}:{project:string;revision:number}){
  const [usage,setUsage]=useState<Usage|null>(null);
  useEffect(()=>setUsage(null),[project]);
  useEffect(()=>{const controller=new AbortController();if(project)void fetch(`/api/v1/projects/${project}/storage`,{signal:controller.signal}).then(async r=>{if(r.ok){const data=await r.json();if(!controller.signal.aborted)setUsage(data);}}).catch(()=>{});return()=>controller.abort();},[project,revision]);
  return usage?<details className="project-storage"><summary>资料存储 · {size(usage.original_bytes)} / {size(usage.max_original_bytes)}</summary><p>已保存 {usage.versions} / {usage.max_versions} 个文档版本。历史版本占用容量，不会自动删除。用量按原始文件计，解析索引和 SEC 快照另占磁盘空间。单次研究仍最多选择 12 份文档、合计 80 MiB。</p></details>:null;
}
