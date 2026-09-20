import {useState} from 'react';

export type EntityProfile={type:string;roles:string[];institution_type?:string;country?:string;registration_country?:string;jurisdiction?:string;identity_basis?:string};
export function entityArea(profile?:EntityProfile){return ['agency','macro_collection'].includes(profile?.type||'')?'policy':['investment_institution','fund'].includes(profile?.type||'')?'institutions':'companies';}
export const areaNames:Record<string,string>={companies:'公司',institutions:'投资机构与基金',policy:'宏观与监管'};
const types:Record<string,string>={agency:'政策发布机构',macro_collection:'宏观与政策资料',investment_institution:'投资机构',fund:'基金产品',company:'公司'};
const roles:Record<string,string>={company:'经营企业',investment_institution:'投资机构',reporting_manager:'持仓申报管理人',agency:'发布与监管机构',macro_collection:'跨机构资料集合',fund:'基金产品'};

export function InstitutionProfile({profile,card,name,country}:{profile:EntityProfile;card:{legal_name?:string;sec_cik?:string;selection_reason:string};name:string;country?:string}){
  const known=(v?:string)=>!v||v==='to_verify'?'待核实':({US:'美国',CN:'中国',CA:'加拿大',JP:'日本',AE:'阿联酋',multi_jurisdiction:'多个国家与地区'}[v]||v);
  return <article><h2>{profile.type==='macro_collection'?'宏观与政策资料卡':(types[profile.type]||'机构')+'资料卡'}</h2><dl>
    <dt>名称</dt><dd>{card.legal_name||name}</dd><dt>机构 / 资料类型</dt><dd>{profile.institution_type||types[profile.type]}</dd>
    <dt>所属国家或地区</dt><dd>{known(profile.country||country)}</dd><dt>身份与职责</dt><dd>{profile.roles.map(r=>roles[r]||r).join('、')||'待核实'}</dd>
    {profile.jurisdiction&&<><dt>管辖 / 适用范围</dt><dd>{profile.jurisdiction}</dd></>}
    {card.sec_cik&&<><dt>申报身份</dt><dd>CIK {card.sec_cik}</dd></>}
    <dt>资料范围</dt><dd>{card.selection_reason}</dd>
  </dl>{profile.type==='investment_institution'&&<p className="cw-caption">管理人申报持仓与具体基金持仓分别记录；当前 13F 数据不能自动归属于旗下某一只基金。</p>}
  {profile.type==='macro_collection'&&<p className="cw-caption">此处汇总跨机构资料。发布者、适用地区与规则状态见各材料；未确认适用关系的文件不自动关联为公司风险。</p>}</article>;
}

type Material={id:string;category:string;published_at:string|null;material_group?:string;material_group_label?:string;relevance_status?:string};
export function MaterialDirectory({sources,label,onSelect}:{sources:Material[];label:(s:string)=>string;onSelect:(category:string,year:string,group:string)=>void}){
  const [choice,setChoice]=useState('');
  const groups=[...new Set(sources.map(s=>s.material_group||'other'))];
  const select=(category:string,year='',group='')=>{setChoice(group+category+year);onSelect(category,year,group);};
  return <nav className="cw-directory" aria-label="材料层级目录"><button aria-current={!choice?'page':undefined} onClick={()=>select('')}>全部材料 <small>{sources.length}</small></button>
    {groups.map(group=>{const rows=sources.filter(s=>(s.material_group||'other')===group);return <details key={group} open><summary>{rows[0].material_group_label||'其他资料'} <small>{rows.length}</small></summary>
      {[...new Set(rows.map(s=>s.category))].map(category=>{const selected=rows.filter(s=>s.category===category);return <details key={category}><summary><button aria-current={choice===group+category?'page':undefined} onClick={()=>select(category,'',group)}>{label(category)} <small>{selected.length}</small></button></summary>
        {[...new Set(selected.map(s=>s.published_at?.slice(0,4)||'日期待核'))].sort().reverse().map(year=><button key={year} className="cw-year" aria-current={choice===group+category+year?'page':undefined} onClick={()=>select(category,year,group)}>{year} <small>{selected.filter(s=>(s.published_at?.slice(0,4)||'日期待核')===year).length}</small></button>)}
      </details>;})}</details>;})}
  </nav>;
}

export function DataDirectory({kind,group,groups,onSelect}:{kind:string;group:string;groups:{id:string;label:string;count:number}[];onSelect:(kind:string,group:string)=>void}){
  return <nav className="cw-directory" aria-label="数据层级目录">
    <details open><summary><button aria-current={kind==='financial'&&!group?'page':undefined} onClick={()=>onSelect('financial','')}>财务与宏观指标 · 全部</button></summary>
      {(groups.length?groups:[{id:'operating',label:'经营财务',count:0},{id:'offering',label:'发行与注册费用',count:0},{id:'compensation',label:'薪酬与治理',count:0},{id:'macro',label:'宏观数据',count:0}]).map(g=><button className="cw-year" key={g.id} aria-current={kind==='financial'&&group===g.id?'page':undefined} onClick={()=>onSelect('financial',g.id)}>{g.label}{g.count>0&&<small>{g.count}</small>}</button>)}
    </details>
    {[['prices','市场日行情'],['positions','该主体申报的证券持仓'],['holders','持有该公司的机构'],['filings','监管申报目录']].map(([key,title])=><button key={key} aria-current={kind===key?'page':undefined} onClick={()=>onSelect(key,'')}>{title}</button>)}
  </nav>;
}
