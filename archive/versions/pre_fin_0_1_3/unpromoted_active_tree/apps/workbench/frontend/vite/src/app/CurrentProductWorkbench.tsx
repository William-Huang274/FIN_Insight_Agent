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
  KeyRound,
  LockKeyhole,
  Network,
  RefreshCw,
  RotateCcw,
  SearchCheck,
  Send,
  ShieldCheck,
} from "lucide-react";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import {
  CURRENT_PRODUCT_SURFACES,
  CURRENT_INTERNAL_ACTOR,
  CurrentProductCase,
  CurrentRepairReason,
  CurrentReviewControlState,
  CurrentReviewerPacket,
  QualifiedReviewState,
  CurrentProductSurface,
  CurrentProductSurfaceResponse,
  getCurrentProductSurface,
  getCurrentReviewerPacket,
  getQualifiedReviewState,
  getCurrentReviewControl,
  listCurrentProductCases,
  requestCurrentReturnForRepair,
  submitQualifiedReviewDecision,
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
  const [reviewControl, setReviewControl] = useState<CurrentReviewControlState | null>(null);
  const [reviewerPacket, setReviewerPacket] = useState<CurrentReviewerPacket | null>(null);
  const [manifestDigest, setManifestDigest] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [repairSubmitting, setRepairSubmitting] = useState(false);
  const [repairError, setRepairError] = useState<string | null>(null);
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
        const [response, control, packet] = await Promise.all([
          getCurrentProductSurface(resolvedCase, surface, controller.signal),
          getCurrentReviewControl(resolvedCase, controller.signal),
          resolvedCase === "NVDA" ? getCurrentReviewerPacket(resolvedCase, controller.signal) : Promise.resolve(null),
        ]);
        setView(response);
        setReviewControl(control);
        setReviewerPacket(packet);
      }
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : "current_product_load_failed");
        setView(null);
        setReviewControl(null);
        setReviewerPacket(null);
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
          const [nextView, control, packet] = await Promise.all([
            getCurrentProductSurface(resolvedCase, surface, controller.signal),
            getCurrentReviewControl(resolvedCase, controller.signal),
            resolvedCase === "NVDA" ? getCurrentReviewerPacket(resolvedCase, controller.signal) : Promise.resolve(null),
          ]);
          if (!disposed) {
            setView(nextView);
            setReviewControl(control);
            setReviewerPacket(packet);
          }
        }
      })
      .catch((caught) => {
        if (!disposed && !controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "current_product_load_failed");
          setView(null);
          setReviewControl(null);
          setReviewerPacket(null);
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

  const submitRepair = async (reasonCode: CurrentRepairReason, reviewerNote: string) => {
    if (!selectedCase || !view || view.case_key !== selectedCase.case_key || view.surface !== surface) return;
    setRepairSubmitting(true);
    setRepairError(null);
    try {
      const next = await requestCurrentReturnForRepair(selectedCase.case_key, {
        expected_manifest_digest: view.manifest_digest,
        expected_case_projection_digest: view.case_projection_digest,
        target_surface: surface,
        expected_target_view_digest: view.view_digest,
        target_ref: `surface:${surface}`,
        reason_code: reasonCode,
        reviewer_note: reviewerNote.trim(),
        actor_ref: CURRENT_INTERNAL_ACTOR,
        idempotency_key: `${selectedCase.case_key}-${surface}-${crypto.randomUUID()}`,
      });
      setReviewControl(next);
    } catch (caught) {
      setRepairError(caught instanceof Error ? caught.message : "current_repair_request_failed");
      throw caught;
    } finally {
      setRepairSubmitting(false);
    }
  };

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
          <span className="current-readonly"><ShieldCheck size={14} /> BUSINESS TRUTH · READ ONLY</span>
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

          {!loading && !error && view && reviewControl ? (
            <RepairControl
              key={`${view.case_key}:${surface}`}
              surface={surface}
              state={reviewControl}
              submitting={repairSubmitting}
              error={repairError}
              onSubmit={submitRepair}
            />
          ) : null}

          {!loading && !error && view && reviewerPacket ? (
            <QualifiedReviewPanel packet={reviewerPacket} surface={surface} viewDigest={view.view_digest} />
          ) : null}

          <footer className="current-footer">
            <span>Manifest {shortDigest(manifestDigest)}</span>
            <span>业务真值只读 · 返修请求追加留痕 · 原始 capture 与私有推理不暴露</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

const REPAIR_REASON_OPTIONS: Array<{
  value: CurrentRepairReason;
  label: string;
  surfaces: CurrentProductSurface[];
}> = [
  { value: "missing_authority", label: "权威证据不足", surfaces: ["evidence", "gaps", "workpaper", "report"] },
  { value: "numeric_scope_or_unit", label: "数值期间 / 单位 / 口径问题", surfaces: ["numeric", "workpaper", "report"] },
  { value: "unsupported_inference", label: "推断缺少证据支持", surfaces: ["workpaper", "report", "quality"] },
  { value: "missing_counterevidence", label: "缺少反方证据", surfaces: ["evidence", "gaps", "workpaper", "report"] },
  { value: "lineage_mismatch", label: "引用或 lineage 不一致", surfaces: ["evidence", "numeric", "workpaper", "report", "trace"] },
  { value: "delivery_clarity", label: "交付表达不清晰", surfaces: ["report", "quality"] },
];

function RepairControl({
  surface,
  state,
  submitting,
  error,
  onSubmit,
}: {
  surface: CurrentProductSurface;
  state: CurrentReviewControlState;
  submitting: boolean;
  error: string | null;
  onSubmit: (reason: CurrentRepairReason, note: string) => Promise<void>;
}) {
  const options = REPAIR_REASON_OPTIONS.filter((item) => item.surfaces.includes(surface));
  const [reason, setReason] = useState<CurrentRepairReason | "">(options[0]?.value ?? "");
  const [note, setNote] = useState("");
  const [expanded, setExpanded] = useState(false);
  const open = state.return_requests.filter((item) => item.status === "repair_requested");
  const ready = state.T07_handoff.status === "ready_for_qualified_review";

  const submit = async () => {
    if (!reason || !note.trim()) return;
    await onSubmit(reason, note);
    setNote("");
    setExpanded(false);
  };

  return (
    <section className="current-repair-control" data-testid="current-repair-control">
      <header>
        <div><RotateCcw size={18} /><span>返修控制与历史回放</span></div>
        <div className={ready ? "current-handoff is-ready" : "current-handoff is-blocked"}>
          {ready ? "T07 handoff ready" : `${open.length} 个返修请求待处理`}
        </div>
      </header>
      <div className="current-repair-summary">
        <div><span>Replay integrity</span><b>{state.replay_integrity}</b></div>
        <div><span>Event count</span><b>{state.event_count}</b></div>
        <div><span>Replay digest</span><code>{shortDigest(state.replay_digest)}</code></div>
        <div><span>Reviewer authority</span><b>未认证 · 尚未执行（归 T07）</b></div>
      </div>
      {open.length ? (
        <div className="current-repair-history">
          {open.map((item) => (
            <article key={item.request_id}>
              <span>{humanize(item.reason_code)}</span>
              <p>{item.reviewer_note}</p>
              <small>{humanize(item.repair_owner)} · {humanize(item.requested_resolution)} · {formatDate(item.requested_at)}</small>
            </article>
          ))}
        </div>
      ) : <p className="current-muted">当前没有返修请求；exact digest handoff 已准备好，但这不代表 qualified reviewer 已接受。</p>}
      {options.length ? (
        <div className="current-repair-actions">
          {!expanded ? (
            <button type="button" onClick={() => setExpanded(true)}>针对当前“{SURFACE_LABELS[surface]}”请求返修</button>
          ) : (
            <div className="current-repair-form">
              <label>问题类型<select value={reason} onChange={(event) => setReason(event.target.value as CurrentRepairReason)}>{options.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label>返修说明<textarea maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} placeholder="说明需要补什么、为何影响当前判断；不会自动启动模型或来源调用。" /></label>
              {error ? <code className="current-repair-error">{error}</code> : null}
              <div><button type="button" className="is-secondary" onClick={() => setExpanded(false)} disabled={submitting}>取消</button><button type="button" onClick={() => void submit()} disabled={submitting || !reason || !note.trim()}><Send size={15} />{submitting ? "正在记录…" : "记录返修请求"}</button></div>
            </div>
          )}
        </div>
      ) : <p className="current-muted">当前视图没有可用的返修类型；请切换到 Evidence、Numeric、Gap、Workpaper、Report、Trace 或 Quality。</p>}
    </section>
  );
}

function QualifiedReviewPanel({
  packet,
  surface,
  viewDigest,
}: {
  packet: CurrentReviewerPacket;
  surface: CurrentProductSurface;
  viewDigest: string;
}) {
  const [credential, setCredential] = useState("");
  const [state, setState] = useState<QualifiedReviewState | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const burden = packet.review_burden;
  const lead = asRecord(packet.sections.cross_cell_lead);
  const dependencies = asArray(lead.cross_cell_dependencies).map(asRecord);
  const conflicts = asArray(lead.conflict_adjudications).map(asRecord);
  const gaps = asArray(lead.remaining_gaps).map(asRecord);
  const decision = state?.decision;

  const authenticate = async () => {
    if (!credential.trim()) return;
    setBusy(true);
    setAuthError(null);
    try {
      setState(await getQualifiedReviewState(credential.trim()));
    } catch (caught) {
      setState(null);
      setAuthError(caught instanceof Error ? caught.message : "qualified_review_authentication_failed");
    } finally {
      setBusy(false);
    }
  };

  const submitDecision = async (action: "accept_exact_version" | "return_for_repair") => {
    if (!state || !credential.trim() || !note.trim()) return;
    if (action === "accept_exact_version" && confirmation !== "ACCEPT NVDA R3") return;
    const reason = REPAIR_REASON_OPTIONS.find((item) => item.surfaces.includes(surface))?.value ?? "delivery_clarity";
    setBusy(true);
    setAuthError(null);
    try {
      const next = await submitQualifiedReviewDecision(credential.trim(), {
        action,
        reviewer_note: note.trim(),
        idempotency_key: `${action}-${crypto.randomUUID()}`,
        ...(action === "return_for_repair" ? {
          target_surface: surface,
          expected_target_view_digest: viewDigest,
          reason_code: reason,
        } : {}),
      });
      setState(next);
      setCredential("");
      setNote("");
      setConfirmation("");
    } catch (caught) {
      setAuthError(caught instanceof Error ? caught.message : "qualified_review_decision_failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="current-qualified-review" data-testid="current-qualified-review">
      <header>
        <div><LockKeyhole size={18} /><span>NVDA exact qualified review</span></div>
        <code>packet {shortDigest(packet.packet_digest)}</code>
      </header>
      <div className="current-review-burden">
        <Metric value={Number(burden.evidence_rows ?? 0)} label="Evidence" />
        <Metric value={Number(burden.claims ?? 0)} label="Claims" />
        <Metric value={Number(burden.what_would_change_items ?? 0)} label="WWC" />
        <Metric value={Number(burden.unresolved_conflicts ?? 0)} label="Unresolved" tone="amber" />
      </div>
      <div className="current-review-lead">
        <ReviewLeadGroup title="跨单元依赖" rows={dependencies} />
        <ReviewLeadGroup title="未决冲突" rows={conflicts} />
        <ReviewLeadGroup title="Lead gaps" rows={gaps} />
      </div>
      <div className="current-review-checklist">
        {packet.review_checklist.map((item) => (
          <article key={item.check_id}><CheckCircle2 size={15} /><div><b>{humanize(item.check_id)}</b><p>{item.instruction}</p></div><span>{humanize(item.review_status)}</span></article>
        ))}
      </div>
      {!state ? (
        <div className="current-review-auth">
          <label><span>离线签发的一次性 reviewer credential</span><input type="password" name="fin-t07-reviewer-credential" autoComplete="off" value={credential} onChange={(event) => setCredential(event.target.value)} /></label>
          <button type="button" onClick={() => void authenticate()} disabled={busy || !credential.trim()}><KeyRound size={15} />{busy ? "正在认证…" : "认证并打开决策区"}</button>
        </div>
      ) : (
        <div className="current-review-decision">
          <div className="current-authenticated-reviewer"><ShieldCheck size={16} /><span>{state.session.reviewer_ref} · {humanize(state.session.reviewer_role)}</span><b>authenticated</b></div>
          {decision ? (
            <p className="current-review-terminal">已记录 terminal decision：<b>{humanize(decision.action)}</b>。NVDA R3：{state.acceptance.NVDA_R3 ? "成立" : "不成立"}；release 仍未放行。</p>
          ) : (
            <>
              <label>审核说明<textarea maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} placeholder="记录证据、数值、推断、冲突、gap 与最终交付的审核结论。" /></label>
              <label>接受确认<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder="接受时输入：ACCEPT NVDA R3" /></label>
              <div><button type="button" className="is-secondary" disabled={busy || !note.trim()} onClick={() => void submitDecision("return_for_repair")}><RotateCcw size={15} />退回当前视图</button><button type="button" disabled={busy || !note.trim() || confirmation !== "ACCEPT NVDA R3"} onClick={() => void submitDecision("accept_exact_version")}><ShieldCheck size={15} />接受 exact NVDA R3</button></div>
            </>
          )}
        </div>
      )}
      {authError ? <code className="current-repair-error">{authError}</code> : null}
      <p className="current-muted">Credential 只保存在当前页面内存，不写入 localStorage、日志或 Artifact；“退回”只记录 exact decision，不自动启动返修或改写 T06 queue；生产 OIDC/SSO 仍属于 S5。</p>
    </section>
  );
}

function ReviewLeadGroup({ title, rows }: { title: string; rows: Array<Record<string, unknown>> }) {
  return <div><b>{title} · {rows.length}</b>{rows.map((row, index) => <p key={`${title}-${index}`}>{String(row.statement ?? row.terminal_state_summary ?? "—")}</p>)}</div>;
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
