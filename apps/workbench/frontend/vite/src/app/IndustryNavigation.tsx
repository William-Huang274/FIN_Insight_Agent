import {useState} from 'react';

export type EntityProfile={type:string;roles:string[];institution_type?:string;country?:string;registration_country?:string;jurisdiction?:string;identity_basis?:string};
export function entityArea(profile?:EntityProfile){return ['person','project','product','government'].includes(profile?.type||'')?'related_entities':['agency','macro_collection'].includes(profile?.type||'')?'policy':['investment_institution','fund'].includes(profile?.type||'')?'institutions':'companies';}
export const areaNames:Record<string,string>={companies:'公司',institutions:'投资机构与基金',policy:'宏观与监管',related_entities:'其他关联主体'};
const types:Record<string,string>={agency:'政策发布机构',macro_collection:'宏观与政策资料',investment_institution:'投资机构',fund:'基金产品',company:'公司',person:'自然人',government:'政府持股主体',project:'项目',product:'产品'};
const roles:Record<string,string>={...types,company:'经营企业',investment_institution:'投资机构',reporting_manager:'持仓申报管理人',agency:'发布与监管机构',macro_collection:'跨机构资料集合',fund:'基金产品'};

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
    {groups.map(group=>{const rows=sources.filter(s=>(s.material_group||'other')===group);return <section className="cw-directory-group" key={group}><button className="cw-group-title" aria-current={choice===group?'page':undefined} onClick={()=>select('','',group)}>{rows[0].material_group_label||'其他资料'} <small>{rows.length}</small></button>
      {[...new Set(rows.map(s=>s.category))].map(category=>{const selected=rows.filter(s=>s.category===category);return <DirectoryBranch key={category} title={label(category)} count={selected.length} active={choice===group+category} onSelect={()=>select(category,'',group)}>
        {[...new Set(selected.map(s=>s.published_at?.slice(0,4)||'日期待核'))].sort().reverse().map(year=><button key={year} className="cw-year" aria-current={choice===group+category+year?'page':undefined} onClick={()=>select(category,year,group)}>{year} <small>{selected.filter(s=>(s.published_at?.slice(0,4)||'日期待核')===year).length}</small></button>)}
      </DirectoryBranch>;})}</section>;})}
  </nav>;
}

function DirectoryBranch({title,count,active,onSelect,children}:{title:string;count:number;active:boolean;onSelect:()=>void;children:React.ReactNode}){
  const [expanded,setExpanded]=useState(false);
  return <div className="cw-directory-branch"><div className="cw-directory-row"><button className="cw-expand" aria-label={`${expanded?'收起':'展开'}${title}`} aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?'▾':'▸'}</button><button aria-current={active?'page':undefined} onClick={onSelect}>{title} <small>{count}</small></button></div>{expanded&&<div className="cw-directory-years">{children}</div>}</div>;
}
export type DataChannel={kind:string;group:string;label:string;count:number};
export function DataDirectory({kind,group,groups,channels,onSelect}:{kind:string;group:string;groups:{id:string;label:string;count:number}[];channels:DataChannel[];onSelect:(kind:string,group:string)=>void}){
  return <nav className="cw-directory" aria-label="数据层级目录">
    {channels.map(channel=><section className="cw-directory-group" key={channel.kind}><button className="cw-group-title" aria-current={kind===channel.kind&&!group?'page':undefined} onClick={()=>onSelect(channel.kind,'')}>{channel.label} <small>{channel.count}</small></button>
      {channel.kind==='financial'&&groups.map(g=><button className="cw-year" key={g.id} aria-current={kind==='financial'&&group===g.id?'page':undefined} onClick={()=>onSelect('financial',g.id)}>{g.label} <small>{g.count}</small></button>)}
    </section>)}
    {!channels.length&&<p className="cw-caption">尚无已接入的数据表；可先查看原始材料与接入缺口。</p>}
  </nav>;
}
