import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Ban,
  CalendarDays,
  Calculator,
  ChevronRight,
  CirclePlay,
  FileSearch,
  Filter,
  Link2,
  RefreshCcw,
  RotateCcw,
  Send,
  ShieldCheck,
  Wrench,
  X,
} from "lucide-react";

import { CaseApiClient, CaseApiError, CaseWorkspaceProjection } from "../../api/cases";
import {
  CompileEvidenceFixtureCommand,
  EvidenceApiClient,
  EvidenceApiError,
  EvidenceCandidateState,
  EvidenceCandidateView,
  EvidenceCellSectionView,
  EvidenceRepairOutcomeView,
  EvidenceWorkbenchView,
  ExecuteEvidenceRepairCommand,
  LocalResearchPreviewView,
  RejectEvidenceCandidateCommand,
  RequestEvidenceRepairCommand,
} from "../../api/evidence";
import { ExecutionApiClient, ExecutionApiError, WorkUnitExecutionView } from "../../api/execution";
import { DecisionSurfaceView, PlanningApiClient, PlanningApiError } from "../../api/planning";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { RemoteStatus } from "../../shared/RemoteStatus";

type EvidenceWorkbenchProps = {
  caseId: string;
  online: boolean;
  onBack: () => void;
  onOpenActivity: () => void;
  onOpenNumeric: () => void;
};

type Prerequisites = {
  workspace: CaseWorkspaceProjection;
  surface: DecisionSurfaceView;
  execution: WorkUnitExecutionView;
};

type Projection = Prerequisites & { evidence: EvidenceWorkbenchView };
type FailureKind = "permission" | "conflict" | "stale" | "error";
type RemoteState =
  | { kind: "loading" }
  | { kind: "ready"; data: Projection }
  | { kind: "empty"; prerequisites: Prerequisites }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type MutationState =
  | { kind: "idle" }
  | { kind: "loading"; target: string }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type LocalPreviewState =
  | { kind: "loading" }
  | { kind: "ready"; data: LocalResearchPreviewView }
  | { kind: "unavailable" };
type StatusFilter = "all" | "candidate" | "context_only" | "rejected" | "gap";
type IdempotencyRecord = { fingerprint: string; key: string };
type Copy = (zhCN: string, en: string) => string;
type ReviewDraft =
  | { kind: "reject"; candidate: EvidenceCandidateView }
  | { kind: "repair"; evidenceSlotId: string; label: string };

const caseApi = new CaseApiClient();
const planningApi = new PlanningApiClient();
const executionApi = new ExecutionApiClient();
const evidenceApi = new EvidenceApiClient();

