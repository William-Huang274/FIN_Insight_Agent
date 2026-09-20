import {useEffect,useState} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {X,ExternalLink} from 'lucide-react';

type RecordItem={record_index:number;title:string;url?:string;publisher?:string;published_at?:string;created_at?:string;updated_at?:string;summary:string;body:string;body_available:boolean;record_kind:string;metrics:Record<string,unknown>};
type Presentation={kind:string;items?:RecordItem[];total?:number;next_offset?:number;notice?:string};
type SourceRef={id:string;title:string;url:string;category:string;published_at:string|null;captured_at?:string;publisher_names?:string[];metadata:{original_filing_url?:string;[key:string]:unknown}};
const metricNames:Record<string,string>={stargazers_count:'Stars',forks_count:'Forks',downloads:'下载次数',likes:'喜欢',comments:'评论数',state:'状态',language:'语言'};
function TextBody({text}:{text:string}){
  try{
    const parsed=JSON.parse(text);
    if(parsed&&typeof parsed==='object')return <dl className="cw-structured-record">{Object.entries(parsed).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{typeof v==='object'?JSON.stringify(v,null,2):String(v??'未提供')}</dd></div>)}</dl>;
  }catch{/* Archived prose is rendered as Markdown, never executable HTML. */}
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>;
}
export default function MaterialReader({source,onClose,label}:{source:SourceRef;onClose:()=>void;label:(x:string)=>string}){
  const [offset,setOffset]=useState(0),[view,setView]=useState<Presentation|null>(null),[parts,setParts]=useState<{body:string;id:string;locator:string}[]>([]),[total,setTotal]=useState(0),[error,setError]=useState('');
  useEffect(()=>{const listener=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose();};window.addEventListener('keydown',listener);return()=>window.removeEventListener('keydown',listener);},[onClose]);
  useEffect(()=>{const controller=new AbortController();setError('');setView(null);setParts([]);
    const base='/api/v1/data-library/research-sources/'+encodeURIComponent(source.id);
    const read=async()=>{
      const response=await fetch(`${base}/presentation?offset=${offset}&limit=20`,{signal:controller.signal});if(!response.ok)throw new Error('材料结构解析失败，原始记录仍保留，请检查解析记录。');const presentation=await response.json() as Presentation;
      if(presentation.kind==='directory'){setView(presentation);setTotal(presentation.total||0);return;}
      const r=await fetch(`${base}?offset=${offset}&limit=3`,{signal:controller.signal});if(!r.ok)throw new Error('材料读取失败');const result=await r.json();setParts(result.items||[]);setTotal(result.total||0);setView(presentation);
    };void read().catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>controller.abort();
  },[source.id,offset]);
  const directory=view?.kind==='directory',size=directory?20:3;
  return <div className="cw-reader-backdrop" role="presentation" onClick={onClose}><section className="cw-reader" role="dialog" aria-modal="true" aria-label="材料原文" onClick={e=>e.stopPropagation()}>
    <header><div><small>{label(source.category)} · {source.published_at?`发布于 ${source.published_at}`:'原件未确认发布日期'}{source.captured_at&&` · 抓取于 ${source.captured_at.slice(0,10)}`}</small><h2>{source.title||'未命名材料'}</h2><a href={source.metadata.original_filing_url||source.url} target="_blank" rel="noreferrer">打开来源 <ExternalLink size={12}/></a></div><button aria-label="关闭原文" onClick={onClose}><X size={20}/></button></header>
    <div className="cw-reader-body">{error&&<p role="alert">{error}</p>}{!view&&!error&&<p>正在读取…</p>}
      {directory&&<><p className="cw-caption">{view.notice}</p>{view.items?.map(r=><article className="cw-record-card" key={r.record_index}><h3><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a></h3><p className="cw-record-meta">{r.publisher&&`${r.publisher} · `}{r.published_at?`发布 ${r.published_at}`:r.created_at?`创建 ${r.created_at.slice(0,10)}`:'发布日期未提供'}{r.updated_at&&` · 更新 ${r.updated_at.slice(0,10)}`}</p>{r.summary&&<p>{r.summary}</p>}{r.body?<TextBody text={r.body}/>:r.record_kind==='news_discovery'&&<p className="cw-caption">目前仅保存标题和来源链接，尚未获取新闻正文。</p>}<div className="cw-record-metrics">{Object.entries(r.metrics).map(([k,v])=><span key={k}>{metricNames[k]||k}：{String(v)}</span>)}</div></article>)}</>}
      {!directory&&parts.length>0&&<article><small>{parts[0].locator} — {parts[parts.length-1].locator}</small><TextBody text={parts.map((p,i)=>i>0&&p.locator===`text-part:${offset+i}`?p.body.slice(250):p.body).join('')}/></article>}
    </div><footer><button disabled={!offset||!view} onClick={()=>setOffset(Math.max(0,offset-size))}>上一组</button><span>{directory?'目录条目':'原文片段'} {total?offset+1:0}–{Math.min(offset+size,total)} / {total}</span><button disabled={!view||offset+size>=total} onClick={()=>setOffset(offset+size)}>下一组</button></footer>
  </section></div>;
}
