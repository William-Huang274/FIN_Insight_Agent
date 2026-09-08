import { useEffect, useMemo, useRef, useState } from "react";
import { Background, Controls, MarkerType, Position, ReactFlow, type Node, type Edge } from "@xyflow/react";
import { sessionsApi, type Citation, type Session, type Source, type RevisionTarget, type ReportDiff } from "../api/reportSessions";
import { ReportDiffView } from "./ReportDiffView";
import { sourceCalculation } from "./sourceCalculation";
import { reportTopics } from "./reportTopics";
import { ResearchOutline } from "./ResearchOutline";
import { SourceReader } from "./SourceReader";
import ReactMarkdown from "react-markdown";
import { useSearchParams } from "react-router";
import { readMemory, writeMemory } from "./workspaceMemory";
import remarkGfm from "remark-gfm";
import "@xyflow/react/dist/style.css";
import "./research-graph.css";

type Props = { id: string; version: number; checkpoint?: string; report: NonNullable<Session["report"]>;
  digest?: string; canRevise: boolean; runs: NonNullable<Session["runs"]>; active: boolean; onReport: () => void; onRefresh: () => Promise<void> };
type Detail = { title: string; description: string; sourceId?: string; source?: Source };
const verification = (v?: boolean) => v === true ? "已记录通过" : v === false ? "未通过 / 未验证" : "未记录";

