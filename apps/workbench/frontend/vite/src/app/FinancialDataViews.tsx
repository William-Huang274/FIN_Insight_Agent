import {useState} from 'react';

// Round display strings with integer arithmetic; SQL values retain their exact
// precision. In particular, do not coerce large share/currency amounts to float.
export function displayNumber(value:unknown, digits=2):string{
  if(value==null||value==='')return '—';
  const raw=String(value),m=raw.match(/^([+-]?)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i);
  if(!m)return raw;
  const negative=m[1]==='-',fraction=m[3]||'',exponent=Number(m[4]||0);
  if(Math.abs(exponent)>100)return raw;
  const power=digits+exponent-fraction.length;
  let number=BigInt(m[2]+fraction);
  if(power>=0)number*=10n**BigInt(power);
  else{const divisor=10n**BigInt(-power);number=(number+divisor/2n)/divisor;}
  const text=number.toString().padStart(digits+1,'0');
  const whole=(digits?text.slice(0,-digits):text).replace(/\B(?=(\d{3})+(?!\d))/g,',');
  return (negative&&number!==0n?'-':'')+whole+(digits?'.'+text.slice(-digits):'');
}

export type AccountNode={path:string;label:string;count:number};
export function AccountDirectory({nodes,selected,onSelect}:{nodes:AccountNode[];selected:string;onSelect:(path:string)=>void}){
  const [expanded,setExpanded]=useState<Set<string>>(new Set(['balance','income','cashflow']));
  function branch(parent:string){return nodes.filter(n=>n.path.includes('/')?n.path.slice(0,n.path.lastIndexOf('/'))===parent:parent==='').map(n=>{
    const children=nodes.some(c=>c.path.startsWith(n.path+'/'));
    return <div key={n.path} className="cw-account-branch"><div className="cw-account-row">{children?<button className="cw-expand" aria-label={`${expanded.has(n.path)?'收起':'展开'}${n.label}`} aria-expanded={expanded.has(n.path)} onClick={()=>setExpanded(old=>{const next=new Set(old);next.has(n.path)?next.delete(n.path):next.add(n.path);return next;})}>{expanded.has(n.path)?'▾':'▸'}</button>:<span className="cw-leaf-space"/>}<button aria-current={selected===n.path?'page':undefined} onClick={()=>onSelect(n.path)}>{n.label}<small>{n.count}</small></button></div>{children&&expanded.has(n.path)&&<div className="cw-account-children">{branch(n.path)}</div>}</div>;
  });}
  return <nav className="cw-account-directory" aria-label="财务报表科目"><button aria-current={!selected?'page':undefined} onClick={()=>onSelect('')}>全部报表科目</button>{branch('')}<p className="cw-caption">按科目性质归类；不将子项自动相加。原始指标及披露版本保留。</p></nav>;
}

