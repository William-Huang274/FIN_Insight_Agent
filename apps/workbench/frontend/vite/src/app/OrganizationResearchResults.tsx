import {useEffect,useRef,useState} from 'react';
import {useSearchParams} from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {assetRequest} from '../api/assetWorkspace';
import {RefreshCw,Plus,FileText} from 'lucide-react';
import {OrganizationReportDownload} from './OrganizationReportDownload';
import {OrganizationResearchActions} from './OrganizationResearchActions';
import {OrganizationResearchEvents} from './OrganizationResearchEvents';

type Row={execution_id:string;draft_id:string;title:string;run_id:string|null};
type Source={source_id:string;text?:string;period?:string;unit?:string;next_offset?:number|null};
type Snapshot={title:string;checkpoint_id?:string|null;run_id?:string|null;status?:string;phase?:string;conversation?:{role:string;content:string}[];research_stop_reason?:string;report?:{title:string;narrative_markdown:string;citations?:Record<string,{sources?:Source[]}>};research_orientation?:{overview?:string;findings?:{finding_id:string;judgment:string;unresolved?:string}[]}};
const phases:Record<string,string>={research_orientation_submitted:'预研究已提交',research_needs_attention:'研究待处理',ready_for_human_review:'报告待审阅',single_agent_unreviewed:'单 Agent 结果 · 未经独立复核',needs_revision:'报告待修订'};

