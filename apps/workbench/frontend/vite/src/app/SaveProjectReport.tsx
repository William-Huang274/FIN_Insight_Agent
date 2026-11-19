import {useState} from 'react';

export function SaveProjectReport({thread,version,digest,checkpoint,projects,onOpen}:{thread:string;version:number;digest?:string;checkpoint?:string;projects:{id:string;name:string}[];onOpen:(id:string)=>void}){
  const [project,setProject]=useState(projects[0]?.id||'');
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  return <section className="fs-save-project-report" aria-label="保存报告到项目">
    <p>将这版报告保存为可查找、可用于后续研究的项目资料。修改后需再次保存新版本；每个版本占一份资料额度。</p>
    <label>目标项目<select aria-label="保存报告的目标项目" value={project} disabled={busy} onChange={e=>{setProject(e.target.value);setNotice('');}}>
      {!project&&<option value="">选择项目</option>}{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <button disabled={busy||!project||!digest} onClick={async()=>{setBusy(true);setNotice('');setError('');
      try{const r=await fetch(`/api/v1/projects/${project}/reports`,{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},body:JSON.stringify({thread_id:thread,checkpoint_id:checkpoint,report_digest:digest})});
        const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'保存未完成');
        setNotice(`v${version} 已保存，正文可查找。研究成果仍须核对原始依据。`);
      }catch(e){setError((e as Error).message);}finally{setBusy(false);}
    }}>{busy?'正在保存…':`保存 v${version} 到项目`}</button>
    {!projects.length&&<p>请先在“管理项目”中创建项目。</p>}
    {notice&&<p role="status">{notice} <button onClick={()=>onOpen(project)}>打开已保存项目</button></p>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
