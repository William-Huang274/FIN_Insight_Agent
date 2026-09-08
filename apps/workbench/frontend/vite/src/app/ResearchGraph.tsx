import { useEffect, useMemo, useRef, useState } from "react";
import { Background, Controls, MarkerType, Position, ReactFlow, type Node, type Edge } from "@xyflow/react";
import { sessionsApi, type Citation, type Session, type Source } from "../api/reportSessions";
import { sourceCalculation } from "./sourceCalculation";
import "@xyflow/react/dist/style.css";
import "./research-graph.css";

type Props = { id: string; version: number; checkpoint?: string; report: NonNullable<Session["report"]>;
  active: boolean; onReport: () => void };
type Detail = { title: string; description: string; sourceId?: string; source?: Source };
const verification = (v?: boolean) => v === true ? "已记录通过" : v === false ? "未通过 / 未验证" : "未记录";

/** A read-only projection of saved citation and calculation relationships, not an execution graph. */
export function ResearchGraph({ id, version, checkpoint, report, active, onReport }: Props) {
  const entries = useMemo(() => Object.entries(report.citations || {}), [report.citations]);
  const [claimId, setClaimId] = useState(entries[0]?.[0] || "");
  const citation: Citation | undefined = report.citations[claimId];
  const [pinned, setPinned] = useState(checkpoint || "");
  const [pinError, setPinError] = useState("");
  const [pinAttempt, setPinAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Record<string, Source>>({});
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [expandedSource, setExpandedSource] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState(false);
  const [editing, setEditing] = useState(false);
  const request = useRef(0);
  const detailsRef = useRef<HTMLElement>(null);
  const current = drafts[claimId] || "";

  useEffect(() => {
    if (!active || pinned) return;
    let live = true;
    setPinError("");
    sessionsApi.versions(id).then(result => {
      if (!live) return;
      const match = result.versions.find(item => item.version === version);
      if (!match) throw new Error("当前报告检查点不在最近版本页，请刷新报告后重试。");
      setPinned(match.checkpoint_id);
    }).catch(e => { if (live) setPinError(e.message); });
    return () => { live = false; };
  }, [active, pinned, id, version, pinAttempt]);
  useEffect(() => () => { request.current += 1; }, []);
  useEffect(() => { request.current += 1; setDetail(null); setError(""); setLoading(false);
    setExpanded(false); setPreview(false); setEditing(false); }, [claimId]);

  const read = async (sourceId: string, expand = false) => {
    if (!pinned) return;
    const ticket = ++request.current;
    setDetail({ title: "保存的来源", description: "", sourceId });
    setError(""); setLoading(true);
    try {
      const result = loaded[sourceId] || await sessionsApi.source(id, sourceId, 0, pinned);
      if (ticket !== request.current) return;
      setLoaded(old => ({ ...old, [sourceId]: result }));
      setDetail({ title: result.title || "保存的来源", description: result.text || result.notice || "此窗口未返回原文。", sourceId, source: result });
      if (expand && sourceCalculation(result)) { setExpandedSource(sourceId); setExpanded(true); }
    } catch (e) { if (ticket === request.current) setError((e as Error).message); }
    finally { if (ticket === request.current) setLoading(false); }
  };

  const graph = useMemo(() => {
    const nodes: Node[] = [], edges: Edge[] = [];
    const info: Record<string, Detail> = {};
    const add = (nodeId: string, x: number, y: number, title: string, caption: string, description: string, sourceId?: string, source?: Source) => {
      nodes.push({ id: nodeId, position: { x, y }, data: { label: <><small>{caption}</small><strong>{title}</strong></> },
        sourcePosition: Position.Right, targetPosition: Position.Left,
        className: current.trim() && ["claim", "report"].includes(nodeId) ? "rg-affected" : "",
        ariaLabel: `${caption}：${title}`, style: { width: 220 } });
      info[nodeId] = { title, description, sourceId, source };
    };
    const edge = (from: string, to: string, label: string) => edges.push({ id: `${from}->${to}`, source: from, target: to,
      label, type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed } });
    add("claim", 330, 70, "引用记录中的原始主张", "研究引用", citation?.claim.statement || "没有保存主张文本");
    add("report", 330, 260, `报告 v${version}`, "报告输出", report.title);
    edge("claim", "report", "引用绑定");
    (citation?.sources || []).filter(s => !expanded || s.source_id === expandedSource).forEach((s, index) => {
      const sourceId = `source:${s.source_id}`;
      const saved = loaded[s.source_id] || s;
      const calc = sourceCalculation(saved);
      if (info[sourceId]) return;
      add(sourceId, 40, index * 180, calc ? calc.expression : s.title || "保存的来源", calc ? "保存计算" : "来源记录",
        saved.text || saved.notice || "选择此节点读取原文或计算。", s.source_id, saved);
      edge(sourceId, "claim", "被引用");
      if (expanded && calc) Object.entries(calc.operands).forEach(([name, operand], i) => {
        const operandId = `${sourceId}:operand:${name}`;
        const rawId = operand.source_id;
        const actualId = rawId ? calc.operand_source_aliases?.[rawId] || rawId : undefined;
        const value = operand.value_decimal ?? operand.literal ?? "数值未记录";
        add(operandId, -240, i * 170, `${name} = ${value}`, "计算操作数",
          `单位：${operand.unit || operand.source_provenance?.unit || "未记录"}\n期间：${operand.period_end || operand.source_provenance?.fiscal_period || "未记录"}\n${operand.quote || ""}${actualId ? "" : "\n未绑定来源；可能为常量或显式假设，请核对原计算。"}`, actualId);
        edge(operandId, sourceId, name);
      });
    });
    return { nodes, edges, info };
  }, [citation, loaded, expanded, expandedSource, current, report.title, version]);

  const calc = sourceCalculation(detail?.source || null);
  if (!entries.length) return <div className="rg-empty">这版报告尚未保存可展示的引用关系。<button onClick={onReport}>阅读报告</button></div>;
  return <section className="rg-workspace" aria-label="研究依据图">
    <div className="rg-toolbar">
      <label htmlFor="rg-claim-picker">选择研究引用 <span>{entries.length} 条</span></label>
      <select id="rg-claim-picker" value={claimId} onChange={e => setClaimId(e.target.value)}>
        {entries.map(([key, c], index) => <option key={key} value={key}>{index + 1}. {c.claim.statement.slice(0, 130)}</option>)}
      </select>
      <button onClick={onReport}>阅读完整报告</button>
    </div>
    <div className="rg-summary"><strong>{citation?.claim.statement}</strong><span>引用原始主张可能早于报告修订；请结合当前正文核对。图仅展示保存的引用与计算关系。</span></div>
    {pinError && <div className="rg-error" role="alert">{pinError} <button onClick={() => setPinAttempt(n => n + 1)}>重试版本读取</button></div>}
    <div className="rg-layout">
      <div className="rg-canvas-area">
        <div className="rg-canvas-tools"><span>{pinned ? `已固定报告 v${version} 的来源版本` : "正在定位报告来源版本…"}</span>
          <button disabled={!pinned || loading || !citation?.sources.length} onClick={async () => {
            if (expanded) { setExpanded(false); return; }
            // Read one selected source on demand; never preload an entire report's evidence.
            await read(detail?.sourceId && citation.sources.some(s => s.source_id === detail.sourceId) ? detail.sourceId : citation.sources[0].source_id, true);
          }}>{expanded ? "收起操作数" : "展开来源 / 计算"}</button>
        </div>
        <div className="rg-canvas">
          {active && <ReactFlow key={`${claimId}:${expanded}`} nodes={graph.nodes} edges={graph.edges} fitView fitViewOptions={{ padding: .18, maxZoom: 1 }}
            minZoom={.25} maxZoom={1.6} nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null}
            onNodeClick={(_, node) => { request.current += 1; setLoading(false); const selected = graph.info[node.id]; setDetail(selected); setError("");
              if (selected.sourceId) void read(selected.sourceId);
              if (window.innerWidth < 1000) detailsRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }); }}>
            <Background gap={22} size={1} /><Controls showInteractive={false} />
          </ReactFlow>}
        </div>
        {expanded && (citation?.sources.length || 0) > 1 && <div className="rg-other-sources"><span>同一引用的其他依据</span>{citation.sources.filter(s => s.source_id !== expandedSource).map(s => <button key={s.source_id} onClick={() => { setExpanded(false); void read(s.source_id, true); }}>{s.title || s.source_id}</button>)}</div>}
        <div className="rg-mobile-nodes" aria-label="图节点列表">{Object.entries(graph.info).map(([key, d]) =>
          <button key={key} onClick={() => { request.current += 1; setLoading(false); setError(""); setDetail(d); if (d.sourceId) void read(d.sourceId); }}>{d.title}</button>)}</div>
        <p className="rg-hint">箭头表示已记录的依赖。选中节点可查看详情；关系缺失时不推定完整推导过程。</p>
      </div>
      <aside className="rg-details" aria-label="研究节点详情" ref={detailsRef}>
        <span className="rg-eyebrow">{detail ? "节点详情" : "从依据到判断"}</span>
        <h3>{detail?.title || "参与这条研究引用"}</h3>
        {loading && <p role="status">读取保存的来源中…</p>}
        {error && <div role="alert" className="rg-error">{error}<button disabled={!detail?.sourceId} onClick={() => detail?.sourceId && void read(detail.sourceId)}>重试来源读取</button></div>}
        {calc ? <div className="rg-calculation"><p><code>{calc.expression}</code></p><strong>{calc.value_decimal || detail?.source?.value_decimal || "数值未记录"} {calc.result_unit || detail?.source?.unit}</strong>
          <p>算术：{verification(calc.arithmetic_verified)}<br />金融语义：{verification(calc.financial_semantics_verified)}</p>
          <p>{calc.rationale}</p><button onClick={() => { setExpandedSource(detail?.sourceId || ""); setExpanded(true); }}>在图上展开操作数</button>
        </div> : <p className="rg-source-text">{detail?.description || "点击图里的来源核对原文，也可以先写下你的质疑、假设或希望补充的证据。"}</p>}
        {detail?.sourceId && <details><summary>来源标识与版本</summary><p>{detail.sourceId}</p><p>{pinned || "版本未定位"}</p></details>}
        <div className="rg-edit-area"><button className="rg-primary" onClick={() => { setEditing(true); setPreview(false); }}>针对这条引用写修订意见</button>
          {editing && <><label htmlFor="rg-draft">你的假设 / 质疑 / 补证要求</label><textarea id="rg-draft" value={current} onChange={e => { setDrafts(old => ({ ...old, [claimId]: e.target.value })); setPreview(false); }} placeholder="例如：请检查回款跨期的影响，并区分假设与已披露事实。" />
            <div className="rg-draft-actions"><button disabled={!current.trim()} onClick={() => setPreview(true)}>查看修订范围</button><button onClick={() => { setDrafts(old => ({ ...old, [claimId]: "" })); setPreview(false); }}>清空草稿</button></div>
            <small>草稿仅保留在当前页面；刷新后清除。原始证据不变。</small></>}
        </div>
        {preview && <div className="rg-preview" role="status"><strong>草稿 · 基于报告 v{version}</strong><p>{current}</p><p>已知关联：当前引用及其报告。尚未记录完整判断依赖，实际修订可能涉及上游研究和整份报告复核。</p><p>本版先供图交互审阅，尚未连接修订执行；未发起模型调用。</p></div>}
      </aside>
    </div>
  </section>;
}
