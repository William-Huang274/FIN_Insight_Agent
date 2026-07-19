import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, Pencil, RefreshCcw, RotateCcw, Save, X } from "lucide-react";

import { CaseApiClient, CaseApiError, CaseWorkspaceProjection } from "../../api/cases";
import {
  DecisionSurfaceCellView,
  DecisionSurfaceRevision,
  DecisionSurfaceView,
  PlanningApiClient,
  PlanningApiError,
  PlanningCheckpointDecision,
  PlanningCheckpointDecisionCommand,
  ReviseDecisionSurfaceCommand,
} from "../../api/planning";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { RemoteStatus, RemoteStatusKind } from "../../shared/RemoteStatus";

type DecisionSurfaceProps = {
  caseId: string;
  online: boolean;
  onBack: () => void;
};

type SurfaceProjection = {
  workspace: CaseWorkspaceProjection;
  surface: DecisionSurfaceView;
};

type RemoteResult =
  | { kind: "loading" }
  | { kind: "ready"; data: SurfaceProjection }
  | { kind: "empty"; workspace: CaseWorkspaceProjection }
  | { kind: "offline"; message: string }
  | { kind: Exclude<RemoteStatusKind, "loading" | "empty" | "reconnecting">; message: string };

type MutationResult =
  | { kind: "idle" }
  | { kind: "loading"; action: "revise" | PlanningCheckpointDecision }
  | { kind: "offline"; message: string }
  | FailureResult;

type FailureResult = { kind: "error" | "permission" | "stale" | "conflict"; message: string };
type IdempotentAttempt = { fingerprint: string; key: string };
type CellDraft = { whatWouldChange: string; stopRule: string };
type Copy = (zhCN: string, en: string) => string;

const caseApi = new CaseApiClient();
const planningApi = new PlanningApiClient();

