import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Calculator,
  ChevronRight,
  ClipboardCheck,
  FileSearch,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";

import { EvidenceApiClient, EvidenceApiError, EvidenceWorkbenchView } from "../../api/evidence";
import {
  CompileNumericFixtureCommand,
  IntegrityApiClient,
  IntegrityApiError,
  NumericFactView,
  NumericWorkbenchView,
} from "../../api/integrity";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { LocalAnalysisPreview } from "../../shared/LocalAnalysisPreview";
import { RemoteStatus } from "../../shared/RemoteStatus";

type NumericWorkbenchProps = {
  caseId: string;
  online: boolean;
  onOpenEvidence: () => void;
  onOpenWorkpaper: () => void;
};

type FailureKind = "permission" | "conflict" | "stale" | "error";
type EmptyState = { evidence: EvidenceWorkbenchView | null; message: string };
type RemoteState =
  | { kind: "loading" }
  | { kind: "ready"; numeric: NumericWorkbenchView }
  | { kind: "empty"; data: EmptyState }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type MutationState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "offline"; message: string }
  | { kind: FailureKind; message: string };
type IdempotencyRecord = { fingerprint: string; key: string };
type Copy = (zhCN: string, en: string) => string;

const evidenceApi = new EvidenceApiClient();
const integrityApi = new IntegrityApiClient();

