import {
  AlertTriangle,
  BarChart3,
  BookOpenCheck,
  Boxes,
  CheckCircle2,
  Database,
  FileCheck2,
  FileText,
  GitBranch,
  Network,
  RefreshCw,
  SearchCheck,
  ShieldCheck,
} from "lucide-react";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import {
  CURRENT_PRODUCT_SURFACES,
  CurrentProductCase,
  CurrentProductSurface,
  CurrentProductSurfaceResponse,
  getCurrentProductSurface,
  listCurrentProductCases,
} from "../api/currentProduct";
import "./current-product.css";

type CurrentProductWorkbenchProps = { online: boolean };

const SURFACE_LABELS: Record<CurrentProductSurface, string> = {
  case: "研究案例",
  run: "运行状态",
  evidence: "证据池",
  numeric: "数值事实",
  graph: "关系图谱",
  gaps: "证据缺口",
  workpaper: "研究底稿",
  report: "交付报告",
  trace: "链路追踪",
  quality: "质量验收",
};

const SURFACE_ICONS: Record<CurrentProductSurface, typeof Database> = {
  case: BookOpenCheck,
  run: Boxes,
  evidence: SearchCheck,
  numeric: BarChart3,
  graph: Network,
  gaps: AlertTriangle,
  workpaper: FileCheck2,
  report: FileText,
  trace: GitBranch,
  quality: ShieldCheck,
};

export function isCurrentProductPath(pathname: string): boolean {
  return pathname === "/current" || pathname.startsWith("/current/");
}

