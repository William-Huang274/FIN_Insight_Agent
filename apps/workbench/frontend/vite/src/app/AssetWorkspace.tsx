import {useState} from 'react';
import {useSearchParams} from 'react-router';
import {BookOpen,Database,FolderOpen,Layers,ArrowLeft,PanelLeftClose,PanelLeftOpen} from 'lucide-react';
import {DataLibrary} from './DataLibrary';
import ProjectAssetWorkspace from './ProjectAssetWorkspace';
import CompanyWorkspace from './CompanyWorkspace';
import './research-session.css';
import './workspace-design.css';
import './asset-workspace.css';

export default function AssetWorkspace(){
  const [params,setParams]=useSearchParams();
  const view=params.get('view')||(params.has('project')?'project':'companies');
  const [collapsed,setCollapsed]=useState(false);
  const [catalogueArea,setCatalogueArea]=useState(view);
  const displayView=['companies','institutions','policy'].includes(view)?catalogueArea:view==='company-data'?'financial-data':view;
  const theme=localStorage.getItem('finsight.theme')||'system';
  const thread=params.get('return_thread');
  const research=thread?`/workspace/session?thread=${encodeURIComponent(thread)}&view=graph`:'/workspace/session';
  const navigate=(next:string)=>setParams(current=>{current.set('view',next);return current;});
  const tabs=[{id:'companies',title:'公司光谱',icon:Layers,description:'关系、资料卡与行业网络'},
    {id:'institutions',title:'投资机构与基金',icon:Layers,description:'机构身份、投资与申报持仓'},
    {id:'policy',title:'宏观与监管',icon:BookOpen,description:'发布机构、经济数据与政策'},
    {id:'library',title:'知识库',icon:BookOpen,description:'公司披露与研究资料'},
    {id:'financial-data',title:'数据库',icon:Database,description:'公司财务、行情与机构持仓'},
    {id:'project',title:'项目资料',icon:FolderOpen,description:'项目文件与研究成果'}];
  return <div className={`rs-shell fs-workspace fa-workspace ${collapsed?'fa-collapsed':''}`} data-theme={theme}>
    <aside className="fa-nav"><a className="fs-brand" href="/workspace/assets"><span className="fs-logo"><Layers size={21}/></span><strong>FinSight<small>ASSET WORKSPACE</small></strong></a>
      <div className="fa-area"><a href={research}><Layers size={16}/><span>研究工作台</span></a><a href="/workspace/assets" aria-current="page"><Database size={16}/><span>资产工作区</span></a></div>
      <p className="fa-caption">资产</p><nav aria-label="资产分类导航">{tabs.map(t=><button title={t.title} aria-label={t.title} key={t.id} aria-current={displayView===t.id?'page':undefined} onClick={()=>navigate(t.id)}><t.icon size={18}/><span><strong>{t.title}</strong><small>{t.description}</small></span></button>)}</nav>
      <footer><p>资料和数据统一查阅。<br/>项目文件可在研究中随时打开。</p><a href={research}><ArrowLeft size={15}/><span>返回研究工作台</span></a></footer>
    </aside>
    <main className="fa-main"><header className="rs-top"><button className="fa-toggle" aria-label={collapsed?'展开资产导航':'收起资产导航'} onClick={()=>setCollapsed(!collapsed)}>{collapsed?<PanelLeftOpen size={17}/>:<PanelLeftClose size={17}/>}</button><div className="rs-breadcrumb">资产工作区 <span>/</span> <b>{tabs.find(t=>t.id===displayView)?.title||'知识库'}</b></div><a className="fa-research-return" href={research}>返回研究 <ArrowLeft size={14}/></a></header>
      {(['companies','institutions','policy','company-data','financial-data','library'].includes(view)&&!params.has('source')&&!params.has('metric'))?<CompanyWorkspace onAreaChange={setCatalogueArea} key={view} area={['institutions','policy'].includes(view)?view:'companies'} database={['company-data','financial-data'].includes(view)} materials={view==='library'}/>:view==='project'?<ProjectAssetWorkspace/>:<DataLibrary key={view} page={['financial-data','financial-history'].includes(view)?'financial-data':'library'} navigate={navigate} onSupplement={question=>window.location.assign(`/workspace/session?view=new&question=${encodeURIComponent(question)}`)}/>}
    </main>
  </div>;
}