export function NumericWorkbench({ caseId, online, onOpenEvidence, onOpenWorkpaper }: NumericWorkbenchProps) {
  const { copy, labelToken } = useWorkbenchLocale();
  const copyRef = useRef(copy);
  copyRef.current = copy;
  const [remote, setRemote] = useState<RemoteState>({ kind: "loading" });
  const [mutation, setMutation] = useState<MutationState>({ kind: "idle" });
  const [selectedFactId, setSelectedFactId] = useState<string | null>(null);
  const compileAttemptRef = useRef<IdempotencyRecord | null>(null);

  const load = useCallback(async () => {
    const localCopy = copyRef.current;
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: localCopy("连接不可用。重新连接后可恢复数字核验。", "Connection is unavailable. Reconnect to restore numeric verification.") });
      return;
    }
    setRemote({ kind: "loading" });
    setMutation({ kind: "idle" });
    try {
      let evidence: EvidenceWorkbenchView;
      try {
        evidence = await evidenceApi.getEvidenceWorkbench(caseId);
      } catch (error) {
        if (isMissing(error)) {
          setRemote({ kind: "empty", data: { evidence: null, message: localCopy("请先准备证据与反证工作区，并完成其限定修复，再编译数字事实。", "Prepare the Evidence & counterevidence workspace and complete its bounded repair before compiling numeric facts.") } });
          return;
        }
        throw error;
      }
      try {
        const numeric = await integrityApi.getNumericWorkbench(caseId);
        if (numeric.status === "not_compiled") {
          setRemote({ kind: "empty", data: { evidence, message: numericPrerequisite(evidence, localCopy) } });
        } else {
          setRemote({ kind: "ready", numeric });
        }
      } catch (error) {
        if (isMissing(error)) setRemote({ kind: "empty", data: { evidence, message: numericPrerequisite(evidence, localCopy) } });
        else throw error;
      }
    } catch (error) {
      setRemote(remoteFailure(error, localCopy));
    }
  }, [caseId, online]);

  useEffect(() => {
    void load();
  }, [load]);

  const numeric = remote.kind === "ready" ? remote.numeric : null;
  useEffect(() => {
    if (!numeric) return;
    if (numeric.facts.some((fact) => fact.normalized_fact_id === selectedFactId)) return;
    setSelectedFactId(numeric.facts[0]?.normalized_fact_id ?? null);
  }, [numeric, selectedFactId]);

  const selectedFact = useMemo(
    () => numeric?.facts.find((fact) => fact.normalized_fact_id === selectedFactId) ?? null,
    [numeric, selectedFactId],
  );

  async function compileFixture() {
    if (remote.kind !== "empty" || !remote.data.evidence) return;
    if (!online || !navigator.onLine) {
      setMutation({ kind: "offline", message: copy("连接不可用。请重新连接后再编译数字夹具。", "Connection is unavailable. Reconnect before compiling the numeric fixture.") });
      return;
    }
    const evidence = remote.data.evidence;
    const fingerprint = `numeric:${caseId}:${evidence.workspace_version}`;
    const command: CompileNumericFixtureCommand = {
      expected_evidence_workspace_version: evidence.workspace_version,
      actor_ref: integrityApi.actorRef,
      idempotency_key: keyForAttempt(compileAttemptRef, fingerprint),
    };
    setMutation({ kind: "loading" });
    try {
      const compiled = await integrityApi.compileNumericFixture(caseId, command);
      compileAttemptRef.current = null;
      setMutation({ kind: "idle" });
      setRemote({ kind: "ready", numeric: compiled });
    } catch (error) {
      setMutation(mutationFailure(error, copy));
    }
  }

  const canCompile = remote.kind === "empty" && Boolean(remote.data.evidence?.summary.repair_completed_count);

  return (
    <section className="p02-workspace vt2-workspace" aria-label={copy("数字核验", "Numeric verification")}>
      <button type="button" className="p02-back-button" onClick={onOpenEvidence}>
        <ArrowLeft size={16} aria-hidden="true" />
        {copy("证据与反证", "Evidence & counterevidence")}
      </button>

      <div className="p02-page-heading vt2-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("数字核验", "Numeric verification")}</p>
          <h1>{caseId}</h1>
          {numeric ? <p className="p02-heading-meta">{copy(`数字核验版本 ${numeric.numeric_workspace_version} / 证据版本 ${numeric.evidence_workspace_version}`, `Numeric verification v${numeric.numeric_workspace_version} / Evidence v${numeric.evidence_workspace_version}`)}</p> : null}
        </div>
        <div className="p02-page-actions">
          <button type="button" className="p02-secondary-button" onClick={onOpenEvidence}>
            <FileSearch size={16} aria-hidden="true" /> {copy("证据与反证", "Evidence & counterevidence")}
          </button>
          {numeric ? (
            <button type="button" className="p02-primary-button" onClick={onOpenWorkpaper}>
              <ClipboardCheck size={16} aria-hidden="true" /> {copy("研究底稿", "Research workpaper")}
            </button>
          ) : null}
          <button type="button" className="p02-icon-button" title={copy("刷新数字核验", "Refresh numeric verification")} aria-label={copy("刷新数字核验", "Refresh numeric verification")} onClick={() => void load()}>
            <RefreshCcw size={17} aria-hidden="true" />
          </button>
        </div>
      </div>

      <BoundaryBanner title={copy("仅限内部夹具", "Internal fixture only")} detail={copy("数字事实仅为可审计夹具投影；不可供写作引用、不可提升至运行时，也不是发布证据。", "Numeric facts are auditable fixture projections. They are not writer-citable, runtime-promoted, or release evidence.")} />

      <LocalAnalysisPreview caseId={caseId} online={online} view="numeric" />

      {remote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载证据与反证及数字核验投影。", "Loading Evidence & counterevidence and numeric verification projections.")} /> : null}
      {remote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} onRetry={() => void load()} /> : null}
      {isRemoteFailure(remote) ? <FailureState kind={remote.kind} message={remote.message} onRetry={() => void load()} /> : null}
      {mutation.kind === "offline" ? <RemoteStatus kind="reconnecting" message={mutation.message} /> : null}
      {isMutationFailure(mutation) ? <FailureState kind={mutation.kind} message={mutation.message} onRetry={() => void load()} /> : null}

      {remote.kind === "empty" ? (
        <section className="vt2-compile-panel" aria-labelledby="vt2-numeric-empty-heading">
          <div>
            <p className="p02-eyebrow">{copy("编译前提", "Compilation prerequisite")}</p>
            <h2 id="vt2-numeric-empty-heading">{copy("数字夹具尚未编译", "Numeric fixture not compiled")}</h2>
            <p>{remote.data.message}</p>
            <code>{remote.data.evidence ? `evidence_workspace_version:${remote.data.evidence.workspace_version}` : "evidence_workspace:missing"}</code>
          </div>
          <button type="button" className="p02-primary-button" disabled={!canCompile || mutation.kind === "loading"} onClick={() => void compileFixture()}>
            <Calculator size={16} aria-hidden="true" />
            {mutation.kind === "loading" ? copy("正在编译", "Compiling") : copy("编译数字夹具", "Compile numeric fixture")}
          </button>
        </section>
      ) : null}

      {numeric ? (
        <>
          <WorkspaceMeta
            items={[
              [copy("事实", "Facts"), String(numeric.facts.length)],
              [copy("工作区", "Workspace"), numeric.numeric_workspace_id],
              [copy("状态", "Status"), labelToken(numeric.status)],
              ...Object.entries(numeric.counts).map(([key, value]) => [labelToken(key), String(value)]),
            ]}
          />
          {numeric.facts.length === 0 ? (
            <RemoteStatus kind="empty" message={copy("已编译的数字核验工作区不包含事实。", "The compiled numeric verification workspace contains no facts.")} />
          ) : (
            <div className="vt2-split-layout">
              <section className="vt2-table-region" aria-labelledby="vt2-fact-table-heading">
                <div className="vt2-section-heading"><div><p className="p02-eyebrow">{copy("精确事实", "Exact facts")}</p><h2 id="vt2-fact-table-heading">{copy("标准化事实表", "Normalized fact table")}</h2></div></div>
                <div className="vt2-table-scroll">
                  <table className="vt2-fact-table">
                    <thead><tr><th>{copy("单元格 / 实体", "Cell / entity")}</th><th>{copy("期间", "Period")}</th><th>{copy("数值", "Value")}</th><th>{copy("单位", "Unit")}</th><th>{copy("倍率", "Scale")}</th><th>{copy("坐标", "Coordinate")}</th><th aria-label={copy("查看", "Inspect")} /></tr></thead>
                    <tbody>
                      {numeric.facts.map((fact) => (
                        <tr key={fact.normalized_fact_id} className={selectedFactId === fact.normalized_fact_id ? "is-selected" : undefined}>
                          <td><button type="button" onClick={() => setSelectedFactId(fact.normalized_fact_id)}><strong>{fact.entity_ref}</strong><span>{fact.cell_id}</span></button></td>
                          <td>{labelToken(fact.period)}</td>
                          <td className="vt2-value-cell">{fact.normalized_value}</td>
                          <td>{fact.unit}</td>
                          <td>{fact.scale_multiplier}</td>
                          <td><code>{fact.source_coordinate}</code></td>
                          <td><button type="button" className="vt2-row-open" aria-label={copy(`查看 ${fact.row_label}`, `Inspect ${fact.row_label}`)} onClick={() => setSelectedFactId(fact.normalized_fact_id)}><ChevronRight size={15} aria-hidden="true" /></button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <aside className="vt2-inspector" aria-label={copy("数字事实检查器", "Numeric fact inspector")}>
                {selectedFact ? <NumericInspector fact={selectedFact} /> : null}
              </aside>
            </div>
          )}
          <HardBoundaries boundaries={numeric.hard_boundaries} />
        </>
      ) : null}
    </section>
  );
}

function NumericInspector({ fact }: { fact: NumericFactView }) {
  const { copy, labelToken } = useWorkbenchLocale();
  return (
    <div className="vt2-inspector-content">
      <div className="vt2-inspector-heading"><div><p className="p02-eyebrow">{copy("事实检查", "Fact inspector")}</p><h2>{fact.row_label}</h2></div><span className="vt2-status-badge">{copy("仅内部使用", "Internal only")}</span></div>
      <div className="vt2-value-readout"><strong>{fact.output_value}</strong><span>{fact.unit} / {copy(`倍率 ${fact.scale_multiplier}`, `scale ${fact.scale_multiplier}`)}</span></div>
      <dl className="vt2-field-grid">
        <div><dt>{copy("实体", "Entity")}</dt><dd>{fact.entity_ref}</dd></div>
        <div><dt>{copy("期间", "Period")}</dt><dd>{labelToken(fact.period)}</dd></div>
        <div className="is-wide"><dt>{copy("证据槽位", "Evidence slot")}</dt><dd><code>{fact.evidence_slot_id}</code></dd></div>
        <div className="is-wide"><dt>{copy("来源坐标", "Source coordinate")}</dt><dd><code>{fact.source_coordinate}</code></dd></div>
        <div className="is-wide"><dt>{copy("指标定义", "Metric definition")}</dt><dd><code>{fact.metric_definition_ref}</code></dd></div>
      </dl>
      <section className="vt2-trace-section"><h3>{copy("程序步骤", "Program steps")}</h3><ol>{fact.program_steps.map((step, index) => <li key={`${index}:${step}`}><span>{index + 1}</span><code>{step}</code></li>)}</ol></section>
      <dl className="vt2-identity-list">
        <div><dt>{copy("解析候选", "Parser candidate")}</dt><dd>{fact.parser_candidate_id}</dd></div>
        <div><dt>{copy("标准化事实", "Normalized fact")}</dt><dd>{fact.normalized_fact_id}</dd></div>
        <div><dt>{copy("数字追溯", "Numeric trace")}</dt><dd>{fact.numeric_trace_id}</dd></div>
        <div><dt>{copy("提升决策", "Promotion decision")}</dt><dd>{fact.promotion_decision_id}</dd></div>
      </dl>
      <div className="vt2-boundary-note"><strong>{labelToken(fact.promotion_status)}</strong><p>{labelToken(fact.promotion_scope)}. {fact.boundary}</p><span>{fact.writer_citable ? copy("可供写作引用", "Writer-citable") : copy("不可供写作引用", "Not writer-citable")}</span></div>
    </div>
  );
}

function BoundaryBanner({ title, detail }: { title: string; detail: string }) {
  return <div className="vt2-boundary-banner"><ShieldCheck size={18} aria-hidden="true" /><div><strong>{title}</strong><span>{detail}</span></div></div>;
}

function WorkspaceMeta({ items }: { items: string[][] }) {
  return <dl className="vt2-meta-strip">{items.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}

function HardBoundaries({ boundaries }: { boundaries: Record<string, number | string> }) {
  const { copy, labelToken } = useWorkbenchLocale();
  return <section className="vt2-hard-boundaries" aria-labelledby="vt2-numeric-boundaries"><h2 id="vt2-numeric-boundaries">{copy("硬性边界", "Hard boundaries")}</h2><dl>{Object.entries(boundaries).map(([key, value]) => <div key={key}><dt>{labelToken(key)}</dt><dd>{String(value)}</dd></div>)}</dl></section>;
}

function FailureState({ kind, message, onRetry }: { kind: FailureKind; message: string; onRetry: () => void }) {
  const { copy } = useWorkbenchLocale();
  return <div className="p02-failure-stack"><RemoteStatus kind={kind} message={message} />{kind !== "permission" ? <button type="button" className="p02-secondary-button" onClick={onRetry}><RotateCcw size={16} aria-hidden="true" />{copy("重新打开当前视图", "Reopen current")}</button> : null}</div>;
}

function numericPrerequisite(evidence: EvidenceWorkbenchView, copy: Copy): string {
  return evidence.summary.repair_completed_count > 0
    ? copy("限定的证据与反证修复已完成。请基于此证据工作区版本编译精确的内部数字夹具。", "The bounded Evidence & counterevidence repair is complete. Compile the exact internal numeric fixture against this Evidence workspace version.")
    : copy("请先请求并完成限定的证据与反证修复，再编译数字事实。", "Request and complete the bounded Evidence & counterevidence repair before compiling numeric facts.");
}

function isMissing(error: unknown): boolean {
  return (error instanceof IntegrityApiError || error instanceof EvidenceApiError) && (error.statusCode === 404 || error.code.includes("not_found") || error.code.includes("not_compiled") || error.code.includes("not_prepared"));
}

function remoteFailure(error: unknown, copy: Copy): RemoteState {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接夹具 API。重新连接后将重新加载数字数据。", "The fixture API could not be reached. Numeric data will reload after reconnecting.") };
  return apiFailure(error, copy);
}

function mutationFailure(error: unknown, copy: Copy): MutationState {
  if (isOfflineError(error)) return { kind: "offline", message: copy("无法连接夹具 API。请重新连接后再发送命令。", "The fixture API could not be reached. Reconnect before sending the command.") };
  return apiFailure(error, copy);
}

function apiFailure(error: unknown, copy: Copy): { kind: FailureKind; message: string } {
  if (error instanceof IntegrityApiError || error instanceof EvidenceApiError) {
    const kind = error.code === "permission_denied" || error.statusCode === 403 ? "permission"
      : error.code.includes("stale") || error.code.includes("superseded") ? "stale"
        : error.code.includes("conflict") || error.statusCode === 409 ? "conflict" : "error";
    return { kind, message: error.traceId ? `${error.message} ${copy("追踪 ID", "Trace ID")}: ${error.traceId}` : error.message };
  }
  return { kind: "error", message: copy("夹具 API 未返回可用的数字核验响应。", "The fixture API did not return a usable numeric verification response.") };
}

function isOfflineError(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof IntegrityApiError || error instanceof EvidenceApiError) && error.statusCode === 0;
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
