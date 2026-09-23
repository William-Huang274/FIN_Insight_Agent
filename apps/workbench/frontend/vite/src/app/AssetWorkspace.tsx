import {useSearchParams} from 'react-router';
import {DataLibrary} from './DataLibrary';
import ProjectAssetWorkspace from './ProjectAssetWorkspace';
import CompanyWorkspace from './CompanyWorkspace';
import {ProjectCatalog} from './ProjectCatalog';
import ResourceWorkspace from './ResourceWorkspace';
import './research-session.css';
import './workspace-design.css';
import './asset-workspace.css';

export default function AssetWorkspace(){
  const [params,setParams]=useSearchParams();
  const view=params.get('view')||(params.has('project')?'project':'files');
  const navigate=(next:string)=>setParams(current=>{current.set('view',next);return current;});
  const publicView=['companies','institutions','policy','company-data','financial-data','library'].includes(view);
  return <ResourceWorkspace>{view==='files'?<ProjectCatalog/>:view==='project'?<ProjectAssetWorkspace/>:publicView&&!params.has('source')&&!params.has('metric')?<>
    {params.has('scope')&&<p className="pw-muted">这里展示部署级公开资料。项目筛选保留在文件资料页，尚未对公开知识库或数据库应用项目关联过滤。</p>}
    <CompanyWorkspace key={view} area={['institutions','policy'].includes(view)?view:'companies'} database={['company-data','financial-data'].includes(view)} materials={view==='library'}/>
  </>:<DataLibrary key={view} page={['financial-data','financial-history'].includes(view)?'financial-data':'library'} navigate={navigate} onSupplement={question=>window.location.assign(`/workspace/session?view=new&question=${encodeURIComponent(question)}`)}/>}</ResourceWorkspace>;
}
