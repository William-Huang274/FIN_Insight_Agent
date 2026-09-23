import {BookOpen,Database,FileSearch,Files,FolderOpen,Layers,ListTodo,Settings,MessageSquare,Workflow} from 'lucide-react';
import type {WorkspaceProject} from './workspaceProjects';
import './project-workspace.css';

export const projectUrl=(id:string,view='overview')=>`/workspace/projects?${new URLSearchParams({project:id,view})}`;
export function ProjectNavigation({project,projects,view='overview',global='projects'}:{project?:WorkspaceProject;projects:WorkspaceProject[];view?:string;global?:string}){
  return <aside className="pw-sidebar"><a className="fs-brand" href="/workspace/projects"><span className="fs-logo"><Layers size={21}/></span><strong>FinSight<small>RESEARCH WORKSPACE</small></strong></a>
    <nav aria-label="工作空间导航">{[{id:'projects',href:'/workspace/projects',title:'所有项目',Icon:FolderOpen},{id:'todo',href:'/workspace/session?view=all',title:'我的研究',Icon:ListTodo},{id:'assets',href:'/workspace/assets?view=files',title:'资料库',Icon:Database}].map(({id,href,title,Icon})=><a key={id} href={href} aria-current={!project&&global===id?'page':undefined}><Icon size={17}/>{title}</a>)}</nav>
    {project?<section className="pw-context"><label>当前项目<select aria-label="切换项目" value={project.id} onChange={e=>window.location.assign(projectUrl(e.target.value))}>{projects.map(p=><option key={p.id} value={p.id}>{p.name}{p.description?` · ${p.description.slice(0,24)}`:''}{p.archived?'（已归档）':''}</option>)}</select></label><nav aria-label="项目导航">{[{id:'overview',title:'项目概览',Icon:Layers},{id:'research',title:'研究',Icon:FileSearch},{id:'files',title:'资料',Icon:Files},{id:'results',title:'成果',Icon:BookOpen},{id:'settings',title:'项目管理',Icon:Settings}].map(({id,title,Icon})=><a key={id} href={projectUrl(project.id,id)} aria-current={view===id?'page':undefined}><Icon size={17}/>{title}</a>)}</nav></section>:<section className="pw-context"><p>最近项目</p><nav aria-label="项目快捷入口">{projects.filter(p=>!p.archived).slice(-5).reverse().map(p=><a key={p.id} href={projectUrl(p.id)}><FolderOpen size={16}/><span>{p.name}</span></a>)}</nav></section>}
    <footer><a href="/workspace/assistant"><MessageSquare size={16}/>通用对话</a><a href="/workspace/session?view=studio"><Workflow size={16}/>研究配置</a><a href="/workspace/session?view=preferences"><Settings size={16}/>外观与偏好</a><small>个人工作区</small></footer>
  </aside>;
}
