import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Calculator,
  Check,
  ClipboardCheck,
  FileSearch,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  Undo2,
} from "lucide-react";

import {
  CompleteLeadReviewCommand,
  CompileWorkpaperFixtureCommand,
  IntegrityApiClient,
  IntegrityApiError,
  LeadReviewDecision,
  NumericWorkbenchView,
  WorkpaperJudgmentView,
  WorkpaperView,
} from "../../api/integrity";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { LocalAnalysisPreview } from "../../shared/LocalAnalysisPreview";
import { RemoteStatus } from "../../shared/RemoteStatus";

type WorkpaperReviewProps = {
  caseId: string;
  online: boolean;
  onOpenEvidence: () => void;
  onOpenNumeric: () => void;
};

type FailureKind = "permission" | "conflict" | "stale" | "error";
type RemoteState =
  | { kind: "loading" }
  | { kind: "ready"; workpaper: WorkpaperView }
  | { kind: "empty"; numeric: NumericWorkbenchView | null; message: string }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type MutationState =
  | { kind: "idle" }
  | { kind: "loading"; target: "compile" | "review" }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type IdempotencyRecord = { fingerprint: string; key: string };
type Copy = (zhCN: string, en: string) => string;

const integrityApi = new IntegrityApiClient();

export function WorkpaperReview({ caseId, online, onOpenEvidence, onOpenNumeric }: WorkpaperReviewProps) {
  const { copy, labelToken } = useWorkbenchLocale();
  const copyRef = useRef(copy);
  copyRef.current = copy;
  const [remote, setRemote] = useState<RemoteState>({ kind: "loading" });
  const [mutation, setMutation] = useState<MutationState>({ kind: "idle" });
  const [selectedJudgmentId, setSelectedJudgmentId] = useState<string | null>(null);
  const [decision, setDecision] = useState<LeadReviewDecision>("admit_fixture_writer_preview");
  const [reason, setReason] = useState("");
  const compileAttemptRef = useRef<IdempotencyRecord | null>(null);
  const reviewAttemptRef = useRef<IdempotencyRecord | null>(null);

  const load = useCallback(async () => {
    const localCopy = copyRef.current;
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: localCopy("连接不可用。重新连接后可恢复研究底稿。", "Connection is unavailable. Reconnect to restore the research workpaper.") });
      return;
    }
    setRemote({ kind: "loading" });
    setMutation({ kind: "idle" });
    try {
      let numeric: NumericWorkbenchView;
      try {
        numeric = await integrityApi.getNumericWorkbench(caseId);
      } catch (error) {
        if (isMissing(error)) {
          setRemote({ kind: "empty", numeric: null, message: localCopy("请先编译数字夹具，再汇编 P36 研究底稿。", "Compile the numeric fixture before assembling the P36 research workpaper.") });
          return;
        }
        throw error;
      }
      try {
        const workpaper = await integrityApi.getWorkpaper(caseId);
        if (workpaper.status === "not_compiled") {
          setRemote({ kind: "empty", numeric, message: localCopy("数字血缘已就绪。请基于精确的数字工作区版本编译研究底稿。", "Numeric lineage is ready. Compile the research workpaper against the exact numeric workspace version.") });
        } else {
          setRemote({ kind: "ready", workpaper });
        }
      } catch (error) {
        if (isMissing(error)) setRemote({ kind: "empty", numeric, message: localCopy("数字血缘已就绪。请基于精确的数字工作区版本编译研究底稿。", "Numeric lineage is ready. Compile the research workpaper against the exact numeric workspace version.") });
        else throw error;
      }
    } catch (error) {
      setRemote(remoteFailure(error, localCopy));
    }
  }, [caseId, online]);

  useEffect(() => {
    void load();
  }, [load]);

  const workpaper = remote.kind === "ready" ? remote.workpaper : null;
  useEffect(() => {
    if (!workpaper) return;
    if (workpaper.judgments.some((judgment) => judgment.judgment_id === selectedJudgmentId)) return;
    setSelectedJudgmentId(workpaper.judgments[0]?.judgment_id ?? null);
  }, [selectedJudgmentId, workpaper]);

  const selectedJudgment = workpaper?.judgments.find((judgment) => judgment.judgment_id === selectedJudgmentId) ?? null;

  async function compileWorkpaper() {
    if (remote.kind !== "empty" || !remote.numeric) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请重新连接后再编译研究底稿。", "Connection is unavailable. Reconnect before compiling the research workpaper.") });
      return;
    }
    const fingerprint = `workpaper:${caseId}:${remote.numeric.numeric_workspace_version}`;
    const command: CompileWorkpaperFixtureCommand = {
      expected_numeric_workspace_version: remote.numeric.numeric_workspace_version,
      actor_ref: integrityApi.actorRef,
      idempotency_key: keyForAttempt(compileAttemptRef, fingerprint),
    };
    setMutation({ kind: "loading", target: "compile" });
    try {
      const compiled = await integrityApi.compileWorkpaperFixture(caseId, command);
      compileAttemptRef.current = null;
      setMutation({ kind: "idle" });
      setRemote({ kind: "ready", workpaper: compiled });
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  async function submitLeadReview(event: FormEvent) {
    event.preventDefault();
    if (!workpaper || !reason.trim()) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请重新连接后再提交负责人审阅。", "Connection is unavailable. Reconnect before submitting the lead review.") });
      return;
    }
    const fingerprint = [workpaper.workpaper_version, workpaper.content_digest, decision, reason.trim()].join(":");
    const command: CompleteLeadReviewCommand = {
      expected_workpaper_version: workpaper.workpaper_version,
      expected_content_digest: workpaper.content_digest,
      decision,
      reason: reason.trim(),
      actor_ref: integrityApi.actorRef,
      idempotency_key: keyForAttempt(reviewAttemptRef, fingerprint),
    };
    setMutation({ kind: "loading", target: "review" });
    try {
      const reviewed = await integrityApi.completeLeadReview(caseId, command);
      reviewAttemptRef.current = null;
      setMutation({ kind: "idle" });
      setRemote({ kind: "ready", workpaper: reviewed });
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  return (
    <section className="p02-workspace vt2-workspace" aria-label={copy("研究底稿审阅", "Research workpaper review")}>
      <button type="button" className="p02-back-button" onClick={onOpenNumeric}>
        <ArrowLeft size={16} aria-hidden="true" /> {copy("数字核验", "Numeric verification")}
      </button>

      <div className="p02-page-heading vt2-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("研究底稿", "Research workpaper")}</p>
          <h1>{caseId}</h1>
          {workpaper ? <p className="p02-heading-meta">{copy(`底稿版本 ${workpaper.workpaper_version}，内容校验摘要：${workpaper.content_digest}`, `Workpaper v${workpaper.workpaper_version}, content digest: ${workpaper.content_digest}`)}</p> : null}
        </div>
        <div className="p02-page-actions">
          <button type="button" className="p02-secondary-button" onClick={onOpenEvidence}><FileSearch size={16} aria-hidden="true" /> {copy("证据与反证", "Evidence & counterevidence")}</button>
          <button type="button" className="p02-secondary-button" onClick={onOpenNumeric}><Calculator size={16} aria-hidden="true" /> {copy("数字核验", "Numeric verification")}</button>
          <button type="button" className="p02-icon-button" title={copy("刷新研究底稿", "Refresh research workpaper")} aria-label={copy("刷新研究底稿", "Refresh research workpaper")} onClick={() => void load()}><RefreshCcw size={17} aria-hidden="true" /></button>
        </div>
      </div>

      <div className="vt2-boundary-banner"><ShieldCheck size={18} aria-hidden="true" /><div><strong>{copy("夹具审阅边界", "Fixture review boundary")}</strong><span>{copy("负责人准入仅可打开夹具预览；写作执行、运行时提升及发布证据仍被禁止。", "Lead admission can open fixture preview only. Writer execution, runtime promotion, and release evidence remain forbidden.")}</span></div></div>

      <LocalAnalysisPreview caseId={caseId} online={online} view="workpaper" />

      {remote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载数字血缘与研究底稿投影。", "Loading numeric lineage and research workpaper projections.")} /> : null}
      {remote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} onRetry={() => void load()} /> : null}
      {isRemoteFailure(remote) ? <FailureState kind={remote.kind} message={remote.message} onRetry={() => void load()} /> : null}
      {mutation.kind === "offline" ? <RemoteStatus kind="reconnecting" message={mutation.message} /> : null}
      {isMutationFailure(mutation) ? <FailureState kind={mutation.kind} message={mutation.message} onRetry={() => void load()} /> : null}

      {remote.kind === "empty" ? (
        <section className="vt2-compile-panel" aria-labelledby="vt2-workpaper-empty-heading">
          <div><p className="p02-eyebrow">{copy("编译前提", "Compilation prerequisite")}</p><h2 id="vt2-workpaper-empty-heading">{copy("研究底稿尚未编译", "Research workpaper not compiled")}</h2><p>{remote.message}</p><code>{remote.numeric ? `numeric_workspace_version:${remote.numeric.numeric_workspace_version}` : "numeric_workspace:missing"}</code></div>
          {remote.numeric ? <button type="button" className="p02-primary-button" disabled={mutation.kind === "loading"} onClick={() => void compileWorkpaper()}><ClipboardCheck size={16} aria-hidden="true" />{mutation.kind === "loading" ? copy("正在编译", "Compiling") : copy("编译研究底稿夹具", "Compile research workpaper fixture")}</button> : <button type="button" className="p02-secondary-button" onClick={onOpenNumeric}><Calculator size={16} aria-hidden="true" />{copy("打开数字核验", "Open numeric verification")}</button>}
        </section>
      ) : null}

      {workpaper ? (
        <>
          <dl className="vt2-meta-strip">
            <div><dt>{copy("判断卡", "Judgments")}</dt><dd>{workpaper.judgments.length}</dd></div>
            <div><dt>{copy("状态", "Status")}</dt><dd>{labelToken(workpaper.status)}</dd></div>
            <div><dt>{copy("证据", "Evidence")}</dt><dd>v{workpaper.evidence_workspace_version}</dd></div>
            <div><dt>{copy("数字", "Numeric")}</dt><dd>v{workpaper.numeric_workspace_version}</dd></div>
            <div><dt>{copy("负责人审阅", "Lead review")}</dt><dd>{workpaper.lead_review ? labelToken(workpaper.lead_review.decision) : copy("待处理", "Pending")}</dd></div>
          </dl>

          {workpaper.judgments.length === 0 ? <RemoteStatus kind="empty" message={copy("已编译的研究底稿不包含判断卡。", "The compiled research workpaper contains no judgments.")} /> : (
            <div className="vt2-workpaper-layout">
              <nav className="vt2-judgment-list" aria-label={copy("单元格判断", "Cell judgments")}>
                <div className="vt2-section-heading"><div><p className="p02-eyebrow">{copy(`${workpaper.judgments.length} 个单元格`, `${workpaper.judgments.length} cells`)}</p><h2>{copy("研究判断", "Research judgments")}</h2></div></div>
                {workpaper.judgments.map((judgment, index) => (
                  <button type="button" key={judgment.judgment_id} className={selectedJudgmentId === judgment.judgment_id ? "is-selected" : undefined} aria-pressed={selectedJudgmentId === judgment.judgment_id} onClick={() => setSelectedJudgmentId(judgment.judgment_id)}>
                    <span>{index + 1}</span><span><strong>{labelToken(judgment.cell_id)}</strong><small>{labelToken(judgment.owner_role)}</small></span><em>{labelToken(judgment.judgment_status)}</em>
                  </button>
                ))}
              </nav>
              <main className="vt2-judgment-detail">
                {selectedJudgment ? <JudgmentDetail judgment={selectedJudgment} /> : null}
              </main>
            </div>
          )}

          <section className="vt2-lead-review" aria-labelledby="vt2-lead-review-heading">
            <div className="vt2-section-heading"><div><p className="p02-eyebrow">{copy("精确审阅关口", "Exact review gate")}</p><h2 id="vt2-lead-review-heading">{copy("负责人审阅", "Lead review")}</h2></div><code>v{workpaper.workpaper_version} / {workpaper.content_digest}</code></div>
            {workpaper.lead_review ? (
              <div className="vt2-review-result">
                <div><span className="vt2-status-badge">{copy("审阅人决策", "Reviewer decision")}</span><h3>{labelToken(workpaper.lead_review.decision)}</h3><p>{workpaper.lead_review.reason}</p><code>{workpaper.lead_review.lead_review_id}</code></div>
                <div><span className="vt2-status-badge">{copy("写作准入", "Writer admission")}</span>{workpaper.writer_admission ? <><h3>{labelToken(workpaper.writer_admission.status)}</h3><p>{workpaper.writer_admission.boundary}</p><strong>{workpaper.writer_admission.fixture_only ? copy("仅夹具写作准入", "Fixture-only writer admission") : copy("非夹具准入", "Non-fixture admission")}</strong><small>{workpaper.writer_admission.writer_execution_authorized ? copy("已授权写作执行", "Writer execution authorized") : copy("未授权写作执行", "No writer execution")}</small></> : <><h3>{copy("未准入", "Not admitted")}</h3><p>{copy("研究底稿已退回修复，未生成 WriterAdmission。", "The research workpaper was returned for repair. No WriterAdmission was emitted.")}</p></>}</div>
              </div>
            ) : (
              <form className="vt2-review-form" onSubmit={submitLeadReview}>
                <div className="vt2-decision-control" role="group" aria-label={copy("负责人审阅决策", "Lead review decision")}>
                  <button type="button" className={decision === "admit_fixture_writer_preview" ? "is-selected" : undefined} aria-pressed={decision === "admit_fixture_writer_preview"} onClick={() => setDecision("admit_fixture_writer_preview")}><Check size={16} aria-hidden="true" /><span><strong>{copy("准入夹具预览", "Admit fixture preview")}</strong><small>{copy("不执行写作", "No writer execution")}</small></span></button>
                  <button type="button" className={decision === "return_for_repair" ? "is-selected" : undefined} aria-pressed={decision === "return_for_repair"} onClick={() => setDecision("return_for_repair")}><Undo2 size={16} aria-hidden="true" /><span><strong>{copy("退回修复", "Return for repair")}</strong><small>{copy("不授予准入", "No admission")}</small></span></button>
                </div>
                <label>{copy("审阅理由", "Review reason")}<textarea required value={reason} onChange={(event) => setReason(event.target.value)} placeholder={copy("说明为何应将这一精确底稿版本准入夹具预览，或将其退回。", "State why this exact workpaper version should be admitted for fixture preview or returned.")} /></label>
                <div className="vt2-review-submit"><p>{copy("命令将绑定上方展示的精确底稿版本和内容校验摘要。", "The command binds the exact workpaper version and content digest shown above.")}</p><button type="submit" className="p02-primary-button" disabled={!reason.trim() || mutation.kind === "loading"}><ClipboardCheck size={16} aria-hidden="true" />{mutation.kind === "loading" ? copy("正在提交", "Submitting") : copy("提交负责人审阅", "Submit lead review")}</button></div>
              </form>
            )}
          </section>

          <section className="vt2-hard-boundaries" aria-labelledby="vt2-workpaper-boundaries"><h2 id="vt2-workpaper-boundaries">{copy("硬性边界", "Hard boundaries")}</h2><dl>{Object.entries(workpaper.hard_boundaries).map(([key, value]) => <div key={key}><dt>{labelToken(key)}</dt><dd>{String(value)}</dd></div>)}</dl></section>
        </>
      ) : null}
    </section>
  );
}

function JudgmentDetail({ judgment }: { judgment: WorkpaperJudgmentView }) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  return (
    <article>
      <header><div><p className="p02-eyebrow">{labelToken(judgment.owner_role)}</p><h2>{labelToken(judgment.cell_id)}</h2></div><div><span className="vt2-status-badge">{labelToken(judgment.judgment_status)}</span><small>{labelToken(judgment.confidence)} {copy("置信度", "confidence")}</small></div></header>
      <section className="vt2-judgment-copy"><h3>{copy("研究判断", "Research judgment")}</h3><p>{localizeFixtureText(judgment.judgment)}</p></section>
      <div className="vt2-reference-grid">
        <ReferenceList title={copy("证据引用", "Evidence refs")} values={judgment.evidence_refs} />
        <ReferenceList title={copy("数字引用", "Numeric refs")} values={judgment.numeric_refs} />
        <ReferenceList title={copy("修复结果引用", "Repair outcome refs")} values={judgment.repair_outcome_refs} />
      </div>
      <section className="vt2-judgment-section"><h3>{copy("反证与结论边界", "Counterevidence and conclusion boundary")}</h3><p>{localizeFixtureText(judgment.counter_thesis)}</p></section>
      <section className="vt2-judgment-section"><h3>{copy("可能改变结论的条件", "What would change")}</h3><p>{localizeFixtureText(judgment.what_would_change)}</p></section>
      <section className="vt2-judgment-section"><h3>{copy("剩余缺口", "Remaining gaps")}</h3>{judgment.remaining_gaps.length ? <ul>{judgment.remaining_gaps.map((gap) => <li key={gap}>{localizeFixtureText(gap)}</li>)}</ul> : <p>{copy("此夹具判断未记录剩余缺口。", "No remaining gaps are recorded for this fixture judgment.")}</p>}</section>
    </article>
  );
}

