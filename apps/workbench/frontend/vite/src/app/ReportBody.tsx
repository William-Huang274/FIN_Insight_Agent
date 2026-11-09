import {BoundCitationMarkdown} from './BoundCitationMarkdown';
import type {Citation} from '../api/reportSessions';
import {unified} from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import {sourceUrl} from './sourceUrl';

export type BoundChart={title:string;kind?:string;unit:string;scale_divisor?:number;interpretation:string;after_heading?:string;points:{label:string;series:string;value:number;source_id?:string;provenance?:unknown}[]};
function chartSourceLinks(value:unknown):string[]{
  if(Array.isArray(value))return [...new Set(value.flatMap(chartSourceLinks))];
  if(value&&typeof value==='object')return [...new Set(Object.entries(value).flatMap(([key,item])=>
    ['url','source_url'].includes(key)&&typeof item==='string'?(sourceUrl(item)?[item]:[]):key==='citation_urls'&&Array.isArray(item)?item.filter((v):v is string=>typeof v==='string'&&!!sourceUrl(v)):chartSourceLinks(item)))];
  return [];
}
export type ReadableReport={title:string;narrative_markdown:string;citations?:Record<string,Citation>;charts?:BoundChart[]};
/** Placement is display metadata, never a rewrite of the saved narrative. */
export function ReportBody({report,chartUrl,onCitation}:{report:ReadableReport;chartUrl:(i:number)=>string;onCitation:(key:string,c:Citation)=>void}) {
  const text=report.narrative_markdown, charts=report.charts||[], used=new Set<number>();
  const ast=unified().use(remarkParse).use(remarkGfm).parse(text);
  const headings=ast.children.filter(n=>n.type==='heading');
  const definitions=ast.children.filter(n=>n.type==='definition').map(n=>text.slice(n.position!.start.offset,n.position!.end.offset)).join('\n');
  const slots=new Map<number,number[]>();
  charts.forEach((chart,index)=>{
    const matches=headings.filter(h=>chart.after_heading&&text.slice(h.position!.start.offset,h.position!.end.offset).replace(/^#{1,6}\s+|\s+#+\s*$/g,'').trim()===chart.after_heading);
    if(matches.length!==1)return;
    const h=matches[0],end=headings.find(n=>n.position!.start.offset!>h.position!.start.offset!&&n.depth<=h.depth)?.position!.start.offset??text.length;
    slots.set(end,[...(slots.get(end)||[]),index]);used.add(index);
  });
  const cuts=[...new Set([...slots.keys(),text.length])].sort((a,b)=>a-b);
  function figure(chart:BoundChart,index:number){return <figure key={`chart-${index}`} id={`report-chart-${index}`} className="fs-report-figure">
    <img src={chartUrl(index)} alt={chart.title}/><figcaption><strong>{chart.title}</strong><BoundCitationMarkdown text={chart.interpretation} citations={report.citations} onCitation={onCitation}/></figcaption>
    <details><summary>查看图表数据与单位</summary><p>单位：{chart.scale_divisor&&chart.scale_divisor!==1?`${chart.scale_divisor.toLocaleString()} × `:''}{chart.unit}</p><div className="fs-report-table"><table><thead><tr><th>项目</th><th>系列</th><th>数值</th><th>出处</th></tr></thead><tbody>{chart.points.map((p,i)=><tr key={i}><td>{p.label}</td><td>{p.series}</td><td>{p.value.toLocaleString()}</td><td>{chartSourceLinks(p.provenance).map((url,j)=><a href={url} key={url} target="_blank" rel="noopener noreferrer">原始来源 {j+1} </a>)}<details><summary>定位与计算明细</summary><code>{p.source_id}</code><pre>{JSON.stringify(p.provenance,null,2)}</pre></details></td></tr>)}</tbody></table></div></details>
  </figure>;}
  return <div className="fs-report-body">{cuts.map((end,i)=>{
    const start=i?cuts[i-1]:0;
    return <section key={i}><BoundCitationMarkdown text={text.slice(start,end)+'\n\n'+definitions} citations={report.citations} onCitation={onCitation} reportHeadings headingOffset={start}/>{(slots.get(end)||[]).map(j=>figure(charts[j],j))}</section>;
  })}{charts.map((c,j)=>!used.has(j)?figure(c,j):null)}</div>;
}
