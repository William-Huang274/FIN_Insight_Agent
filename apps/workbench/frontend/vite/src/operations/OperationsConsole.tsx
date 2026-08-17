import {
  Activity,
  Boxes,
  CheckCircle2,
  CircleStop,
  Database,
  ExternalLink,
  FileSearch,
  FlaskConical,
  LoaderCircle,
  Play,
  RefreshCcw,
  ServerCog,
  Settings2,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ComplexDocumentQuality,
  EvalCatalogItem,
  OperationsApiClient,
  RetrievalQuality,
  SupplementQuality,
  RunJob,
  SourceIntakeAttempt,
  SourceIntakeRoute,
  StoredProfile,
  StoredSourceBundle,
  SystemStatus,
} from "../api/operations";
import { SourceIntakePanel } from "./SourceIntakePanel";
import "./operations-console.css";

type Snapshot = {
  status: SystemStatus;
  profiles: StoredProfile[];
  bundles: StoredSourceBundle[];
  runs: RunJob[];
  evals: EvalCatalogItem[];
  sourceRoutes: SourceIntakeRoute[];
  sourceAttempts: SourceIntakeAttempt[];
  complexDocumentQuality: ComplexDocumentQuality;
  retrievalQuality: RetrievalQuality;
  supplementQuality: SupplementQuality;
};

type ViewState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; snapshot: Snapshot };

const api = new OperationsApiClient();

export function OperationsConsole() {
  const [state, setState] = useState<ViewState>({ kind: "loading" });
  const [action, setAction] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setState({ kind: "loading" });
    Promise.all([api.status(), api.profiles(), api.sourceBundles(), api.runs(), api.evals(), api.sourceIntakeRoutes(), api.sourceIntakeAttempts(), api.complexDocumentQuality(), api.retrievalQuality(), api.supplementQuality()])
      .then(([status, profiles, bundles, runs, evals, sourceRoutes, sourceAttempts, complexDocumentQuality, retrievalQuality, supplementQuality]) => {
        setState({ kind: "ready", snapshot: { status, profiles, bundles, runs, evals, sourceRoutes, sourceAttempts, complexDocumentQuality, retrievalQuality, supplementQuality } });
      })
      .catch((error: Error) => setState({ kind: "error", message: error.message }));
  }, []);

  useEffect(() => refresh(), [refresh]);

  const startSmoke = async () => {
    setAction("smoke");
    setActionError(null);
    try {
      await api.startSmoke();
      refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setAction(null);
    }
  };

  const cancel = async (jobId: string) => {
    setAction(jobId);
    setActionError(null);
    try {
      await api.cancelRun(jobId);
      refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setAction(null);
    }
  };

  const uploadSource = async (routeId: string, file: File) => {
    setAction("source-upload");
    setActionError(null);
    try {
      await api.uploadSource(routeId, file);
      refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setAction(null);
    }
  };

  const acquireSourceAutomatically = async (routeId: string) => {
    setAction("source-automatic");
    setActionError(null);
    try {
      await api.acquireSourceAutomatically(routeId);
      refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setAction(null);
    }
  };

  return (
    <div className="operations-console">
      <header className="operations-console__topbar">
        <a className="operations-console__brand" href="/operations">
          <span><ServerCog size={19} /></span>
          <div><strong>FinSight Operations</strong><small>Runtime · data · jobs · evals</small></div>
        </a>
        <div className="operations-console__actions">
          <a href="/workspace">研究工作区 <ExternalLink size={13} /></a>
          <button className="operations-console__refresh" type="button" onClick={refresh}><RefreshCcw size={15} />刷新</button>
          <button type="button" className="is-primary" disabled={action === "smoke"} onClick={startSmoke}>
            {action === "smoke" ? <LoaderCircle className="is-spinning" size={15} /> : <Play size={15} />}本地 smoke
          </button>
        </div>
      </header>

      <main className="operations-console__page">
        <section className="operations-console__heading">
          <div><p>OPERATOR SURFACE</p><h1>运行与数据控制台</h1><span>这里管理运行时、数据源、作业和评测；不会形成或改写研究事实。</span></div>
        </section>
        {actionError ? <div className="operations-console__error"><ShieldAlert size={17} />{actionError}</div> : null}
        {state.kind === "loading" ? <div className="operations-console__loading"><LoaderCircle className="is-spinning" /><span>正在读取当前运行状态…</span></div> : null}
        {state.kind === "error" ? <div className="operations-console__error"><ShieldAlert size={17} />{state.message}</div> : null}
        {state.kind === "ready" ? <OperationsSnapshot snapshot={state.snapshot} action={action} onCancel={cancel} onUploadSource={uploadSource} onAutomaticSource={acquireSourceAutomatically} /> : null}
      </main>
    </div>
  );
}