export function EvidenceWorkbench({ caseId, online, onBack, onOpenActivity, onOpenNumeric }: EvidenceWorkbenchProps) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const [remote, setRemote] = useState<RemoteState>({ kind: "loading" });
  const [localPreview, setLocalPreview] = useState<LocalPreviewState>({ kind: "loading" });
  const [mutation, setMutation] = useState<MutationState>({ kind: "idle" });
  const [cellFilter, setCellFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [reviewDraft, setReviewDraft] = useState<ReviewDraft | null>(null);
  const [reason, setReason] = useState("");
  const prepareAttemptRef = useRef<IdempotencyRecord | null>(null);
  const reviewAttemptRef = useRef(new Map<string, IdempotencyRecord>());
  const repairAttemptRef = useRef(new Map<string, IdempotencyRecord>());

  const load = useCallback(async () => {
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: copy("连接不可用。恢复连接后可重新打开证据台账。", "Connection is unavailable. Reconnect to restore the Evidence Ledger.") });
      return;
    }
    setRemote({ kind: "loading" });
    setLocalPreview({ kind: "loading" });
    setMutation({ kind: "idle" });
    setReviewDraft(null);
    try {
      const [workspace, surface, execution, preview] = await Promise.all([
        caseApi.getCase(caseId),
        planningApi.getDecisionSurface(caseId),
        executionApi.listWorkUnits(caseId),
        evidenceApi.getLocalResearchPreview(caseId).catch(() => null),
      ]);
      setLocalPreview(preview ? { kind: "ready", data: preview } : { kind: "unavailable" });
      const prerequisites = { workspace, surface, execution };
      try {
        const evidence = await evidenceApi.getEvidenceWorkbench(caseId);
        if (evidence.status === "not_prepared") {
          setRemote({ kind: "empty", prerequisites });
        } else {
          setRemote({ kind: "ready", data: { ...prerequisites, evidence } });
        }
      } catch (error) {
        if (isEvidenceMissing(error)) setRemote({ kind: "empty", prerequisites });
        else throw error;
      }
    } catch (error) {
      setRemote(remoteFailure(error, copy));
    }
  }, [caseId, copy, online]);

  useEffect(() => {
    void load();
  }, [load]);

  const projection = remote.kind === "ready" ? remote.data : null;
  const evidence = projection?.evidence ?? null;
  const filteredCells = useMemo(
    () => evidence ? evidence.cells
      .filter((cell) => cellFilter === "all" || cell.cell_id === cellFilter)
      .map((cell) => ({ ...cell, candidates: cell.candidates.filter((candidate) => matchesStatus(candidate.state, statusFilter)) }))
      .filter((cell) => cell.candidates.length > 0 || statusFilter === "all" && Boolean(cell.typed_gap) || statusFilter === "gap" && Boolean(cell.typed_gap))
      : [],
    [cellFilter, evidence, statusFilter],
  );
  const visibleCandidates = useMemo(() => filteredCells.flatMap((cell) => cell.candidates), [filteredCells]);

  useEffect(() => {
    if (visibleCandidates.some((candidate) => candidate.candidate_id === selectedCandidateId)) return;
    setSelectedCandidateId(visibleCandidates[0]?.candidate_id ?? null);
  }, [selectedCandidateId, visibleCandidates]);

  const selectedCandidate = evidence?.cells
    .flatMap((cell) => cell.candidates)
    .find((candidate) => candidate.candidate_id === selectedCandidateId) ?? null;

  async function prepareFixture() {
    const prerequisites = remote.kind === "empty" ? remote.prerequisites : projection;
    if (!prerequisites) return;
    const admission = preparationAdmission(prerequisites, copy);
    if (!admission.workUnit) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请恢复连接后准备证据样例。", "Connection is unavailable. Reconnect before preparing the evidence fixture.") });
      return;
    }
    const fingerprint = [
      prerequisites.workspace.case_version,
      prerequisites.surface.contract_version,
      prerequisites.surface.checkpoint_version,
      admission.workUnit.work_unit_version,
    ].join(":");
    const command: CompileEvidenceFixtureCommand = {
      expected_workspace_version: 0,
      actor_ref: evidenceApi.actorRef,
      idempotency_key: keyForAttempt(prepareAttemptRef, fingerprint),
    };
    setMutation({ kind: "loading", target: "prepare" });
    try {
      const compiled = await evidenceApi.compileEvidenceFixture(caseId, command);
      prepareAttemptRef.current = null;
      setMutation({ kind: "idle" });
      setRemote({ kind: "ready", data: { ...prerequisites, evidence: compiled } });
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  function beginReview(draft: ReviewDraft) {
    setReviewDraft(draft);
    setReason("");
  }

  async function submitReview(event: FormEvent) {
    event.preventDefault();
    if (!projection || !reviewDraft || !reason.trim()) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请恢复连接后提交处理说明。", "Connection is unavailable. Reconnect before submitting the review.") });
      return;
    }
    const target = reviewDraft.kind === "reject" ? reviewDraft.candidate.candidate_id : reviewDraft.evidenceSlotId;
    const fingerprint = `${reviewDraft.kind}:${target}:${projection.evidence.workspace_version}:${reason.trim()}`;
    const idempotencyKey = mapIdempotencyKey(reviewAttemptRef.current, target, fingerprint);
    setMutation({ kind: "loading", target });
    try {
      let updated: EvidenceWorkbenchView;
      if (reviewDraft.kind === "reject") {
        const command: RejectEvidenceCandidateCommand = {
          expected_workspace_version: projection.evidence.workspace_version,
          reason: reason.trim(),
          actor_ref: evidenceApi.actorRef,
          idempotency_key: idempotencyKey,
        };
        updated = await evidenceApi.rejectEvidenceCandidate(caseId, reviewDraft.candidate.candidate_id, command);
      } else {
        const command: RequestEvidenceRepairCommand = {
          expected_workspace_version: projection.evidence.workspace_version,
          reason: reason.trim(),
          actor_ref: evidenceApi.actorRef,
          idempotency_key: idempotencyKey,
        };
        updated = await evidenceApi.requestEvidenceRepair(caseId, reviewDraft.evidenceSlotId, command);
      }
      reviewAttemptRef.current.delete(target);
      setMutation({ kind: "idle" });
      setReviewDraft(null);
      setReason("");
      setRemote({ kind: "ready", data: { ...projection, evidence: updated } });
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  async function executeRepair(evidenceSlotId: string) {
    if (!projection) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请恢复连接后运行受限来源补充。", "Connection is unavailable. Reconnect before running the bounded source repair.") });
      return;
    }
    const fingerprint = `execute-repair:${evidenceSlotId}:${projection.evidence.workspace_version}`;
    const command: ExecuteEvidenceRepairCommand = {
      expected_workspace_version: projection.evidence.workspace_version,
      actor_ref: evidenceApi.actorRef,
      idempotency_key: mapIdempotencyKey(repairAttemptRef.current, evidenceSlotId, fingerprint),
    };
    setMutation({ kind: "loading", target: `repair:${evidenceSlotId}` });
    try {
      const updated = await evidenceApi.executeEvidenceRepair(caseId, evidenceSlotId, command);
      repairAttemptRef.current.delete(evidenceSlotId);
      setMutation({ kind: "idle" });
      setRemote({ kind: "ready", data: { ...projection, evidence: updated } });
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  const emptyPrerequisites = remote.kind === "empty" ? remote.prerequisites : null;
  const admission = emptyPrerequisites ? preparationAdmission(emptyPrerequisites, copy) : null;

  return (
    <section className="p02-workspace p03-evidence-workbench" aria-label={copy("证据台账", "Evidence Ledger")}>
      <button type="button" className="p02-back-button" onClick={onBack}>
        <ArrowLeft size={16} aria-hidden="true" />
        {copy("研究概览", "Case overview")}
      </button>

      <div className="p02-page-heading p03-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("证据台账", "Evidence Ledger")}</p>
          <h1>{localPreview.kind === "ready" ? localizeFixtureText(localPreview.data.query) : copy("正在读取研究问题", "Loading research question")}</h1>
          <p className="p02-heading-meta">
            {caseId}
            {evidence && projection ? copy(` · 台账版本 v${evidence.workspace_version} / 案例版本 v${projection.workspace.case_version}`, ` · Ledger v${evidence.workspace_version} / Case v${projection.workspace.case_version}`) : ""}
          </p>
        </div>
        <div className="p02-page-actions">
          {evidence && evidence.summary.repair_completed_count > 0 ? (
            <button type="button" className="p02-primary-button" onClick={onOpenNumeric}>
              <Calculator size={16} aria-hidden="true" />
              {copy("打开数值分析", "Open numeric analysis")}
            </button>
          ) : null}
          <button type="button" className="p02-secondary-button" onClick={onOpenActivity}>
            <FileSearch size={16} aria-hidden="true" />
            {copy("研究进度", "Research progress")}
          </button>
          <button type="button" className="p02-icon-button" title={copy("刷新证据台账", "Refresh evidence ledger")} aria-label={copy("刷新证据台账", "Refresh evidence ledger")} onClick={() => void load()}>
            <RefreshCcw size={17} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="p03-boundary-banner">
        <ShieldCheck size={18} aria-hidden="true" />
        <div><strong>{copy("仅供候选证据研判", "Candidate evidence review only")}</strong><span>{copy("此页面仅展示元数据候选项与来源缺口；不会将任何内容提升为正式证据或已确认事实。", "This page shows metadata candidates and source gaps only; nothing is promoted to formal evidence or a confirmed fact.")}</span></div>
      </div>

      <LocalResearchPreview state={localPreview} />

      {remote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载研究案例、研究判断框架、研究进度与证据台账。", "Loading the case, decision framework, research progress, and evidence ledger.")} /> : null}
      {remote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} onRetry={() => void load()} /> : null}
      {isRemoteFailure(remote) ? <FailureState kind={remote.kind} message={remote.message} onReopen={() => void load()} /> : null}
      {mutation.kind === "offline" ? <RemoteStatus kind="reconnecting" message={mutation.message} /> : null}
      {isMutationFailure(mutation) ? <FailureState kind={mutation.kind} message={mutation.message} onReopen={() => void load()} /> : null}

      {remote.kind === "empty" ? (
        <section className="p03-prepare-panel" aria-labelledby="p03-prepare-heading">
          <div>
            <p className="p02-eyebrow">{copy("样例准备", "Fixture preparation")}</p>
            <h2 id="p03-prepare-heading">{copy("尚未准备证据台账", "Evidence ledger not prepared")}</h2>
            <p>{admission?.message}</p>
          </div>
          <button
            type="button"
            className="p02-primary-button"
            disabled={!admission?.workUnit || mutation.kind === "loading" || !online}
            onClick={() => void prepareFixture()}
          >
            <FileSearch size={16} aria-hidden="true" />
            {mutation.kind === "loading" ? copy("正在准备", "Preparing") : copy("准备证据样例", "Prepare evidence fixture")}
          </button>
        </section>
      ) : null}

      {projection && evidence ? (
        <>
          <SummaryStrip evidence={evidence} />
          <div className="p03-filter-bar" aria-label={copy("证据筛选", "Evidence filters")}>
            <label className="p03-cell-filter">
              <Filter size={15} aria-hidden="true" />
              <span>{copy("研究单元", "Research cell")}</span>
              <select value={cellFilter} onChange={(event) => setCellFilter(event.target.value)}>
                <option value="all">{copy(`全部 ${evidence.cells.length} 个研究单元`, `All ${evidence.cells.length} research cells`)}</option>
                {evidence.cells.map((cell, index) => <option key={cell.cell_id} value={cell.cell_id}>{copy(`研究单元 ${index + 1}：${cell.evidence_role}`, `Cell ${index + 1}: ${cell.evidence_role}`)}</option>)}
              </select>
            </label>
            <div className="p03-status-filters" role="group" aria-label={copy("证据状态", "Evidence status")}>
              {statusOptions(evidence, copy).map((option) => (
                <button
                  type="button"
                  key={option.value}
                  className={statusFilter === option.value ? "is-active" : undefined}
                  aria-pressed={statusFilter === option.value}
                  onClick={() => setStatusFilter(option.value)}
                >
                  {option.label}<span>{option.count}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="p03-workbench-grid">
            <div className="p03-cell-sections" aria-live="polite">
              {filteredCells.length === 0 ? (
                <div className="p03-filter-empty"><strong>{copy("没有匹配的证据项", "No matching evidence")}</strong><span>{copy("请选择其他研究单元或状态。", "Choose another research cell or status.")}</span></div>
              ) : filteredCells.map((cell) => (
                <CellSection
                  key={cell.cell_id}
                  cell={cell}
                  originalCell={evidence.cells.find((item) => item.cell_id === cell.cell_id) ?? cell}
                  selectedCandidateId={selectedCandidateId}
                  showGap={statusFilter === "all" || statusFilter === "gap"}
                  repairOutcome={evidence.repair_outcomes.find((outcome) => outcome.evidence_slot_id === cell.evidence_slot_id) ?? null}
                  repairRunning={mutation.kind === "loading" && mutation.target === `repair:${cell.evidence_slot_id}`}
                  onSelectCandidate={setSelectedCandidateId}
                  onRequestRepair={(evidenceSlotId, label) => beginReview({ kind: "repair", evidenceSlotId, label })}
                  onExecuteRepair={(evidenceSlotId) => void executeRepair(evidenceSlotId)}
                />
              ))}
            </div>

            <aside className="p03-inspector" aria-label={copy("候选证据详情", "Candidate evidence inspector")}>
              {reviewDraft ? (
                <ReviewForm
                  draft={reviewDraft}
                  reason={reason}
                  loading={mutation.kind === "loading"}
                  onReasonChange={setReason}
                  onCancel={() => { setReviewDraft(null); setReason(""); }}
                  onSubmit={submitReview}
                />
              ) : selectedCandidate ? (
                <CandidateInspector
                  candidate={selectedCandidate}
                  onReject={() => beginReview({ kind: "reject", candidate: selectedCandidate })}
                  onRequestRepair={() => beginReview({
                    kind: "repair",
                    evidenceSlotId: selectedCandidate.evidence_slot_id,
                    label: selectedCandidate.title,
                  })}
                />
              ) : (
                <div className="p03-inspector-empty">
                  <FileSearch size={22} aria-hidden="true" />
                  <strong>{copy("候选证据详情", "Candidate evidence inspector")}</strong>
                  <span>{copy("选择候选项以查看来源及适用边界。", "Select a candidate to review its source and applicability boundary.")}</span>
                </div>
              )}
            </aside>
          </div>
        </>
      ) : null}
    </section>
  );
}

function LocalResearchPreview({ state }: { state: LocalPreviewState }) {
  const { copy, labelToken } = useWorkbenchLocale();
  if (state.kind === "loading") {
    return <div className="p03-local-preview-status">{copy("正在读取本地真实研究候选项...", "Loading real local research candidates...")}</div>;
  }
  if (state.kind === "unavailable") {
    return <div className="p03-local-preview-status is-unavailable">{copy("本地真实研究源暂不可用，现有样例链仍可继续使用。", "Real local research sources are unavailable; the existing fixture path remains usable.")}</div>;
  }
  const preview = state.data;
  return (
    <section className="p03-local-preview" aria-labelledby="p03-local-preview-heading">
      <header>
        <div>
          <p className="p02-eyebrow">{copy("受限真实研究链", "Bounded real research path")}</p>
          <h2 id="p03-local-preview-heading">{copy("P36 十个研究单元", "Ten P36 research cells")}</h2>
          <p>{copy("从三个最高价值单元扩展到六类必需研究范围；读取本地已物化的官方来源、结构化对象、精确数值与关系图。", "Expanded from the three highest-value cells to all six mandatory research families using locally materialized official sources, structured objects, exact values, and graph relationships.")}</p>
        </div>
        <dl>
          <div><dt>{copy("研究单元", "Cells")}</dt><dd>{preview.selected_cell_count}</dd></div>
          <div><dt>{copy("真实候选项", "Real candidates")}</dt><dd>{preview.candidate_count}</dd></div>
          <div><dt>{copy("外部调用", "External calls")}</dt><dd>{preview.execution_counts.network_calls ?? 0}</dd></div>
        </dl>
      </header>
      <div className="p03-local-preview-grid">
        {preview.cells.map((cell) => (
          <article key={cell.cell_key}>
            <div className="p03-local-cell-heading">
              <span>{localCellLabel(cell.evidence_role, copy)}</span>
              <code>{localLaneLabel(cell.retrieval_lane, copy)}</code>
            </div>
            <h3>{localCellQuestion(cell.evidence_role, cell.decision_question, copy)}</h3>
            {cell.candidates.length ? (
              <ol>
                {cell.candidates.slice(0, 3).map((candidate) => (
                  <li key={candidate.candidate_id}>
                    <div><strong>{candidate.ticker} · {candidate.title}</strong><span>{candidate.source_type} / {candidate.published_at || labelToken(candidate.authority_mode)}</span></div>
                    {candidate.value ? <b>{candidate.value} {candidate.unit}</b> : null}
                    {candidate.citation_url ? <a href={candidate.citation_url} target="_blank" rel="noreferrer" title={copy("打开官方来源", "Open official source")}><Link2 size={14} aria-hidden="true" /></a> : null}
                  </li>
                ))}
              </ol>
            ) : <p className="p03-local-gap">{labelToken(cell.typed_gap || "typed_gap")}</p>}
          </article>
        ))}
      </div>
      <footer>{copy("边界：候选项已可进入只读内部分析预览，但证据晋升、senior R2、RG1 与发布准入仍未发生。", "Boundary: candidates can enter the read-only internal analysis preview, but evidence promotion, senior R2, RG1, and release admission have not occurred.")}</footer>
    </section>
  );
}

function localCellLabel(role: string, copy: Copy): string {
  const labels: Record<string, string> = {
    demand_signal: copy("需求真实性", "Demand reality"),
    revenue_capture: copy("价值与利润捕获", "Value and profit capture"),
    thesis_counterevidence: copy("瓶颈与反证", "Bottlenecks and counterevidence"),
    server_oem_orders: copy("服务器订单与收入", "Server OEM orders and revenue"),
    server_oem_margin_cash: copy("服务器利润与现金", "Server OEM margin and cash"),
    advanced_packaging_capacity: copy("先进封装产能", "Advanced-packaging capacity"),
    hbm_supply_pricing: copy("HBM 供给与定价", "HBM supply and pricing"),
    semicap_capex_cycle: copy("设备资本开支与周期", "Semicap capex and cycle"),
    export_policy_risk: copy("出口政策风险", "Export-policy risk"),
    customer_concentration: copy("客户集中度", "Customer concentration"),
  };
  return labels[role] ?? role;
}

function localCellQuestion(role: string, fallback: string, copy: Copy): string {
  const questions: Record<string, string> = {
    demand_signal: copy(
      "AI 基础设施需求是否正在转化为公司披露的数据中心增长与客户部署信号，这种转化有多可持续？",
      fallback,
    ),
    revenue_capture: copy(
      "需求信号中有多少已经转化为加速器层的收入、毛利润与营业利润？",
      fallback,
    ),
    thesis_counterevidence: copy(
      "哪些封装、存储、设备、营运资本或政策约束可能推翻简单的需求到利润逻辑？",
      fallback,
    ),
    server_oem_orders: copy("服务器厂商的订单与积压是否真正转化为发货和收入，而非时点错配？", fallback),
    server_oem_margin_cash: copy("AI 服务器收入是否转化为利润和现金，而非库存与营运资本压力？", fallback),
    advanced_packaging_capacity: copy("先进封装产能是否仍是约束，相关经济收益由谁捕获？", fallback),
    hbm_supply_pricing: copy("HBM 供给、定价和客户集中度有多紧张，利润捕获能否持续？", fallback),
    semicap_capex_cycle: copy("设备需求对资本开支时点、周期位置和出口政策传导意味着什么？", fallback),
    export_policy_risk: copy("当前出口限制可能如何影响供应、市场准入与已确认收入？", fallback),
    customer_concentration: copy("已确认收入的客户集中度有多高，它如何改变持续性与 price-in 风险？", fallback),
  };
  return questions[role] ?? fallback;
}

function localLaneLabel(lane: string, copy: Copy): string {
  const labels: Record<string, string> = {
    object_bm25: copy("结构化 RAG", "Structured RAG"),
    gold_fact_sql: copy("精确数值 SQL", "Exact-value SQL"),
    research_graph: copy("研究关系图", "Research graph"),
  };
  return labels[lane] ?? lane;
}

function SummaryStrip({ evidence }: { evidence: EvidenceWorkbenchView }) {
  const { copy } = useWorkbenchLocale();
  const summary = evidence.summary;
  return (
    <dl className="p03-summary-strip">
      <div><dt>{copy("研究单元", "Research cells")}</dt><dd>{evidence.cells.length}</dd></div>
      <div><dt>{copy("候选证据", "Candidates")}</dt><dd>{summary.candidate_count}</dd></div>
      <div><dt>{copy("仅作背景", "Context only")}</dt><dd>{summary.context_only_count}</dd></div>
      <div><dt>{copy("已排除", "Rejected")}</dt><dd>{summary.rejected_count}</dd></div>
      <div><dt>{copy("来源缺口", "Source gaps")}</dt><dd>{summary.gap_count}</dd></div>
      <div><dt>{copy("已请求补充", "Source repair requested")}</dt><dd>{summary.repair_requested_count}</dd></div>
      <div><dt>{copy("已完成补充", "Source repair completed")}</dt><dd>{summary.repair_completed_count}</dd></div>
    </dl>
  );
}

function CellSection({
  cell,
  originalCell,
  selectedCandidateId,
  showGap,
  repairOutcome,
  repairRunning,
  onSelectCandidate,
  onRequestRepair,
  onExecuteRepair,
}: {
  cell: EvidenceCellSectionView;
  originalCell: EvidenceCellSectionView;
  selectedCandidateId: string | null;
  showGap: boolean;
  repairOutcome: EvidenceRepairOutcomeView | null;
  repairRunning: boolean;
  onSelectCandidate: (candidateId: string) => void;
  onRequestRepair: (evidenceSlotId: string, label: string) => void;
  onExecuteRepair: (evidenceSlotId: string) => void;
}) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  return (
    <section className="p03-cell-section" aria-labelledby={`p03-${cell.cell_id}`}>
      <header className="p03-cell-section-header">
        <div>
          <p className="p03-cell-meta"><span>{labelToken(cell.evidence_role)}</span><span>{labelToken(cell.bundle_status)}</span></p>
          <h2 id={`p03-${cell.cell_id}`}>{localizeFixtureText(cell.decision_question)}</h2>
          <p className="p03-cell-owner">{labelToken(cell.owner)} / {labelToken(cell.materiality)}</p>
        </div>
        <button type="button" className="p02-icon-button" title={copy("请求补充来源", "Request source repair")} aria-label={copy("请求补充来源", "Request source repair")} onClick={() => onRequestRepair(cell.evidence_slot_id, cell.decision_question)}>
          <Wrench size={16} aria-hidden="true" />
        </button>
      </header>
      <div className="p03-candidate-list">
        {cell.candidates.map((candidate) => (
          <button
            type="button"
            className={`p03-candidate-row ${selectedCandidateId === candidate.candidate_id ? "is-selected" : ""}`}
            key={candidate.candidate_id}
            aria-pressed={selectedCandidateId === candidate.candidate_id}
            onClick={() => onSelectCandidate(candidate.candidate_id)}
          >
            <span className={`p03-state-badge p03-state-badge--${candidate.state}`}>{repairOutcome?.candidate_id === candidate.candidate_id ? copy("已补充候选项", "Source-repaired candidate") : evidenceStateLabel(candidate.state, copy)}</span>
            <span className="p03-candidate-copy"><strong>{localizeFixtureText(candidate.title)}</strong><span>{candidate.source_name} / {candidate.citation}</span></span>
            <span className="p03-authority-rank">A{candidate.source_authority_rank}</span>
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        ))}
        {showGap && originalCell.typed_gap ? (
          <article className={`p03-gap-row p03-gap-row--${repairOutcome ? "repair_completed" : originalCell.typed_gap.state}`}>
            <div>
              <span className="p03-state-badge p03-state-badge--gap">{repairOutcome ? copy("已完成补充", "Source repair completed") : gapStateLabel(originalCell.typed_gap.state, copy, labelToken)}</span>
              <strong>{repairOutcome ? copy("受限来源补充结果", "Bounded source-repair result") : originalCell.typed_gap.title}</strong>
              <p>{localizeFixtureText(repairOutcome?.outcome_boundary ?? originalCell.typed_gap.detail)}</p>
              <code>{repairOutcome?.repair_outcome_id ?? originalCell.typed_gap.gap_code}</code>
            </div>
            {originalCell.typed_gap.state === "repair_requested" && !repairOutcome ? (
              <button type="button" className="p02-primary-button" disabled={repairRunning} onClick={() => onExecuteRepair(originalCell.typed_gap!.evidence_slot_id)}>
                <CirclePlay size={15} aria-hidden="true" />
                {repairRunning ? copy("正在补充", "Repairing") : copy("运行受限来源补充", "Run bounded source repair")}
              </button>
            ) : !repairOutcome ? (
              <button type="button" className="p02-secondary-button" onClick={() => onRequestRepair(originalCell.typed_gap!.evidence_slot_id, originalCell.typed_gap!.title)}>
                <Wrench size={15} aria-hidden="true" />
                {copy("请求补充来源", "Request source repair")}
              </button>
            ) : null}
          </article>
        ) : null}
      </div>
    </section>
  );
}

function CandidateInspector({ candidate, onReject, onRequestRepair }: { candidate: EvidenceCandidateView; onReject: () => void; onRequestRepair: () => void }) {
  const { copy, formatDateTime, labelToken, localizeFixtureText } = useWorkbenchLocale();
  return (
    <div className="p03-inspector-content">
      <div className="p03-inspector-heading"><p className="p02-eyebrow">{copy("候选证据详情", "Candidate evidence inspector")}</p><span className={`p03-state-badge p03-state-badge--${candidate.state}`}>{evidenceStateLabel(candidate.state, copy)}</span></div>
      <h2>{localizeFixtureText(candidate.title)}</h2>
      <p className="p03-not-promoted"><ShieldCheck size={16} aria-hidden="true" /><span><strong>{copy("未提升为正式证据", "Not promoted")}</strong>{copy("此元数据候选项尚非正式证据，不能作为最终事实依据。", "This metadata candidate is not formal evidence and cannot support a final fact.")}</span></p>
      <p className="p03-excerpt">{localizeFixtureText(candidate.excerpt)}</p>
      <dl className="p03-inspector-fields">
        <div><dt>{copy("来源", "Source")}</dt><dd>{candidate.source_name}<small>{candidate.source_type}</small></dd></div>
        <div><dt>{copy("来源权限", "Authority")}</dt><dd>{candidate.authority_label}<small>{copy(`等级 ${candidate.source_authority_rank}`, `Rank ${candidate.source_authority_rank}`)}</small></dd></div>
        <div><dt>{copy("引文", "Citation")}</dt><dd><Link2 size={14} aria-hidden="true" />{candidate.citation}</dd></div>
        <div><dt>{copy("发布日期", "Published")}</dt><dd><CalendarDays size={14} aria-hidden="true" />{formatDateTime(candidate.published_at)}</dd></div>
        <div><dt>{copy("实体 / 期间", "Entity / period")}</dt><dd>{candidate.entity_ref}<small>{labelToken(candidate.period_ref)}</small></dd></div>
        <div><dt>{copy("候选类型", "Candidate kind")}</dt><dd>{labelToken(candidate.candidate_kind)}</dd></div>
        <div className="is-wide"><dt>{copy("文档", "Document")}</dt><dd><code>{candidate.document_id}</code><small>{candidate.document_version} / {candidate.section_or_table_ref}</small></dd></div>
        <div className="is-wide"><dt>{copy("来源策略", "Source policy")}</dt><dd><code>{candidate.source_policy_ref}</code><small>{candidate.route_id}</small></dd></div>
      </dl>
      <div className="p03-applicability"><strong>{copy("适用边界", "Applicability boundary")}</strong><p>{localizeFixtureText(candidate.applicability_boundary)}</p></div>
      {candidate.rejection_reason ? <div className="p03-rejection-reason"><strong>{copy("排除原因", "Rejection reason")}</strong><p>{candidate.rejection_reason}</p></div> : null}
      <div className="p03-inspector-actions">
        <button type="button" className="p02-secondary-button" onClick={onRequestRepair}><Wrench size={15} aria-hidden="true" />{copy("请求补充来源", "Request source repair")}</button>
        {candidate.state !== "rejected" ? <button type="button" className="p02-secondary-button p03-reject-button" onClick={onReject}><Ban size={15} aria-hidden="true" />{copy("排除候选项", "Reject candidate")}</button> : null}
      </div>
    </div>
  );
}

function ReviewForm({ draft, reason, loading, onReasonChange, onCancel, onSubmit }: { draft: ReviewDraft; reason: string; loading: boolean; onReasonChange: (value: string) => void; onCancel: () => void; onSubmit: (event: FormEvent) => void }) {
  const { copy } = useWorkbenchLocale();
  const rejecting = draft.kind === "reject";
  const label = rejecting ? draft.candidate.title : draft.label;
  return (
    <form className="p03-review-form" onSubmit={onSubmit}>
      <div className="p03-review-form-heading"><div><p className="p02-eyebrow">{copy("处理操作", "Review action")}</p><h2>{rejecting ? copy("排除候选项", "Reject candidate") : copy("请求补充来源", "Request source repair")}</h2></div><button type="button" className="p02-icon-button" title={copy("取消", "Cancel")} aria-label={copy("取消当前操作", "Cancel review action")} onClick={onCancel}><X size={16} aria-hidden="true" /></button></div>
      <p className="p03-review-target">{label}</p>
      <label>{copy("原因", "Reason")}<textarea required autoFocus value={reason} onChange={(event) => onReasonChange(event.target.value)} placeholder={rejecting ? copy("请说明该候选项不适用的原因。", "Explain why this candidate is unsuitable.") : copy("请说明需要补充的来源、背景或适用边界。", "Describe the missing source, context, or boundary to repair.")} /></label>
      <p className="p03-form-note">{copy("操作仅针对当前证据台账版本。", "This action targets the exact current evidence-ledger version.")}</p>
      <div className="p03-review-actions"><button type="button" className="p02-secondary-button" onClick={onCancel}>{copy("取消", "Cancel")}</button><button type="submit" className="p02-primary-button" disabled={loading || !reason.trim()}>{rejecting ? <Ban size={15} aria-hidden="true" /> : <Send size={15} aria-hidden="true" />}{loading ? copy("正在提交", "Submitting") : rejecting ? copy("排除", "Reject") : copy("发送补充请求", "Send source-repair request")}</button></div>
    </form>
  );
}

function FailureState({ kind, message, onReopen }: { kind: FailureKind; message: string; onReopen: () => void }) {
  const { copy } = useWorkbenchLocale();
  return <div className="p02-failure-stack"><RemoteStatus kind={kind} message={message} />{kind !== "permission" ? <button type="button" className="p02-secondary-button" onClick={onReopen}><RotateCcw size={16} aria-hidden="true" />{copy("重新打开当前视图", "Reopen current view")}</button> : null}</div>;
}

function preparationAdmission(prerequisites: Prerequisites, copy: Copy) {
  if (prerequisites.surface.review_status !== "accepted") return { workUnit: null, message: copy("需先确认最新研究判断框架，才能准备证据台账。", "Confirm the latest decision framework before preparing the evidence ledger.") };
  if (prerequisites.execution.work_units.length !== 1) return { workUnit: null, message: copy("准备证据台账前需有且仅有一个研究进度样例。", "Exactly one research-progress fixture is required before preparing the evidence ledger.") };
  const workUnit = prerequisites.execution.work_units[0];
  if (workUnit.state !== "pending") return { workUnit: null, message: copy("研究进度样例必须处于待处理状态。请打开研究进度查看阻断说明。", "The research-progress fixture must be pending. Reopen research progress to inspect its recorded stop.") };
  return { workUnit, message: copy("准备确定性 P36 候选包样例；不会运行检索、工具或模型，也不会提升证据。", "Prepare the deterministic P36 candidate-bundle fixture. It does not run retrieval, tools, or models, and does not promote evidence.") };
}

function statusOptions(evidence: EvidenceWorkbenchView, copy: Copy): { value: StatusFilter; label: string; count: number }[] {
  const summary = evidence.summary;
  return [
    { value: "all", label: copy("全部", "All"), count: summary.candidate_count + summary.context_only_count + summary.rejected_count + summary.gap_count },
    { value: "candidate", label: copy("候选证据", "Candidates"), count: summary.candidate_count },
    { value: "context_only", label: copy("仅作背景", "Context only"), count: summary.context_only_count },
    { value: "rejected", label: copy("已排除", "Rejected"), count: summary.rejected_count },
    { value: "gap", label: copy("来源缺口", "Source gaps"), count: summary.gap_count },
  ];
}

function matchesStatus(state: EvidenceCandidateState, filter: StatusFilter): boolean {
  return filter === "all" || filter === state;
}

function evidenceStateLabel(state: EvidenceCandidateState, copy: Copy): string {
  if (state === "candidate") return copy("候选证据 / 未提升", "Candidate / not promoted");
  if (state === "context_only") return copy("仅作背景", "Context only");
  return copy("已排除", "Rejected");
}

function gapStateLabel(state: string, copy: Copy, labelToken: (value: string) => string): string {
  if (state === "repair_requested") return copy("已请求补充", "Source repair requested");
  if (state === "repair_completed") return copy("已完成补充", "Source repair completed");
  return labelToken(state);
}

function isEvidenceMissing(error: unknown): boolean {
  return error instanceof EvidenceApiError && error.code !== "case_not_found" && (error.statusCode === 404 || error.code === "evidence_workbench_not_found" || error.code === "evidence_not_prepared");
}

function remoteFailure(error: unknown, copy: Copy): RemoteState {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接样例 API。恢复连接后将重新加载证据台账。", "The fixture API could not be reached. The evidence ledger will reload after reconnecting.") };
  return apiFailure(error, copy);
}

function mutationFailure(error: unknown, copy: Copy): MutationState {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接样例 API。请恢复连接后再发送请求。", "The fixture API could not be reached. Reconnect before sending the request.") };
  return apiFailure(error, copy);
}

function apiFailure(error: unknown, copy: Copy): { kind: FailureKind; message: string } {
  if (isApiError(error)) {
    if (error.code === "case_not_found") return { kind: "error", message: copy("找不到此研究案例。请返回研究概览选择有效案例，或刷新后重试。", "This research case could not be found. Return to the case overview to select a valid case, or refresh and try again.") };
    const kind = error.code === "permission_denied" || error.statusCode === 403
      ? "permission"
      : error.code.includes("stale") || error.code.includes("superseded")
        ? "stale"
        : error.code === "version_conflict" || error.code === "idempotency_conflict" || error.statusCode === 409
          ? "conflict"
          : "error";
    return { kind, message: error.traceId ? `${error.message} ${copy("追踪 ID：", "Trace ID: ")}${error.traceId}` : error.message };
  }
  return { kind: "error", message: copy("样例 API 未返回可用的证据台账响应。", "The fixture API did not return a usable evidence-ledger response.") };
}

function isApiError(error: unknown): error is CaseApiError | PlanningApiError | ExecutionApiError | EvidenceApiError {
  return error instanceof CaseApiError || error instanceof PlanningApiError || error instanceof ExecutionApiError || error instanceof EvidenceApiError;
}

function isOfflineError(error: unknown): boolean {
  return error instanceof TypeError || isApiError(error) && error.statusCode === 0;
}

function isRemoteFailure(remote: RemoteState): remote is Extract<RemoteState, { kind: FailureKind }> {
  return remote.kind === "permission" || remote.kind === "conflict" || remote.kind === "stale" || remote.kind === "error";
}

function isMutationFailure(mutation: MutationState): mutation is Extract<MutationState, { kind: FailureKind }> {
  return mutation.kind === "permission" || mutation.kind === "conflict" || mutation.kind === "stale" || mutation.kind === "error";
}

function keyForAttempt(ref: { current: IdempotencyRecord | null }, fingerprint: string): string {
  if (ref.current?.fingerprint === fingerprint) return ref.current.key;
  const key = `workbench-${crypto.randomUUID()}`;
  ref.current = { fingerprint, key };
  return key;
}

function mapIdempotencyKey(records: Map<string, IdempotencyRecord>, id: string, fingerprint: string): string {
  const current = records.get(id);
  if (current?.fingerprint === fingerprint) return current.key;
  const key = `workbench-${crypto.randomUUID()}`;
  records.set(id, { fingerprint, key });
  return key;
}
