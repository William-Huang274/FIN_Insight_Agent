import {useEffect,useRef,useState} from 'react';
import {Download} from 'lucide-react';

const formats={
  html:{label:'网页阅读版',mime:'text/html'},
  md:{label:'Markdown',mime:'text/markdown'},
  pdf:{label:'PDF',mime:'application/pdf'},
  docx:{label:'Word',mime:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
  pptx:{label:'PowerPoint',mime:'application/vnd.openxmlformats-officedocument.presentationml.presentation'},
} as const;
type Format=keyof typeof formats;

/** One current-reader request; denied responses must never become downloaded files. */
export function OrganizationReportDownload({base,checkpointId,onDenied}:{base:string;checkpointId?:string|null;onDenied:(message:string)=>void}){
  const [busy,setBusy]=useState<Format|null>(null),[error,setError]=useState('');
  const pending=useRef<AbortController|null>(null);
  useEffect(()=>()=>{pending.current?.abort();pending.current=null;},[base,checkpointId]);
  async function download(format:Format){
    if(pending.current||!checkpointId)return;
    const controller=new AbortController();pending.current=controller;setBusy(format);setError('');
    try{
      const response=await fetch(`/api/v1/${base}/report/export/${format}?checkpoint_id=${encodeURIComponent(checkpointId)}`,{
        credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal,
      });
      if(!response.ok){
        const detail=await response.json().catch(()=>null);
        const message=typeof detail?.detail==='string'?detail.detail:`导出未完成 (${response.status})，请重新读取研究记录。`;
        if(controller.signal.aborted)return;
        if([401,403,404].includes(response.status)){onDenied(message);return;}
        throw new Error(message);
      }
      // A redirected login page or proxy error must not be saved as a report.
      if(response.headers.get('content-type')?.split(';')[0].trim()!==formats[format].mime){
        throw new Error('导出响应格式不正确，未下载文件。请核对登录状态和服务。');
      }
      const blob=await response.blob();
      if(controller.signal.aborted)return;
      if(!blob.size)throw new Error('导出内容为空，未下载文件。');
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=`finsight-organization-research.${format}`;
      document.body.append(link);link.click();link.remove();
      // Give the browser time to consume the object URL, then release its memory.
      window.setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'导出未完成，请检查连接后手动重试。');}
    finally{if(pending.current===controller){pending.current=null;setBusy(null);}}
  }
  return <div><nav className="pw-toolbar" aria-label="组织报告导出">{(Object.keys(formats) as Format[]).map(format=>
    <button key={format} disabled={busy!==null||!checkpointId} onClick={()=>void download(format)}><Download size={14}/>{formats[format].label}</button>)}</nav>
    {!checkpointId&&<p role="status">尚未取得报告版本记录，请刷新研究记录后导出。</p>}
    {busy&&<p role="status">正在准备 {formats[busy].label} 下载…</p>}{error&&<p role="alert">{error}</p>}</div>;
}