export function CurrentProductWorkbench({ online }: CurrentProductWorkbenchProps) {
  const initial = useMemo(() => decodeCurrentPath(window.location.pathname), []);
  const [cases, setCases] = useState<CurrentProductCase[]>([]);
  const [caseKey, setCaseKey] = useState(initial.caseKey);
  const [surface, setSurface] = useState<CurrentProductSurface>(initial.surface);
  const [view, setView] = useState<CurrentProductSurfaceResponse | null>(null);
  const [manifestDigest, setManifestDigest] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const selectedCase = cases.find((item) => item.case_key === caseKey) ?? cases[0] ?? null;

  const loadCases = useCallback(async (signal?: AbortSignal) => {
    const response = await listCurrentProductCases(signal);
    const allowed = response.items.map((item) => item.case_key);
    const nextCase = allowed.includes(caseKey) ? caseKey : allowed[0] ?? "";
    setCases(response.items);
    setManifestDigest(response.manifest_digest);
    if (nextCase !== caseKey) {
      window.history.replaceState({}, "", `/current/${encodeURIComponent(nextCase)}/${surface}`);
      setCaseKey(nextCase);
    }
    return nextCase;
  }, [caseKey, surface]);

  const load = useCallback(async () => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    try {
      const resolvedCase = await loadCases(controller.signal);
      if (resolvedCase) {
        const response = await getCurrentProductSurface(resolvedCase, surface, controller.signal);
        setView(response);
      }
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : "current_product_load_failed");
        setView(null);
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
    return () => controller.abort();
  }, [loadCases, surface]);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    listCurrentProductCases(controller.signal)
      .then(async (response) => {
        if (disposed) return;
        const keys = response.items.map((item) => item.case_key);
        const resolvedCase = keys.includes(caseKey) ? caseKey : keys[0] ?? "";
        setCases(response.items);
        setManifestDigest(response.manifest_digest);
        if (resolvedCase !== caseKey) {
          window.history.replaceState({}, "", `/current/${encodeURIComponent(resolvedCase)}/${surface}`);
          setCaseKey(resolvedCase);
        }
        if (resolvedCase) {
          const nextView = await getCurrentProductSurface(resolvedCase, surface, controller.signal);
          if (!disposed) setView(nextView);
        }
      })
      .catch((caught) => {
        if (!disposed && !controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "current_product_load_failed");
          setView(null);
        }
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
      controller.abort();
    };
  }, [caseKey, surface]);

  const navigate = (nextCase: string, nextSurface: CurrentProductSurface) => {
    window.history.pushState({}, "", `/current/${encodeURIComponent(nextCase)}/${nextSurface}`);
    setCaseKey(nextCase);
    setSurface(nextSurface);
  };

  useEffect(() => {
    const onPopState = () => {
      const next = decodeCurrentPath(window.location.pathname);
      setCaseKey(next.caseKey);
      setSurface(next.surface);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  return (
    <div
      className="current-product"
      data-testid="current-product-root"
      data-active-case={selectedCase?.case_key ?? ""}
    >
      <header className="current-topbar">
        <div className="current-brand">
          <div className="current-brand-mark">F</div>
          <div>
            <strong>FinSight Current Research</strong>
            <span>可追溯的三案例研究产品面</span>
          </div>
        </div>
        <div className="current-status-cluster">
          <a className="current-back" href="/tasks">内部任务台</a>
          <span className={`current-online ${online ? "is-online" : ""}`}>{online ? "本机在线" : "本机离线"}</span>
          <span className="current-readonly"><ShieldCheck size={14} /> CURRENT · READ ONLY</span>
          <button type="button" className="current-refresh" onClick={() => void load()} aria-label="刷新 current product">
            <RefreshCw size={16} /> 刷新
          </button>
        </div>
      </header>

      <div className="current-layout">
        <aside className="current-sidebar">
          <div className="current-sidebar-heading">
            <span>已验收案例</span>
            <b>{cases.length}</b>
          </div>
          <div className="current-case-list">
            {cases.map((item) => (
              <button
                key={item.case_key}
                type="button"
                data-testid={`case-${item.case_key}`}
                className={item.case_key === selectedCase?.case_key ? "is-active" : ""}
                onClick={() => navigate(item.case_key, surface)}
              >
                <span className="current-case-ticker">{item.ticker}</span>
                <span className="current-case-status"><CheckCircle2 size={13} /> Owner accepted R2</span>
                <span className="current-case-date">截至 {formatDate(item.as_of)}</span>
              </button>
            ))}
          </div>
          <div className="current-mode-note">
            <ShieldCheck size={18} />
            <div><strong>模式隔离已开启</strong><span>当前产品只读取 digest-bound 成品，不接入 fixture 工作流。</span></div>
          </div>
        </aside>

        <main className="current-main">
          {selectedCase ? (
            <section className="current-case-hero">
              <div>
                <p className="current-kicker">CURRENT CASE · {selectedCase.case_key}</p>
                <h1>{selectedCase.ticker} 研究工作台</h1>
                <p>{selectedCase.natural_objective}</p>
              </div>
              <div className="current-counts" aria-label="案例数据计数">
                <Metric value={selectedCase.counts.evidence} label="Evidence" />
                <Metric value={selectedCase.counts.numeric} label="Numeric" />
                <Metric value={selectedCase.counts.typed_gaps} label="Typed gaps" tone="amber" />
                <Metric value={selectedCase.counts.business_artifacts} label="Artifacts" />
              </div>
            </section>
          ) : null}

          <nav className="current-surface-nav" aria-label="产品视图">
            {CURRENT_PRODUCT_SURFACES.map((item) => {
              const Icon = SURFACE_ICONS[item];
              return (
                <button
                  key={item}
                  type="button"
                  data-testid={`surface-${item}`}
                  className={surface === item ? "is-active" : ""}
                  onClick={() => selectedCase && navigate(selectedCase.case_key, item)}
                >
                  <Icon size={16} /> {SURFACE_LABELS[item]}
                </button>
              );
            })}
          </nav>

          <section className="current-content" aria-live="polite">
            <div className="current-content-heading">
              <div><span>只读视图</span><h2>{SURFACE_LABELS[surface]}</h2></div>
              {view ? <code title={view.view_digest}>view {shortDigest(view.view_digest)}</code> : null}
            </div>
            {loading ? <LoadingState /> : null}
            {!loading && error ? <ErrorState error={error} onRetry={() => void load()} /> : null}
            {!loading && !error && view ? <SurfaceRenderer surface={surface} data={view.data} /> : null}
          </section>

          <footer className="current-footer">
            <span>Manifest {shortDigest(manifestDigest)}</span>
            <span>原始 capture 与私有推理不暴露 · 所有视图均为 GET-only</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function SurfaceRenderer({ surface, data }: { surface: CurrentProductSurface; data: Record<string, unknown> }) {
  if (surface === "case") return <CaseSurface data={data} />;
  if (surface === "run") return <RunSurface data={data} />;
  if (surface === "evidence") return <EvidenceSurface data={data} />;
  if (surface === "numeric") return <NumericSurface data={data} />;
  if (surface === "graph") return <GraphSurface data={data} />;
  if (surface === "gaps") return <GapSurface data={data} />;
  if (surface === "workpaper") return <WorkpaperSurface data={data} />;
  if (surface === "report") return <ReportSurface data={data} />;
  if (surface === "trace") return <TraceSurface data={data} />;
  return <QualitySurface data={data} />;
}

function CaseSurface({ data }: { data: Record<string, unknown> }) {
  const cells = asArray(data.program_cell_ids);
  return <div className="current-grid two">
    <Panel title="产品状态" icon={<CheckCircle2 size={18} />}>
      <StatusLine label="状态" value={humanize(data.status)} tone="green" />
      <StatusLine label="截至日期" value={formatDate(String(data.as_of ?? ""))} />
      <StatusLine label="方法" value={data.method_id ? String(data.method_id) : "未单独声明（保留为空）"} />
    </Panel>
    <Panel title="接受边界" icon={<ShieldCheck size={18} />}><p className="current-prose">{String(data.accepted_product_scope ?? "")}</p></Panel>
    <Panel title="三个研究单元" icon={<Boxes size={18} />} wide>
      <div className="current-cell-list">{cells.map((cell, index) => <div key={String(cell)}><b>0{index + 1}</b><span>{humanize(cell)}</span></div>)}</div>
    </Panel>
  </div>;
}

function RunSurface({ data }: { data: Record<string, unknown> }) {
  const topology = asRecord(data.interaction_topology);
  const budget = asRecord(data.observed_budget);
  return <div className="current-grid two">
    <Panel title="Terminal result" icon={<CheckCircle2 size={18} />}>
      <StatusLine label="状态" value={humanize(data.status)} tone="green" />
      <StatusLine label="阶段" value={humanize(data.phase)} />
      <StatusLine label="可晋升" value={data.business_promotable === true ? "是" : "否"} tone="green" />
      <StatusLine label="结果码" value={humanize(data.code)} />
    </Panel>
    <Panel title="交互拓扑" icon={<GitBranch size={18} />}><MiniStats values={[
      [topology.provider_interaction_count, "Provider calls"],
      [topology.logical_node_count, "Logical nodes"],
      [topology.business_artifact_count, "Artifacts"],
    ]} /></Panel>
    <Panel title="实际预算" icon={<BarChart3 size={18} />}><MiniStats values={[
      [budget.input_tokens, "Input tokens"], [budget.output_tokens, "Output tokens"],
      [`$${Number(budget.estimated_cost_usd ?? 0).toFixed(4)}`, "Estimated cost"],
    ]} /></Panel>
    <Panel title="执行身份" icon={<Database size={18} />}><DigestList values={[
      ["Execution", data.execution_identity], ["Admission", data.admission_id],
      ["Input", data.input_digest], ["Terminal", data.terminal_result_digest],
    ]} /></Panel>
  </div>;
}

function EvidenceSurface({ data }: { data: Record<string, unknown> }) {
  const rows = asRecords(data.rows);
  return <div className="current-evidence-list" data-testid="evidence-list">{rows.map((row, index) => (
    <article key={String(row.evidence_row_digest ?? index)} className="current-evidence-card">
      <div className="current-card-meta"><span>{humanize(row.evidence_role)}</span><b>Authority {String(row.source_authority_rank ?? "—")}</b></div>
      <h3>{String(row.title ?? "Untitled evidence")}</h3>
      <p>{String(row.statement ?? "")}</p>
      <div className="current-citation"><span>{String(row.published_at ?? "")}</span><code>{String(row.citation ?? "")}</code></div>
    </article>
  ))}</div>;
}

function NumericSurface({ data }: { data: Record<string, unknown> }) {
  const rows = asRecords(data.rows);
  return <div className="current-table-wrap"><table className="current-table"><thead><tr><th>指标</th><th>期间</th><th>数值</th><th>权威口径</th></tr></thead><tbody>{rows.map((row, index) => (
    <tr key={String(row.numeric_row_digest ?? index)}><td><strong>{String(row.metric_name ?? "")}</strong><span>{humanize(row.metric_family)}</span></td><td>{String(row.period ?? "")}</td><td className="current-number">{formatNumber(row.value)} <small>{String(row.unit ?? "")}</small></td><td><span className={row.exact_value_authority === true ? "current-pill green" : "current-pill"}>{row.exact_value_authority === true ? "Exact" : "Bounded"}</span><small>{humanize(row.authority_scope)}</small></td></tr>
  ))}</tbody></table></div>;
}

function GraphSurface({ data }: { data: Record<string, unknown> }) {
  const edges = asArray(data.edges);
  if (edges.length === 0) return <div className="current-empty" data-testid="graph-empty"><Network size={38} /><h3>当前没有获批的 Graph 边</h3><p>这是一个经过类型化的诚实空状态。系统不会用候选关系、fixture 或推测性连接补齐图谱。</p><code>{humanize(data.reason)}</code></div>;
  return <GenericJson data={data} />;
}

function GapSurface({ data }: { data: Record<string, unknown> }) {
  return <div className="current-gap-list">{asRecords(data.rows).map((row, index) => <article key={String(row.gap_code ?? index)}><AlertTriangle size={18} /><div><strong>{humanize(row.gap_code)}</strong><p>不能推断：{String(row.cannot_infer ?? "")}</p><small>{asArray(row.program_cell_ids).map(humanize).join(" · ")}</small></div></article>)}</div>;
}

function WorkpaperSurface({ data }: { data: Record<string, unknown> }) {
  const cells = asRecords(data.cells);
  return <div className="current-workpaper">{cells.map((cell, index) => (
    <article key={String(cell.program_cell_id ?? index)}><div className="current-workpaper-index">0{index + 1}</div><div><h3>{humanize(cell.program_cell_id)}</h3><StatusLine label="Terminal" value={humanize(cell.terminal_class)} tone={cell.terminal_class === "supported" ? "green" : undefined} /><h4>判断原子</h4>{asRecords(cell.judgment_layer).map((claim, claimIndex) => <p key={String(claim.claim_id ?? claimIndex)} className="current-claim"><span>{humanize(claim.epistemic_status)}</span>{String(claim.statement ?? "")}</p>)}<h4>Remaining gaps</h4><p className="current-muted">{asArray(cell.remaining_gaps).join("；")}</p></div></article>
  ))}</div>;
}

function ReportSurface({ data }: { data: Record<string, unknown> }) {
  const preview = asRecord(data.final_delivery_preview);
  return <article className="current-report" data-testid="current-report"><header><span>VERIFIED DELIVERY PREVIEW</span><h2>{String(preview.title_zh_cn ?? "研究备忘录")}</h2><p>{String(preview.executive_summary_zh_cn ?? "")}</p></header>{asRecords(preview.sections).map((section, index) => <section key={String(section.program_cell_id ?? index)}><div className="current-report-section-number">0{index + 1}</div><div><h3>{humanize(section.program_cell_id)}</h3><p className="current-question">{String(section.decision_question ?? "")}</p>{asRecords(section.claims).map((claim, claimIndex) => <blockquote key={claimIndex}><span>{humanize(claim.epistemic_status)}</span>{String(claim.rendered_text_zh_cn ?? "")}</blockquote>)}</div></section>)}<footer><strong>局限</strong>{asArray(preview.limitations_zh_cn).map((item, index) => <p key={index}>— {String(item)}</p>)}</footer></article>;
}

function TraceSurface({ data }: { data: Record<string, unknown> }) {
  const terminal = asRecord(data.terminal);
  const topology = asRecord(data.interaction_topology);
  return <div className="current-grid two"><Panel title="Terminal receipt" icon={<CheckCircle2 size={18} />}><DigestList values={Object.entries(terminal)} /></Panel><Panel title="Trace coverage" icon={<GitBranch size={18} />}><MiniStats values={[[asArray(data.local_fact_receipts).length, "Local fact receipts"], [asArray(data.node_receipts).length, "Node receipts"], [topology.provider_capture_count, "Provider captures"]]} /></Panel><Panel title="隐私边界" icon={<ShieldCheck size={18} />} wide><StatusLine label="Raw content exposed" value={data.raw_content_exposed === true ? "是" : "否"} tone={data.raw_content_exposed === false ? "green" : undefined} /><p className="current-muted">Telemetry 仅承担索引与 lineage；产品面不显示 capture 正文或 Provider 私有推理。</p></Panel></div>;
}

function QualitySurface({ data }: { data: Record<string, unknown> }) {
  const layered = asRecord(data.layered_assessment);
  const owner = asRecord(data.owner_decision);
  const preserved = asRecord(data.preserved_boundaries);
  return <div className="current-grid two" data-testid="quality-surface"><Panel title="L1–L4 分层验收" icon={<ShieldCheck size={18} />}><StatusLine label="L1 · 确定性完整性" value={humanize(layered.L1_deterministic_integrity)} tone="green" /><StatusLine label="L2 · 权威覆盖" value={humanize(layered.L2_authority_coverage)} tone="green" /><StatusLine label="L3 · Agent 增益" value={humanize(layered.L3_agent_gain)} /><StatusLine label="L4 · 最终交付" value={humanize(layered.L4_final_delivery)} tone="green" /></Panel><Panel title="Owner decision" icon={<CheckCircle2 size={18} />}><p className="current-owner-quote">“{String(owner.owner_comment ?? "") }”</p><StatusLine label="Material gain accepted" value={owner.material_gain_accepted === true ? "是" : "否"} tone="green" /><p className="current-muted">{String(owner.accepted_product_scope ?? "")}</p></Panel><Panel title="仍保留的产品边界" icon={<AlertTriangle size={18} />} wide><div className="current-boundaries">{Object.entries(preserved).map(([key, value]) => <div key={key}><span>{humanize(key)}</span><b>{humanize(value)}</b></div>)}</div></Panel></div>;
}

function Metric({ value, label, tone }: { value: number; label: string; tone?: string }) { return <div className={tone === "amber" ? "is-amber" : ""}><strong>{value}</strong><span>{label}</span></div>; }
function Panel({ title, icon, wide, children }: { title: string; icon: ReactNode; wide?: boolean; children: ReactNode }) { return <article className={`current-panel ${wide ? "wide" : ""}`}><header>{icon}<h3>{title}</h3></header>{children}</article>; }
function StatusLine({ label, value, tone }: { label: string; value: string; tone?: string }) { return <div className="current-status-line"><span>{label}</span><b className={tone === "green" ? "is-green" : ""}>{value}</b></div>; }
function MiniStats({ values }: { values: Array<[unknown, string]> }) { return <div className="current-mini-stats">{values.map(([value, label]) => <div key={label}><strong>{String(value ?? "—")}</strong><span>{label}</span></div>)}</div>; }
function DigestList({ values }: { values: Array<[string, unknown]> }) { return <div className="current-digests">{values.map(([label, value]) => <div key={label}><span>{humanize(label)}</span><code title={String(value ?? "")}>{shortDigest(String(value ?? ""))}</code></div>)}</div>; }
function LoadingState() { return <div className="current-loading"><span /><span /><span /></div>; }
function ErrorState({ error, onRetry }: { error: string; onRetry: () => void }) { return <div className="current-empty is-error"><AlertTriangle size={34} /><h3>Current product 加载失败</h3><code>{error}</code><button type="button" onClick={onRetry}>重新加载</button></div>; }
function GenericJson({ data }: { data: Record<string, unknown> }) { return <pre className="current-json">{JSON.stringify(data, null, 2)}</pre>; }

function decodeCurrentPath(pathname: string): { caseKey: string; surface: CurrentProductSurface } {
  const match = /^\/current\/([^/]+)(?:\/([^/]+))?\/?$/.exec(pathname);
  const requestedSurface = match?.[2] as CurrentProductSurface | undefined;
  return {
    caseKey: match ? decodeURIComponent(match[1]).toUpperCase() : "NVDA",
    surface: requestedSurface && CURRENT_PRODUCT_SURFACES.includes(requestedSurface) ? requestedSurface : "case",
  };
}
function asArray(value: unknown): unknown[] { return Array.isArray(value) ? value : []; }
function asRecord(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function asRecords(value: unknown): Array<Record<string, unknown>> { return asArray(value).map(asRecord); }
function humanize(value: unknown): string { return String(value ?? "—").replace(/_/g, " "); }
function shortDigest(value: string): string { return value.length > 18 ? `${value.slice(0, 9)}…${value.slice(-7)}` : value || "—"; }
function formatDate(value: string): string { return value ? value.slice(0, 10) : "—"; }
function formatNumber(value: unknown): string { const parsed = Number(value); return Number.isFinite(parsed) ? new Intl.NumberFormat("en-US").format(parsed) : String(value ?? "—"); }
