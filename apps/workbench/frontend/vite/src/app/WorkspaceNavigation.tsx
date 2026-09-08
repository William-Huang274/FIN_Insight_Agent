import { useRef } from "react";
import { ArrowUpRight, BookOpen, CircleUserRound, FileClock, Files, FolderOpen, House, Layers, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus, Radio, Settings2, ShieldCheck, X } from "lucide-react";
import type { Session } from "../api/reportSessions";

export const taskViews = [
  { id: "graph", title: "研究地图", icon: Layers }, { id: "report", title: "研究报告", icon: BookOpen },
  { id: "sources", title: "研究资料", icon: Files }, { id: "revisions", title: "修订记录", icon: FileClock },
  { id: "conversation", title: "追问与反馈", icon: MessageSquare }, { id: "activity", title: "运行与费用", icon: Radio },
] as const;
export const pageTitles: Record<string, string> = { home: "工作台", all: "全部研究", inbox: "待审阅", new: "新建研究", preferences: "外观与偏好", review: "审查意见", ...Object.fromEntries(taskViews.map(v => [v.id, v.title])) };
export const sessionStatus = (s: Session) => s.is_draft || s.phase === "draft" ? "资料准备中" : s.status === "busy" ? "运行中" : s.status === "error" ? "执行失败" : s.phase === "human_reviewed_not_released" ? "已人工审阅" : s.status === "interrupted" ? "等待审阅" : "已保存";

export function WorkspaceNavigation({ sessions, id, page, collapsed, onCollapse, navigate }: { sessions: Session[]; id: string; page: string; collapsed: boolean; onCollapse: () => void; navigate: (page: string, id?: string) => void }) {
  const drawer = useRef<HTMLDialogElement>(null);
  const go = (view: string, thread?: string) => { navigate(view, thread); drawer.current?.close(); };
  const content = (mobile = false) => <>
    <div className="fs-brand"><span className="fs-logo"><Layers size={21} /></span><strong>FinSight<small>RESEARCH WORKSPACE</small></strong>
      <button aria-label={mobile ? "关闭导航" : collapsed ? "展开侧边栏" : "收起侧边栏"} onClick={() => mobile ? drawer.current?.close() : onCollapse()}>{mobile ? <X size={17} /> : collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button></div>
    <button className="fs-create" title="新建研究" onClick={() => go("new")}><Plus size={17} /><span>新建研究</span></button>
    <nav aria-label={mobile ? "移动工作区导航" : "工作区导航"} className="fs-global-nav">{[
      { id: "home", title: "工作台", icon: House }, { id: "all", title: "全部研究", icon: FolderOpen }, { id: "inbox", title: "待审阅", icon: ShieldCheck },
    ].map(item => <button title={item.title} aria-current={page === item.id ? "page" : undefined} key={item.id} onClick={() => go(item.id)}><item.icon size={17} /><span>{item.title}</span></button>)}</nav>
    <div className="fs-recent"><div className="fs-side-caption">最近研究 <button title="查看全部研究" aria-label="查看全部研究" onClick={() => go("all")}><ArrowUpRight size={15} /></button></div>
      <nav aria-label="最近研究">{sessions.slice(0, 12).map(s => <div key={s.thread_id} className={s.thread_id === id ? "fs-task selected" : "fs-task"}>
        <button className="fs-task-link" title={s.title} onClick={() => go("graph", s.thread_id)}><FileClock size={16} /><span>{s.title || "未命名研究"}<small>{sessionStatus(s)} · {s.thread_id.slice(-6)}</small></span></button>
        {s.thread_id === id && <div className="fs-subnav">{taskViews.map(v => <button key={v.id} aria-current={page === v.id ? "page" : undefined} onClick={() => go(v.id, id)}><v.icon size={15} />{v.title}</button>)}</div>}
      </div>)}{!sessions.length && <p>尚无已保存研究</p>}</nav>
    </div>
    <div className="fs-sidebar-footer"><button title="外观与偏好" onClick={() => go("preferences")}><Settings2 size={17} /><span>外观与偏好</span></button><div title="本地个人工作区"><CircleUserRound size={25} /><span>个人工作区<small>本地环境 · FIN 0.1.3</small></span></div></div>
  </>;
  return <><aside className={`fs-sidebar ${collapsed ? "is-collapsed" : ""}`}>{content()}</aside>
    <button className="fs-mobile-nav" aria-label="打开导航" onClick={() => drawer.current?.showModal()}><PanelLeftOpen size={18} /></button>
    <dialog ref={drawer} className="fs-nav-dialog">{content(true)}</dialog></>;
}