function OperationsSnapshot({ snapshot, action, onCancel, onUploadSource, onAutomaticSource }: { snapshot: Snapshot; action: string | null; onCancel: (jobId: string) => void; onUploadSource: (routeId: string, file: File) => Promise<void>; onAutomaticSource: (routeId: string) => Promise<void> }) {
  const activeRuns = useMemo(() => snapshot.runs.filter((run) => ["queued", "running", "cancelling"].includes(run.status)), [snapshot.runs]);
  return (
    <>
      <section className="operations-console__status-grid">
        <StatusCard icon={Activity} label="服务状态" value={snapshot.status.status} ok={snapshot.status.status === "ok"} />
        <StatusCard icon={Settings2} label="Profiles" value={String(snapshot.profiles.length)} ok />
        <StatusCard icon={Database} label="Source Bundles" value={String(snapshot.bundles.length)} ok />
        <StatusCard icon={Boxes} label="活动作业" value={String(activeRuns.length)} ok={activeRuns.length === 0} />
        <StatusCard icon={FlaskConical} label="Eval runners" value={String(snapshot.evals.length)} ok />
      </section>

      <ComplexDocumentQualityPanel value={snapshot.complexDocumentQuality} />
      <RetrievalQualityPanel value={snapshot.retrievalQuality} />
      <SupplementQualityPanel value={snapshot.supplementQuality} />

      <section className="operations-console__columns">
        <article className="operations-console__panel is-wide">
          <div className="operations-console__panel-title"><h2>已保存作业</h2><span>{snapshot.runs.length} 条 · 仅供审计，不代表当前能力</span></div>
          <div className="operations-console__table-wrap"><table><thead><tr><th>Job</th><th>类型</th><th>状态</th><th>Profile</th><th /></tr></thead><tbody>
            {snapshot.runs.length === 0 ? <tr><td colSpan={5} className="is-empty">暂无作业</td></tr> : snapshot.runs.slice(0, 20).map((run) => (
              <tr key={run.job_id}><td><code>{run.job_id}</code></td><td>{run.job_type}</td><td><RunStatus status={run.status} /></td><td>{run.profile_id ?? "—"}</td><td>{["queued", "running", "cancelling"].includes(run.status) ? <button type="button" disabled={action === run.job_id} onClick={() => onCancel(run.job_id)}><CircleStop size={14} />停止</button> : null}</td></tr>
            ))}
          </tbody></table></div>
        </article>

        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>路径与依赖</h2><span>{snapshot.status.status}</span></div>
          <dl className="operations-console__checks">
            {Object.entries(snapshot.status.checks).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className={value === "ok" || value === "available" ? "is-ok" : ""}>{value}</dd></div>)}
          </dl>
        </article>
      </section>

      <SourceIntakePanel routes={snapshot.sourceRoutes} attempts={snapshot.sourceAttempts} action={action} onUpload={onUploadSource} onAutomatic={onAutomaticSource} />

      <section className="operations-console__columns">
        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>运行 Profiles</h2><span>{snapshot.profiles.length}</span></div>
          <SimpleList rows={snapshot.profiles.map((row) => ({ title: row.display_name, primary: row.profile_id, secondary: `${row.source_policy}${row.model_name ? ` · ${row.model_name}` : ""}` }))} empty="尚未保存 Profile" />
        </article>
        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>Source Bundles</h2><span>{snapshot.bundles.length}</span></div>
          <SimpleList rows={snapshot.bundles.map((row) => ({ title: row.display_name, primary: row.bundle_id, secondary: `${row.market} · ${row.coverage_theme} · ${row.ticker_count} tickers` }))} empty="尚未导入 Source Bundle" />
        </article>
        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>评测目录</h2><span>{snapshot.evals.length}</span></div>
          <SimpleList rows={snapshot.evals.map((row) => ({ title: row.label ?? row.eval_id, primary: row.eval_id, secondary: row.description ?? row.runner ?? "registered eval" }))} empty="未注册评测 Runner" />
        </article>
      </section>
    </>
  );
}

