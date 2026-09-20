type RecordValue=Record<string,unknown>;
const fieldNames:Record<string,string>={role:'业务角色',scope_note:'关系范围',products:'产品与业务',valid_from:'起始日期',valid_to:'结束日期',observation_date:'观察日期',period_end:'持仓截至日',fiscal_year:'财年',periods:'各期披露范围',position_rows:'证券持仓记录数',amount:'金额',currency:'币种',capacity:'容量',capacity_gw:'容量（GW）',ownership_share:'持股比例',conditions:'条件',transaction_status:'交易状态'};
const termNames:Record<string,string>={investment:'投资额',ownership:'持股比例',investment_commitment:'投资承诺',expected_cumulative_ownership:'完成后的预计累计持股比例',contract_term:'合同期限',planned_capacity:'计划容量',capacity:'容量'};
function valueText(value:unknown):string{return Array.isArray(value)?value.map(valueText).join('、'):typeof value==='object'&&value?Object.entries(value).map(([k,v])=>`${fieldNames[k]||k}：${valueText(v)}`).join('；'):String(value??'');}
export default function RelationshipRecord({value,onSource}:{value:RecordValue;onSource?:(id:string)=>void}){
  const terms=Array.isArray(value.terms)?value.terms as RecordValue[]:[];
  const fields=Object.entries(fieldNames).filter(([key])=>value[key]!=null&&value[key]!==''&&(!Array.isArray(value[key])||(value[key] as unknown[]).length));
  return <div className="cw-relationship-record">
    {fields.map(([key,label])=><div className="cw-relationship-field" key={key}><strong>{label}</strong><span>{valueText(value[key])}</span></div>)}
    {terms.length>0&&<div className="cw-relationship-terms">{terms.map((term,i)=><div key={i}><strong>{termNames[String(term.metric)]||String(term.metric)}</strong><span>{term.operator==='approximately'?'约 ':term.operator==='='?'':String(term.operator||'')}{Number.isFinite(Number(term.value))?Number(term.value).toLocaleString('zh-CN',{maximumFractionDigits:6}):String(term.value)} {String(term.unit||'')}</span><small>{String(term.basis||'')}</small></div>)}</div>}
    {typeof value.source_title==='string'&&<p>{value.source_title}</p>}
    {onSource&&typeof value.source_id==='string'&&<button onClick={()=>onSource(value.source_id as string)}>查看原文依据</button>}
    <details><summary>查看保存的完整字段</summary><pre>{JSON.stringify(value,null,2)}</pre></details>
  </div>;
}