const statuses:Record<string,string>={missing_fx:'缺少对应交易日汇率',stale_financial_input:'财务输入期间过旧',not_meaningful_nonpositive_base:'分母非正，不适用',available:'已计算',missing_inputs:'待补计算依据',not_meaningful_nonpositive_earnings:'盈利非正，PE无经济意义',stale_earnings:'盈利期间过旧',stale_or_invalid_share_count:'股数过旧或无效',invalid_denominator_or_sign:'分母或符号不适用'};
const gaps:Record<string,string>={reviewed_security_and_split_basis:'尚未核实证券类别、ADR比例或拆股口径',same_currency_annual_diluted_eps:'缺同币种完整财年稀释每股收益',annual_diluted_eps_on_reviewed_security_basis:'缺可用的完整财年稀释每股收益',reported_common_shares:'缺可用的实际流通在外普通股数',usable_reference_market_cap:'该价格日期没有可用的参考市值',revenue:'缺可比口径的完整财年收入',equity:'缺可用的归母权益'};
type MetricRow=Record<string,unknown>;
function CalculationInputs({inputs,digits,onSource}:{inputs:MetricRow[];digits:number;onSource:(id:string)=>void}){
  return <ul>{inputs.map((x,i)=><li key={i}><span>{String(x.concept||x.price_basis||x.role)}：<strong title={String(x.value)}>{displayNumber(x.value,digits)} {String(x.unit||'')}</strong> · {String(x.trade_date||x.period_end||'')}{x.period_start?`（自 ${x.period_start}）`:''}</span>{Boolean(x.source_id)&&<button onClick={()=>onSource(String(x.source_id))}>查看依据</button>}{Array.isArray(x.components)&&<details><summary>输入的计算过程</summary><code>{String(x.derivation)}</code><CalculationInputs inputs={x.components as MetricRow[]} digits={digits} onSource={onSource}/></details>}</li>)}</ul>;
}
function CalculationDetail({row:r,digits,onSource}:{row:MetricRow;digits:number;onSource:(id:string)=>void}){
  const detail=r.detail as {missing?:string[];security_basis?:{share_count_note?:string}};
  return <details><summary>公式与计算依据</summary><p><code>{String(r.formula)}</code> · {String(r.formula_version)}</p><p className="cw-caption">可获知日期 {String(r.available_at)}；显示经过舍入，计算保留原始精度。</p>{detail?.missing?.length&&<p>{detail.missing.map(x=>gaps[x]||x).join('；')}</p>}{detail?.security_basis?.share_count_note&&<p>{detail.security_basis.share_count_note}</p>}<CalculationInputs inputs={r.inputs as MetricRow[]} digits={digits} onSource={onSource}/></details>;
}
const periodNames:Record<string,string>={FY:'全年',Q1:'第一季度',Q2:'第二季度',Q3:'第三季度',Q4:'第四季度',H1:'上半年累计',M9:'前三季度累计',instant:'期末余额',unknown:'期间待核',other:'其他期间'};
export function DerivedMetrics({rows,digits,onSource,view='latest'}:{rows:MetricRow[];digits:number;onSource:(id:string)=>void;view?:'latest'|'history'}){
  const status=(r:MetricRow)=>statuses[String(r.status)]||({nonpositive_comparison_base:'比较期为零或亏损，不显示增长率'} as Record<string,string>)[String(r.status)]||String(r.status);
  return <div className="cw-derived"><p className="cw-caption">固定公式预计算。历史记录保留各期最新可用披露版本；单季、累计和全年分别列示。PE使用完整财年盈利，参考市值使用披露股数。日期筛选对应价格日期或财务期末。</p>{view==='history'?<div className="cw-table"><table><thead><tr><th>指标</th><th>财年 / 期间</th><th>财务起止日期</th><th>价格日期</th><th>数值</th><th>状态与依据</th></tr></thead><tbody>{rows.map(r=><tr key={String(r.id)}><td>{String(r.label)}</td><td>{String(r.fiscal_year||'')} {periodNames[String(r.fiscal_period)]||String(r.fiscal_period||'')}</td><td>{r.period_start?`${r.period_start} — `:''}{String(r.period_end||'—')}</td><td>{String(r.valuation_date||'—')}</td><td>{displayNumber(r.value,digits)} {String(r.unit)}</td><td>{status(r)}<CalculationDetail row={r} digits={digits} onSource={onSource}/></td></tr>)}</tbody></table></div>:rows.map(r=><article key={String(r.id)}><header><div><strong>{String(r.label)}</strong><p>{r.valuation_date?`价格日期 ${r.valuation_date} · `:''}财务期间 {String(r.period_start||'')} {r.period_start?'— ':''}{String(r.period_end||'待补')}</p></div><div className="cw-derived-value">{displayNumber(r.value,digits)} <small>{String(r.unit)}</small><p>{status(r)}</p></div></header>{r.status!=='available'&&<p className="cw-caption">{((r.detail as {missing?:string[]})?.missing||[]).map(x=>gaps[x]||x).join('；')}</p>}<CalculationDetail row={r} digits={digits} onSource={onSource}/></article>)}</div>;
}