function ReferenceList({ title, values }: { title: string; values: string[] }) {
  const { copy } = useWorkbenchLocale();
  return <section><h3>{title}</h3>{values.length ? <ul>{values.map((value) => <li key={value}><code>{value}</code></li>)}</ul> : <p>{copy("无", "None")}</p>}</section>;
}

function FailureState({ kind, message, onRetry }: { kind: FailureKind; message: string; onRetry: () => void }) {
  const { copy } = useWorkbenchLocale();
  return <div className="p02-failure-stack"><RemoteStatus kind={kind} message={message} />{kind !== "permission" ? <button type="button" className="p02-secondary-button" onClick={onRetry}><RotateCcw size={16} aria-hidden="true" />{copy("重新打开当前视图", "Reopen current")}</button> : null}</div>;
}

function isMissing(error: unknown): boolean {
  return error instanceof IntegrityApiError && (error.statusCode === 404 || error.code.includes("not_found") || error.code.includes("not_compiled"));
}

function remoteFailure(error: unknown, copy: Copy): RemoteState {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接夹具 API。重新连接后将重新加载研究底稿数据。", "The fixture API could not be reached. Research workpaper data will reload after reconnecting.") };
  return apiFailure(error, copy);
}

function mutationFailure(error: unknown, copy: Copy): MutationState {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接夹具 API。请重新连接后再发送命令。", "The fixture API could not be reached. Reconnect before sending the command.") };
  return apiFailure(error, copy);
}

function apiFailure(error: unknown, copy: Copy): { kind: FailureKind; message: string } {
  if (error instanceof IntegrityApiError) {
    const kind = error.code === "permission_denied" || error.statusCode === 403 ? "permission"
      : error.code.includes("stale") || error.code.includes("superseded") ? "stale"
        : error.code.includes("conflict") || error.statusCode === 409 ? "conflict" : "error";
    return { kind, message: error.traceId ? `${error.message} ${copy("追踪 ID", "Trace ID")}: ${error.traceId}` : error.message };
  }
  return { kind: "error", message: copy("夹具 API 未返回可用的研究底稿响应。", "The fixture API did not return a usable research workpaper response.") };
}

function isOfflineError(error: unknown): boolean {
  return error instanceof TypeError || error instanceof IntegrityApiError && error.statusCode === 0;
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