/** A read-only projection of saved citation and calculation relationships, not an execution graph. */
export function ResearchGraph({ id, version, checkpoint, report, digest, canRevise, runs, active, onReport, onRefresh }: Props) {
  const entries = useMemo(() => Object.entries(report.citations || {}), [report.citations]);
  const topics = useMemo(() => reportTopics(report), [report]);
  const memoryKey = `graph:${id}:${digest || checkpoint || version}`;
  const [params, setParams] = useSearchParams();
  const saved = readMemory(memoryKey, { topic: "", level: "overview", claim: entries[0]?.[0] || "" });
  const topicId = params.get("topic") || saved.topic;
  const requestedLevel = params.get("level") || saved.level;
  const level = topics.some(t => t.id === topicId) ? requestedLevel : "overview";
  const topic = topics.find(t => t.id === topicId);
  const claimId = params.get("claim") || saved.claim;
  const go = (nextLevel: string, nextTopic = topicId, nextClaim = claimId) => {
    writeMemory(memoryKey, { topic: nextTopic, level: nextLevel, claim: nextClaim });
    setParams(next => { next.set("level", nextLevel); next.set("topic", nextTopic); next.set("claim", nextClaim); return next; });
  };
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
  const [drafts, setDrafts] = useState<Record<string, string>>(() => readMemory(`drafts:${memoryKey}`, {}));
  useEffect(() => { writeMemory(`drafts:${memoryKey}`, drafts); }, [drafts, memoryKey]);
  const [preview, setPreview] = useState(false);
  const [editing, setEditing] = useState(false);
  const [reader, setReader] = useState<Source | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submission, setSubmission] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const submitLock = useRef(false);
  const [diff, setDiff] = useState<ReportDiff | null>(null);
  const [diffOpen, setDiffOpen] = useState(false);
  const [diffLoading, setDiffLoading] = useState(false);
  useEffect(() => { setDiff(null); setDiffOpen(false); }, [id, version]);
  const request = useRef(0);
  const detailsRef = useRef<HTMLElement>(null);
  const current = drafts[claimId] || "";
  const targetedRun = runs.find(r => r.revision_target);
  const submit = async () => {
    if (!digest || !pinned || !current.trim() || !canRevise || submitLock.current || uncertain) return;
    submitLock.current = true; setSubmitting(true); setSubmission("");
    const target: RevisionTarget = { request_id: crypto.randomUUID(), citation_id: claimId, base_version: version, base_digest: digest, base_checkpoint: pinned };
    try {
      const result = await sessionsApi.action(id, "revise", current, "deep", target);
      setSubmission(`已提交修订，运行 ${result.run_id}。原报告保留，等待实际结果。`);
      setDrafts(old => ({ ...old, [claimId]: "" })); setPreview(false);
      await onRefresh();
    } catch (e) { setSubmission(`提交未确认：${(e as Error).message}。请刷新运行状态，勿直接重复发送。`); setUncertain(true); }
    finally { setSubmitting(false); submitLock.current = false; }
  };

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
    const shift = expanded ? 280 : 0;
    add("claim", 300 + shift, 70, "引用记录中的原始主张", "研究引用", citation?.claim.statement || "没有保存主张文本");
    add("report", 590 + shift, 70, `报告 v${version}`, "报告输出", report.title);
    edge("claim", "report", "引用绑定");
    (citation?.sources || []).filter(s => !expanded || s.source_id === expandedSource).forEach((s, index) => {
      const sourceId = `source:${s.source_id}`;
      const saved = loaded[s.source_id] || s;
      const calc = sourceCalculation(saved);
      if (info[sourceId]) return;
      add(sourceId, 10 + shift, index * 180, calc ? calc.expression : s.title || "保存的来源", calc ? "保存计算" : "来源记录",
        saved.text || saved.notice || "选择此节点读取原文或计算。", s.source_id, saved);
      edge(sourceId, "claim", "被引用");
      if (expanded && calc) Object.entries(calc.operands).forEach(([name, operand], i) => {
        const operandId = `${sourceId}:operand:${name}`;
        const rawId = operand.source_id;
        const actualId = rawId ? calc.operand_source_aliases?.[rawId] || rawId : undefined;
        const value = operand.value_decimal ?? operand.literal ?? "数值未记录";
        add(operandId, 10, i * 170, `${name} = ${value}`, "计算操作数",
          `单位：${operand.unit || operand.source_provenance?.unit || "未记录"}\n期间：${operand.period_end || operand.source_provenance?.fiscal_period || "未记录"}\n${operand.quote || ""}${actualId ? "" : "\n未绑定来源；可能为常量或显式假设，请核对原计算。"}`, actualId);
        edge(operandId, sourceId, name);
      });
    });
    return { nodes, edges, info };
  }, [citation, loaded, expanded, expandedSource, current, report.title, version]);

  const calc = sourceCalculation(detail?.source || null);
  if (!entries.length) return <div className="rg-empty" hidden={!active}>这版报告尚未保存可展示的引用关系。<button onClick={onReport}>阅读报告</button></div>;
  return <section className="rg-workspace" aria-label="研究依据图">
    <div className="rg-toolbar">
      <nav aria-label="研究图路径"><button onClick={() => go("overview")}>报告总览</button>{level !== "overview" && <><span> / </span><button onClick={() => go("topic")}>{topic?.title || "专题"}</button></>}{level === "claim" && <span> / 判断与依据</span>}</nav>
      <button onClick={onReport}>阅读完整报告</button>
    </div>
    {targetedRun && <div className="rg-run-result" role="status"><strong>节点修订：{({ pending: "等待执行", running: "正在修订", success: "运行完成，待审阅", error: "修订失败，旧结果保留", interrupted: "运行已停止 / 等待处理" } as Record<string, string>)[targetedRun.status] || targetedRun.status}</strong>
      <p>目标：{targetedRun.revision_target!.citation_id} · 基线 v{targetedRun.revision_target!.base_version} → 当前报告 v{version}。运行完成不等同于判断已通过审阅。</p>
      <button aria-expanded={diffOpen} aria-controls="targeted-report-diff" disabled={diffLoading} onClick={async () => { if (diffOpen) { setDiffOpen(false); return; } if (diff) { setDiffOpen(true); return; } setDiffLoading(true); try { const result = await sessionsApi.diff(id, targetedRun.revision_target!.base_checkpoint); setDiff(result); setDiffOpen(true); } catch (e) { setError((e as Error).message); } finally { setDiffLoading(false); } }}>{diffLoading ? "正在读取变化…" : diffOpen ? "收起报告变化" : "查看相对基线的报告变化"}</button>
      <div id="targeted-report-diff" hidden={!diffOpen}>{diff && <><ReportDiffView value={diff} /><button onClick={() => { setDiffOpen(false); document.querySelector<HTMLButtonElement>('[aria-controls="targeted-report-diff"]')?.focus(); }}>收起并返回研究图 ↑</button></>}</div></div>}
    {submission && <div className="rg-run-result" role="status">{submission}<button onClick={() => void onRefresh()}>刷新运行状态</button></div>}
    {level === "overview" && <div className="rg-hierarchy"><h2>这份报告研究了什么？</h2><p>按报告章节浏览。连线表示内容归属，不代表已证实的因果关系。</p>{active && <ResearchOutline title={report.title} items={topics.map(t => ({ id: t.id, title: t.title, subtitle: `${t.claimIds.length} 条研究引用` }))} onOpen={next => { go("topic", next); }} />}</div>}
    {level === "topic" && topic && <div className="rg-hierarchy"><h2>{topic.title}</h2><p>{topic.excerpt}</p><details><summary>展开本专题的报告正文</summary><ReactMarkdown skipHtml remarkPlugins={[remarkGfm]}>{topic.markdown}</ReactMarkdown></details>
      {!topic.claimIds.length && <p>本节没有定位到已绑定引用，可先阅读正文。</p>}{active && topic.claimIds.length > 0 && <ResearchOutline title={topic.title} items={topic.claimIds.map(key => ({ id: key, title: report.citations[key].claim.statement, subtitle: `${report.citations[key].sources.length} 条来源 / 计算依据` }))} onOpen={next => { go("claim", topicId, next); }} />}</div>}
    <div hidden={level !== "claim"}>
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
          {active && level === "claim" && <div style={{ width: expanded ? 1130 : 850, height: Math.max(420, ...graph.nodes.map(n => n.position.y + 185)) }}><ReactFlow key={`${claimId}:${expanded}`} nodes={graph.nodes} edges={graph.edges} defaultViewport={{ x: 15, y: 20, zoom: 1 }}
            minZoom={1} maxZoom={1} panOnDrag={false} zoomOnScroll={false} zoomOnPinch={false} zoomOnDoubleClick={false} preventScrolling={false} nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null}
            onNodeClick={(_, node) => { request.current += 1; setLoading(false); const selected = graph.info[node.id]; setDetail(selected); setError("");
              if (selected.sourceId) void read(selected.sourceId);
              if (window.innerWidth < 1000) detailsRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }); }}>
            <Background gap={22} size={1} />
          </ReactFlow></div>}
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
        {detail?.source && <button className="rg-open-reader" onClick={() => setReader(detail.source!)}>扩展上下文 / 阅读原文</button>}
        <div className="rg-edit-area"><button className="rg-primary" onClick={() => { setEditing(true); setPreview(false); }}>针对这条引用写修订意见</button>
          {editing && <><label htmlFor="rg-draft">你的假设 / 质疑 / 补证要求</label><textarea id="rg-draft" value={current} onChange={e => { setDrafts(old => ({ ...old, [claimId]: e.target.value })); setPreview(false); }} placeholder="例如：请检查回款跨期的影响，并区分假设与已披露事实。" />
            <div className="rg-draft-actions"><button disabled={!current.trim()} onClick={() => setPreview(true)}>查看修订范围</button><button onClick={() => { setDrafts(old => ({ ...old, [claimId]: "" })); setPreview(false); }}>清空草稿</button></div>
            <small>草稿按任务、引用和报告基线保存在此浏览器标签页，刷新后可继续。原始证据不变。</small></>}
        </div>
        {preview && <div className="rg-preview" role="status"><strong>修订预览 · 基于报告 v{version}</strong><p>{current}</p><p>目标是这条已绑定引用及其报告表述。交由现有研究修订与复核流程处理，可能涉及上游研究和整份报告，不承诺仅重跑图上节点。</p><p>确认提交后会调用研究模型并产生费用，实际用量见“运行与费用”。原报告历史保留；候选仍需审阅。</p>
          <button className="rg-primary" disabled={!canRevise || !digest || !pinned || submitting || uncertain} onClick={() => void submit()}>{submitting ? "正在提交…" : "确认提交修订"}</button>{(!canRevise || !digest) && <p>历史版只读，或当前尚未处于可修订审阅点；请返回当前报告核对状态。</p>}</div>}
      </aside>
    </div>
    </div>
    {reader && <SourceReader key={reader.source_id} id={id} checkpoint={pinned} source={reader} context={citation?.claim.statement || ""} quote={[citation?.claim.citation_quotes?.[reader.source_id] || ""].flat()[0]} onClose={() => setReader(null)} />}
  </section>;
}
