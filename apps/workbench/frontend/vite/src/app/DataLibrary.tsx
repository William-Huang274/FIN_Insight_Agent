import { useEffect, useRef, useState } from "react";
import { BookOpen, Database, ExternalLink, Search, X, ArrowRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./data-library.css";

type Source = { document_id:string; title:string; ticker:string; company:string; fiscal_period:string; period_end:string; publication_date:string; source_role:string; stable_url:string; preview:string; sections:number; passages:number };
type Financial = { ticker:string; legal_name:string; metric_id:string; value_decimal:string; unit:string; period_start:string; period_end:string; fiscal_year:number; fiscal_period:string; filed_at:string; citation_url:string; superseded_by_observation_id:string|null };
type Result = { items:(Source|Financial)[]; total:number; tickers:string[]; years:(string|number)[]; kinds?:string[]; metrics?:string[]; metric_labels?:Record<string,string>; periods?:string[]; notice:string };
const labels:Record<string,string> = {hyperscaler_demand_primary:"云厂商披露",industry_benchmark_primary:"行业资料",issuer_filing_narrative:"公司申报文件",issuer_management_disclosure:"公司业绩披露",model_provider_primary:"模型厂商资料",named_deployment_primary:"产品部署资料",peer_financial_disclosure:"同业财务披露",peer_management_disclosure:"同业业绩披露",regulator_primary:"监管资料",supplier_management_disclosure:"供应商业绩披露",supplier_platform_primary:"供应商产品资料","10-K":"年度报告 · 10-K","10-Q":"季度报告 · 10-Q","8-K":"重要事项 · 8-K",earnings_release:"业绩新闻稿",revenue:"营业收入",operating_cash_flow:"经营现金流",capital_expenditures:"资本开支",net_income:"净利润"};
export function DataLibrary({page,navigate,onSupplement}:{page:string;navigate:(page:string,id?:string)=>void;onSupplement:(question:string)=>void}) {
  const financial = page === "financial-data";
  const [query,setQuery]=useState(""); const [ticker,setTicker]=useState(""); const [year,setYear]=useState("");
  const [kind,setKind]=useState(""); const [offset,setOffset]=useState(0); const [submitted,setSubmitted]=useState("");
  const [asOf,setAsOf]=useState(""); const [period,setPeriod]=useState("");
  const reader=useRef<HTMLDialogElement>(null);
  const supplement=()=>onSupplement(`请研究并补充 ${ticker||"所选公司"} ${year||"所需期间"} 的 ${submitted||"公开财务资料"}。优先查询本地公司资料库和财务数据库；本地不足时允许查找并读取 SEC 或公司官网公开披露，保留来源和资料时点。`);
  const [storedData,setData]=useState<(Result&{financial:boolean})|null>(null); const [error,setError]=useState(""); const [loading,setLoading]=useState(false);
  const data=storedData?.financial===financial?storedData:null;
  const [selected,setSelected]=useState<Source|null>(null); const [sections,setSections]=useState<{title:string;text:string}[]>([]);
  const [sectionTotal,setSectionTotal]=useState(0); const [readOffset,setReadOffset]=useState(0); const [readError,setReadError]=useState("");
  useEffect(()=>{setOffset(0);setKind("");setData(null);setYear("");setSelected(null);},[page]);
  useEffect(()=>{
    const controller=new AbortController(); setLoading(true);setError("");
    const params=new URLSearchParams({query:submitted,ticker,offset:String(offset),limit:"24"});
    if(year) params.set(financial?"fiscal_year":"year",year);
    if(kind) params.set(financial?"metric":"kind",kind);
    if(asOf) params.set("as_of",asOf);
    if(financial&&period) params.set("period",period);
    fetch(`/api/v1/data-library/${financial?"financials":"sources"}?${params}`,{signal:controller.signal})
      .then(async r=>{if(!r.ok)throw new Error((await r.json()).detail||"资料暂不可用");return r.json();})
      .then(r=>setData({...r,financial})).catch(e=>{if(e.name!=="AbortError")setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[financial,submitted,ticker,year,kind,offset,asOf,period]);
  useEffect(()=>{
    if(!selected)return;
    reader.current?.showModal();
    const controller=new AbortController();setReadError("");setSections([]);
    fetch(`/api/v1/data-library/sources/${encodeURIComponent(selected.document_id)}?offset=${readOffset}`,{signal:controller.signal})
      .then(async r=>{if(!r.ok)throw new Error("原文暂不可用");return r.json();}).then(r=>{setSections(r.sections);setSectionTotal(r.total);})
      .catch(e=>{if(e.name!=="AbortError")setReadError(e.message);});return ()=>controller.abort();
  },[selected,readOffset]);
  return <section className="fs-page dl-page">
    <header className="dl-heading"><div><span className="fs-kicker">LIBRARY & DATA</span><h1>{financial?"财务数据":"公司资料库"}</h1><p>{financial?"直接查阅已保存的财务数字，核对期间、单位与披露版本。":"先看看有哪些资料，再开始有依据的研究。"}</p></div><button onClick={()=>navigate(financial?"library":"financial-data")}><Database size={17}/>{financial?"浏览公司资料":"查询财务数据"}<ArrowRight size={16}/></button></header>
    <form className="dl-filters" onSubmit={e=>{e.preventDefault();setOffset(0);setSubmitted(query);}}>
      <label><Search size={17}/><input aria-label="资料关键词" placeholder={financial?"公司、指标中英文名称或 SEC 标签":"搜索公司或资料标题"} value={query} onChange={e=>setQuery(e.target.value)}/></label>
      <select aria-label="公司" value={ticker} onChange={e=>{setTicker(e.target.value);setOffset(0);}}><option value="">全部公司</option>{data?.tickers.map(t=><option key={t}>{t}</option>)}</select>
      <select aria-label={financial?"财年":"报告期结束年份"} value={year} onChange={e=>{setYear(e.target.value);setOffset(0);}}><option value="">{financial?"全部财年":"全部报告期年份"}</option>{data?.years.map(y=><option key={y}>{y}</option>)}</select>
      <select aria-label={financial?"指标":"资料类型"} value={kind} onChange={e=>{setKind(e.target.value);setOffset(0);}}><option value="">{financial?"全部指标":"全部资料类型"}</option>{(financial?data?.metrics:data?.kinds)?.map(k=><option key={k} value={k}>{data?.metric_labels?.[k]||labels[k]||k.replaceAll('_',' ')}</option>)}</select>
      {financial&&<select aria-label="财务期间" value={period} onChange={e=>{setPeriod(e.target.value);setOffset(0);}}><option value="">全部期间</option>{data?.periods?.map(p=><option key={p}>{p}</option>)}</select>}
      <label className="dl-date">披露截至<input aria-label="披露截至日期" type="date" value={asOf} onChange={e=>{setAsOf(e.target.value);setOffset(0);}}/></label><button type="submit">查询</button>
    </form>
    <div className="dl-summary"><strong>{data?.total??"—"} {financial?"条披露记录":"份公共资料"}</strong><span>{data?.notice}</span></div>
    {error&&<p role="alert">{error}</p>}{loading&&<p role="status">正在读取资料…</p>}
    {!loading&&!error&&data?.total===0&&<div className="dl-empty"><BookOpen/><h2>当前筛选范围尚无资料</h2><p>这表示本地覆盖不足，不代表公司未披露。可允许研究使用公开外源补充，或添加你持有的原始文件。</p><button onClick={supplement}>开始研究并补充资料</button></div>}
    {!financial&&<div className="dl-cards">{(data?.items as Source[]||[]).map(s=><button className="dl-card" key={s.document_id} onClick={()=>{setSelected(s);setReadOffset(0);}}><div className="dl-cover"><span>{s.ticker||"公开资料"}</span><BookOpen size={28}/><strong>{labels[s.source_role]||s.source_role?.replaceAll('_',' ')}</strong><small>{s.period_end||s.fiscal_period}</small></div><div><small>{s.company} · 发布于 {s.publication_date}</small><h2>{s.title.replace("earnings_release","业绩新闻稿")}</h2><div className="dl-preview"><ReactMarkdown components={{a:({children})=><span>{children}</span>,img:()=>null,p:({children})=><span>{children}</span>}}>{s.preview}</ReactMarkdown></div><footer>{s.sections} 个章节 · 查看内容 <ArrowRight size={16}/></footer></div></button>)}</div>}
    {financial&&!!data?.items.length&&<div className="dl-table"><table><thead><tr>{["公司 / 财年","指标","数值 / 来源单位","期间","披露版本","原始披露"].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{(data.items as Financial[]).map((r,i)=><tr key={i}><td><b>{r.ticker}</b><br/>FY{r.fiscal_year} {r.fiscal_period}</td><td>{data?.metric_labels?.[r.metric_id]||labels[r.metric_id]||r.metric_id.replaceAll('_',' ')}</td><td><strong>{r.value_decimal}</strong><br/>{r.unit}</td><td>{r.period_start||"时点"}<br/>{r.period_end}</td><td>{r.filed_at}<br/>{r.superseded_by_observation_id?"有后续披露版本":"保留版本"}</td><td><a href={r.citation_url} target="_blank" rel="noreferrer">查看来源 <ExternalLink size={14}/></a></td></tr>)}</tbody></table></div>}
    <div className="dl-pagination"><button disabled={offset===0||loading} onClick={()=>setOffset(Math.max(0,offset-24))}>上一页</button><span>第 {Math.floor(offset/24)+1} 页</span><button disabled={!data||offset+24>=data.total||loading} onClick={()=>setOffset(offset+24)}>下一页</button></div>
    {!financial&&<aside className="dl-supplement"><strong>没有所需的公司或期间？</strong><p>允许研究搜索并读取公开披露；外源读取按现有缓存策略复用。个人上传文件仍属于对应研究，不会自动进入公共资料库。</p><button onClick={supplement}>准备外源补充研究</button></aside>}
    {selected&&<dialog ref={reader} className="dl-overlay" aria-label="公共资料阅读" onCancel={()=>setSelected(null)}><article className="dl-reader"><header><div><small>{selected.company} · {selected.publication_date}</small><h2>{selected.title}</h2><a href={selected.stable_url} target="_blank" rel="noreferrer">打开官方原文 <ExternalLink size={14}/></a></div><button autoFocus aria-label="关闭公共资料" onClick={()=>setSelected(null)}><X/></button></header><div className="dl-reading">{readError&&<p role="alert">{readError}</p>}{!sections.length&&!readError&&<p>正在读取正文…</p>}{sections.map((s,i)=><section key={i}><h3>{s.title}</h3><ReactMarkdown remarkPlugins={[remarkGfm]}>{s.text}</ReactMarkdown></section>)}</div><footer><button disabled={readOffset===0} onClick={()=>setReadOffset(Math.max(0,readOffset-5))}>前五章</button><span>{readOffset+1}–{Math.min(readOffset+5,sectionTotal)} / {sectionTotal} 章</span><button disabled={readOffset+5>=sectionTotal} onClick={()=>setReadOffset(readOffset+5)}>后五章</button></footer></article></dialog>}
  </section>;
}
