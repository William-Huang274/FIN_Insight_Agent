import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen, Download, RefreshCw, X } from "lucide-react";
import "./working-notes.css";

type Item = { id:string; actor:string; title:string; version:number; preview:string };
type Note = { id:string; title:string; version:number; body:string; next_offset:number|null; is_current:boolean };

export function WorkingNotes({ endpoint }: { endpoint:string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [items,setItems]=useState<Item[]>([]), [note,setNote]=useState<Note|null>(null);
  const [query,setQuery]=useState(""), [notice,setNotice]=useState(""), [busy,setBusy]=useState(false);
  const [next,setNext]=useState<number|null>(null);
  const [instruction,setInstruction]=useState(''),[revisionLink,setRevisionLink]=useState('');
  const [model,setModel]=useState('deepseek-v4-flash'),[harness,setHarness]=useState('native');
  async function revise(){
    if(!note||!instruction.trim())return;setBusy(true);setNotice('');
    try{const response=await fetch(`${endpoint}/revise`,{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},body:JSON.stringify({note_id:note.id,version:note.version,instruction,model,harness})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||'修订请求未完成');
      setRevisionLink(`/workspace/assistant?thread=${data.thread_id}`);setNotice(data.notice);setInstruction('');
    }catch(e){setNotice((e as Error).message);}finally{setBusy(false);}
  }
  async function get(params:Record<string,string>) {
    const response=await fetch(`${endpoint}?${new URLSearchParams(params)}`);
    const data=await response.json();
    if(!response.ok) throw new Error(typeof data.detail==="string" ? data.detail : "工作底稿暂不可读取");
    return data;
  }
  async function list(offset=0) {
    setBusy(true); setNotice("");
    try {const data=await get({query,offset:String(offset)});setItems(old=>offset?[...old,...(data.items||[])]:data.items||[]);setNext(data.next_offset??null);setNotice(data.notice||"");}
    catch(e){setNotice((e as Error).message);}finally{setBusy(false);}
  }
  async function read(id:string,version?:number,offset=0) {
    setBusy(true);setNotice("");
    try {const data=await get({note_id:id,offset:String(offset),...(version?{version:String(version)}:{})});
      if(!data.found) throw new Error(data.notice||"底稿不可读取");
      setNote(old=>({...data,body:offset?(old?.body||"")+data.body:data.body}));
    }catch(e){setNotice((e as Error).message);}finally{setBusy(false);}
  }
  async function download() {
    if(!note)return;setBusy(true);
    try {const data=await get({note_id:note.id,download:"true",version:String(note.version)});
      if(typeof data.markdown!=="string")throw new Error("正文下载失败");
      const url=URL.createObjectURL(new Blob([data.markdown],{type:"text/markdown;charset=utf-8"}));
      const a=document.createElement("a");a.href=url;a.download="finsight-working-note.md";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){setNotice((e as Error).message);}finally{setBusy(false);}
  }
  return <><button onClick={()=>{dialog.current?.showModal();void list();}}><BookOpen size={15}/>工作底稿</button>
    <dialog ref={dialog} className="fs-working-notes" aria-label="工作底稿" onClick={e=>{if(e.target===dialog.current)dialog.current?.close();}}>
      <header><div><h2>工作底稿</h2><p>研究中的记录，允许未完成和待核实；与工具日志、已核验事实分开保存。</p></div><button aria-label="关闭工作底稿" onClick={()=>dialog.current?.close()}><X size={20}/></button></header>
      <form onSubmit={e=>{e.preventDefault();void list();}}><input aria-label="检索工作底稿" placeholder="输入简短关键词，或留空浏览…" value={query} onChange={e=>setQuery(e.target.value)}/><button disabled={busy}>检索</button><button type="button" disabled={busy} onClick={()=>void list()}><RefreshCw size={15}/>刷新</button></form>
      {notice&&<p role="status">{notice}</p>}
      {revisionLink&&<a href={revisionLink}>查看本次修订的实时过程与结果 →</a>}
      <div className="fs-working-notes-body"><nav aria-label="底稿目录">{!items.length&&!busy&&<p>暂无匹配底稿。未保存的模型输出不会被伪装成已有底稿。</p>}{items.map(i=><button disabled={busy} key={i.id} onClick={()=>void read(i.id)} aria-current={note?.id===i.id?"true":undefined}><strong>{i.title}</strong><small>{i.actor} · v{i.version}</small><span>{i.preview}</span></button>)}{next!==null&&<button disabled={busy} onClick={()=>void list(next)}>更多底稿</button>}</nav>
      <article>{note?<><div className="fs-working-notes-version"><h3>{note.title} · v{note.version}</h3><span>{note.is_current?"当前版本":"历史版本"}</span><button disabled={busy||note.version<=1} onClick={()=>void read(note.id,note.version-1)}>上一版本</button><button disabled={busy} onClick={()=>void read(note.id)}>最新版本</button><button disabled={busy} onClick={()=>void download()}><Download size={15}/>下载正文</button></div><ReactMarkdown remarkPlugins={[remarkGfm]}>{note.body}</ReactMarkdown>{note.next_offset!==null&&<button disabled={busy} onClick={()=>void read(note.id,note.version,note.next_offset!)}>继续阅读</button>}</>:<p>选择一份底稿查看正文、表格及历史版本。</p>}</article></div>
      {note&&<form onSubmit={e=>{e.preventDefault();void revise();}} className="fs-working-note-revision"><label>针对「{note.title} · v{note.version}」提出修改<textarea aria-label="底稿修改意见" value={instruction} onChange={e=>setInstruction(e.target.value)} placeholder="说明哪些判断、依据或后续安排需要调整…"/></label><select aria-label="修订模型" value={model} onChange={e=>setModel(e.target.value)}><option value="deepseek-v4-flash">DeepSeek Flash</option><option value="deepseek-v4-pro">DeepSeek Pro</option></select><select aria-label="修订执行方式" value={harness} onChange={e=>setHarness(e.target.value)}><option value="native">当前 Agent</option><option value="hermes">Hermes · 工作底稿试用</option></select><button disabled={busy||!note.is_current||!instruction.trim()}>交给责任 Agent 修订</button></form>}
    </dialog></>;
}
