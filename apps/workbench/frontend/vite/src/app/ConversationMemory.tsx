import { useEffect, useRef, useState } from 'react';
import { BookOpen, Database, FileText, History, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './conversation-memory.css';

export type ContextMemory = {
  regions: Record<string,number>; original_message_count:number; projected_message_count:number;
  summary_count:number; summary_status:string; summary_text:string; notice:string; failure_notice?:string;
};
type Region = 'conversation'|'numbers'|'sources';
type Page = {items:{key:string;label:string;preview:string;read_tool?:string}[];next_offset:number|null;total_matches:number};
type Original = {text:string;next_offset:number|null;total_characters:number};
const regions: {id:Region;label:string;icon:typeof History}[] = [
  {id:'conversation',label:'会话原文',icon:History},{id:'numbers',label:'数字与计算',icon:Database},{id:'sources',label:'来源记录',icon:FileText},
];

export function ConversationMemory({thread, memory}:{thread:string;memory?:ContextMemory}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open,setOpen]=useState(false), [region,setRegion]=useState<Region>('conversation');
  const [query,setQuery]=useState(''), [offset,setOffset]=useState(0), [page,setPage]=useState<Page>();
  const [chosen,setChosen]=useState(''), [original,setOriginal]=useState<Original>(), [error,setError]=useState(''), [loading,setLoading]=useState(false);
  const serial=useRef(0);
  useEffect(()=>{
    if(!open)return;
    const abort=new AbortController(); serial.current++; setChosen('');setOriginal(undefined);setPage(undefined);setError('');setLoading(true);
    const params=new URLSearchParams({region,query,offset:String(offset)});
    fetch(`/api/v1/conversations/${thread}/context?${params}`,{signal:abort.signal}).then(async r=>{if(!r.ok)throw new Error('无法读取当前对话目录');return r.json() as Promise<Page>;}).then(setPage).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!abort.signal.aborted)setLoading(false);});
    return ()=>{abort.abort();serial.current++;};
  },[thread,open,region,query,offset]);
  const read=async(key:string,start=0)=>{
    const ticket=++serial.current;setChosen(key);setLoading(true);setError('');if(!start)setOriginal(undefined);
    try{
      const params=new URLSearchParams({key,region,offset:String(start)});
      const r=await fetch(`/api/v1/conversations/${thread}/context/read?${params}`);
      if(!r.ok)throw new Error('这条原文暂不可读，请重新选择目录');
      const value=await r.json() as Original;
      if(ticket===serial.current)setOriginal(previous=>({...value,text:start?(previous?.text||'')+value.text:value.text}));
    }catch(e){if(ticket===serial.current)setError((e as Error).message);}finally{if(ticket===serial.current)setLoading(false);}
  };
  if(!memory)return null;
  const label=memory.summary_status==='unavailable'?'Hermes · 原文保存':memory.summary_status==='failed'?'摘要暂停 · 原文保留':memory.summary_count?`已摘要 ${memory.summary_count} 次 · 原文保留`:'按需摘要 · 原文保存';
  return <section className="fs-memory-strip" aria-label="上下文与记忆">
    <div><BookOpen size={18}/><strong>上下文与记忆</strong><span>{label}</span><button onClick={()=>{setOpen(true);dialog.current?.showModal();}}>查看记忆目录</button></div>
    {memory.failure_notice && <p role="status">{memory.failure_notice}</p>}
    {memory.summary_status==='limited' && <p>已用完本窗口两次自动摘要。后续原文继续保留；接近输入保护上限时，请保留进度并开新对话。</p>}
    <dialog ref={dialog} className="fs-memory-dialog" onClose={()=>{setOpen(false);serial.current++;}} aria-label="记忆目录" onClick={e=>{if(e.target===dialog.current)dialog.current.close();}}>
      <header><div><small>CONTEXT & MEMORY</small><h2>从记录接着做</h2></div><button aria-label="关闭记忆目录" onClick={()=>dialog.current?.close()}><X size={20}/></button></header>
      <p>{memory.notice}</p>
      <div className="fs-memory-summary"><span>原始记录 <strong>{memory.original_message_count}</strong> 条</span>{memory.summary_status!=='unavailable'&&<span>当前历史投影 <strong>{memory.projected_message_count}</strong> 条</span>}<small>{memory.summary_status==='unavailable'?'Hermes 实时输入量尚未接入；记录条数不是 tokens，用量缺失不代表零消耗。':'记录条数不等于模型输入 tokens；精确用量见单次请求记录。'}</small></div>
      {memory.summary_text && <details><summary>当前接续摘要 · 定位参考，非金融依据</summary><ReactMarkdown remarkPlugins={[remarkGfm]}>{memory.summary_text}</ReactMarkdown></details>}
      <nav aria-label="记忆分区">{regions.map(r=><button key={r.id} aria-pressed={region===r.id} onClick={()=>{setRegion(r.id);setOffset(0);setQuery('');}}><r.icon size={16}/>{r.label}<span>{memory.regions[r.id]||0}</span></button>)}</nav>
      <input aria-label="检索记忆目录" placeholder="按原文预览或原始查询参数检索；留空浏览全部" value={query} onChange={e=>{setQuery(e.target.value);setOffset(0);}}/>
      {error&&<p role="alert">{error}</p>}
      <div className="fs-memory-browser"><aside>{!page?.items.length&&!loading&&<p>此分区没有匹配记录。可缩短关键词或留空浏览；不代表资料未披露。</p>}{page?.items.map(row=><button key={row.key} disabled={!row.read_tool} aria-pressed={chosen===row.key} onClick={()=>void read(row.key)}><strong>{row.label}</strong><span>{row.preview}</span><small>{row.read_tool?'展开原文 →':'操作未成功，不能作为成功凭证回读'}</small></button>)}<div>{offset>0&&<button onClick={()=>setOffset(Math.max(0,offset-12))}>上一页</button>}{page?.next_offset!=null&&<button onClick={()=>setOffset(page.next_offset!)}>下一页</button>}</div></aside><article aria-label="记忆原文">{loading&&<p role="status">正在读取…</p>}{original?<><small>已保存原文 · {original.total_characters.toLocaleString()} 字符</small><ReactMarkdown remarkPlugins={[remarkGfm]}>{original.text}</ReactMarkdown>{original.next_offset!=null&&<button disabled={loading} onClick={()=>void read(chosen,original.next_offset!)}>继续读取原文</button>}</>:!loading&&<p>选择左侧记录，核对原始表述、公司、期间与单位。工作底稿请在独立的底稿面板检索。</p>}</article></div>
    </dialog>
  </section>;
}