export function DecisionSurface({ caseId, online, onBack }: DecisionSurfaceProps) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  const [remote, setRemote] = useState<RemoteResult>({ kind: "loading" });
  const [mutation, setMutation] = useState<MutationResult>({ kind: "idle" });
  const [editingCellId, setEditingCellId] = useState<string | null>(null);
  const [draft, setDraft] = useState<CellDraft>({ whatWouldChange: "", stopRule: "" });
  const versionRef = useRef<number | undefined>(undefined);
  const revisionAttemptRef = useRef<IdempotentAttempt | null>(null);
  const reviewAttemptRef = useRef<IdempotentAttempt | null>(null);
  const copyRef = useRef<Copy>(copy);
  copyRef.current = copy;

  const load = useCallback(async (validateVersion: boolean) => {
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: copyRef.current("连接不可用。请重新连接以恢复当前研究计划。", "Connection is unavailable. Reconnect to restore the current research plan.") });
      return;
    }
    setRemote({ kind: "loading" });
    setMutation({ kind: "idle" });
    try {
      const workspace = await caseApi.getCase(caseId, validateVersion ? versionRef.current : undefined);
      versionRef.current = workspace.case_version;
      try {
        const surface = await planningApi.getDecisionSurface(caseId);
        setRemote({ kind: "ready", data: { workspace, surface } });
      } catch (error) {
        setRemote(isPlanningMissing(error) ? { kind: "empty", workspace } : planningFailure(error, copyRef.current));
      }
    } catch (error) {
      setRemote(caseFailure(error, copyRef.current));
    }
  }, [caseId, online]);

  useEffect(() => {
    void load(false);
  }, [load]);

  const projection = remote.kind === "ready" ? remote.data : null;
  const isMutating = mutation.kind === "loading";
  const isReviewable = projection?.surface.review_status === "awaiting_review" || projection?.surface.review_status === "draft";

  function beginRevision(cell: DecisionSurfaceCellView) {
    setEditingCellId(cell.cell_id);
    setDraft({ whatWouldChange: cell.what_would_change, stopRule: cell.stop_rule });
    setMutation({ kind: "idle" });
    revisionAttemptRef.current = null;
  }

  function cancelRevision() {
    setEditingCellId(null);
    setDraft({ whatWouldChange: "", stopRule: "" });
    setMutation({ kind: "idle" });
    revisionAttemptRef.current = null;
  }

  async function reviseCell(event: FormEvent<HTMLFormElement>, cell: DecisionSurfaceCellView) {
    event.preventDefault();
    if (!projection) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copyRef.current("连接不可用。请重新连接后再保存修订。", "Connection is unavailable. Reconnect before saving this revision.") });
      return;
    }

    const change: DecisionSurfaceRevision = {
      cell_id: cell.cell_id,
      what_would_change: draft.whatWouldChange.trim(),
    };
    const revisedStopRule = draft.stopRule.trim();
    if (revisedStopRule !== cell.stop_rule) change.stop_rule = revisedStopRule;

    const baseCommand = {
      expected_case_version: projection.workspace.case_version,
      expected_decision_surface_contract_version: projection.surface.contract_version,
      expected_checkpoint_version: projection.surface.checkpoint_version,
      changes: [change],
      actor_ref: planningApi.actorRef,
    };
    const command: ReviseDecisionSurfaceCommand = {
      ...baseCommand,
      idempotency_key: keyForAttempt(revisionAttemptRef, JSON.stringify(baseCommand)),
    };
    setMutation({ kind: "loading", action: "revise" });
    try {
      const surface = await planningApi.reviseDecisionSurface(caseId, command);
      revisionAttemptRef.current = null;
      setRemote({ kind: "ready", data: { workspace: projection.workspace, surface } });
      setEditingCellId(null);
      setDraft({ whatWouldChange: "", stopRule: "" });
      setMutation({ kind: "idle" });
    } catch (error) {
      setMutation(planningFailure(error, copyRef.current));
    }
  }

  async function review(decision: PlanningCheckpointDecision) {
    if (!projection) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copyRef.current("连接不可用。请重新连接后再提交分析师复核结论。", "Connection is unavailable. Reconnect before recording the analyst review decision.") });
      return;
    }
    const baseCommand = {
      decision,
      expected_case_version: projection.workspace.case_version,
      expected_decision_surface_contract_version: projection.surface.contract_version,
      expected_checkpoint_version: projection.surface.checkpoint_version,
      actor_ref: planningApi.actorRef,
    };
    const command: PlanningCheckpointDecisionCommand = {
      ...baseCommand,
      idempotency_key: keyForAttempt(reviewAttemptRef, JSON.stringify(baseCommand)),
    };
    setMutation({ kind: "loading", action: decision });
    try {
      const surface = await planningApi.reviewPlanningCheckpoint(caseId, command);
      reviewAttemptRef.current = null;
      setRemote({ kind: "ready", data: { workspace: projection.workspace, surface } });
      setMutation({ kind: "idle" });
    } catch (error) {
      setMutation(planningFailure(error, copyRef.current));
    }
  }

  return (
    <section className="p02-workspace p02-decision-surface" aria-label={copy("研究问题与研究单元", "Research questions and cells")}>
      <button type="button" className="p02-back-button" onClick={onBack}>
        <ArrowLeft size={16} aria-hidden="true" />
        {copy("案例概览", "Case overview")}
      </button>
      <div className="p02-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("研究计划", "Research plan")}</p>
          <h1>{copy("研究问题", "Research questions")}</h1>
          <p className="p02-heading-meta">{caseId}</p>
        </div>
        <button type="button" className="p02-icon-button" title={copy("刷新研究计划", "Refresh research plan")} aria-label={copy("刷新研究计划", "Refresh research plan")} onClick={() => void load(true)}>
          <RefreshCcw size={17} aria-hidden="true" />
        </button>
      </div>

      {remote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载研究问题。", "Loading research questions.")} /> : null}
      {remote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} /> : null}
      {isRemoteFailure(remote) ? <RemoteStatus kind={remote.kind} message={remote.message} onRetry={() => void load(false)} /> : null}
      {remote.kind === "empty" ? (
        <section className="p02-empty-panel">
          <div>
            <h2>{copy("暂无研究单元", "No research cells")}</h2>
            <p>{copy("当前案例尚未生成研究单元。", "This Case has not compiled research cells yet.")}</p>
          </div>
          <button type="button" className="p02-secondary-button" onClick={onBack}>{copy("返回案例概览", "Return to overview")}</button>
        </section>
      ) : null}

      {projection ? (
        <>
          {mutation.kind === "offline" ? <RemoteStatus kind="reconnecting" message={mutation.message} /> : null}
          {isMutationFailure(mutation) ? <RemoteStatus kind={mutation.kind} message={mutation.message} onRetry={() => void load(false)} /> : null}

          <div className="p02-cell-list" aria-label={copy("研究单元", "Research cells")}>
            {projection.surface.cells.map((cell, index) => (
              <article className="p02-cell" key={cell.cell_id}>
                <header className="p02-cell-header">
                  <div className="p02-cell-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</div>
                  <div className="p02-cell-title">
                    <h2>{localizeFixtureText(cell.decision_question)}</h2>
                    <div className="p02-cell-kicker">
                      <span>{labelToken(cell.owner)}</span>
                      <span>{copy(`${labelToken(cell.materiality)}重要性`, `${labelToken(cell.materiality)} materiality`)}</span>
                      <span>{copy(`研究单元 v${cell.cell_version}`, `Cell v${cell.cell_version}`)}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="p02-icon-button"
                    title={copy("修订研究单元", "Revise research cell")}
                    aria-label={`${copy("修订研究单元：", "Revise research cell: ")}${cell.decision_question}`}
                    disabled={isMutating}
                    onClick={() => beginRevision(cell)}
                  >
                    <Pencil size={16} aria-hidden="true" />
                  </button>
                </header>

                <div className="p02-cell-body">
                  <section className="p02-cell-judgment" aria-label={copy("研究单元修订", "Research cell revision")}>
                    {editingCellId === cell.cell_id ? (
                      <form className="p02-revision-form" onSubmit={(event) => void reviseCell(event, cell)}>
                        <label>
                          {copy("什么证据或结论会改变", "What evidence or conclusion would change")}
                          <textarea
                            value={draft.whatWouldChange}
                            onChange={(event) => setDraft((current) => ({ ...current, whatWouldChange: event.target.value }))}
                            rows={5}
                            required
                          />
                        </label>
                        <label>
                          {copy("停止条件", "Stop condition")} <span className="p02-optional-label">{copy("可调整", "May be adjusted")}</span>
                          <textarea
                            value={draft.stopRule}
                            onChange={(event) => setDraft((current) => ({ ...current, stopRule: event.target.value }))}
                            rows={4}
                            required
                          />
                        </label>
                        <div className="p02-form-footer">
                          <button type="button" className="p02-icon-button" title={copy("取消修订", "Cancel revision")} aria-label={copy("取消修订", "Cancel revision")} onClick={cancelRevision}>
                            <X size={16} aria-hidden="true" />
                          </button>
                          <button type="submit" className="p02-primary-button" disabled={!online || isMutating}>
                            <Save size={16} aria-hidden="true" />
                            {mutation.kind === "loading" && mutation.action === "revise" ? copy("正在保存", "Saving") : copy("保存修订", "Save revision")}
                          </button>
                        </div>
                      </form>
                    ) : (
                      <dl className="p02-judgment-fields">
                        <div>
                          <dt>{copy("停止条件", "Stop condition")}</dt>
                          <dd>{localizeFixtureText(cell.stop_rule)}</dd>
                        </div>
                        <div>
                          <dt>{copy("什么证据或结论会改变", "What evidence or conclusion would change")}</dt>
                          <dd>{localizeFixtureText(cell.what_would_change)}</dd>
                        </div>
                      </dl>
                    )}
                  </section>

                  <section className="p02-evidence-section" aria-labelledby={`evidence-${cell.cell_id}`}>
                    <div className="p02-evidence-heading">
                      <h3 id={`evidence-${cell.cell_id}`}>{copy("所需证据", "Evidence needed")}</h3>
                      <span>{copy(`${cell.evidence_slots.filter((slot) => slot.required).length} 个证据槽`, `${cell.evidence_slots.filter((slot) => slot.required).length} slots`)}</span>
                    </div>
                    <div className="p02-evidence-list">
                      {cell.evidence_slots.map((slot) => (
                        <article className="p02-evidence-slot" key={slot.evidence_slot_id}>
                          <div className="p02-slot-heading">
                            <h4>{labelToken(slot.evidence_role)}</h4>
                            <span className={`p02-required-badge ${slot.required ? "is-required" : ""}`}>{slot.required ? copy("必需", "Required") : copy("可选", "Optional")}</span>
                          </div>
                          <dl>
                            <div><dt>{copy("对象", "Entities")}</dt><dd>{slot.entity_scope.join(", ")}</dd></div>
                            <div><dt>{copy("期间", "Period")}</dt><dd>{labelToken(slot.period_scope)}</dd></div>
                            <div><dt>{copy("来源策略", "Source policy")}</dt><dd>{slot.source_policy_ref}</dd></div>
                          </dl>
                        </article>
                      ))}
                    </div>
                  </section>
                </div>
              </article>
            ))}
          </div>

          <section className="p02-surface-toolbar" aria-label={copy("研究计划元数据与分析师操作", "Research plan metadata and analyst actions")}>
            <dl className="p02-surface-version">
              <div><dt>{copy("计划版本", "Plan version")}</dt><dd>v{projection.surface.contract_version}</dd></div>
              <div><dt>{copy("复核批次", "Review checkpoint")}</dt><dd>v{projection.surface.checkpoint_version}</dd></div>
              <div><dt>{copy("分析师状态", "Analyst status")}</dt><dd><StatusBadge value={projection.surface.review_status} labelToken={labelToken} /></dd></div>
              <div><dt>{copy("案例版本", "Case version")}</dt><dd>v{projection.workspace.case_version}</dd></div>
            </dl>
            <div className="p02-review-actions">
              <button
                type="button"
                className="p02-secondary-button p02-return-button"
                disabled={!online || isMutating || !isReviewable}
                onClick={() => void review("return")}
              >
                <RotateCcw size={16} aria-hidden="true" />
                {mutation.kind === "loading" && mutation.action === "return" ? copy("正在退回", "Returning") : copy("退回修订", "Return for revision")}
              </button>
              <button
                type="button"
                className="p02-primary-button"
                disabled={!online || isMutating || !isReviewable}
                onClick={() => void review("accept")}
              >
                <Check size={16} aria-hidden="true" />
                {mutation.kind === "loading" && mutation.action === "accept" ? copy("正在记录", "Recording") : copy("标记已复核", "Mark reviewed")}
              </button>
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}

function StatusBadge({ value, labelToken }: { value: string; labelToken: (value: string) => string }) {
  return <span className={`p02-status-badge p02-status-badge--${statusClass(value)}`}>{labelToken(value)}</span>;
}

function isPlanningMissing(error: unknown): boolean {
  return error instanceof PlanningApiError && (error.statusCode === 404 || error.code === "decision_surface_not_found" || error.code === "planning_not_compiled");
}

function planningFailure(error: unknown, copy: Copy): FailureResult {
  if (error instanceof PlanningApiError) return apiFailure(error, copy);
  return { kind: "error", message: copy("演示 API 未返回可用的研究计划响应。", "The fixture API did not return a usable research-plan response.") };
}

function caseFailure(error: unknown, copy: Copy): FailureResult {
  if (error instanceof CaseApiError) return apiFailure(error, copy);
  return { kind: "error", message: copy("演示 API 未返回可用的案例响应。", "The fixture API did not return a usable Case response.") };
}

function apiFailure(error: CaseApiError | PlanningApiError, copy: Copy): FailureResult {
  const kind = error.code === "permission_denied" || error.statusCode === 403
    ? "permission"
    : error.code === "version_conflict" || error.code === "idempotency_conflict"
      ? "conflict"
      : error.code.includes("stale") || error.code.includes("superseded")
        ? "stale"
        : "error";
  return { kind, message: error.traceId ? `${error.message} ${copy("追踪编号", "Trace")}: ${error.traceId}` : error.message };
}

function isRemoteFailure(remote: RemoteResult): remote is FailureResult {
  return remote.kind === "error" || remote.kind === "permission" || remote.kind === "stale" || remote.kind === "conflict";
}

function isMutationFailure(remote: MutationResult): remote is FailureResult {
  return remote.kind === "error" || remote.kind === "permission" || remote.kind === "stale" || remote.kind === "conflict";
}

function keyForAttempt(ref: { current: IdempotentAttempt | null }, fingerprint: string): string {
  if (ref.current?.fingerprint === fingerprint) return ref.current.key;
  const key = `workbench-${crypto.randomUUID()}`;
  ref.current = { fingerprint, key };
  return key;
}

function statusClass(value: string): string {
  if (value === "accepted") return "accepted";
  if (value === "returned") return "returned";
  return "pending";
}
