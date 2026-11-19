import type {ReactNode} from 'react';
export type TopicRecord={id:string;title:string;topic_id?:string;revision_note?:string;created_at?:string};
/** Explicit server lineage only. Same titles are not proof of shared history. */
export function ResearchTopicList<T extends TopicRecord>({rows,selected,onChoose,subtitle}:{rows:T[];selected:string;onChoose:(id:string)=>void;subtitle:(row:T)=>ReactNode}) {
  const groups=new Map<string,T[]>();
  rows.forEach(r=>{const key=r.topic_id||r.id;groups.set(key,[...(groups.get(key)||[]),r]);});
  return <>{[...groups].map(([topic,items])=>{
    const root=items.find(r=>r.id===topic)||items[items.length-1];
    if(items.length===1)return <button className="pw-row" aria-current={root.id===selected?'true':undefined} key={topic} onClick={()=>onChoose(root.id)}><span>{root.title}<small>{subtitle(root)}{root.created_at?` · ${new Date(root.created_at).toLocaleString('zh-CN')}`:''}</small></span></button>;
    return <details key={topic} className="fs-topic-group" open={items.some(r=>r.id===selected)||items.length===1}>
      <summary>{root.title}<small> · {items.length} 项研究（本页）</small></summary>
      {items.map((r,i)=><button className="pw-row" aria-current={r.id===selected?'true':undefined} key={r.id} onClick={()=>onChoose(r.id)}><span>{r.revision_note||r.title}<small>{subtitle(r)}{r.created_at?` · ${new Date(r.created_at).toLocaleString('zh-CN')}`:''}</small>{items.length>1&&<small>{r.revision_note?'同议题的独立输入／实验记录':'历史记录未填写本轮说明'}</small>}</span></button>)}
    </details>;
  })}</>;
}
