import {
  AlertTriangle,
  ArrowLeft,
  BookOpenCheck,
  Building2,
  CheckCircle2,
  Database,
  ExternalLink,
  FileSearch,
  Fingerprint,
  LoaderCircle,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  EvidenceItem,
  ResearchCaseDetail,
  ResearchCaseList,
  ResearchCaseSummary,
  ResearchEvidenceView,
  ResearchRetrievalView,
  S1CanonicalSpineView,
  S1ProductReadinessView,
  ResearchWorkspaceApiClient,
} from "../api/researchWorkspace";
import "./research-workspace.css";

type WorkspaceRoute =
  | { kind: "cases" }
  | { kind: "case"; caseId: string; surface: "overview" | "evidence" | "retrieval" };

type LoadState<T> =
  | { kind: "loading" }
  | { kind: "ready"; value: T }
  | { kind: "error"; message: string };

const api = new ResearchWorkspaceApiClient();

export function isResearchWorkspacePath(pathname: string): boolean {
  return pathname === "/workspace" || pathname.startsWith("/workspace/");
}

export function ResearchWorkspace() {
  const [route, setRoute] = useState<WorkspaceRoute>(() => decodeRoute(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setRoute(decodeRoute(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (next: WorkspaceRoute) => {
    window.history.pushState({}, "", pathForRoute(next));
    setRoute(next);
  };

  return (
    <div className="research-workspace">
      <header className="research-workspace__topbar">
        <button className="research-workspace__brand" type="button" onClick={() => navigate({ kind: "cases" })}>
          <span>F</span>
          <div>
            <strong>FinSight Research</strong>
            <small>FIN 0.1.3 · reviewed evidence workspace</small>
          </div>
        </button>
        <div className="research-workspace__topbar-actions">
          <span className="research-workspace__online is-online">
            <i />只读审证模式
          </span>
          <a href="/operations">运行与运维 <ExternalLink size={14} /></a>
        </div>
      </header>

      {route.kind === "cases" ? (
        <ResearchCaseIndex onOpen={(caseId) => navigate({ kind: "case", caseId, surface: "overview" })} />
      ) : (
        <ResearchCaseWorkspace
          route={route}
          onBack={() => navigate({ kind: "cases" })}
          onSurface={(surface) => navigate({ ...route, surface })}
        />
      )}
    </div>
  );
}

function ResearchCaseIndex({ onOpen }: { onOpen: (caseId: string) => void }) {
  const [state, setState] = useState<LoadState<ResearchCaseList>>({ kind: "loading" });
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    api.listCases(controller.signal)
      .then((value) => setState({ kind: "ready", value }))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setState({ kind: "error", message: error.message });
      });
    return () => controller.abort();
  }, [refreshKey]);

  return (
    <main className="research-workspace__page">
      <section className="research-workspace__hero">
        <div>
          <p className="research-workspace__eyebrow">PRIMARY PRODUCT SURFACE</p>
          <h1>当前研究案例</h1>
          <p>这里仅展示已绑定公司身份、研究截至日和不可变 Evidence Pack 的真实案例。</p>
        </div>
        <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>
          <RefreshCcw size={16} /> 刷新
        </button>
      </section>

      {state.kind === "loading" ? <Loading label="正在核验案例与 Evidence Pack 绑定…" /> : null}
      {state.kind === "error" ? <Failure message={state.message} /> : null}
      {state.kind === "ready" ? (
        <>
          <div className="research-workspace__assurance">
            <ShieldCheck size={19} />
            <span>{state.value.items.length} 个案例已通过身份与摘要绑定；{state.value.evidence_objects_ready ? "证据对象已挂载" : `仍需挂载 ${state.value.unavailable_case_keys.join("、")} 证据对象`}。</span>
            <code>{shortDigest(state.value.evidence_pack_result_digest)}</code>
          </div>
          <section className="research-workspace__case-grid">
            {state.value.items.map((item) => <CaseCard key={item.case_id} item={item} onOpen={onOpen} />)}
          </section>
          <Boundary text={state.value.known_boundary} />
        </>
      ) : null}
    </main>
  );
}

