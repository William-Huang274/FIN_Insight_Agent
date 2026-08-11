import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  FileText,
  MessageSquare,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  Undo2,
} from "lucide-react";

import {
  CompileDeliverablePreviewCommand,
  DeliverablePreviewView,
  DeliverableReviewDecision,
  DeliverableTraceView,
  DeliverablesApiClient,
  DeliverablesApiError,
  MaterialClaimView,
  ReviewDeliverableVersionCommand,
  TraceDirection,
  TraceNodeType,
  TraceNodeView,
} from "../../api/deliverables";
import { IntegrityApiClient, WorkpaperView } from "../../api/integrity";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { LocalAnalysisPreview } from "../../shared/LocalAnalysisPreview";
import { RemoteStatus } from "../../shared/RemoteStatus";

type DeliverableReviewProps = {
  caseId: string;
  online: boolean;
  onOpenWorkpaper: () => void;
};

type FailureKind = "permission" | "conflict" | "stale" | "error";
type RemoteState =
  | { kind: "loading" }
  | { kind: "ready"; deliverable: DeliverablePreviewView }
  | { kind: "empty"; message: string; workpaper: WorkpaperView | null }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type TraceState =
  | { kind: "loading" }
  | { kind: "ready"; trace: DeliverableTraceView }
  | { kind: "empty"; message: string }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type MutationState =
  | { kind: "idle" }
  | { kind: "loading"; target: "compile" | "review" }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type IdempotencyRecord = { fingerprint: string; key: string };
type RendererTab = "html" | "markdown";
type Copy = (zhCN: string, en: string) => string;

const deliverablesApi = new DeliverablesApiClient();
const integrityApi = new IntegrityApiClient();
const SAFE_TRACE_NODE_TYPES = new Set<TraceNodeType>([
  "material_claim",
  "evidence_candidate",
  "numeric_fact",
  "repair_outcome",
  "explicit_gap",
]);

