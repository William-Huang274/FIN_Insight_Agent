import { useRef, useState } from "react";
import { ChevronRight, FolderPlus, Pin, Workflow, BookOpen, CircleUserRound, FileClock, Files, FolderOpen, House, Layers, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus, Radio, Settings2, ShieldCheck, X } from "lucide-react";
import type { ProjectIndex } from "./workspaceProjects";
import type { Session } from "../api/reportSessions";

export const taskViews = [
  { id: "graph", title: "研究地图", icon: Layers }, { id: "report", title: "研究报告", icon: BookOpen },
  { id: "sources", title: "研究资料", icon: Files }, { id: "revisions", title: "修订记录", icon: FileClock },
  { id: "conversation", title: "追问与反馈", icon: MessageSquare }, { id: "activity", title: "运行与费用", icon: Radio },
] as const;
export const pageTitles: Record<string, string> = { home: "开始研究", studio: "研究配置", all: "全部研究", inbox: "待审阅", new: "新建研究", preferences: "外观与偏好", review: "审查意见", ...Object.fromEntries(taskViews.map(v => [v.id, v.title])) };
export const sessionStatus = (s: Session) => s.is_draft || s.phase === "draft" ? "资料准备中" : s.status === "busy" ? "运行中" : s.status === "error" ? "执行失败" : s.phase === "research_needs_attention" ? "研究受阻 · 待处理" : s.phase === "single_agent_unreviewed" ? "单 Agent 结果 · 未复核" : s.phase === "human_reviewed_not_released" ? "已人工审阅" : s.status === "interrupted" ? "等待审阅" : "已保存";

