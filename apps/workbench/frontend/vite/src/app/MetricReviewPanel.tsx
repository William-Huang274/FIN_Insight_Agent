import './metric-review.css';

export type MetricReview={id:string;entity_id:string;field:string;field_label?:string;outcome:string;reason:string;next_action:string;comparison_rule:string;reviewed_at:string;reviewed_materials:{title:string;url:string;source_id?:string;sections:string[]|string;periods?:string[];access_outcome?:string}[]};
const labels:Record<string,string>={resolved:'已补齐本项',bounded_not_found:'已核查 · 范围内未找到',source_access_blocked:'来源获取仍受阻',definition_boundary:'口径边界',precision_limit:'披露精度限制'};

export default function MetricReviewPanel({reviews,onSource}:{reviews:MetricReview[];onSource:(id:string)=>void}){
  if(!reviews.length)return null;
  const resolved=reviews.filter(r=>r.outcome==='resolved').length;
  return <details className="mr-panel"><summary><span>行业指标核查</span><small>{reviews.length} 项 · {resolved} 项补齐 · {reviews.length-resolved} 项保留限制</small></summary>
    <p className="mr-intro">结论限于列出的材料、期间和字段；未找到不表示公司从未披露。</p>
    <div className="mr-list">{reviews.map(r=><article key={r.id}>
      <header><strong>{r.field_label||r.field}</strong><span data-outcome={r.outcome}>{labels[r.outcome]||r.outcome}</span></header>
      <p>{r.reason}</p><dl><dt>使用规则</dt><dd>{r.comparison_rule}</dd><dt>后续处理</dt><dd>{r.next_action}</dd></dl>
      <details><summary>核查依据 · {r.reviewed_materials.length} 份 · {r.reviewed_at}</summary><ul>{r.reviewed_materials.map((s,i)=><li key={s.url+i}>{s.source_id?<button onClick={()=>onSource(s.source_id!)}>{s.title} ↗</button>:<a href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a>}<small>{Array.isArray(s.sections)?s.sections.join('、'):s.sections}{s.periods?.length?' · '+s.periods.join('、'):''}</small></li>)}</ul></details>
    </article>)}</div>
  </details>;
}