function CaseCard({ item, onOpen }: { item: ResearchCaseSummary; onOpen: (caseId: string) => void }) {
  return (
    <button className="research-workspace__case-card" type="button" disabled={!item.evidence_object_ready} onClick={() => onOpen(item.case_id)}>
      <div className="research-workspace__case-heading">
        <span className="research-workspace__ticker">{item.case_key}</span>
        <CheckCircle2 size={18} />
      </div>
      <h2>{item.subject.legal_name}</h2>
      <p>{item.subject.exchange} · CIK {item.subject.issuer_id} · 截至 {item.research_as_of}</p>
      <div className="research-workspace__metrics">
        <Metric value={item.evidence_summary.accepted_evidence_items} label="已审证据" />
        <Metric value={item.evidence_summary.source_materials} label="来源材料" />
        <Metric value={item.evidence_summary.residual_gaps} label="剩余缺口" warn />
      </div>
      <footer>
        <span><Fingerprint size={14} /> {shortDigest(item.pack_binding.binding_digest)}</span>
        <b>{item.evidence_object_ready ? "打开研究案例 →" : "证据对象未挂载"}</b>
      </footer>
    </button>
  );
}

function ResearchCaseWorkspace({
  route,
  onBack,
  onSurface,
}: {
  route: Extract<WorkspaceRoute, { kind: "case" }>;
  onBack: () => void;
  onSurface: (surface: "overview" | "evidence" | "retrieval") => void;
}) {
  const [state, setState] = useState<LoadState<{ detail: ResearchCaseDetail; evidence: ResearchEvidenceView; retrieval: ResearchRetrievalView }>>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    Promise.all([
      api.getCase(route.caseId, controller.signal),
      api.getEvidence(route.caseId, controller.signal),
      api.getRetrieval(route.caseId.replace(/^case_/, "").replace(/_current$/, "").toUpperCase(), controller.signal),
    ])
      .then(([detail, evidence, retrieval]) => setState({ kind: "ready", value: { detail, evidence, retrieval } }))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setState({ kind: "error", message: error.message });
      });
    return () => controller.abort();
  }, [route.caseId]);

  if (state.kind === "loading") return <main className="research-workspace__page"><Loading label="正在核验案例身份、内容摘要与来源…" /></main>;
  if (state.kind === "error") return <main className="research-workspace__page"><Failure message={state.message} /></main>;

  const { detail, evidence, retrieval } = state.value;
  return (
    <main className="research-workspace__page">
      <button className="research-workspace__back" type="button" onClick={onBack}><ArrowLeft size={16} /> 返回案例列表</button>
      <section className="research-workspace__case-title">
        <div>
          <p className="research-workspace__eyebrow">{detail.case_key} · IDENTITY BOUND</p>
          <h1>{detail.subject.legal_name}</h1>
          <p>{detail.research_context.research_question}</p>
        </div>
        <div className="research-workspace__identity-badge">
          <Building2 size={19} />
          <div><strong>{detail.subject.exchange}:{detail.subject.ticker}</strong><small>CIK {detail.subject.issuer_id}</small></div>
        </div>
      </section>

      <nav className="research-workspace__tabs" aria-label="研究案例页面">
        <button className={route.surface === "overview" ? "is-active" : ""} type="button" onClick={() => onSurface("overview")}>
          <BookOpenCheck size={16} /> 研究概览
        </button>
        <button className={route.surface === "evidence" ? "is-active" : ""} type="button" onClick={() => onSurface("evidence")}>
          <FileSearch size={16} /> 证据与缺口
        </button>
        <button className={route.surface === "retrieval" ? "is-active" : ""} type="button" onClick={() => onSurface("retrieval")}>
          <Database size={16} /> 检索候选
        </button>
      </nav>

      {route.surface === "overview" ? <CaseOverview detail={detail} evidence={evidence} /> : null}
      {route.surface === "evidence" ? <EvidenceSurface evidence={evidence} /> : null}
      {route.surface === "retrieval" ? <RetrievalSurface retrieval={retrieval} /> : null}
      <Boundary text={detail.known_boundary} />
    </main>
  );
}

