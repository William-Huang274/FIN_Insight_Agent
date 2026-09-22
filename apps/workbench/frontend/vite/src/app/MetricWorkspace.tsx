import {useEffect,useMemo,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {ArrowLeft,ArrowUpRight,BarChart3,ChevronRight,LayoutGrid,List,Search,X} from 'lucide-react';
import {displayNumber} from './FinancialDataViews';
import './metric-workspace.css';
import MetricReviewPanel,{type MetricReview} from './MetricReviewPanel';

type Company={entity_id:string;name:string};
type Basis={label:string;fiscal_year:number|null;fiscal_period:string|null;period_kind:string;start:string|null;end:string|null};
type Input={display_label?:string;id?:string;concept?:string;role?:string;value?:string;unit?:string;period_start?:string;period_end?:string;trade_date?:string;source_id?:string;components?:Input[];derivation?:string};
type Row={id:string;entity_id:string;company_name:string;metric:string;label:string;value:string|null;unit:string;status:string;period_label:string;period_kind:string;group:string;record_type:string;value_state:string;observation_kind:string;observation_date:string;axis_key:string|null;financial_basis?:Basis;available_at:string;formula?:string;formula_version?:string;inputs?:Input[];comparison_note:string;source_id?:string;sources?:{id:string;title:string;url:string;published_at:string}[];detail?:{missing?:string[];security_basis?:{share_count_note?:string}};text_value?:string;qualifiers?:string[];comparator?:string;business_scope?:string;evidence_quote?:string;evidence_locator?:string;available_at_basis?:string;chart_policy?:string;effective_at?:string;reference_year?:number;reference_date_precision?:string};
type Catalog={id:string;label:string;group:string;units:string[];companies:string[];period_kinds:string[]};
type Result={industry_reviews?:MetricReview[];items:Row[];total:number;next_offset:number|null;metric_catalog:Catalog[];fiscal_years:number[];coverage:{entity_id:string;count:number;state:string}[];comparison:{state:string;notes:string[]}};
type Section='overview'|'history'|'valuation'|'compare';
const groups:Record<string,string>={profitability:'盈利能力',cashflow:'现金流与投入',solvency:'偿债能力',efficiency:'回报与效率',growth:'增长表现',valuation:'市场估值',industry:'行业与业务'};
const kinds:Record<string,string>={quarter:'单季',ytd:'累计',annual:'全年',instant:'期末时点',daily:'日频',unknown:'期间待核',event:'事件',ttm:'滚动十二个月'};
const statuses:Record<string,string>={available:'有效',missing_inputs:'缺少输入',missing_fx:'缺少汇率',not_meaningful_nonpositive_earnings:'亏损，不适用PE',not_meaningful_nonpositive_base:'分母非正，不适用',stale_or_invalid_share_count:'股数过旧或无效',stale_earnings:'盈利期间过旧',stale_financial_input:'财务输入过旧',invalid_denominator_or_sign:'分母或符号不适用',nonpositive_comparison_base:'比较基数不适用',reported:'公司披露'};
const colors=['#5558d9','#168177','#c57725','#a34d79','#527da4','#8a6a39','#6c8750','#835bc0','#ca6553','#477b88','#9a8327','#745f7b'];
const stateName=(r:Row)=>statuses[r.status]||r.status;
const valueText=(r:Row,digits:number)=>r.value==null&&r.text_value?'文字披露':(r.comparator&&r.comparator!=='eq'?({gt:'>',ge:'≥',lt:'<',le:'≤',approx:'约 ',text:''}[r.comparator]||''):'')+displayNumber(r.value,digits);
const stateLabel:Record<string,string>={actual:'实际',plan:'计划',guidance:'指引'};
const axisOrder=(a:string,b:string)=>{const parse=(v:string)=>{const m=/^FY(\d+) (Q[1-4]|FY) /.exec(v);return m?Number(m[1])*10+(m[2]==='FY'?5:Number(m[2][1])):null;};const x=parse(a),y=parse(b);return x!=null&&y!=null?x-y||a.localeCompare(b):a.localeCompare(b);};
async function query(body:Record<string,unknown>,signal?:AbortSignal):Promise<Result>{
  const res=await fetch('/api/v1/data-library/metrics/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});
  const data=await res.json();if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'指标读取失败，请稍后重试');return data;
}

function Trend({rows,digits,open,alignment,frequency}:{rows:Row[];digits:number;open:(r:Row)=>void;alignment:string;frequency:string}){
  const [hidden,setHidden]=useState<Set<string>>(new Set());
  const [selected,setSelected]=useState<Row|null>(null);
  const series=useMemo(()=>{
    const all=new Map<string,Row[]>();
    for(const r of rows){const key=`${r.entity_id}|${r.period_kind}|${r.unit}|${r.value_state}|${(r as Row & {series_scope?:string}).series_scope||r.business_scope||''}`;all.set(key,[...(all.get(key)||[]),r]);}
    return [...all.entries()].map(([id,values])=>({id,values:values.sort((a,b)=>axisOrder(a.axis_key||'',b.axis_key||'')),name:`${values[0].company_name}${values[0].record_type==='reported'?' · '+values[0].label:''} · ${kinds[values[0].period_kind]||values[0].period_kind}${values[0].value_state!=='actual'?' · '+(stateLabel[values[0].value_state]||values[0].value_state):''}`}));
  },[rows]);
  const plotted=series.filter(s=>!hidden.has(s.id));
  const values=plotted.flatMap(s=>s.values).filter(r=>r.value!=null&&r.axis_key&&(!r.comparator||r.comparator==='eq')&&Number.isFinite(Number(r.value)));
  const legend=<div className="mw-legend">{series.map((s,i)=><button key={s.id} aria-pressed={!hidden.has(s.id)} onClick={()=>setHidden(prev=>{const next=new Set(prev);next.has(s.id)?next.delete(s.id):next.add(s.id);return next;})}><i style={{background:colors[i%colors.length],opacity:hidden.has(s.id)?.25:1}}/>{s.name}</button>)}</div>;
  const units=[...new Set(values.map(r=>r.unit))];
  if(units.length>1)return <div className="mw-empty">当前数据含多种单位，请先选择一个单位，避免共用刻度造成误读。</div>;
  if(!values.length)return <div className="mw-chart">{legend}<div className="mw-empty">{hidden.size===series.length?'所有序列已隐藏，点击上方图例可恢复。':'当前没有精确数值可绘制。文字、约数、上下限及缺项请在列表或数据卡查看。'}</div></div>;
  const keys=[...new Set(values.map(r=>r.axis_key!))].sort(axisOrder);
  const dateAxis=alignment==='date';
  const keyNumber=(k:string)=>dateAxis?Date.parse(k):keys.indexOf(k);
  const xs=keys.map(keyNumber),xMin=Math.min(...xs),xMax=Math.max(...xs);
  const nums=values.map(r=>Number(r.value)),low=Math.min(...nums),high=Math.max(...nums),padding=(high-low||Math.abs(high)||1)*.12;
  const yMin=low-padding,yMax=high+padding;
  const x=(r:Row)=>76+(keyNumber(r.axis_key!)-xMin)/(xMax-xMin||1)*828;
  const y=(r:Row)=>280-(Number(r.value)-yMin)/(yMax-yMin)*242;
  const tick=(v:number)=>new Intl.NumberFormat('zh-CN',{notation:Math.abs(v)>=1e6?'compact':'standard',maximumFractionDigits:2}).format(v);
  return <div className="mw-chart">{legend}
    <svg viewBox="0 0 960 340" role="img" aria-label="指标趋势图，点击数据点打开数据卡">
      {[0,1,2,3,4].map(i=><g key={i}><line x1="76" x2="904" y1={38+i*60.5} y2={38+i*60.5} stroke="var(--line)" strokeDasharray="3 5"/><text x="65" y={42+i*60.5} textAnchor="end">{tick(yMax-i*(yMax-yMin)/4)}</text></g>)}
      {keys.filter((_,i)=>i===0||i===keys.length-1||i%Math.max(1,Math.ceil(keys.length/5))===0).map(k=><text key={k} x={76+(keyNumber(k)-xMin)/(xMax-xMin||1)*828} y="310" textAnchor="middle">{k}</text>)}
      {series.map((s,i)=>{if(hidden.has(s.id))return null;let prev:Row|null=null;const lines:React.ReactNode[]=[];return <g key={s.id}>{s.values.map(r=>{if(r.value==null||!r.axis_key||(r.comparator&&r.comparator!=='eq')||!Number.isFinite(Number(r.value))){prev=null;return null;}const gap=prev?(Date.parse(r.observation_date)-Date.parse(prev.observation_date))/86400000:0;
        const maxGap=r.period_kind==='daily'?(frequency==='month_end'?40:frequency==='week_end'?10:7):r.period_kind==='annual'?410:r.period_kind==='ytd'?220:140;
        if(prev&&r.chart_policy!=='points_only'&&prev.chart_policy!=='points_only'&&r.value_state==='actual'&&r.period_kind!=='event'&&(!dateAxis||gap<=maxGap))lines.push(<line key={'l'+r.id} x1={x(prev)} y1={y(prev)} x2={x(r)} y2={y(r)} stroke={colors[i%colors.length]} strokeWidth="2"/>);prev=r;
        return <g key={r.id} role="button" tabIndex={0} aria-label={`${r.company_name} ${r.period_label} ${valueText(r,digits)} ${r.unit}`} onMouseEnter={()=>setSelected(r)} onFocus={()=>setSelected(r)} onClick={()=>open(r)} onKeyDown={e=>{if(e.key==='Enter')open(r);}}><circle cx={x(r)} cy={y(r)} r="9" fill="transparent"/><circle cx={x(r)} cy={y(r)} r={s.values.length>90?2.3:4} fill={colors[i%colors.length]} stroke="var(--surface)" strokeWidth="1.5"/><title>{`${r.company_name} · ${r.period_label}：${valueText(r,digits)} ${r.unit}`}</title></g>;
      })}{lines}</g>})}
      <text x="76" y="18">{units[0]}</text>
    </svg><div className="mw-chart-readout">{selected?<><span>{selected.company_name} · {selected.period_label}</span><strong>{displayNumber(selected.value,digits)} {selected.unit}</strong><button onClick={()=>open(selected)}>查看数据卡 <ArrowUpRight size={13}/></button></>:<span>指向数据点查看数值，点击打开数据卡。缺失值不补零、不插值。</span>}</div>
  </div>;
}

function ComparisonTable({rows,companies,digits,open,alignment}:{rows:Row[];companies:Company[];digits:number;open:(r:Row)=>void;alignment:string}){
  const grouped=new Map<string,Row[]>();
  for(const r of rows){const key=`${r.period_kind} · ${r.unit} · ${stateLabel[r.value_state]||r.value_state}`;grouped.set(key,[...(grouped.get(key)||[]),r]);}
  return <>{[...grouped.entries()].map(([group,values])=>{
    const keys=[...new Set(values.map(r=>r.axis_key||r.observation_date))].sort(axisOrder).reverse();
    return <section className="mw-comparison-section" key={group}><h3>{group.replace(values[0].period_kind,kinds[values[0].period_kind]||values[0].period_kind)}</h3><div className="mw-history-table"><table><thead><tr><th>{alignment==='fiscal'?'公司财务阶段':'实际日期'}</th>{companies.map(c=><th key={c.entity_id}>{c.name}</th>)}</tr></thead><tbody>{keys.map(key=><tr key={key}><td>{key}</td>{companies.map(c=>{const cells=values.filter(r=>r.entity_id===c.entity_id&&(r.axis_key||r.observation_date)===key);return <td key={c.entity_id}>{cells.length?cells.map(r=><button key={r.id} className="mw-comparison-cell" onClick={()=>open(r)}><strong>{valueText(r,digits)} {r.unit}</strong><small>{r.period_label}</small>{r.business_scope&&<small>{r.business_scope}</small>}<span>数据卡 ↗</span></button>):<span className="mw-missing">— 暂无同日／同期记录</span>}</td>;})}</tr>)}</tbody></table></div></section>;
  })}</>;
}

function DataCard({row,digits,close,onSource}:{row:Row;digits:number;close:()=>void;onSource:(id:string)=>void}){
  const ref=useRef<HTMLDivElement>(null),[path,setPath]=useState<Input[]>([]);
  const input=path[path.length-1];
  useEffect(()=>{const prev=document.activeElement as HTMLElement|null;ref.current?.focus();function key(e:KeyboardEvent){if(document.querySelector('.dl-overlay,.cw-reader-backdrop'))return;if(e.key==='Escape'){e.stopImmediatePropagation();close();}if(e.key==='Tab'){const items=ref.current?.querySelectorAll<HTMLElement>('button,a,[tabindex="0"]');if(!items?.length)return;const first=items[0],last=items[items.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}}document.addEventListener('keydown',key,true);return()=>{document.removeEventListener('keydown',key,true);prev?.focus();};},[close]);
  const inputs=input?(input.components||[]):(row.inputs||[]);
  const businessNotes=(row.qualifiers||[]).filter(q=>!/r17|numeric cells|machine-verifiable|value_in_source|native validator|original millions token|direct official HTML was captured/i.test(q));
  return createPortal(<div className="mw-card-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)close();}}><div className="mw-data-card" ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label="指标数据卡"><header><div><small>DATA RECORD · {row.company_name}</small><h2>{input?.display_label||input?.concept||input?.role||row.label}</h2></div><button aria-label="关闭数据卡" onClick={close}><X size={21}/></button></header>
    <div className="mw-card-content">{path.length>0&&<button className="mw-back" onClick={()=>setPath(path.slice(0,-1))}><ArrowLeft size={14}/>返回上一级依据</button>}
      <div className="mw-card-value">{input?displayNumber(input.value,digits):valueText(row,digits)} <small>{(input?.unit||row.unit)==='text'?'':(input?.unit||row.unit)}</small></div>
      {!input&&<div className="mw-badges"><span>{row.record_type==='calculated'?'标准公式计算':'公司披露'}</span>{row.status!=='reported'&&<span>{stateName(row)}</span>}<span>{stateLabel[row.value_state]||row.value_state}</span></div>}
      <dl className="mw-card-facts"><dt>{row.observation_kind==='valuation'&&!input?'估值日':'数据日期'}</dt><dd>{input?.trade_date||input?.period_end||row.observation_date||'未确认'}</dd>{row.financial_basis&&!input&&<><dt>财务依据</dt><dd>{row.financial_basis.label}<small>{row.financial_basis.start?row.financial_basis.start+' — ':''}{row.financial_basis.end}</small></dd></>}{row.effective_at&&!input&&<><dt>生效时间（UTC）</dt><dd>{row.effective_at}</dd></>}{row.reference_year&&!input&&<><dt>回顾所指年份</dt><dd>{row.reference_year} · 原文未给精确测量日</dd></>}<dt>{row.available_at_basis==='capture_date_publication_unknown'?'采集可知日':'公开／可获知日'}</dt><dd>{row.available_at||'未确认'}</dd></dl>
      {!input&&<p className="mw-card-note">{row.comparison_note}</p>}{row.text_value&&!input&&<p>{row.text_value}</p>}{businessNotes.map(q=><p key={q} className="mw-card-note">{q}</p>)}
      {!input&&row.evidence_quote&&<section><h3>披露依据</h3><blockquote>{row.evidence_quote}</blockquote><small>{row.evidence_locator}</small></section>}{(input?.derivation||row.formula)&&<section><h3>计算方法</h3><code>{input?.derivation||row.formula}</code></section>}
      {inputs.length>0&&<section><h3>计算输入 <small>{inputs.length} 项</small></h3><div className="mw-input-list">{inputs.map((v,i)=><button key={v.id||i} onClick={()=>v.components?.length?setPath([...path,v]):v.source_id?onSource(v.source_id):setPath([...path,v])}><span><strong>{v.role&&/^[a-z]$/.test(v.role)?v.role+' · ':''}{v.display_label||v.concept||v.role||'输入'}</strong><small>{v.trade_date||v.period_end||'日期未确认'}{v.period_start?' · 自 '+v.period_start:''}</small></span><span>{displayNumber(v.value,digits)} {v.unit}</span><ChevronRight size={14}/></button>)}</div></section>}
      {input?.source_id&&<button onClick={()=>onSource(input.source_id!)}>查看该输入原文</button>}
      {!input&&row.sources?.length!==0&&<section><h3>来源材料</h3>{row.sources?.map(s=><button className="mw-source" key={s.id} onClick={()=>onSource(s.id)}><span>{s.title}<small>{s.published_at||'发布日期未确认'}</small></span><ArrowUpRight size={15}/></button>)}</section>}
      {!input&&<details><summary>记录与版本</summary><dl className="mw-card-facts"><dt>记录编号</dt><dd>{row.id}</dd><dt>公式版本</dt><dd>{row.formula_version||'原始披露'}</dd></dl>{row.detail?.security_basis?.share_count_note&&<p>{row.detail.security_basis.share_count_note}</p>}{row.detail?.missing?.length&&<p>缺少输入：{row.detail.missing.join('、')}</p>}{row.qualifiers?.filter(q=>!businessNotes.includes(q)).map(q=><p key={q}>{q}</p>)}</details>}
    </div><footer>显示数值经过舍入；原始精度、日期及出处完整保留。</footer></div></div>,document.body);
}

export default function MetricWorkspace({entityId,companies,onSource}:{entityId:string;companies:Company[];onSource:(id:string)=>void}){
  const [section,setSection]=useState<Section>('overview'),[display,setDisplay]=useState<'table'|'chart'>('table');
  const [metric,setMetric]=useState(''),[period,setPeriod]=useState(''),[year,setYear]=useState(''),[start,setStart]=useState(''),[end,setEnd]=useState(''),[frequency,setFrequency]=useState('native'),[alignment,setAlignment]=useState('date');
  const [selected,setSelected]=useState([entityId]),[companySearch,setCompanySearch]=useState(''),[search,setSearch]=useState(''),[digits,setDigits]=useState(2),[unit,setUnit]=useState('');
  const [data,setData]=useState<Result|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[card,setCard]=useState<Row|null>(null),[offset,setOffset]=useState(0);
  const [catalog,setCatalog]=useState<Catalog[]>([]),[years,setYears]=useState<number[]>([]);
  useEffect(()=>{setSelected([entityId]);setMetric('');setYear('');setPeriod('');setStart('');setEnd('');setCard(null);setUnit('');setOffset(0);},[entityId]);
  const ids=section==='compare'?selected:[entityId];const identity=ids.join('|');
  useEffect(()=>{const controller=new AbortController();query({entity_ids:ids,section:'catalog'},controller.signal).then(v=>{setCatalog(v.items as unknown as Catalog[]);setYears(v.fiscal_years||[]);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>controller.abort();},[identity]);
  useEffect(()=>{if(section==='compare'&&!metric){setData(null);return;}const controller=new AbortController();setBusy(true);setError('');setData(null);
    query({entity_ids:ids,section,metric,fiscal_year:year?Number(year):null,period_kind:period,date_start:start,date_end:end,frequency,alignment,offset:display==='chart'||section==='compare'?0:offset,limit:display==='chart'||section==='compare'?2000:section==='overview'?500:60},controller.signal).then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setBusy(false);});return()=>controller.abort();
  },[identity,section,metric,period,year,start,end,frequency,alignment,offset,display]);
  const cardRequest=useRef(0);
  async function open(r:Row){const request=++cardRequest.current;try{const result=await query({entity_ids:[r.entity_id],section:'card',record_id:r.id});if(request===cardRequest.current)setCard(result.items[0]);}catch(e){setError(e instanceof Error?e.message:'数据卡读取失败');}}
  function changeSection(s:Section){setSection(s);setOffset(0);setYear('');setPeriod('');setMetric('');setDisplay('table');setUnit('');setAlignment('date');setFrequency('native');}
  function reset(){setMetric('');setYear('');setPeriod('');setStart('');setEnd('');setUnit('');setOffset(0);}
  const rows=(data?.items||[]).filter(r=>(!unit||r.unit===unit)&&(!search||r.label.toLowerCase().includes(search.toLowerCase())));
  const units=[...new Set((data?.items||[]).map(r=>r.unit))];
  const selectedCatalog=catalog.find(c=>c.id===metric);
  return <div className="mw-workspace"><div className="mw-title"><div><span className="mw-eyebrow">METRIC EXPLORER</span><h2>指标分析</h2><p>从一个数值，到它的变化与依据。</p></div><label className="mw-digits">小数位<select aria-label="指标显示精度" value={digits} onChange={e=>setDigits(Number(e.target.value))}>{[2,4,6].map(d=><option key={d}>{d}</option>)}</select></label></div>
    <nav className="mw-tabs" aria-label="指标分析视图">{([['overview','指标总览'],['history','财务与经营历史'],['valuation','估值走势'],['compare','公司对比']] as const).map(([v,label])=><button key={v} aria-current={section===v?'page':undefined} onClick={()=>changeSection(v)}>{label}</button>)}</nav>
    {section==='compare'&&<div className="mw-company-picker"><div className="mw-company-chips">{selected.map(id=><button key={id} onClick={()=>{if(selected.length>1)setSelected(selected.filter(x=>x!==id));}}>{companies.find(c=>c.entity_id===id)?.name||id}<X size={12}/></button>)}<span>{selected.length} / 12 家</span></div><label><Search size={15}/><input aria-label="搜索对比公司" placeholder="搜索并加入公司…" value={companySearch} onChange={e=>setCompanySearch(e.target.value)}/></label>{companySearch&&<div className="mw-company-results">{companies.filter(c=>!selected.includes(c.entity_id)&&(c.name+c.entity_id).toLowerCase().includes(companySearch.toLowerCase())).slice(0,8).map(c=><button key={c.entity_id} disabled={selected.length>=12} onClick={()=>{setSelected([...selected,c.entity_id]);setCompanySearch('');setOffset(0);}}>{c.name}<span>加入对比 ＋</span></button>)}</div>}</div>}
    <div className="mw-controls"><label>指标<select aria-label="分析指标" value={metric} onChange={e=>{setMetric(e.target.value);setOffset(0);setUnit('');setPeriod('');setYear('');setAlignment('date');}}><option value="">{section==='compare'?'请选择一个指标':'全部指标'}</option>{Object.entries({...groups,industry:'行业与业务'}).map(([g,label])=><optgroup key={g} label={label}>{catalog.filter(c=>c.group===g&&(section!=='valuation'||g==='valuation')&&(section!=='history'||g!=='valuation')).map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</optgroup>)}</select></label>
      {section!=='valuation'&&selectedCatalog?.group!=='valuation'&&<><label>公司财年<select aria-label="指标公司财年" value={year} onChange={e=>{setYear(e.target.value);setOffset(0);}}><option value="">全部财年</option>{years.map(y=><option key={y} value={y}>FY{y}</option>)}</select></label><label>期间口径<select aria-label="指标期间口径" value={period} onChange={e=>{setPeriod(e.target.value);setOffset(0);}}><option value="">全部口径</option>{Object.entries(kinds).filter(([k])=>k!=='daily').map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label></>}
      {section!=='overview'&&<><label>{section==='valuation'||selectedCatalog?.group==='valuation'?'估值日起':'观察日起'}<input aria-label="指标起始日期" type="date" value={start} max={end||undefined} onChange={e=>{setStart(e.target.value);setOffset(0);}}/></label><label>截至<input aria-label="指标截至日期" type="date" value={end} min={start||undefined} onChange={e=>{setEnd(e.target.value);setOffset(0);}}/></label></>}
      {(section==='valuation'||selectedCatalog?.group==='valuation')&&<label>显示频率<select aria-label="估值显示频率" value={frequency} onChange={e=>{setFrequency(e.target.value);setOffset(0);}}><option value="native">交易日</option><option value="week_end">周末</option><option value="month_end">月末</option></select></label>}
      {section==='compare'&&selectedCatalog?.group!=='valuation'&&<label>时间对齐<select aria-label="公司比较时间轴" value={alignment} onChange={e=>setAlignment(e.target.value)}><option value="date">实际日期</option><option value="fiscal">公司财务阶段</option></select></label>}
      {units.length>1&&<label>单位<select aria-label="指标单位" value={unit} onChange={e=>setUnit(e.target.value)}><option value="">全部单位</option>{units.map(u=><option key={u}>{u}</option>)}</select></label>}<button className="mw-clear" onClick={reset}>重置筛选</button>
    </div>
    {section!=='overview'&&<div className="mw-result-toolbar"><span>{data?.total??0} 条观测{section==='compare'?' · '+ids.length+' 家公司':''}</span><div className="mw-display-switch"><button aria-pressed={display==='table'} onClick={()=>{setDisplay('table');setOffset(0);}}><List size={15}/>列表</button><button aria-pressed={display==='chart'} disabled={!metric} title={!metric?'先选一个指标，避免不同单位共用刻度':''} onClick={()=>{setDisplay('chart');setOffset(0);}}><BarChart3 size={15}/>趋势</button></div></div>}
    {section==='compare'&&data?.next_offset!=null&&<p className="mw-context-note">当前比较包含前2,000条观测，请缩小日期范围查看完整区间。</p>}{section==='compare'&&data&&<div className="mw-context-note">{data.comparison.notes.join(' ')}{alignment==='fiscal'?' 公司财务阶段可能覆盖不同自然月份。':''}{data.coverage.filter(c=>!c.count).map(c=><span key={c.entity_id}> · {companies.find(x=>x.entity_id===c.entity_id)?.name||c.entity_id}：当前筛选无记录</span>)}</div>}
    <MetricReviewPanel reviews={data?.industry_reviews||[]} onSource={onSource}/>
    {error&&<div role="alert" className="mw-error">{error}</div>}
    {busy?<div className="mw-loading" role="status">正在读取指标与期间…</div>:section==='compare'&&!metric?<div className="mw-empty"><LayoutGrid size={25}/><h3>选择一个指标，开始比较</h3><p>公司、期间、数值与出处将一起保留。</p></div>:!rows.length?<div className="mw-empty"><h3>当前筛选没有观测记录</h3><p>可调整指标或期间。没有记录不代表数值为零。</p><button onClick={reset}>清空筛选</button></div>:section==='overview'?<><label className="mw-overview-search"><Search size={15}/><input aria-label="搜索指标总览" placeholder="搜索当前指标…" value={search} onChange={e=>setSearch(e.target.value)}/></label>{Object.entries(groups).map(([g,label])=>{const list=rows.filter(r=>r.group===g);return list.length?<section key={g} className="mw-group"><h3>{label}<small>{list.length}</small></h3><div className="mw-overview-grid">{list.map(r=><button key={r.id} onClick={()=>void open(r)}><span className="mw-tile-title">{r.label}<ArrowUpRight size={15}/></span><strong>{valueText(r,digits)} <small>{r.unit}</small></strong><span>{r.period_label} · {kinds[r.period_kind]||r.period_kind}</span>{r.business_scope&&<span>{r.business_scope}</span>}{r.value_state!=='actual'&&<em>{stateLabel[r.value_state]}</em>}{r.observation_kind==='valuation'&&<span>财务依据：{r.financial_basis?.label}</span>}{r.value==null&&<em>{stateName(r)}</em>}</button>)}</div></section>:null;})}</>:display==='chart'?<><Trend rows={rows} digits={digits} open={r=>void open(r)} alignment={alignment} frequency={frequency}/>{data?.next_offset!=null&&<p className="mw-context-note">本图显示前 2,000 条，请缩小日期范围后查看完整走势。</p>}</>:section==='compare'?<ComparisonTable rows={rows} companies={companies.filter(c=>ids.includes(c.entity_id))} digits={digits} open={r=>void open(r)} alignment={alignment}/>:<div className="mw-history-table"><table><thead><tr>{!metric&&<th>指标</th>}<th>{section==='valuation'||selectedCatalog?.group==='valuation'?'估值日':'报告期 / 观察日'}</th><th>口径 / 财务依据</th><th className="mw-number">数值</th><th>记录</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}>{!metric&&<td>{r.label}</td>}<td>{r.period_label}{r.observation_kind!=='valuation'&&<small>{r.observation_date}</small>}</td><td>{r.observation_kind==='valuation'?r.financial_basis?.label:kinds[r.period_kind]||r.period_kind}{r.business_scope&&<small>{r.business_scope}</small>}{r.value_state!=='actual'&&<small>{stateLabel[r.value_state]}</small>}{r.financial_basis?.start&&<small>{r.financial_basis.start} — {r.financial_basis.end}</small>}</td><td className="mw-number">{valueText(r,digits)} <span>{r.unit==='text'?'':r.unit}</span>{r.value==null&&<small>{stateName(r)}</small>}</td><td><button onClick={()=>void open(r)}>数据卡 <ArrowUpRight size={13}/></button></td></tr>)}</tbody></table></div>}
    {section!=='overview'&&section!=='compare'&&display==='table'&&data&&data.total>60&&<div className="mw-pagination"><span>{offset+1}–{Math.min(offset+60,data.total)} / {data.total}</span><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-60))}>上一页</button><button disabled={data.next_offset==null} onClick={()=>setOffset(data.next_offset||0)}>下一页</button></div>}
    {card&&<DataCard row={card} digits={digits} close={()=>setCard(null)} onSource={onSource}/>}
  </div>;
}
