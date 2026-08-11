import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, CircleStop, ExternalLink, FileSearch, Play, RefreshCcw, RotateCcw } from "lucide-react";

import { CaseApiClient, CaseApiError, CaseWorkspaceProjection } from "../../api/cases";
import {
  ActivityTraceView,
  CancelWorkUnitCommand,
  CreateWorkUnitCommand,
  decisionSurfaceInputHeadDigest,
  ExecutionApiClient,
  ExecutionApiError,
  FIXTURE_NO_LEASE_FENCING_TOKEN,
  P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE,
  WorkUnitExecutionItem,
  WorkUnitExecutionView,
} from "../../api/execution";
import { DecisionSurfaceView, PlanningApiClient, PlanningApiError } from "../../api/planning";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { RemoteStatus } from "../../shared/RemoteStatus";

type ActivityTraceProps = {
  caseId: string;
  online: boolean;
  onBack: () => void;
  onExitCase: () => void;
  onOpenDecisionSurface: () => void;
  onOpenEvidence: () => void;
};

type Projection = {
  workspace: CaseWorkspaceProjection;
  surface: DecisionSurfaceView;
  execution: WorkUnitExecutionView;
  activity: ActivityTraceView;
};

type FailureKind = "permission" | "conflict" | "stale" | "error";
type RemoteState =
  | { kind: "loading" }
  | { kind: "ready"; data: Projection }
  | { kind: "empty" }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type MutationState =
  | { kind: "idle" }
  | { kind: "loading"; workUnitId?: string }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type IdempotencyRecord = { fingerprint: string; key: string };
type Copy = (zhCN: string, en: string) => string;

const caseApi = new CaseApiClient();
const planningApi = new PlanningApiClient();
const executionApi = new ExecutionApiClient();