function RetrievalSurface({ retrieval }: { retrieval: ResearchRetrievalView }) {
  const missing = Object.entries(retrieval.summary.slots_missing_required_source_roles);
  return (
    <>
      <CanonicalSpinePanel spine={retrieval.canonical_spine ?? null} />
      <section className="research-workspace__overview-grid">
        <article className="research-workspace__panel">
          <h2>当前候选检索</h2>
          <div className="research-workspace__metrics is-large">
            <Metric value={retrieval.summary.slot_count} label="Evidence Slots" />
            <Metric value={retrieval.summary.nonempty_lane_count} label="有结果 Facets" />
            <Metric value={retrieval.summary.unique_candidates} label="候选对象" />
          </div>
          <p>这些是待审候选，不是 Evidence。系统已先按披露主体、关系角色和截至日过滤，再执行本地词法检索。</p>
        </article>
        <article className="research-workspace__panel">
          <h2>语料与真实缺口</h2>
          <p>{retrieval.source_gap_summary.interpretation_zh}</p>
          <div className="research-workspace__retrieval-gap-metrics">
            <span>当前对象缺失 <b>{retrieval.source_gap_summary.reviewed_label_occurrences_missing_from_current_corpus}</b></span>
            <span>排名前可用 <b>{retrieval.source_gap_summary.reviewed_label_occurrences_eligible_before_scoring}</b></span>
            <span>当前召回 <b>{retrieval.source_gap_summary.reviewed_label_occurrences_matched_after_scoring}</b></span>
          </div>
          {missing.map(([facet, roles]) => <div className="research-workspace__missing-role" key={facet}><strong>{facet}</strong><span>缺 {roles.join("、")}</span></div>)}
        </article>
      </section>
      {retrieval.ranking_comparison ? <RankingComparisonPanel comparison={retrieval.ranking_comparison} /> : null}
      <section className="research-workspace__panel">
        <div className="research-workspace__section-title"><h2>查询 Facets 与候选</h2><span>{retrieval.summary.lane_count} 条独立查询 lane</span></div>
        <div className="research-workspace__retrieval-lanes">
          {retrieval.lanes.map((lane) => (
            <article className="research-workspace__retrieval-lane" key={lane.lane_id}>
              <header><div><span>{lane.slot_id}</span><h3>{lane.business_question_zh}</h3></div><code>{lane.facet_id}</code></header>
              <p className="research-workspace__retrieval-scope">披露主体：{lane.evidence_owner_tickers.join(" / ")} · 截至 {lane.publication_date_lte}</p>
              <div className="research-workspace__candidate-list">
                {lane.candidates.slice(0, 3).map((candidate) => (
                  <div className="research-workspace__candidate" key={candidate.source_record_id}>
                    <div><strong>{candidate.evidence_owner_ticker} · {candidate.subsection || candidate.source_type}</strong><span>{candidate.publication_date} · {candidate.source_role}</span></div>
                    <p>{candidate.excerpt}</p>
                    <small>{candidate.business_boundary_zh}</small>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
      <Boundary text={retrieval.known_boundary} />
    </>
  );
}

const rankingRouteLabels: Record<string, string> = {
  sparse_bm25: "BM25 关键词",
  dense_bge_m3: "BGE-M3 语义",
  fusion_rrf_1_1: "1:1 RRF 融合",
  typed_financial_rerank: "金融角色重排",
};

const decisionStateLabels: Record<S1CanonicalSpineView["decision_rows"][number]["decision_state"], string> = {
  accepted: "已接受",
  rejected: "已拒绝",
  unjudged: "未裁决",
  needs_review: "待复核",
};

const decisionReasonLabels: Record<string, string> = {
  exact_reviewed_pack_lineage_match: "与已审 Pack 谱系完全一致",
  case_owner_source_period_slot_gate_passed: "公司、来源、期间与槽位校验通过",
  candidate_not_present_in_reviewed_pack: "尚未进入已审 Pack",
};

const productReadinessLabels: Record<string, string> = {
  ready_for_current_scope: "当前范围可用",
  partial_with_material_gaps: "材料仍有缺口",
  blocked_by_candidate_coverage: "候选覆盖不足",
  blocked_by_evidence_admission: "候选待证据准入",
  blocked_by_local_data_materialization: "本地解析或对象化阻断",
  blocked_by_numeric_or_bridge_authority: "等待 S2 数值或桥接",
  blocked_by_retrieval_quality: "检索或排序质量阻断",
  blocked_by_source_access: "官方来源访问阻断",
  candidate_audit_only_explicit_scope_pending: "等待 S3 明确研究范围",
};

const candidateReviewIssueLabels: Record<string, string> = {
  existing_reviewed_evidence_reuse: "已与现有审定 Evidence 精确绑定",
  new_candidate_evidence_adjudication: "新候选尚待 Evidence Gate 审定",
  reviewed_pack_exact_object_binding: "来源已审，但当前对象尚未精确绑定",
  reviewed_pack_slot_facet_binding: "对象与当前命题槽位绑定待确认",
  reviewed_pack_hard_boundary_mismatch: "公司、期间或来源硬边界不一致",
  request_material_binding: "候选与当前研究命题的材料绑定待确认",
  manual_candidate_review_required: "需要人工判断候选能证明什么",
};

function RankingComparisonPanel({ comparison }: { comparison: NonNullable<ResearchRetrievalView["ranking_comparison"]> }) {
  return (
    <section className="research-workspace__panel">
      <div className="research-workspace__section-title">
        <h2>同对象排名对照</h2>
        <span>{comparison.same_object_population_count.toLocaleString("zh-CN")} 个冻结 child · 候选仍不是 Evidence</span>
      </div>
      <div className="research-workspace__ranking-routes">
        {Object.entries(comparison.route_summaries).map(([routeId, summary]) => (
          <article key={routeId}>
            <strong>{rankingRouteLabels[routeId] ?? routeId}</strong>
            <b>{Math.round(summary.recall_at_10_mapped_targets * 100)}%</b>
            <span>映射目标进入前 10 · MRR {summary.mrr_mapped_targets.toFixed(3)}</span>
            <small>{summary.mapped_current_target_count} 条可映射，{summary.typed_target_gap_count} 条目标缺口</small>
          </article>
        ))}
      </div>
      <p className="research-workspace__ranking-note">这组数字只比较同一批对象如何排序；不代表候选内容已通过证据门，也不会把评测答案暴露给产品候选。</p>
      <div className="research-workspace__ranking-queries">
        {comparison.queries.slice(0, 3).map((query) => (
          <article key={query.query_id}>
            <header><strong>{query.evidence_owner_ticker}</strong><span>{query.evidence_slot_id}</span></header>
            <div>
              {Object.entries(query.routes).map(([routeId, route]) => {
                const candidate = route.candidates[0];
                return (
                  <section key={routeId}>
                    <small>{rankingRouteLabels[routeId] ?? routeId}</small>
                    {candidate ? <><b>{candidate.subsection || candidate.section || candidate.source_type}</b><p>{candidate.excerpt}</p></> : <p>无候选</p>}
                  </section>
                );
              })}
            </div>
          </article>
        ))}
      </div>
      <Boundary text={comparison.known_boundary} />
    </section>
  );
}

function CaseOverview({ detail, evidence }: { detail: ResearchCaseDetail; evidence: ResearchEvidenceView }) {
  const slotCoverage = useMemo(() => {
    const slots = new Set<string>();
    evidence.evidence_items.forEach((item) => item.slot_bindings?.forEach((slot) => slots.add(slot.slot_id)));
    return slots.size;
  }, [evidence]);
  return (
    <>
      <section className="research-workspace__overview-grid">
        <article className="research-workspace__panel">
          <h2>当前证据基础</h2>
          <div className="research-workspace__metrics is-large">
            <Metric value={evidence.evidence_items.length} label="已审证据" />
            <Metric value={slotCoverage} label="Evidence Slots" />
            <Metric value={evidence.residual_gaps.length} label="明确缺口" warn />
          </div>
          <p>截至 {detail.research_as_of}。下列内容是可追溯的研究输入，不等同于完整投资结论。</p>
        </article>
        <article className="research-workspace__panel">
          <h2>不可变绑定</h2>
          <DigestRow label="Case subject" value={detail.subject_digest} />
          <DigestRow label="Evidence artifact" value={detail.pack_binding.pack_artifact_digest} />
          <DigestRow label="Pack payload" value={detail.pack_binding.pack_payload_digest} />
          <DigestRow label="Binding" value={detail.pack_binding.binding_digest} />
        </article>
      </section>
      <section className="research-workspace__panel">
        <div className="research-workspace__section-title"><h2>代表性证据</h2><span>前 5 条 · 按已审 Pack 顺序</span></div>
        <div className="research-workspace__evidence-list">
          {evidence.evidence_items.slice(0, 5).map((item) => <EvidenceCard key={item.evidence_item_digest} item={item} compact />)}
        </div>
      </section>
      <section className="research-workspace__panel">
        <div className="research-workspace__section-title"><h2>最先需要补足的缺口</h2><span>{evidence.residual_gaps.length} 条保留在产品面</span></div>
        <GapList gaps={evidence.residual_gaps.slice(0, 6)} />
      </section>
    </>
  );
}

function EvidenceSurface({ evidence }: { evidence: ResearchEvidenceView }) {
  return (
    <>
      <ProductReadinessPanel readiness={evidence.product_readiness ?? null} />
      <CanonicalSpinePanel spine={evidence.canonical_spine ?? null} />
      <section className="research-workspace__evidence-columns">
        <div className="research-workspace__panel">
          <div className="research-workspace__section-title"><h2>已审 Evidence</h2><span>{evidence.evidence_items.length} 条</span></div>
          <div className="research-workspace__evidence-list">
            {evidence.evidence_items.map((item) => <EvidenceCard key={item.evidence_item_digest} item={item} />)}
          </div>
        </div>
        <aside className="research-workspace__panel research-workspace__gap-panel">
          <div className="research-workspace__section-title"><h2>Residual Gaps</h2><span>{evidence.residual_gaps.length} 条</span></div>
          <GapList gaps={evidence.residual_gaps} />
        </aside>
      </section>
    </>
  );
}

function ProductReadinessPanel({ readiness }: { readiness: S1ProductReadinessView | null }) {
  if (!readiness) return null;
  const readyCount = readiness.request_state_counts.ready_for_current_scope ?? 0;
  const coverageBlocked = readiness.request_state_counts.blocked_by_candidate_coverage ?? 0;
  const admissionBlocked = readiness.request_state_counts.blocked_by_evidence_admission ?? 0;
  return (
    <section className="research-workspace__panel research-workspace__product-readiness">
      <div className="research-workspace__section-title">
        <h2>当前 S1 产品就绪诊断</h2>
        <span>{productReadinessLabels[readiness.readiness_state] ?? readiness.readiness_state}</span>
      </div>
      <div className="research-workspace__metrics is-large">
        <Metric value={readyCount} label="当前范围可用" />
        <Metric value={coverageBlocked} label="候选覆盖阻断" warn />
        <Metric value={admissionBlocked} label="待 Evidence 准入" warn />
        <Metric value={readiness.candidate_review_packet_summary.human_review_required_count} label="对象级待复核" warn />
      </div>
      <p className="research-workspace__product-readiness-note">
        这里把“本地没找到候选”“候选已找到但尚未成为 Evidence”“等待 S2 数值”和“等待 S3 明确研究范围”分开显示。下方原文只来自摘要绑定的内部审阅包；不会暴露原始捕获或本地路径，也不会因展示而自动成为 Evidence。
      </p>
      <div className="research-workspace__product-readiness-grid">
        {readiness.requests.map((request) => (
          <article key={request.request_id} className={`is-${request.readiness_state}`}>
            <header>
              <strong>{request.business_question_zh}</strong>
              <span>{productReadinessLabels[request.readiness_state] ?? request.readiness_state}</span>
            </header>
            <p>{request.slot_id} / {request.facet_id}</p>
            <div>
              <small>命题 {request.requirement_count} · 覆盖阻断 {request.requirement_state_counts.blocked_by_candidate_coverage ?? 0} · 待准入 {request.requirement_state_counts.blocked_by_evidence_admission ?? 0}</small>
              <small>候选：接受 {request.candidate_decision_counts.accepted} · 待复核 {request.candidate_decision_counts.needs_human_review} · 拒绝 {request.candidate_decision_counts.rejected}</small>
              <small>数值口径：{request.numeric_authority_state.state}（{request.numeric_authority_state.resolved_count}/{request.numeric_authority_state.request_count} 已解析）</small>
              {request.unexecuted_or_unavailable_routes.length ? <small>尚未执行路线：{request.unexecuted_or_unavailable_routes.join("、")}</small> : null}
            </div>
            {request.candidate_review_items.length ? (
              <details className="research-workspace__candidate-review">
                <summary>查看 {request.candidate_review_items.length} 条对象级候选</summary>
                <div>
                  {request.candidate_review_items.map((item) => (
                    <section key={item.review_item_ref} className="research-workspace__candidate-review-card">
                      <header>
                        <strong>{item.source.source_type} · {item.source.publication_date}</strong>
                        <span>{item.human_review_required ? "待人工准入" : "已审证据复用"}</span>
                      </header>
                      <p>{item.source.bounded_excerpt}</p>
                      <small>证据角色：{item.advisory_evidence_role.labels.join("、") || "尚未分类"}</small>
                      <small>当前问题：{item.issue_classes.map((issue) => candidateReviewIssueLabels[issue] ?? issue).join("；")}</small>
                      <footer>
                        <code title={item.source_lineage_digest}>{shortDigest(item.source_lineage_digest)}</code>
                        {item.source.source_url ? <a href={item.source.source_url} target="_blank" rel="noreferrer">官方来源 <ExternalLink size={11} /></a> : null}
                      </footer>
                    </section>
                  ))}
                </div>
              </details>
            ) : null}
          </article>
        ))}
      </div>
      <div className="research-workspace__canonical-bindings">
        <DigestRow label="Readiness result" value={readiness.result_digest} />
        <DigestRow label="Review packet" value={readiness.candidate_review_packet_summary.review_packet_digest} />
        <DigestRow label="Prepared commit" value={readiness.prepared_from_commit} />
      </div>
    </section>
  );
}

function CanonicalSpinePanel({ spine }: { spine: S1CanonicalSpineView | null }) {
  if (!spine) return null;
  return (
    <section className="research-workspace__panel research-workspace__canonical-spine">
      <div className="research-workspace__section-title">
        <h2>S1 命题级证据账本</h2>
        <span>可用于有边界研究，尚不足以形成完整结论</span>
      </div>
      <div className="research-workspace__metrics is-large">
        <Metric value={spine.coverage_summary.current_exact_reviewed_evidence_count ?? spine.coverage_summary.accepted_evidence_count} label="当前精确绑定 Evidence" />
        <Metric value={spine.candidate_decision_summary.needs_review} label="候选待复核" warn />
        <Metric value={spine.coverage_summary.reviewed_not_recalled_count ?? "未复证"} label="既有证据未召回" warn />
        <Metric value={spine.coverage_summary.unresolved_gap_count} label="尚未补证缺口" warn />
      </div>
      <p className="research-workspace__canonical-note">
        当前 {spine.coverage_summary.unresolved_gap_count} 个缺口尚未完成官方或外源补证，因此不能宣称“公开资料不存在”；本轮可认定的公开信息真空为 {spine.coverage_summary.true_public_information_gap_count}。
      </p>
      <div className="research-workspace__decision-ledger">
        {spine.decision_rows.map((row) => (
          <article key={row.decision_digest} className={`is-${row.decision_state}`}>
            <header><strong>#{row.rank} · {row.source_type}</strong><span>{decisionStateLabels[row.decision_state]}</span></header>
            <p>{row.source_record_id}</p>
            <small>{row.reason_codes.map((code) => decisionReasonLabels[code] ?? code).join(" · ")}</small>
          </article>
        ))}
      </div>
      <div className="research-workspace__canonical-bindings">
        <DigestRow label="Evidence artifact" value={spine.pack_binding.artifact_digest} />
        <DigestRow label="Pack payload" value={spine.pack_binding.pack_payload_digest} />
        <DigestRow label="Workbench projection" value={spine.workbench_projection_digest} />
      </div>
    </section>
  );
}

function EvidenceCard({ item, compact = false }: { item: EvidenceItem; compact?: boolean }) {
  const primarySlot = item.slot_bindings?.[0];
  return (
    <article className="research-workspace__evidence-card">
      <header>
        <span>{item.evidence_role ?? item.disposition}</span>
        <time>{item.publication_date ?? "日期未披露"}</time>
      </header>
      <h3>{primarySlot?.business_meaning_zh ?? primarySlot?.slot_id ?? item.target_id}</h3>
      <p className={compact ? "is-clamped" : ""}>{item.source.reviewed_source_excerpt}</p>
      {primarySlot?.claim_boundary_zh ? <div className="research-workspace__claim-boundary">边界：{primarySlot.claim_boundary_zh}</div> : null}
      <footer>
        <span>{item.source.source_tier} · {item.source.source_type}</span>
        <a href={item.source.source_url} target="_blank" rel="noreferrer">查看来源 <ExternalLink size={12} /></a>
      </footer>
    </article>
  );
}

function GapList({ gaps }: { gaps: ResearchEvidenceView["residual_gaps"] }) {
  return (
    <div className="research-workspace__gap-list">
      {gaps.map((gap) => (
        <article key={gap.gap_id}>
          <AlertTriangle size={15} />
          <div>
            <strong>{gap.business_reason_zh ?? gap.gap_code}</strong>
            {gap.supplement_direction_zh ? <p>{gap.supplement_direction_zh}</p> : null}
            <small>{[gap.slot_id, gap.facet_id].filter(Boolean).join(" / ")}</small>
          </div>
        </article>
      ))}
    </div>
  );
}

function Metric({ value, label, warn = false }: { value: number | string; label: string; warn?: boolean }) {
  return <div className={warn ? "research-workspace__metric is-warn" : "research-workspace__metric"}><strong>{value}</strong><span>{label}</span></div>;
}

function DigestRow({ label, value }: { label: string; value: string }) {
  return <div className="research-workspace__digest-row"><span>{label}</span><code title={value}>{shortDigest(value)}</code></div>;
}

function Boundary({ text }: { text: string }) {
  return <div className="research-workspace__boundary"><Database size={17} /><div><strong>当前产品边界</strong><p>{text}</p></div></div>;
}

function Loading({ label }: { label: string }) {
  return <div className="research-workspace__state"><LoaderCircle className="is-spinning" size={24} /><p>{label}</p></div>;
}

function Failure({ message }: { message: string }) {
  return <div className="research-workspace__state is-error"><AlertTriangle size={24} /><strong>研究工作区未能通过绑定校验</strong><p>{message}</p></div>;
}

function shortDigest(value: string): string {
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value;
}

function decodeRoute(pathname: string): WorkspaceRoute {
  const match = /^\/workspace\/cases\/([^/]+)(?:\/(overview|evidence|retrieval))?\/?$/.exec(pathname);
  if (!match) return { kind: "cases" };
  return {
    kind: "case",
    caseId: decodeURIComponent(match[1]),
    surface: match[2] === "evidence" || match[2] === "retrieval" ? match[2] : "overview",
  };
}

function pathForRoute(route: WorkspaceRoute): string {
  if (route.kind === "cases") return "/workspace";
  return `/workspace/cases/${encodeURIComponent(route.caseId)}/${route.surface}`;
}