export function WorkspaceNavigation({ sessions, id, page, collapsed, onCollapse, navigate, projects, onProjects }: { sessions: Session[]; id: string; page: string; collapsed: boolean; onCollapse: () => void; navigate: (page: string, id?: string) => void; projects: ProjectIndex; onProjects: (index: ProjectIndex) => void }) {
  const organize = useRef<HTMLDialogElement>(null);
  const [projectName, setProjectName] = useState("");
  const drawer = useRef<HTMLDialogElement>(null);
  const go = (view: string, thread?: string) => { navigate(view, thread); drawer.current?.close(); };
  const content = (mobile = false) => <>
    <div className="fs-brand"><span className="fs-logo"><Layers size={21} /></span><strong>FinSight<small>RESEARCH WORKSPACE</small></strong>
      <button aria-label={mobile ? "关闭导航" : collapsed ? "展开侧边栏" : "收起侧边栏"} onClick={() => mobile ? drawer.current?.close() : onCollapse()}>{mobile ? <X size={17} /> : collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button></div>
    <button className="fs-create" title="新建研究" onClick={() => go("new")}><Plus size={17} /><span>新建研究</span></button>
    <a className="fs-assistant-entry" href="/workspace/assistant"><MessageSquare size={17}/><span>通用对话</span></a>
    <nav aria-label={mobile ? "移动工作区导航" : "工作区导航"} className="fs-global-nav">{[
      { id: "home", title: "开始研究", icon: House }, { id: "studio", title: "研究配置", icon: Workflow }, { id: "all", title: "全部研究", icon: FolderOpen }, { id: "inbox", title: "待审阅", icon: ShieldCheck },
    ].map(item => <button title={item.title} aria-current={page === item.id ? "page" : undefined} key={item.id} onClick={() => go(item.id)}><item.icon size={17} /><span>{item.title}</span></button>)}</nav>
    <div className="fs-recent"><div className="fs-side-caption">项目与研究 <button title="管理项目" aria-label="管理项目" onClick={() => { drawer.current?.close(); organize.current?.showModal(); }}><FolderPlus size={16} /></button></div>
      <nav aria-label="最近研究">
        {!!projects.pinned.length && <div className="fs-pinned"><span className="fs-side-caption">置顶</span>{sessions.filter(s => projects.pinned.includes(s.thread_id)).map(s => <button key={s.thread_id} onClick={() => go("graph", s.thread_id)}><Pin size={13} />{s.title}</button>)}</div>}
        {[...projects.projects, {id:"",name:"未归类研究"}].map(project => {
          const items = sessions.filter(s => (projects.assignments[s.thread_id] || "") === project.id);
          if (!project.id && !items.length) return null;
          return <details className="fs-project" key={project.id} open><summary><ChevronRight size={13} /><FolderOpen size={16} /><span>{project.name}</span><small>{items.length}</small></summary>
            {items.map(s => <div key={s.thread_id} className={s.thread_id === id ? "fs-task selected" : "fs-task"}>
              <button className="fs-task-link" title={s.title} onClick={() => go("graph", s.thread_id)}><FileClock size={15} /><span><span className="fs-task-title">{s.title || "未命名研究"}</span><small>{sessionStatus(s)} · {s.thread_id.slice(-6)}</small></span></button>
              {s.thread_id === id && !["home","all","inbox","preferences","studio","new"].includes(page) && <div className="fs-subnav">{taskViews.map(v => <button key={v.id} aria-current={page === v.id ? "page" : undefined} onClick={() => go(v.id, id)}><v.icon size={15} />{v.title}</button>)}</div>}
            </div>)}{!items.length && <p className="fs-project-empty">在管理项目中添加研究</p>}
          </details>;
        })}
        {!sessions.length && <p>尚无已保存研究</p>}
      </nav>
    </div>
    <div className="fs-sidebar-footer"><button title="外观与偏好" onClick={() => go("preferences")}><Settings2 size={17} /><span>外观与偏好</span></button><div title="本地个人工作区"><CircleUserRound size={25} /><span>个人工作区<small>本地环境 · FIN 0.1.3</small></span></div></div>
  </>;
  return <><aside className={`fs-sidebar ${collapsed ? "is-collapsed" : ""}`}>{content()}</aside>
    <button className="fs-mobile-nav" aria-label="打开导航" onClick={() => drawer.current?.showModal()}><PanelLeftOpen size={18} /></button>
    <dialog ref={drawer} className="fs-nav-dialog">{content(true)}</dialog>
    <dialog ref={organize} className="fs-organize-dialog" aria-label="管理项目">
      <header><div><h2>整理你的研究</h2><p>项目 → 研究任务 → 报告、追问与修订。归类与置顶保存在此浏览器。</p></div><button aria-label="关闭项目管理" onClick={() => organize.current?.close()}><X size={19} /></button></header>
      <form onSubmit={e => { e.preventDefault(); const name = projectName.trim(); if (!name || projects.projects.some(p => p.name === name)) return; onProjects({...projects, projects:[...projects.projects,{id:crypto.randomUUID(),name}]}); setProjectName(""); }}>
        <input aria-label="新项目名称" maxLength={60} value={projectName} onChange={e => setProjectName(e.target.value)} placeholder="如：AI 基础设施、消费行业…" /><button disabled={!projectName.trim() || projects.projects.some(p => p.name === projectName.trim())}><FolderPlus size={16} />创建项目</button>
      </form>
      <div className="fs-organize-list">{sessions.map(s => <div key={s.thread_id}><span>{s.title || "未命名研究"}<small>{s.thread_id.slice(-6)}</small></span>
        <select aria-label={`归类 ${s.title}`} value={projects.assignments[s.thread_id] || ""} onChange={e => onProjects({...projects,assignments:{...projects.assignments,[s.thread_id]:e.target.value}})}><option value="">未归类研究</option>{projects.projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        <button aria-label={`置顶 ${s.title}`} aria-pressed={projects.pinned.includes(s.thread_id)} onClick={() => onProjects({...projects,pinned:projects.pinned.includes(s.thread_id) ? projects.pinned.filter(p => p !== s.thread_id) : [...projects.pinned,s.thread_id]})}><Pin size={16} /></button>
      </div>)}</div>
    </dialog></>;
}