function ComplexDocumentQualityPanel({ value }: { value: ComplexDocumentQuality }) {
  const counts = value.candidate_decision_summary;
  const businessFailure = String(value.business_result.current_retrieval_failure_zh ?? "");
  return (
    <section className="operations-console__panel operations-console__document-quality">
      <div className="operations-console__panel-title">
        <h2><FileSearch size={18} />复杂文档纵切</h2>
        <span>VS2 · 开发样本，不是产品案例</span>
      </div>
      <div className="operations-console__document-summary">
        <div>
          <p>官方来源</p>
          <strong>{value.source.issuer_name}</strong>
          <small>{value.source.document_type} · {value.source.publication_date} · 全文 {value.source.page_count} 页</small>
        </div>
        <div>
          <p>解析对象</p>
          <strong>{value.financial_objects.object_count}</strong>
          <small>{value.document_quality.table_region_count} 个表格 · {value.document_quality.footnote_count} 个脚注 · {value.financial_objects.cross_page_relation_count} 个跨页关系</small>
        </div>
        <div>
          <p>候选决策</p>
          <strong>{counts.accepted ?? 0} accepted / {counts.needs_review ?? 0} review</strong>
          <small>{value.coverage_summary.reviewed_not_recalled_count} 个经复核复杂对象未召回</small>
        </div>
        <div>
          <p>权威边界</p>
          <strong>Evidence / NumericFact 分离</strong>
          <small>真实扫描件资格：未关闭 · S1：未通过</small>
        </div>
      </div>
      <p className="operations-console__document-finding">{businessFailure}</p>
      <div className="operations-console__document-meta">
        <span>选页 {value.source.selected_page_numbers.join(" / ")}</span>
        <span>OCR mutation {value.document_quality.forced_ocr_pages.join(" / ")}</span>
        <code>{value.result_digest.slice(0, 12)}…{value.result_digest.slice(-8)}</code>
      </div>
    </section>
  );
}

function RetrievalQualityPanel({ value }: { value: RetrievalQuality }) {
  const summary = value.summary;
  const stage = summary.vs3_vertical_slice_integrated ? "纵切已集成" : "门禁未通过";
  return (
    <section className="operations-console__panel operations-console__document-quality">
      <div className="operations-console__panel-title">
        <h2><FileSearch size={18} />检索与金融排序纵切</h2>
        <span>VS3 · 开发资格，不是 S1 发布资格</span>
      </div>
      <div className="operations-console__document-summary">
        <div>
          <p>有限候选池</p>
          <strong>{summary.combined_union_positive_atom_count} / {summary.positive_atom_count}</strong>
          <small>已知正例进入候选池；完整 CandidateDecision 仍保留</small>
        </div>
        <div>
          <p>金融审阅前十</p>
          <strong>{summary.financial_shortlist_positive_top10_count} / {summary.positive_atom_count}</strong>
          <small>确认 hard negative：{summary.financial_shortlist_hard_negative_top10_count}</small>
        </div>
        <div>
          <p>跨纵切回归</p>
          <strong>VS1 {summary.vs1_reviewed_objects_in_candidate_pool} / VS2 {summary.vs2_reviewed_objects_in_candidate_pool}</strong>
          <small>数字原生与复杂文档共同消费同一候选合同</small>
        </div>
        <div>
          <p>阶段结论</p>
          <strong>{stage}</strong>
          <small>Candidate ≠ Evidence · NumericFact 权威未授予 · S1 未通过</small>
        </div>
      </div>
      <p className="operations-console__document-finding">{value.business_findings[0] ?? "暂无业务结论"}</p>
      <div className="operations-console__document-meta">
        <span>{summary.accepted_object_count} 个已绑定对象</span>
        <span>{summary.needs_review_candidate_count} 个候选待审，不等于缺口</span>
        <code>{value.result_digest.slice(0, 12)}…{value.result_digest.slice(-8)}</code>
      </div>
    </section>
  );
}

