import { Background, Controls, MarkerType, Position, ReactFlow } from "@xyflow/react";

export function ResearchOutline({ title, items, onOpen }: { title: string; items: { id: string; title: string; subtitle: string }[]; onOpen: (id: string) => void }) {
  const nodes = [{ id: "outline-root", position: { x: 165, y: 0 }, data: { label: <strong>{title}</strong> }, sourcePosition: Position.Bottom, style: { width: 260 } },
    ...items.map((item, i) => ({ id: item.id, position: { x: (i % 2) * 330, y: 160 + Math.floor(i / 2) * 175 },
      data: { label: <><strong>{item.title.length > 66 ? item.title.slice(0, 66) + "…" : item.title}</strong><small>{item.subtitle} · 点击进入</small></> }, targetPosition: Position.Top, style: { width: 260 }, ariaLabel: item.title }))];
  return <><div className="rg-outline-canvas" style={{ height: Math.max(420, 170 + Math.ceil(items.length / 2) * 170) }}>
    <ReactFlow nodes={nodes} edges={items.map(item => ({ id: `contains:${item.id}`, source: "outline-root", target: item.id, type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed } }))}
      fitView fitViewOptions={{ padding: .1, maxZoom: 1 }} nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null} minZoom={.3}
      onNodeClick={(_, node) => { if (node.id !== "outline-root") onOpen(node.id); }}><Background gap={24} /><Controls showInteractive={false} /></ReactFlow>
  </div><div className="rg-outline-list" aria-label="可进入的研究节点">{items.map(item => <button key={item.id} onClick={() => onOpen(item.id)}><strong>{item.title}</strong><span>{item.subtitle} →</span></button>)}</div></>;
}
