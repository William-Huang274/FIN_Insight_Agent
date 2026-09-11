import { ArrowRight, CornerDownRight, Layers } from "lucide-react";

export function ResearchOutline({ title, items, onOpen }: { title: string; items: { id: string; title: string; subtitle: string; preview?:string }[]; onOpen: (id: string) => void }) {
  return <div className="fs-horizontal-tree fs-outline-grid"><div className="fs-tree-root"><span className="fs-kicker"><Layers size={17} /> 当前研究范围</span><h3>{title}</h3><p>{items.length} 个可进入的节点</p><span className="fs-tree-guide">选择章节，阅读内容与依据 <ArrowRight size={16} /></span></div>
    <div className="fs-tree-branches" aria-label="可进入的研究节点">{items.map((item, i) => <div className="fs-tree-branch" key={item.id}><button className="fs-node-card" onClick={() => onOpen(item.id)} aria-label={item.title} title={item.title}><div><span>{String(i + 1).padStart(2, "0")}</span><CornerDownRight size={16} /></div><h3>{item.title}</h3>{item.preview&&<p className="fs-node-preview">{item.preview}</p>}<footer><span>{item.subtitle}</span><ArrowRight size={18} /></footer></button></div>)}</div>
  </div>;
}