function SupplementQualityPanel({ value }: { value: SupplementQuality }) {
  const delta = value.coverage_delta;
  const readyCount = value.proposition_rows.filter((row) => row.proposition_ready).length;
  const falseAccepts = value.proposition_rows.reduce((total, row) => total + row.hard_negative_accepted_object_ids.length, 0);
  return (
    <section className="operations-console__panel operations-console__document-quality">
      <div className="operations-console__panel-title">
        <h2><FileSearch size={18} />命题补证与缺口窄化</h2>
        <span>VS4 · DELL 有界纵切，不是 S1 发布资格</span>
      </div>
      <div className="operations-console__document-summary">
        <div>
          <p>证据继任</p>
          <strong>{delta.retired_broad_or_legacy_evidence_count} 退役 / {delta.added_capture_bound_claim_count} 新增</strong>
          <small>宽 chunk 与整页材料替换为精确 capture-bound claim</small>
        </div>
        <div>
          <p>命题覆盖</p>
          <strong>{readyCount} / {value.proposition_rows.length}</strong>
          <small>营运资金、发行人反方、上游反方</small>
        </div>
        <div>
          <p>错误晋升</p>
          <strong>{falseAccepts}</strong>
          <small>分析师提问、同页无关句不得借用管理层事实权限</small>
        </div>
        <div>
          <p>缺口处置</p>
          <strong>{delta.narrowed_gap_count} 窄化 / {delta.closed_gap_count} 关闭</strong>
          <small>机制已知不等于量化归属或 Dell 分配已知</small>
        </div>
      </div>
      <p className="operations-console__document-finding">{value.business_findings[0] ?? "暂无业务结论"}</p>
      <div className="operations-console__document-meta">
        <span>Successor Evidence {delta.successor_evidence_count}</span>
        <span>S1 仍未通过 · NumericFact 未授权</span>
        <code>{value.result_digest.slice(0, 12)}…{value.result_digest.slice(-8)}</code>
      </div>
    </section>
  );
}

function StatusCard({ icon: Icon, label, value, ok }: { icon: typeof Activity; label: string; value: string; ok: boolean }) {
  return <article className="operations-console__status-card"><div className={ok ? "is-ok" : "is-warn"}><Icon size={18} /></div><span>{label}</span><strong>{value}</strong></article>;
}

function RunStatus({ status }: { status: string }) {
  const ok = ["succeeded", "completed"].includes(status);
  return <span className={`operations-console__run-status ${ok ? "is-ok" : ""}`}>{ok ? <CheckCircle2 size={12} /> : <Activity size={12} />}{status}</span>;
}

function SimpleList({ rows, empty }: { rows: Array<{ title: string; primary: string; secondary: string }>; empty: string }) {
  if (!rows.length) return <p className="operations-console__empty">{empty}</p>;
  return <div className="operations-console__list">{rows.slice(0, 12).map((row) => <div key={row.primary}><strong>{row.title}</strong><code>{row.primary}</code><small>{row.secondary}</small></div>)}</div>;
}