export function DeliverableReview({ caseId, online, onOpenWorkpaper }: DeliverableReviewProps) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const copyRef = useRef(copy);
  copyRef.current = copy;
  const [remote, setRemote] = useState<RemoteState>({ kind: "loading" });
  const [traceState, setTraceState] = useState<TraceState>({ kind: "loading" });
  const [mutation, setMutation] = useState<MutationState>({ kind: "idle" });
  const [renderer, setRenderer] = useState<RendererTab>("html");
  const [decision, setDecision] = useState<DeliverableReviewDecision>("comment");
  const [comment, setComment] = useState("");
  const [traceDirection, setTraceDirection] = useState<TraceDirection>("claim_to_source");
  const [selectedTraceNodeId, setSelectedTraceNodeId] = useState<string | null>(null);
  const compileAttemptRef = useRef<IdempotencyRecord | null>(null);
  const reviewAttemptRef = useRef<IdempotencyRecord | null>(null);

  const loadTrace = useCallback(async (deliverable: DeliverablePreviewView) => {
    const localCopy = copyRef.current;
    setTraceState({ kind: "loading" });
    try {
      const trace = await deliverablesApi.getCaseTrace(caseId);
      setTraceState({ kind: "ready", trace });
    } catch (error) {
      if (isMissing(error)) {
        setTraceState({ kind: "empty", message: localCopy("此结论版本没有可用的追溯清单。", "No trace manifest is available for this conclusion version.") });
      } else {
        setTraceState(traceFailure(error, localCopy));
      }
    }
  }, [caseId]);

  const loadCompilePrerequisite = useCallback(async (message: string) => {
    const localCopy = copyRef.current;
    try {
      const workpaper = await integrityApi.getWorkpaper(caseId);
      const admission = workpaper.writer_admission;
      if (!admission || !admission.fixture_only || admission.writer_execution_authorized) {
        setRemote({ kind: "empty", message: localCopy("编译预览前需要已准入的夹具研究底稿。", "An admitted fixture research workpaper is required before compiling a preview."), workpaper: null });
        return;
      }
      setRemote({ kind: "empty", message, workpaper });
    } catch (error) {
      if (isOfflineError(error)) {
        setRemote({ kind: "offline", message: localCopy("连接不可用。请重新连接后加载研究底稿准入。", "Connection is unavailable. Reconnect to load the research workpaper admission.") });
        return;
      }
      setRemote({ kind: "empty", message: localCopy("编译预览前需要已准入的夹具研究底稿。", "An admitted fixture research workpaper is required before compiling a preview."), workpaper: null });
    }
  }, [caseId]);

  const load = useCallback(async () => {
    const localCopy = copyRef.current;
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: localCopy("连接不可用。重新连接后可恢复研究结论。", "Connection is unavailable. Reconnect to restore research conclusions.") });
      setTraceState({ kind: "offline", message: localCopy("连接不可用。", "Connection is unavailable.") });
      return;
    }
    setRemote({ kind: "loading" });
    setMutation({ kind: "idle" });
    try {
      const deliverable = await deliverablesApi.getDeliverableHead(caseId);
      if (deliverable.status === "not_compiled") {
        await loadCompilePrerequisite(localCopy("此案例尚无研究结论预览。", "No research conclusion preview is available for this case."));
        setTraceState({ kind: "empty", message: localCopy("生成结论版本后即可查看追溯。", "Trace becomes available with a conclusion version.") });
        return;
      }
      setRemote({ kind: "ready", deliverable });
      void loadTrace(deliverable);
    } catch (error) {
      if (isMissing(error)) {
        await loadCompilePrerequisite(localCopy("此案例尚无研究结论预览。", "No research conclusion preview is available for this case."));
        setTraceState({ kind: "empty", message: localCopy("生成结论版本后即可查看追溯。", "Trace becomes available with a conclusion version.") });
      } else {
        setRemote(remoteFailure(error, localCopy));
        setTraceState({ kind: "empty", message: localCopy("加载研究结论后方可查看追溯。", "Trace is unavailable until research conclusions can be loaded.") });
      }
    }
  }, [caseId, loadCompilePrerequisite, loadTrace, online]);

  useEffect(() => {
    void load();
  }, [load]);

  const deliverable = remote.kind === "ready" ? remote.deliverable : null;
  const terminalDecision = deliverable?.review_actions.find((action) => action.action_type === "return_for_repair" || action.action_type === "accept_fixture_preview");
  const trace = traceState.kind === "ready" ? traceState.trace : null;
  const claims = deliverable?.material_claims ?? [];
  const safeTraceNodes = useMemo(() => trace?.nodes.filter((node) => SAFE_TRACE_NODE_TYPES.has(node.node_type)) ?? [], [trace]);

  useEffect(() => {
    if (!deliverable) return;
    const selectedClaimExists = claims.some((claim) => claim.claim_id === selectedTraceNodeId);
    const selectedNodeExists = safeTraceNodes.some((node) => node.node_id === selectedTraceNodeId);
    if (!selectedTraceNodeId || (!selectedClaimExists && !selectedNodeExists)) {
      setSelectedTraceNodeId(claims[0]?.claim_id ?? safeTraceNodes[0]?.node_id ?? null);
    }
  }, [claims, deliverable, safeTraceNodes, selectedTraceNodeId]);

  async function compilePreview() {
    if (remote.kind !== "empty" || !remote.workpaper?.writer_admission) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请重新连接后再编译研究结论预览。", "Connection is unavailable. Reconnect before compiling the research conclusion preview.") });
      return;
    }
    const command: CompileDeliverablePreviewCommand = {
      expected_workpaper_version: remote.workpaper.workpaper_version,
      expected_workpaper_content_digest: remote.workpaper.content_digest,
      writer_admission_id: remote.workpaper.writer_admission.writer_admission_id,
      actor_ref: deliverablesApi.actorRef,
      idempotency_key: keyForAttempt(compileAttemptRef, `deliverable:${caseId}:${remote.workpaper.workpaper_version}:${remote.workpaper.content_digest}:${remote.workpaper.writer_admission.writer_admission_id}`),
    };
    setMutation({ kind: "loading", target: "compile" });
    try {
      const compiled = await deliverablesApi.compileDeliverablePreviewFixture(caseId, command);
      compileAttemptRef.current = null;
      setMutation({ kind: "idle" });
      setRemote({ kind: "ready", deliverable: compiled });
      void loadTrace(compiled);
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  async function submitReview(event: FormEvent) {
    event.preventDefault();
    if (!deliverable || terminalDecision || !comment.trim()) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请重新连接后再提交审阅操作。", "Connection is unavailable. Reconnect before submitting the review action.") });
      return;
    }
    const fingerprint = [
      deliverable.artifact_version,
      deliverable.content_digest,
      deliverable.canonical_presentation_digest,
      decision,
      comment.trim(),
    ].join(":");
    const command: ReviewDeliverableVersionCommand = {
      expected_artifact_version: deliverable.artifact_version,
      expected_content_digest: deliverable.content_digest,
      expected_canonical_presentation_digest: deliverable.canonical_presentation_digest,
      action_type: decision,
      reason: comment.trim(),
      actor_ref: deliverablesApi.actorRef,
      idempotency_key: keyForAttempt(reviewAttemptRef, fingerprint),
    };
    setMutation({ kind: "loading", target: "review" });
    try {
      const reviewed = await deliverablesApi.createDeliverableReviewAction(deliverable.deliverable_id, deliverable.artifact_version, command);
      reviewAttemptRef.current = null;
      setMutation({ kind: "idle" });
      setComment("");
      setRemote({ kind: "ready", deliverable: reviewed });
      void loadTrace(reviewed);
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  function selectClaim(claimId: string) {
    setTraceDirection("claim_to_source");
    setSelectedTraceNodeId(claimId);
  }

  function selectTraceDirection(direction: TraceDirection) {
    setTraceDirection(direction);
    setSelectedTraceNodeId(
      direction === "claim_to_source"
        ? claims[0]?.claim_id ?? null
        : safeTraceNodes.find((node) => node.node_type !== "material_claim")?.node_id ?? null,
    );
  }

  return (
    <section className="p02-workspace vt3-workspace" aria-label={copy("研究结论审阅", "Research conclusion review")}>
      <button type="button" className="p02-back-button" onClick={onOpenWorkpaper}>
        <ArrowLeft size={16} aria-hidden="true" /> {copy("研究底稿", "Research workpaper")}
      </button>

      <div className="p02-page-heading vt3-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("研究结论", "Research conclusions")}</p>
          <h1>{deliverable ? localizeFixtureText(deliverable.title) : caseId}</h1>
          {deliverable ? <p className="p02-heading-meta">{deliverable.artifact_version_id}</p> : null}
        </div>
        <div className="p02-page-actions">
          <button type="button" className="p02-secondary-button" onClick={onOpenWorkpaper}><FileText size={16} aria-hidden="true" /> {copy("研究底稿", "Research workpaper")}</button>
          <button type="button" className="p02-icon-button" title={copy("刷新研究结论", "Refresh research conclusions")} aria-label={copy("刷新研究结论", "Refresh research conclusions")} onClick={() => void load()}><RefreshCcw size={17} aria-hidden="true" /></button>
        </div>
      </div>

      <div className="vt2-boundary-banner"><ShieldCheck size={18} aria-hidden="true" /><div><strong>{copy("仅限内部演示", "Internal fixture only")}</strong><span>{copy("当前为不改变原始版本或校验摘要的中文阅读视图；结论不可执行，也不是发布证据。", "This research conclusion is fixture-only, non-executable, and not release evidence.")}</span></div></div>

      <LocalAnalysisPreview caseId={caseId} online={online} view="writer" />

      {remote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载最新研究结论版本。", "Loading the latest research conclusion version.")} /> : null}
      {remote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} onRetry={() => void load()} /> : null}
      {isRemoteFailure(remote) ? <FailureState kind={remote.kind} message={remote.message} onRetry={() => void load()} /> : null}
      {mutation.kind === "offline" ? <RemoteStatus kind="reconnecting" message={mutation.message} /> : null}
      {isMutationFailure(mutation) ? <FailureState kind={mutation.kind} message={mutation.message} onRetry={() => void load()} /> : null}

      {remote.kind === "empty" ? (
        <section className="vt3-empty-panel" aria-labelledby="vt3-empty-heading">
          <div><p className="p02-eyebrow">{copy("预览", "Preview")}</p><h2 id="vt3-empty-heading">{copy("暂无研究结论版本", "No research conclusion version")}</h2><p>{remote.message}</p></div>
          {remote.workpaper ? <button type="button" className="p02-primary-button" disabled={mutation.kind === "loading"} onClick={() => void compilePreview()}><FileText size={16} aria-hidden="true" />{mutation.kind === "loading" ? copy("正在编译", "Compiling") : copy("编译预览", "Compile preview")}</button> : <button type="button" className="p02-secondary-button" onClick={onOpenWorkpaper}><FileText size={16} aria-hidden="true" /> {copy("研究底稿", "Research workpaper")}</button>}
        </section>
      ) : null}

      {deliverable ? (
        <>
          <IdentityStrip deliverable={deliverable} />

          <div className="vt3-main-grid">
            <section className="vt3-preview-panel" aria-labelledby="vt3-preview-heading">
              <div className="vt3-section-heading">
                <h2 id="vt3-preview-heading">{copy("预览", "Preview")}</h2>
                <div className="vt3-renderer-tabs" role="tablist" aria-label={copy("结论格式", "Conclusion format")}>
                  <button type="button" role="tab" aria-selected={renderer === "html"} className={renderer === "html" ? "is-selected" : undefined} onClick={() => setRenderer("html")}>{copy("HTML", "HTML")}</button>
                  <button type="button" role="tab" aria-selected={renderer === "markdown"} className={renderer === "markdown" ? "is-selected" : undefined} onClick={() => setRenderer("markdown")}>{copy("Markdown", "Markdown")}</button>
                </div>
              </div>
              {renderer === "html" ? (
                <HtmlPreview content={deliverable.renderings.html.content} />
              ) : (
                <MarkdownPreview content={deliverable.renderings.markdown.content} />
              )}
            </section>

            <section className="vt3-claims-panel" aria-labelledby="vt3-claims-heading">
              <div className="vt3-section-heading"><h2 id="vt3-claims-heading">{copy("核心结论", "Material claims")}</h2></div>
              {claims.length ? <ClaimList claims={claims} selectedClaimId={selectedTraceNodeId} onSelect={selectClaim} /> : <RemoteStatus kind="empty" message={copy("此结论版本没有可用的核心结论。", "No material claims are available for this conclusion version.")} />}
            </section>
          </div>

          <ReviewPanel
            deliverable={deliverable}
            terminalDecision={terminalDecision}
            decision={decision}
            comment={comment}
            submitting={mutation.kind === "loading" && mutation.target === "review"}
            onDecision={setDecision}
            onComment={setComment}
            onSubmit={submitReview}
          />

          <TraceExplorer
            traceState={traceState}
            claims={claims}
            trace={trace}
            nodes={safeTraceNodes}
            direction={traceDirection}
            selectedNodeId={selectedTraceNodeId}
            onDirection={selectTraceDirection}
            onSelectNode={setSelectedTraceNodeId}
            onRetry={() => deliverable && void loadTrace(deliverable)}
          />
        </>
      ) : null}
    </section>
  );
}

function IdentityStrip({ deliverable }: { deliverable: DeliverablePreviewView }) {
  const { copy, labelToken } = useWorkbenchLocale();
  return (
    <dl className="vt3-identity-strip">
      <div><dt>{copy("结论版本", "Conclusion version")}</dt><dd>{deliverable.artifact_version_id}</dd></div>
      <div><dt>{copy("版本号", "Version")}</dt><dd>{deliverable.artifact_version}</dd></div>
      <div><dt>{copy("内容校验摘要", "Content digest")}</dt><dd><small>{deliverable.content_digest}</small></dd></div>
      <div><dt>{copy("呈现校验摘要", "Presentation digest")}</dt><dd><small>{deliverable.canonical_presentation_digest}</small></dd></div>
      <div><dt>{copy("状态", "Status")}</dt><dd>{labelToken(deliverable.status)}</dd></div>
    </dl>
  );
}

function HtmlPreview({ content }: { content: string }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  return <iframe className="vt3-html-preview" title={copy("HTML 阅读视图", "HTML preview")} sandbox="" srcDoc={localizeFixtureText(content)} />;
}

function MarkdownPreview({ content }: { content: string }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  return <pre className="vt3-markdown-preview" aria-label={copy("Markdown 阅读视图", "Markdown preview")}>{localizeFixtureText(content)}</pre>;
}

function ClaimList({ claims, selectedClaimId, onSelect }: { claims: MaterialClaimView[]; selectedClaimId: string | null; onSelect: (claimId: string) => void }) {
  const { labelToken, localizeFixtureText } = useWorkbenchLocale();
  return <div className="vt3-claim-list">
    {claims.map((claim) => (
      <button type="button" key={claim.claim_id} className={selectedClaimId === claim.claim_id ? "is-selected" : undefined} aria-pressed={selectedClaimId === claim.claim_id} onClick={() => onSelect(claim.claim_id)}>
        <strong>{localizeFixtureText(claim.claim_text)}</strong>
        <span>{labelToken(claim.claim_kind)}</span>
        <code>{claim.claim_id}</code>
      </button>
    ))}
  </div>
}

function ReviewPanel({ deliverable, terminalDecision, decision, comment, submitting, onDecision, onComment, onSubmit }: {
  deliverable: DeliverablePreviewView;
  terminalDecision: DeliverablePreviewView["review_actions"][number] | undefined;
  decision: DeliverableReviewDecision;
  comment: string;
  submitting: boolean;
  onDecision: (decision: DeliverableReviewDecision) => void;
  onComment: (comment: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  return (
    <section className="vt3-review-panel" aria-labelledby="vt3-review-heading">
      <div className="vt3-section-heading"><h2 id="vt3-review-heading">{copy("结论审阅", "Conclusion review")}</h2><code>{deliverable.artifact_version_id}</code></div>
      <ReviewHistory actions={deliverable.review_actions} />
      {terminalDecision ? <div className="vt3-terminal-review"><strong>{labelToken(terminalDecision.action_type)}</strong><span>{localizeFixtureText(terminalDecision.reason)}</span></div> : (
        <form className="vt3-review-form" onSubmit={onSubmit}>
          <div className="vt3-decision-control" role="group" aria-label={copy("审阅操作", "Review action")}>
            <button type="button" className={decision === "comment" ? "is-selected" : undefined} aria-pressed={decision === "comment"} onClick={() => onDecision("comment")}><MessageSquare size={16} aria-hidden="true" /> {copy("评论", "Comment")}</button>
            <button type="button" className={decision === "return_for_repair" ? "is-selected" : undefined} aria-pressed={decision === "return_for_repair"} onClick={() => onDecision("return_for_repair")}><Undo2 size={16} aria-hidden="true" /> {copy("退回", "Return")}</button>
            <button type="button" className={decision === "accept_fixture_preview" ? "is-selected" : undefined} aria-pressed={decision === "accept_fixture_preview"} onClick={() => onDecision("accept_fixture_preview")}><Check size={16} aria-hidden="true" /> {copy("接受", "Accept")}</button>
          </div>
          <label>{copy("评论", "Comment")}<textarea required value={comment} onChange={(event) => onComment(event.target.value)} /></label>
          <div className="vt3-review-submit"><code>{deliverable.content_digest}</code><button type="submit" className="p02-primary-button" disabled={!comment.trim() || submitting}>{submitting ? copy("正在提交", "Submitting") : copy("提交审阅", "Submit review")}</button></div>
        </form>
      )}
    </section>
  );
}

function ReviewHistory({ actions }: { actions: DeliverablePreviewView["review_actions"] }) {
  const { copy, formatDateTime, labelToken, localizeFixtureText } = useWorkbenchLocale();
  if (!actions.length) return <p className="vt3-no-history">{copy("暂无审阅操作。", "No review actions.")}</p>;
  return <ol className="vt3-review-history">{actions.map((action) => <li key={action.review_action_id}><strong>{labelToken(action.action_type)}</strong><span>{localizeFixtureText(action.reason)}</span><small>{action.actor_ref} / {formatDateTime(action.reviewed_at)}</small></li>)}</ol>;
}

function TraceExplorer({ traceState, claims, trace, nodes, direction, selectedNodeId, onDirection, onSelectNode, onRetry }: {
  traceState: TraceState;
  claims: MaterialClaimView[];
  trace: DeliverableTraceView | null;
  nodes: TraceNodeView[];
  direction: TraceDirection;
  selectedNodeId: string | null;
  onDirection: (direction: TraceDirection) => void;
  onSelectNode: (nodeId: string) => void;
  onRetry: () => void;
}) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  const selectedClaim = claims.find((claim) => claim.claim_id === selectedNodeId) ?? null;
  const selectedNode = nodes.find((node) => node.node_id === selectedNodeId) ?? null;
  const subjects = direction === "claim_to_source" ? claims.map((claim) => ({ id: claim.claim_id, label: localizeFixtureText(claim.claim_text), type: "material_claim" })) : nodes.filter((node) => node.node_type !== "material_claim").map((node) => ({ id: node.node_id, label: localizeFixtureText(node.display_label), type: node.node_type }));
  const related = trace ? relatedTraceNodes(trace, nodes, selectedNodeId, direction) : [];

  return (
    <section className="vt3-trace-panel" aria-labelledby="vt3-trace-heading">
      <div className="vt3-section-heading"><h2 id="vt3-trace-heading">{copy("证据与反证追溯", "Evidence & counterevidence trace")}</h2>{trace ? <code>{trace.manifest_id}</code> : null}</div>
      <div className="vt3-trace-tabs" role="tablist" aria-label={copy("追溯方向", "Trace direction")}>
        <button type="button" role="tab" aria-selected={direction === "claim_to_source"} className={direction === "claim_to_source" ? "is-selected" : undefined} onClick={() => onDirection("claim_to_source")}>{copy("结论至来源", "Claim to source")}</button>
        <button type="button" role="tab" aria-selected={direction === "source_to_claim"} className={direction === "source_to_claim" ? "is-selected" : undefined} onClick={() => onDirection("source_to_claim")}>{copy("来源至结论", "Source to claim")}</button>
      </div>
      {traceState.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载追溯清单。", "Loading the trace manifest.")} /> : null}
      {traceState.kind === "offline" ? <RemoteStatus kind="reconnecting" message={traceState.message} onRetry={onRetry} /> : null}
      {traceState.kind === "empty" ? <RemoteStatus kind="empty" message={traceState.message} /> : null}
      {isTraceFailure(traceState) ? <FailureState kind={traceState.kind} message={traceState.message} onRetry={onRetry} /> : null}
      {trace ? <div className="vt3-trace-grid">
        <div className="vt3-trace-subjects" aria-label={direction === "claim_to_source" ? copy("核心结论", "Material claims") : copy("追溯来源", "Trace sources")}>{subjects.map((subject) => <button type="button" key={subject.id} className={selectedNodeId === subject.id ? "is-selected" : undefined} aria-pressed={selectedNodeId === subject.id} onClick={() => onSelectNode(subject.id)}><span>{subject.label}</span><small>{labelToken(subject.type)}</small></button>)}</div>
        <div className="vt3-trace-results">
          {related.length ? <ul>{related.map((node) => <li key={node.node_id}><strong>{labelToken(node.node_type)}</strong><span>{localizeFixtureText(node.display_label)}</span><code>{node.reference}</code></li>)}</ul> : <ExplicitGap claim={selectedClaim} node={selectedNode} />}
        </div>
      </div> : null}
    </section>
  );
}

function ExplicitGap({ claim, node }: { claim: MaterialClaimView | null; node: TraceNodeView | null }) {
  const { copy } = useWorkbenchLocale();
  const gaps = claim?.gap_refs ?? (node?.node_type === "explicit_gap" ? [node.reference] : []);
  return <div className="vt3-explicit-gap"><strong>{copy("明确缺口", "Explicit gap")}</strong>{gaps.length ? <ul>{gaps.map((gap) => <li key={gap}><code>{gap}</code></li>)}</ul> : <span>{copy("所选标识没有关联的追溯节点。", "No linked trace node is available for the selected identity.")}</span>}</div>;
}

function relatedTraceNodes(trace: DeliverableTraceView, nodes: TraceNodeView[], selectedNodeId: string | null, direction: TraceDirection): TraceNodeView[] {
  if (!selectedNodeId) return [];
  const linkedIds = direction === "claim_to_source" ? trace.claim_to_source[selectedNodeId] ?? [] : trace.source_to_claim[selectedNodeId] ?? [];
  return nodes.filter((node) => linkedIds.includes(node.node_id));
}

function FailureState({ kind, message, onRetry }: { kind: FailureKind; message: string; onRetry: () => void }) {
  const { copy } = useWorkbenchLocale();
  return <div className="p02-failure-stack"><RemoteStatus kind={kind} message={message} />{kind !== "permission" ? <button type="button" className="p02-secondary-button" onClick={onRetry}><RotateCcw size={16} aria-hidden="true" />{copy("重试", "Retry")}</button> : null}</div>;
}

function isMissing(error: unknown): boolean {
  return error instanceof DeliverablesApiError && (error.statusCode === 404 || error.code.includes("not_found") || error.code.includes("not_compiled"));
}

function remoteFailure(error: unknown, copy: Copy): Exclude<RemoteState, { kind: "loading" } | { kind: "ready" } | { kind: "empty" }> {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接研究结论 API。重新连接后将重新加载最新版本。", "The research conclusion API could not be reached. The latest version will reload after reconnecting.") };
  return apiFailure(error, copy);
}

function traceFailure(error: unknown, copy: Copy): Exclude<TraceState, { kind: "loading" } | { kind: "ready" } | { kind: "empty" }> {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接追溯 API。重新连接后将重新加载清单。", "The trace API could not be reached. The manifest will reload after reconnecting.") };
  return apiFailure(error, copy);
}

function mutationFailure(error: unknown, copy: Copy): Exclude<MutationState, { kind: "idle" } | { kind: "loading" }> {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接研究结论 API。请重新连接后再发送操作。", "The research conclusion API could not be reached. Reconnect before sending the action.") };
  return apiFailure(error, copy);
}

function apiFailure(error: unknown, copy: Copy): { kind: FailureKind; message: string } {
  if (error instanceof DeliverablesApiError) {
    const kind = error.code === "permission_denied" || error.statusCode === 403 ? "permission"
      : error.code.includes("stale") || error.code.includes("superseded") ? "stale"
        : error.code.includes("conflict") || error.statusCode === 409 ? "conflict" : "error";
    return { kind, message: error.traceId ? `${error.message} ${copy("追踪 ID", "Trace ID")}: ${error.traceId}` : error.message };
  }
  return { kind: "error", message: copy("研究结论 API 未返回可用响应。", "The research conclusion API did not return a usable response.") };
}

function isOfflineError(error: unknown): boolean {
  return error instanceof TypeError || error instanceof DeliverablesApiError && error.statusCode === 0;
}

function isRemoteFailure(remote: RemoteState): remote is Extract<RemoteState, { kind: FailureKind }> {
  return remote.kind === "permission" || remote.kind === "conflict" || remote.kind === "stale" || remote.kind === "error";
}

function isTraceFailure(traceState: TraceState): traceState is Extract<TraceState, { kind: FailureKind }> {
  return traceState.kind === "permission" || traceState.kind === "conflict" || traceState.kind === "stale" || traceState.kind === "error";
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