export function ActivityTrace({ caseId, online, onBack, onExitCase, onOpenDecisionSurface, onOpenEvidence }: ActivityTraceProps) {
  const { copy, formatDateTime, labelToken } = useWorkbenchLocale();
  const [remote, setRemote] = useState<RemoteState>({ kind: "loading" });
  const [mutation, setMutation] = useState<MutationState>({ kind: "idle" });
  const caseVersionRef = useRef<number | undefined>(undefined);
  const startKeyRef = useRef<IdempotencyRecord | null>(null);
  const cancelKeyRef = useRef(new Map<string, IdempotencyRecord>());

  const load = useCallback(async (validateVersion: boolean) => {
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: copy("连接不可用。恢复连接后可重新加载研究进度。", "Connection is unavailable. Reconnect to restore research progress.") });
      return;
    }

    setRemote({ kind: "loading" });
    try {
      const workspace = await caseApi.getCase(caseId, validateVersion ? caseVersionRef.current : undefined);
      const [surface, execution, activity] = await Promise.all([
        planningApi.getDecisionSurface(caseId),
        executionApi.listWorkUnits(caseId),
        executionApi.getActivityTrace(caseId),
      ]);
      caseVersionRef.current = workspace.case_version;
      setRemote({ kind: "ready", data: { workspace, surface, execution, activity } });
    } catch (error) {
      setRemote(remoteFailure(error, copy));
    }
  }, [caseId, copy, online]);

  useEffect(() => {
    void load(false);
  }, [load]);

  const projection = remote.kind === "ready" ? remote.data : null;
  const canStart = projection?.surface.review_status === "accepted" && projection.execution.work_units.length === 0;

  async function startWorkUnit() {
    if (!projection || !canStart) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请恢复连接后建立研究进度样例。", "Connection is unavailable. Reconnect before creating the research-progress fixture.") });
      return;
    }

    setMutation({ kind: "loading" });
    try {
      const inputHeadDigest = await decisionSurfaceInputHeadDigest(projection.surface.contract_version_id);
      const fingerprint = `${projection.workspace.case_version}:${projection.surface.contract_version_id}:${inputHeadDigest}`;
      const command: CreateWorkUnitCommand = {
        work_unit_type: P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE,
        expected_case_version: projection.workspace.case_version,
        input_head_digest: inputHeadDigest,
        actor_ref: executionApi.actorRef,
        idempotency_key: idempotencyKey(startKeyRef, fingerprint),
      };
      await executionApi.createWorkUnit(caseId, command);
      startKeyRef.current = null;
      setMutation({ kind: "idle" });
      await load(false);
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  async function cancelWorkUnit(workUnit: WorkUnitExecutionItem) {
    if (workUnit.state !== "pending") return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请恢复连接后取消待处理的研究进度项。", "Connection is unavailable. Reconnect before cancelling the pending research item.") });
      return;
    }

    const fingerprint = `${workUnit.work_unit_id}:${workUnit.work_unit_version}:${workUnit.state_version}`;
    const command: CancelWorkUnitCommand = {
      expected_work_unit_version: workUnit.work_unit_version,
      expected_state_version: workUnit.state_version,
      fencing_token: FIXTURE_NO_LEASE_FENCING_TOKEN,
      actor_ref: executionApi.actorRef,
      idempotency_key: mapIdempotencyKey(cancelKeyRef.current, workUnit.work_unit_id, fingerprint),
    };
    setMutation({ kind: "loading", workUnitId: workUnit.work_unit_id });
    try {
      await executionApi.cancelWorkUnit(caseId, workUnit.work_unit_id, command);
      cancelKeyRef.current.delete(workUnit.work_unit_id);
      setMutation({ kind: "idle" });
      await load(false);
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  return (
    <section className="p02-workspace p02-detail" aria-label={copy("研究进度", "Research progress")}>
      <button type="button" className="p02-back-button" onClick={onBack}>
        <ArrowLeft size={16} aria-hidden="true" />
        {copy("研究概览", "Case overview")}
      </button>

      <div className="p02-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("研究进度", "Research progress")}</p>
          <h1>{caseId}</h1>
          {projection ? <p className="p02-heading-meta">{copy(`案例版本 v${projection.workspace.case_version} · 记录版本 v${projection.activity.case_version}`, `Case v${projection.workspace.case_version} · trace v${projection.activity.case_version}`)}</p> : null}
        </div>
        <div className="p02-page-actions">
          {projection?.execution.work_units.length ? (
            <button type="button" className="p02-secondary-button" onClick={onOpenEvidence}>
              <FileSearch size={16} aria-hidden="true" />
              {copy("证据台账", "Evidence ledger")}
            </button>
          ) : null}
          {canStart ? (
            <button type="button" className="p02-primary-button" disabled={mutation.kind === "loading"} onClick={() => void startWorkUnit()}>
              <Play size={16} aria-hidden="true" />
              {mutation.kind === "loading" && !mutation.workUnitId ? copy("正在建立", "Creating") : copy("建立研究进度样例", "Create research-progress fixture")}
            </button>
          ) : null}
          <button type="button" className="p02-icon-button" title={copy("刷新研究进度", "Refresh research progress")} aria-label={copy("刷新研究进度", "Refresh research progress")} onClick={() => void load(true)}>
            <RefreshCcw size={17} aria-hidden="true" />
          </button>
        </div>
      </div>

      {remote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载研究案例、研究判断框架、研究进度与记录。", "Loading the case, decision framework, research progress, and trace.")} /> : null}
      {remote.kind === "empty" ? <RemoteStatus kind="empty" message={copy("此研究案例暂无研究进度记录。", "No research-progress record is available for this case.")} /> : null}
      {remote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} /> : null}
      {isRemoteFailure(remote) ? <FailureState kind={remote.kind} message={remote.message} onReopen={() => void load(false)} onExitCase={onExitCase} showExit /> : null}
      {mutation.kind === "offline" ? <RemoteStatus kind="reconnecting" message={mutation.message} /> : null}
      {isMutationFailure(mutation) ? <FailureState kind={mutation.kind} message={mutation.message} onReopen={() => void load(false)} onExitCase={onExitCase} /> : null}

      {projection ? (
        <>
          <dl className="p02-activity-summary">
            <div><dt>{copy("研究判断框架", "Decision framework")}</dt><dd>v{projection.surface.contract_version}</dd></div>
            <div><dt>{copy("研究状态", "Research status")}</dt><dd><StateBadge state={projection.surface.review_status} /></dd></div>
            <div><dt>{copy("研究进度项", "Research items")}</dt><dd>{projection.execution.work_units.length}</dd></div>
            <div><dt>{copy("记录更新", "Recorded updates")}</dt><dd>{projection.activity.events.length}</dd></div>
          </dl>

          <NextAction projection={projection} onBack={onBack} onOpenDecisionSurface={onOpenDecisionSurface} onOpenEvidence={onOpenEvidence} />

          <section className="p02-activity-section" aria-labelledby="p02-work-units-heading">
            <div className="p02-section-heading">
              <div>
                <p className="p02-eyebrow">{copy("研究进度", "Research progress")}</p>
                <h2 id="p02-work-units-heading">{copy("研究进度项", "Research items")}</h2>
              </div>
            </div>
            {projection.execution.work_units.length === 0 ? (
              <div className="p02-empty-panel">
                <div><h3>{copy("暂无研究进度项", "No research items")}</h3><p>{copy("此研究案例尚无研究进度样例记录。", "This case has no research-progress fixture history yet.")}</p></div>
              </div>
            ) : (
              <div className="p02-work-unit-list">
                {projection.execution.work_units.map((workUnit) => (
                  <article className="p02-work-unit-row" key={`${workUnit.work_unit_id}:${workUnit.work_unit_version}`}>
                    <div className="p02-work-unit-heading">
                      <div>
                        <p className="p02-mono-label">{workUnit.work_unit_id}</p>
                        <StateBadge state={workUnit.state} />
                      </div>
                      {workUnit.state === "pending" ? (
                        <button
                          type="button"
                          className="p02-secondary-button p02-cancel-button"
                          disabled={mutation.kind === "loading"}
                          onClick={() => void cancelWorkUnit(workUnit)}
                        >
                          <CircleStop size={16} aria-hidden="true" />
                          {mutation.kind === "loading" && mutation.workUnitId === workUnit.work_unit_id ? copy("正在取消", "Cancelling") : copy("取消待处理项", "Cancel pending item")}
                        </button>
                      ) : null}
                    </div>
                    <dl className="p02-work-unit-meta">
                      <div><dt>{copy("进度项版本", "Item version")}</dt><dd>v{workUnit.work_unit_version}</dd></div>
                      <div><dt>{copy("状态版本", "Status version")}</dt><dd>v{workUnit.state_version}</dd></div>
                      <div><dt>{copy("输入快照", "Input snapshot")}</dt><dd>{workUnit.input_head_digest}</dd></div>
                    </dl>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="p02-activity-section" aria-labelledby="p02-event-heading">
            <div className="p02-section-heading">
              <div>
                <p className="p02-eyebrow">{copy("研究记录", "Research record")}</p>
                <h2 id="p02-event-heading">{copy("更新记录", "Recorded updates")}</h2>
              </div>
            </div>
            {projection.activity.events.length === 0 ? (
              <div className="p02-empty-panel">
                <div><h3>{copy("暂无研究记录", "No research updates")}</h3><p>{copy("更新将按记录顺序显示在此处。", "Updates will appear here in recorded sequence order.")}</p></div>
              </div>
            ) : (
              <ol className="p02-event-list">
                {[...projection.activity.events].sort((left, right) => left.sequence - right.sequence).map((event) => (
                  <li key={event.event_id} className="p02-event-row">
                    <span className="p02-event-sequence">{event.sequence}</span>
                    <div className="p02-event-body">
                      <div className="p02-event-heading">
                        <strong>{labelToken(event.event_type)}</strong>
                        <time dateTime={event.occurred_at}>{formatDateTime(event.occurred_at)}</time>
                      </div>
                      <p className="p02-mono-label">{event.event_id}</p>
                      {event.typed_stop ? (
                        <p className="p02-typed-stop"><span>{copy("进度阻断说明", "Recorded stop")}</span><strong>{event.typed_stop}</strong></p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}

function NextAction({
  projection,
  onBack,
  onOpenDecisionSurface,
  onOpenEvidence,
}: {
  projection: Projection;
  onBack: () => void;
  onOpenDecisionSurface: () => void;
  onOpenEvidence: () => void;
}) {
  const { copy } = useWorkbenchLocale();
  const hasWorkUnit = projection.execution.work_units.length > 0;
  let title = copy("建立研究进度样例", "Create research-progress fixture");
  let detail = copy("研究判断框架已确认，尚未创建研究进度样例。", "The decision framework is confirmed; no research-progress fixture has been created.");
  if (projection.surface.review_status !== "accepted") {
    title = copy("查看研究判断框架", "Review decision framework");
    detail = copy("最新研究判断框架尚未确认，研究进度样例仍保持关闭。", "The latest decision framework is not confirmed, so the research-progress fixture remains closed.");
  } else if (hasWorkUnit) {
    title = copy("查看证据台账", "Open evidence ledger");
    detail = copy("研究进度样例已记录。可在证据台账中准备或检查 P36 候选样例，不会将其提升为正式证据。", "The research-progress fixture is recorded. Prepare or inspect the P36 candidate fixture in the evidence ledger without promoting evidence.");
  }
  return (
    <section className="p02-next-action" aria-labelledby="p02-next-action-heading">
      <div><p className="p02-eyebrow">{copy("下一步", "Next action")}</p><h2 id="p02-next-action-heading">{title}</h2><p>{detail}</p></div>
      {projection.surface.review_status !== "accepted" ? (
        <button type="button" className="p02-secondary-button" onClick={onOpenDecisionSurface}>
          <ExternalLink size={16} aria-hidden="true" />
          {copy("打开研究判断框架", "Open decision framework")}
        </button>
      ) : null}
      {hasWorkUnit ? (
        <button type="button" className="p02-secondary-button" onClick={onOpenEvidence}>
          <FileSearch size={16} aria-hidden="true" />
          {copy("打开证据台账", "Open evidence ledger")}
        </button>
      ) : null}
      {hasWorkUnit ? (
        <button type="button" className="p02-secondary-button" onClick={onBack}>
          <ArrowLeft size={16} aria-hidden="true" />
          {copy("返回研究概览", "Return to case overview")}
        </button>
      ) : null}
    </section>
  );
}

function FailureState({ kind, message, onReopen, onExitCase, showExit = false }: { kind: FailureKind; message: string; onReopen: () => void; onExitCase: () => void; showExit?: boolean }) {
  const { copy } = useWorkbenchLocale();
  return (
    <div className="p02-failure-stack">
      <RemoteStatus kind={kind} message={message} />
      {showExit ? (
        <button type="button" className="p02-primary-button" onClick={onExitCase}>
          <ArrowLeft size={16} aria-hidden="true" />
          {copy("返回研究任务", "Return to research cases")}
        </button>
      ) : null}
      {kind !== "permission" ? (
        <button type="button" className="p02-secondary-button" onClick={onReopen}>
          <RotateCcw size={16} aria-hidden="true" />
          {copy("重新打开当前视图", "Reopen current view")}
        </button>
      ) : null}
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const { labelToken } = useWorkbenchLocale();
  return <span className={`p02-status-badge p02-status-badge--${stateClass(state)}`}>{labelToken(state)}</span>;
}

function stateClass(state: string): string {
  if (state === "accepted") return "accepted";
  if (state === "cancelled" || state === "returned") return "returned";
  return "pending";
}

function remoteFailure(error: unknown, copy: Copy): RemoteState {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接样例 API。恢复连接后将重新加载研究进度。", "The fixture API could not be reached. Research progress will reload after reconnecting.") };
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
  return { kind: "error", message: copy("样例 API 未返回可用的研究进度响应。", "The fixture API did not return a usable research-progress response.") };
}

function isApiError(error: unknown): error is CaseApiError | PlanningApiError | ExecutionApiError {
  return error instanceof CaseApiError || error instanceof PlanningApiError || error instanceof ExecutionApiError;
}

function isOfflineError(error: unknown): boolean {
  return error instanceof TypeError || error instanceof ExecutionApiError && error.statusCode === 0 || error instanceof PlanningApiError && error.statusCode === 0;
}

function isRemoteFailure(remote: RemoteState): remote is Extract<RemoteState, { kind: FailureKind }> {
  return remote.kind === "permission" || remote.kind === "conflict" || remote.kind === "stale" || remote.kind === "error";
}

function isMutationFailure(mutation: MutationState): mutation is Extract<MutationState, { kind: FailureKind }> {
  return mutation.kind === "permission" || mutation.kind === "conflict" || mutation.kind === "stale" || mutation.kind === "error";
}

function idempotencyKey(ref: { current: IdempotencyRecord | null }, fingerprint: string): string {
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