export function OrganizationResearchResults({project}:{project:{id:string}}){
  const [params,setParams]=useSearchParams(),id=params.get('execution')||'';
  const base=`organization-projects/${project.id}/research`;
  const [rows,setRows]=useState<Row[]>([]),[snapshot,setSnapshot]=useState<Snapshot|null>(null),[source,setSource]=useState<Source|null>(null);
  const [offset,setOffset]=useState(0),[next,setNext]=useState<number|null>(null),[revision,refresh]=useState(0);
  const [loading,setLoading]=useState(true),[error,setError]=useState('');const generation=useRef(0);
  useEffect(()=>{let alive=true;const current=++generation.current;setLoading(true);setRows([]);setSnapshot(null);setSource(null);setError('');setNext(null);
    (async()=>{const list=await assetRequest<{items:Row[];next_offset:number|null}>(`${base}?offset=${offset}`);
      const item=id?await assetRequest<Snapshot>(`${base}/${id}`):null;
      if(alive&&generation.current===current){setRows(list.items);setNext(list.next_offset);setSnapshot(item);}
    })().catch(e=>alive&&setError(e.message)).finally(()=>alive&&setLoading(false));
    return()=>{alive=false;++generation.current;};
  },[base,id,offset,revision]);
  async function readSource(sourceId:string,start=0){const current=++generation.current;setSource(null);setError('');
    if(!snapshot?.checkpoint_id){setError('尚未取得报告版本记录，请刷新研究记录后读取引用。');return;}
    try{const result=await assetRequest<Source>(`${base}/${id}/source?source_id=${encodeURIComponent(sourceId)}&offset=${start}&checkpoint_id=${encodeURIComponent(snapshot.checkpoint_id)}`);if(current===generation.current)setSource(result);}
    catch(e){if(current===generation.current){setRows([]);setSnapshot(null);setSource(null);setError((e as Error).message);}}
  }
  const sources=Object.values(snapshot?.report?.citations||{}).flatMap(c=>c.sources||[]);
  const distinct=[...new Map(sources.map(s=>[s.source_id,s])).values()];
  return <section className="org-results" aria-label="组织研究成果"><header className="pw-title"><div><h2>研究记录与成果</h2><p>按项目查看当前有权读取的研究。预研究、未完成结果与正式报告分别显示。</p></div><div className="pw-toolbar"><button onClick={()=>refresh(n=>n+1)}><RefreshCw size={15}/>刷新研究记录</button><a className="pw-primary" href={`/workspace/projects?scope=organization&project=${project.id}&view=research`}><Plus size={15}/>新建研究</a></div></header>
    {error&&<p role="alert">{error}</p>}{loading&&<p role="status">正在读取研究记录…</p>}
    <div className="org-research-layout"><section className="pw-card org-records"><h3>项目研究</h3>{rows.map(row=><button className="pw-row" aria-current={id===row.execution_id?'true':undefined} key={row.execution_id} onClick={()=>setParams(p=>{p.set('execution',row.execution_id);return p;})}><FileText size={17}/><span>{row.title}<small>{row.run_id?'已有运行记录':'待确认启动'}</small></span></button>)}
      {!loading&&!error&&!rows.length&&<p>本页没有当前有权读取的研究记录。</p>}<div className="pw-toolbar"><button disabled={loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-30))}>上一页研究</button><button disabled={loading||next===null} onClick={()=>next!==null&&setOffset(next)}>下一页研究</button></div></section>
      <article className="pw-card org-document" aria-label="组织研究内容">{snapshot?<><span className="org-eyebrow">PROJECT RESEARCH</span><h3>{snapshot.title}</h3><p className="org-status">{snapshot.status==='busy'?'正在执行研究':snapshot.status==='error'?'运行异常，请核对原记录':phases[snapshot.phase||'']||'研究记录'}</p><OrganizationResearchActions key={`${id}:${snapshot.checkpoint_id}`} base={`${base}/${id}`} phase={snapshot.phase} hasReport={!!snapshot.report} busyRun={snapshot.status==='busy'} citations={Object.keys(snapshot.report?.citations||{})} onChanged={()=>refresh(n=>n+1)}/><OrganizationResearchEvents key={`${id}:${snapshot.run_id}`} base={`${base}/${id}`} run={snapshot.run_id} verifyAccess={async()=>{const current=generation.current;try{await assetRequest(`${base}/${id}`);return current===generation.current;}catch(e){if(current===generation.current){setSnapshot(null);setRows([]);setSource(null);setError((e as Error).message);}return false;}}}/>
        {!!snapshot.conversation?.length&&<section aria-label="报告交流记录"><h4>报告交流</h4>{snapshot.conversation.map((m,i)=><div className="org-finding" key={i}><strong>{m.role==='user'?'你的问题与意见':m.role==='assistant'?'研究回复':'操作说明'}</strong><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>)}</section>}
        {snapshot.research_orientation&&<section className="org-orientation"><h4>预研究判断</h4><ReactMarkdown remarkPlugins={[remarkGfm]}>{snapshot.research_orientation.overview||''}</ReactMarkdown>{snapshot.research_orientation.findings?.map(f=><div className="org-finding" key={f.finding_id}><p>{f.judgment}</p>{f.unresolved&&<p>待核查：{f.unresolved}</p>}</div>)}<p className="pw-muted">预研究供确定方向，不表示正式研究完成或结论通过审批。</p></section>}
        {snapshot.report?<><h4>{snapshot.report.title}</h4><ReactMarkdown remarkPlugins={[remarkGfm]}>{snapshot.report.narrative_markdown}</ReactMarkdown><OrganizationReportDownload key={`${base}/${id}:${revision}:${snapshot.checkpoint_id}`} base={`${base}/${id}`} checkpointId={snapshot.checkpoint_id} onDenied={message=>{++generation.current;setRows([]);setSnapshot(null);setSource(null);setError(message);}}/>
          {distinct.length>0&&<section aria-label="组织报告引用"><h4>引用快照</h4>{distinct.map(s=><button key={s.source_id} onClick={()=>void readSource(s.source_id)}>查看引用 {s.source_id}</button>)}</section>}</>:<p>这项研究尚无报告。已保存的预研究内容不作为报告导出。</p>}
        {source&&<section aria-label="引用快照内容"><h4>{source.source_id}</h4><p>{source.period} {source.unit}</p><p style={{whiteSpace:'pre-wrap'}}>{source.text}</p><p className="pw-muted">这是成果保存的引用片段；完整原件需从项目资料按当前权限阅读。</p>{source.next_offset!=null&&<button onClick={()=>void readSource(source.source_id,source.next_offset!)}>继续读取引用</button>}</section>}
      </>:!loading&&<div className="org-reading-empty"><FileText size={32}/><h3>把研究放回项目中</h3><p>选择一项研究，查看预研究、运行进展与报告。<br/>新研究从问题和项目资料开始。</p></div>}</article></div>
  </section>;
}
