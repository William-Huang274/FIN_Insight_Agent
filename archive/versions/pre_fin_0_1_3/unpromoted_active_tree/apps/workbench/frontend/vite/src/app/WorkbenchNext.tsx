import {
  Activity,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Database,
  FileCheck2,
  FileSearch,
  FileText,
  GitBranch,
  Globe2,
  History,
  Languages,
  LayoutDashboard,
  LoaderCircle,
  MessageSquareText,
  Network,
  PanelRight,
  Play,
  RefreshCcw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { CaseApiClient, CaseWorkspaceProjection, TaskCenterProjection, TaskCenterRow } from "../api/cases";
import { DeliverablePreviewView, DeliverableTraceView, DeliverablesApiClient } from "../api/deliverables";
import {
  EvidenceApiClient,
  EvidenceWorkbenchView,
  LocalAnalysisPreviewView,
  LocalResearchPreviewView,
} from "../api/evidence";
import {
  AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
  ActivityTraceView,
  decisionSurfaceInputHeadDigest,
  ExecutionApiClient,
  ResearchRunArtifactView,
  ResearchRunProjectionItem,
  ResearchRunProjectionView,
  S4CaseRuntimeProjection,
  S3ThreeCellPresentationPackView,
  WorkUnitExecutionView,
} from "../api/execution";
import { HumanBaselineApiClient, HumanBaselineSession, HumanBaselineSessionList } from "../api/humanBaseline";
import { IntegrityApiClient, NumericWorkbenchView, WorkpaperView } from "../api/integrity";
import { DecisionSurfaceView, PlanningApiClient } from "../api/planning";
import { useWorkbenchLocale } from "../i18n/WorkbenchLocale";
import "./workbench-next.css";

type NextSurface = "run" | "evidence" | "workpaper" | "review" | "report" | "inspect";
type NextRoute = { kind: "tasks" } | { kind: "case"; caseId: string; surface: NextSurface };

type CaseBundle = {
  caseProjection?: CaseWorkspaceProjection;
  plan?: DecisionSurfaceView;
  workUnits?: WorkUnitExecutionView;
  activity?: ActivityTraceView;
  runProjection?: ResearchRunProjectionView;
  research?: LocalResearchPreviewView;
  analysis?: LocalAnalysisPreviewView;
  evidence?: EvidenceWorkbenchView;
  numeric?: NumericWorkbenchView;
  workpaper?: WorkpaperView;
  deliverable?: DeliverablePreviewView;
  trace?: DeliverableTraceView;
  baseline?: HumanBaselineSessionList;
  failures: string[];
};

type BundleState =
  | { kind: "idle" | "loading" }
  | { kind: "ready"; data: CaseBundle }
  | { kind: "error"; message: string };

type TaskState =
  | { kind: "loading" }
  | { kind: "ready"; data: TaskCenterProjection }
  | { kind: "error"; message: string };

type Captured<T> = { ok: true; value: T } | { ok: false; label: string; message: string };

const caseApi = new CaseApiClient();
const planningApi = new PlanningApiClient();
const executionApi = new ExecutionApiClient();
const evidenceApi = new EvidenceApiClient();
const integrityApi = new IntegrityApiClient();
const deliverablesApi = new DeliverablesApiClient();
const baselineApi = new HumanBaselineApiClient();

const surfaceItems: Array<{
  surface: NextSurface;
  zh: string;
  en: string;
  icon: typeof Activity;
}> = [
  { surface: "run", zh: "研究运行", en: "Research run", icon: MessageSquareText },
  { surface: "evidence", zh: "证据矩阵", en: "Evidence matrix", icon: FileSearch },
  { surface: "workpaper", zh: "工作底稿", en: "Workpaper", icon: BookOpen },
  { surface: "report", zh: "研究报告", en: "Report", icon: FileText },
  { surface: "review", zh: "Senior Review", en: "Senior review", icon: FileCheck2 },
  { surface: "inspect", zh: "运行检查", en: "Inspect run", icon: Activity },
];

export function isWorkbenchNextPath(pathname: string): boolean {
  return pathname === "/next" || pathname.startsWith("/next/");
}

export function WorkbenchNext({ online }: { online: boolean }) {
  const { copy, locale, setLocale } = useWorkbenchLocale();
  const [route, navigate] = useNextRoute();
  const [searchText, setSearchText] = useState("");

  return (
    <div className="next-app">
      <header className="next-topbar">
        <button type="button" className="next-brand" onClick={() => navigate({ kind: "tasks" })}>
          <span>F</span>
          <b>FinSight Workbench</b>
        </button>
        <label className="next-global-search">
          <Search size={17} aria-hidden="true" />
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder={copy("搜索公司、研究任务、指标或证据", "Search companies, cases, metrics, or evidence")}
          />
        </label>
        <div className="next-topbar-actions">
          <span className="next-alpha-chip">INTERNAL ALPHA</span>
          <button
            type="button"
            className="next-icon-action"
            title={copy("切换语言", "Switch language")}
            onClick={() => setLocale(locale === "zh-CN" ? "en" : "zh-CN")}
          >
            <Languages size={17} aria-hidden="true" />
            {locale === "zh-CN" ? "中" : "EN"}
          </button>
          <span className={`next-connection ${online ? "is-online" : ""}`}>
            <CircleDot size={13} aria-hidden="true" />
            {online ? copy("本地研究服务", "Local research service") : copy("离线", "Offline")}
          </span>
          <span className="next-avatar">RA</span>
        </div>
      </header>

      <div className="next-shell">
        <NextSidebar route={route} navigate={navigate} />
        <main className="next-main">
          {route.kind === "tasks" ? (
            <NextTaskCenter online={online} searchText={searchText} navigate={navigate} />
          ) : (
            <NextCaseWorkspace route={route} online={online} navigate={navigate} />
          )}
        </main>
      </div>
    </div>
  );
}

function NextSidebar({ route, navigate }: { route: NextRoute; navigate: (route: NextRoute) => void }) {
  const { copy } = useWorkbenchLocale();
  const caseId = route.kind === "case" ? route.caseId : null;
  return (
    <aside className="next-sidebar">
      <p className="next-sidebar-label">{copy("分析师工作区", "Analyst workspace")}</p>
      <button type="button" className={route.kind === "tasks" ? "is-active" : ""} onClick={() => navigate({ kind: "tasks" })}>
        <LayoutDashboard size={17} aria-hidden="true" />
        {copy("研究任务", "Research cases")}
      </button>
      {surfaceItems.map(({ surface, zh, en, icon: Icon }) => (
        <button
          key={surface}
          type="button"
          disabled={!caseId}
          className={route.kind === "case" && route.surface === surface ? "is-active" : ""}
          onClick={() => caseId && navigate({ kind: "case", caseId, surface })}
        >
          <Icon size={17} aria-hidden="true" />
          {copy(zh, en)}
        </button>
      ))}
      <div className="next-sidebar-spacer" />
      <p className="next-sidebar-label">{copy("研究资产", "Research assets")}</p>
      <button type="button" disabled>
        <Database size={17} aria-hidden="true" />
        {copy("公司与主题", "Companies & topics")}
      </button>
      <button type="button" disabled>
        <BarChart3 size={17} aria-hidden="true" />
        {copy("指标库", "Metric library")}
      </button>
    </aside>
  );
}

function NextTaskCenter({
  online,
  searchText,
  navigate,
}: {
  online: boolean;
  searchText: string;
  navigate: (route: NextRoute) => void;
}) {
  const { copy, formatDateTime, localizeFixtureText } = useWorkbenchLocale();
  const [tasks, setTasks] = useState<TaskState>({ kind: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [localSearch, setLocalSearch] = useState("");
  const [status, setStatus] = useState("all");
  const detail = useCaseBundle(selectedId, online);

  const load = useCallback(async () => {
    if (!online) {
      setTasks({ kind: "error", message: copy("本地研究服务不可用。", "Local research service is unavailable.") });
      return;
    }
    setTasks({ kind: "loading" });
    try {
      const data = await caseApi.listCases();
      setTasks({ kind: "ready", data });
      setSelectedId((current) => current ?? data.items[0]?.case_id ?? null);
    } catch (error) {
      setTasks({ kind: "error", message: errorMessage(error) });
    }
  }, [copy, online]);

  useEffect(() => {
    void load();
  }, [load]);

  const items = tasks.kind === "ready" ? tasks.data.items : [];
  const search = `${searchText} ${localSearch}`.trim().toLowerCase();
  const visible = items.filter((item) => {
    const matchesText = !search || `${item.query} ${item.case_id}`.toLowerCase().includes(search);
    const matchesStatus = status === "all" || item.status === status;
    return matchesText && matchesStatus;
  });
  const statuses = Array.from(new Set(items.map((item) => item.status)));
  const selected = items.find((item) => item.case_id === selectedId) ?? null;

  return (
    <div className="next-task-page">
      <section className="next-page-heading">
        <div>
          <p>{copy("研究工作区", "Research workspace")}</p>
          <h1>{copy("研究任务", "Research cases")}</h1>
          <span>{copy("从问题、进度与证据质量判断下一项工作。", "Choose the next action from the question, progress, and evidence quality.")}</span>
        </div>
        <div className="next-heading-actions">
          <button type="button" className="next-icon-button" onClick={() => void load()} title={copy("刷新", "Refresh")}>
            <RefreshCcw size={17} aria-hidden="true" />
          </button>
          <button type="button" className="next-primary-button" onClick={() => { window.location.href = "/cases/new"; }}>
            <Sparkles size={17} aria-hidden="true" />
            {copy("发起研究", "Start research")}
          </button>
        </div>
      </section>

      <div className="next-task-tabs">
        <button type="button" className="is-active">{copy("我的任务", "My cases")} <span>{items.length}</span></button>
        <button type="button">{copy("待复核", "For review")} <span>{countMatching(items, /review|accept/i)}</span></button>
        <button type="button">{copy("存在阻断", "Blocked")} <span>{countMatching(items, /block|fail/i)}</span></button>
        <button type="button">{copy("最近完成", "Recently completed")} <span>{countMatching(items, /complete/i)}</span></button>
      </div>

      <div className="next-task-layout">
        <section className="next-task-ledger">
          <div className="next-task-toolbar">
            <label>
              <Search size={16} aria-hidden="true" />
              <input value={localSearch} onChange={(event) => setLocalSearch(event.target.value)} placeholder={copy("搜索任务或公司", "Search cases or companies")} />
            </label>
            <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label={copy("状态", "Status")}>
              <option value="all">{copy("全部状态", "All statuses")}</option>
              {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <span>{copy(`${visible.length} 个任务`, `${visible.length} cases`)}</span>
          </div>

          <div className="next-task-table">
            <div className="next-task-table-head" aria-hidden="true">
              <span>{copy("研究问题", "Research question")}</span>
              <span>{copy("阶段", "Stage")}</span>
              <span>{copy("进度", "Progress")}</span>
              <span>{copy("证据", "Evidence")}</span>
              <span>{copy("缺口", "Gaps")}</span>
              <span>{copy("下一步", "Next")}</span>
            </div>
            {tasks.kind === "loading" ? <LoadingLine label={copy("正在加载研究任务", "Loading research cases")} /> : null}
            {tasks.kind === "error" ? <ErrorLine message={tasks.message} onRetry={() => void load()} /> : null}
            {visible.map((item) => (
              <TaskRow
                key={item.case_id}
                item={item}
                selected={item.case_id === selectedId}
                detail={item.case_id === selectedId && detail.kind === "ready" ? detail.data : undefined}
                onSelect={() => setSelectedId(item.case_id)}
                localize={localizeFixtureText}
              />
            ))}
          </div>
        </section>

        <aside className="next-task-inspector">
          {selected ? (
            <>
              <header>
                <p>P36 · AI INFRASTRUCTURE</p>
                <h2>{localizeFixtureText(selected.query)}</h2>
                <span>{formatDateTime(selected.updated_at)}</span>
              </header>
              <TaskInspector detail={detail} />
              <button
                type="button"
                className="next-primary-button next-open-case"
                onClick={() => navigate({ kind: "case", caseId: selected.case_id, surface: "run" })}
              >
                {copy("打开研究工作台", "Open research workspace")}
                <ArrowRight size={17} aria-hidden="true" />
              </button>
            </>
          ) : <p className="next-empty-copy">{copy("选择一个研究任务。", "Select a research case.")}</p>}
        </aside>
      </div>
    </div>
  );
}

function TaskRow({
  item,
  selected,
  detail,
  onSelect,
  localize,
}: {
  item: TaskCenterRow;
  selected: boolean;
  detail?: CaseBundle;
  onSelect: () => void;
  localize: (value: string) => string;
}) {
  const { copy } = useWorkbenchLocale();
  const cells = detail?.research?.selected_cell_count ?? detail?.plan?.cells.length ?? 0;
  const completed = detail?.analysis?.judgments.length ?? 0;
  const evidence = detail?.research?.candidate_count ?? detail?.evidence?.summary.candidate_count ?? 0;
  const gaps = detail ? countGaps(detail) : 0;
  const progress = cells ? Math.min(100, Math.round((completed / cells) * 100)) : 0;
  return (
    <button type="button" className={`next-task-row ${selected ? "is-selected" : ""}`} onClick={onSelect}>
      <span className="next-task-question">
        <strong><b>{/P36/i.test(item.query) ? "P36" : copy("研究", "Research")}</b>{localize(item.query)}</strong>
        <small>{item.case_id.slice(0, 20)} · v{item.case_version}</small>
      </span>
      <span className="next-stage-chip">{detail?.analysis ? copy("待复核", "For review") : item.status}</span>
      <span className="next-progress-cell"><b>{cells ? `${completed} / ${cells}` : "—"}</b><i><em style={{ width: `${progress}%` }} /></i></span>
      <span className="next-number-cell"><b>{evidence || "—"}</b><small>{detail?.analysis?.numeric.facts.length ? `${detail.analysis.numeric.facts.length} ${copy("精确事实", "exact facts")}` : ""}</small></span>
      <span className={gaps ? "next-gap-cell" : ""}>{detail ? gaps : "—"}</span>
      <span>{detail?.analysis ? copy("完成 Senior R2", "Complete Senior R2") : copy("继续研究", "Continue research")}</span>
    </button>
  );
}

function TaskInspector({ detail }: { detail: BundleState }) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  if (detail.kind !== "ready") {
    return detail.kind === "error"
      ? <p className="next-empty-copy">{detail.message}</p>
      : <LoadingLine label={copy("读取研究链", "Loading research chain")} />;
  }
  const bundle = detail.data;
  const analysis = bundle.analysis;
  const research = bundle.research;
  const headline = analysis?.judgments[0]?.judgment_zh_cn ?? copy("研究链尚未形成主判断", "The research chain has not formed a primary judgment yet");
  return (
    <div className="next-inspector-body">
      <section className="next-thesis-summary">
        <p>{copy("当前判断", "Current thesis")}</p>
        <strong>{localizeFixtureText(headline)}</strong>
      </section>
      <div className="next-stat-strip">
        <span><small>{copy("研究完成度", "Completion")}</small><b>{research ? `${analysis?.judgments.length ?? 0}/${research.selected_cell_count}` : "—"}</b></span>
        <span><small>{copy("候选证据", "Candidates")}</small><b>{research?.candidate_count ?? 0}</b></span>
        <span><small>{copy("开放缺口", "Open gaps")}</small><b className="is-risk">{countGaps(bundle)}</b></span>
      </div>
      <section className="next-inspector-list">
        <h3>{copy("活跃研究单元", "Active research cells")}</h3>
        {(analysis?.judgments ?? []).slice(0, 6).map((judgment, index) => (
          <div key={judgment.judgment_id}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <b>{labelToken(judgment.evidence_role)}</b>
            <em>{judgment.remaining_gaps.length ? copy("需补证", "Gap") : copy("已形成", "Ready")}</em>
          </div>
        ))}
      </section>
      {bundle.failures.length ? <p className="next-read-warning">{copy("部分可选视图不可用：", "Some optional views are unavailable: ")}{bundle.failures.join(" · ")}</p> : null}
    </div>
  );
}

function NextCaseWorkspace({
  route,
  online,
  navigate,
}: {
  route: Extract<NextRoute, { kind: "case" }>;
  online: boolean;
  navigate: (route: NextRoute) => void;
}) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const [revision, setRevision] = useState(0);
  const [executionPolling, setExecutionPolling] = useState(false);
  const bundle = useCaseBundle(route.caseId, online, revision);
  const refresh = useCallback(() => setRevision((current) => current + 1), []);
  const startExecutionPolling = useCallback(() => setExecutionPolling(true), []);
  useEffect(() => {
    if (bundle.kind !== "ready") return;
    const activeRun = bundle.data.runProjection?.runs.some((run) => /pending|running/.test(run.state)) ?? false;
    const activeWorkUnit = bundle.data.workUnits?.work_units.some((unit) => /pending|running/.test(unit.state)) ?? false;
    if (executionPolling && !activeRun && !activeWorkUnit) {
      setExecutionPolling(false);
      return;
    }
    if (!activeRun && !(executionPolling && activeWorkUnit)) return;
    const timer = window.setTimeout(refresh, 700);
    return () => window.clearTimeout(timer);
  }, [bundle, executionPolling, refresh]);
  return (
    <div className="next-case-page">
      <header className="next-case-header">
        <button type="button" className="next-back-button" onClick={() => navigate({ kind: "tasks" })}>
          <ArrowLeft size={16} aria-hidden="true" />{copy("研究任务", "Research cases")}
        </button>
        <div>
          <p>P36 · AI INFRASTRUCTURE</p>
          <h1>{bundle.kind === "ready" ? localizeFixtureText(bundle.data.caseProjection?.query ?? route.caseId) : route.caseId}</h1>
          <span>{route.caseId} · {copy("内部研究", "Internal research")}</span>
        </div>
        <div className="next-case-header-actions">
          <button type="button" className="next-icon-button" onClick={refresh} title={copy("刷新当前视图", "Refresh current view")}><RefreshCcw size={17} /></button>
          <span className="next-stage-chip">{bundle.kind === "ready" ? caseStage(bundle.data, copy) : copy("读取中", "Loading")}</span>
        </div>
      </header>

      {bundle.kind === "loading" || bundle.kind === "idle" ? <LoadingLine label={copy("正在组合研究工作区", "Assembling research workspace")} /> : null}
      {bundle.kind === "error" ? <ErrorLine message={bundle.message} /> : null}
      {bundle.kind === "ready" ? (
        <>
          {route.surface === "run" ? <RunSurface bundle={bundle.data} caseId={route.caseId} online={online} refresh={refresh} onExecutionQueued={startExecutionPolling} navigate={navigate} /> : null}
          {route.surface === "evidence" ? <EvidenceSurface bundle={bundle.data} /> : null}
          {route.surface === "workpaper" ? <WorkpaperSurface bundle={bundle.data} /> : null}
          {route.surface === "report" ? <ReportSurface bundle={bundle.data} /> : null}
          {route.surface === "review" ? <ReviewSurface bundle={bundle.data} caseId={route.caseId} /> : null}
          {route.surface === "inspect" ? <InspectSurface bundle={bundle.data} /> : null}
        </>
      ) : null}
    </div>
  );
}

type Fin01ProfileKey = "deterministic" | "agent_fixture_shadow";

function RunSurface({
  bundle,
  caseId,
  online,
  refresh,
  onExecutionQueued,
  navigate,
}: {
  bundle: CaseBundle;
  caseId: string;
  online: boolean;
  refresh: () => void;
  onExecutionQueued: () => void;
  navigate: (route: NextRoute) => void;
}) {
  const { copy, localizeFixtureText, formatDateTime } = useWorkbenchLocale();
  const [profile, setProfile] = useState<Fin01ProfileKey>(() => bundle.runProjection?.runs.some(isAgentFixtureRun) ? "agent_fixture_shadow" : "deterministic");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const deterministicRun = bundle.runProjection?.runs.find((run) => !isAgentFixtureRun(run));
  const agentRun = bundle.runProjection?.runs.find(isAgentFixtureRun);
  const selectedRun = profile === "agent_fixture_shadow" ? agentRun : deterministicRun;
  const legacyEvents = buildRunEvents(bundle);
  const events = selectedRun?.events ?? [];
  const agentTraceCount = events.filter((event) => isAgentTraceEvent(event.event_type)).length;
  const isComplete = selectedRun?.state === "succeeded" || (!selectedRun && profile === "deterministic" && Boolean(bundle.analysis));
  const canStartAgent = online && profile === "agent_fixture_shadow" && !agentRun && bundle.plan?.review_status === "accepted" && !starting;
  useEffect(() => {
    if (agentRun) setStarting(false);
  }, [agentRun]);

  async function startAgentFixtureShadow() {
    if (!canStartAgent || !bundle.caseProjection || !bundle.plan) return;
    setStarting(true);
    setStartError(null);
    try {
      await executionApi.createWorkUnit(caseId, {
        work_unit_type: AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
        expected_case_version: bundle.caseProjection.case_version,
        input_head_digest: await decisionSurfaceInputHeadDigest(bundle.plan.contract_version_id),
        actor_ref: executionApi.actorRef,
        idempotency_key: uniqueKey("workbench-next-agent-shadow"),
      });
      onExecutionQueued();
      refresh();
    } catch (error) {
      setStartError(errorMessage(error));
      setStarting(false);
    }
  }

  return (
    <div className="next-run-layout">
      <section className="next-run-thread">
        <header className="next-surface-heading">
          <div><p>{copy("Agent 研究", "Agent research")}</p><h2>{copy("研究运行", "Research run")}</h2></div>
          <span className={`next-run-status ${isComplete ? "is-review" : ""} ${selectedRun?.state === "failed" ? "is-failed" : ""}`}>{runStateLabel(selectedRun?.state, isComplete, copy)}</span>
        </header>
        <div className="next-profile-switcher" aria-label={copy("执行 Profile", "Execution profile")}>
          <ProfileChoice
            active={profile === "deterministic"}
            title={copy("本地确定性预览", "Local deterministic preview")}
            state={deterministicRun?.state ?? (bundle.analysis ? "preview_ready" : "not_run")}
            exactRef={deterministicRun?.execution_profile_version_ref ?? "fin01.execution_profile.p36_local_deterministic:v1"}
            onClick={() => setProfile("deterministic")}
          />
          <ProfileChoice
            active={profile === "agent_fixture_shadow"}
            title={copy("Agent 编排影子（Fixture）", "Agent orchestration shadow (fixture)")}
            state={agentRun?.state ?? "not_run"}
            exactRef={agentRun?.execution_profile_version_ref ?? "fin01.execution_profile.agent_fixture_shadow:v1"}
            onClick={() => setProfile("agent_fixture_shadow")}
          />
        </div>
        <article className="next-user-prompt">
          <span>RA</span>
          <div><small>{copy("研究问题", "Research question")}</small><p>{localizeFixtureText(bundle.caseProjection?.query ?? caseId)}</p></div>
        </article>
        <div className="next-event-stream">
          {selectedRun ? events.map((event) => (
            <article key={event.event_id} className={`next-run-event ${selectedRun.state === "failed" && /FAILED$/.test(event.event_type) ? "failed" : "done"}`}>
              <span className="next-event-icon">{selectedRun.state === "failed" && /FAILED$/.test(event.event_type) ? <AlertCircle size={15} /> : <Check size={15} />}</span>
              <div>
                <header><b>{runEventLabel(event.event_type, copy)}</b><time>{formatDateTime(event.occurred_at)}</time></header>
                <p>{structuredEventSummary(event.event_type, event.details, copy)}</p>
                <small>#{event.sequence} · {event.event_id}</small>
                <details className="next-structured-details"><summary>{copy("结构化字段（不含私有思维链）", "Structured fields (no private chain of thought)")}</summary><pre>{formatJson(event.details)}</pre></details>
              </div>
            </article>
          )) : legacyEvents.map((event, index) => (
            <article key={`${event.label}-${index}`} className={`next-run-event ${event.status}`}>
              <span className="next-event-icon">{event.status === "done" ? <Check size={15} /> : event.status === "active" ? <LoaderCircle size={15} /> : <CircleDot size={14} />}</span>
              <div><header><b>{runEventLabel(event.label, copy)}</b><time>{event.time ? formatDateTime(event.time) : ""}</time></header><p>{event.detail}</p>{event.meta ? <small>{event.meta}</small> : null}</div>
            </article>
          ))}
        </div>
        {selectedRun ? (
          <section className={`next-run-outcome ${selectedRun.state === "failed" ? "is-failed" : ""}`}>
            {selectedRun.state === "failed" ? <AlertCircle size={20} aria-hidden="true" /> : <ShieldCheck size={20} aria-hidden="true" />}
            <div><small>{copy("真实停止原因", "Exact stop reason")}</small><strong>{selectedRun.terminal_reason ?? copy("运行尚未终止", "Run has not stopped")}</strong><span>{agentTraceCount} Agent trace · {selectedRun.artifacts.length} artifacts · {selectedRun.events.length} lifecycle events</span></div>
            <button type="button" onClick={() => navigate({ kind: "case", caseId, surface: "inspect" })}>{copy("检查 exact artifacts", "Inspect exact artifacts")}<ArrowRight size={15} /></button>
          </section>
        ) : null}
        <div className="next-run-composer">
          <textarea placeholder={copy("补充研究问题或要求 Agent 继续核验…", "Add a research question or ask the agent to verify further…")} disabled />
          <button type="button" disabled={!canStartAgent} onClick={() => void startAgentFixtureShadow()}>{starting ? <LoaderCircle size={16} /> : <Play size={16} />}{profile === "agent_fixture_shadow" ? agentRun ? copy("Fixture Run 已形成", "Fixture run exists") : copy("运行 Agent Fixture-Shadow", "Run agent fixture-shadow") : copy("确定性预览只读", "Deterministic preview is read-only")}</button>
        </div>
        {startError ? <p className="next-form-error next-run-error">{startError}</p> : null}
      </section>
      <RunConfiguration bundle={bundle} profile={profile} run={selectedRun} />
    </div>
  );
}

function ProfileChoice({ active, title, state, exactRef, onClick }: { active: boolean; title: string; state: string; exactRef: string; onClick: () => void }) {
  return <button type="button" className={active ? "is-active" : ""} aria-pressed={active} onClick={onClick}><span>{title}</span><b>{state}</b><code>{exactRef}</code></button>;
}

function RunConfiguration({ bundle, profile, run }: { bundle: CaseBundle; profile: Fin01ProfileKey; run?: ResearchRunProjectionItem }) {
  const { copy } = useWorkbenchLocale();
  const executionCounts = runExecutionCounts(run);
  return (
    <aside className="next-run-config">
      <header><Settings2 size={18} /><h2>{copy("运行配置", "Run configuration")}</h2></header>
      <ConfigSection icon={<Bot size={16} />} label="Profile" value={run?.execution_profile_version_ref ?? (profile === "agent_fixture_shadow" ? "fin01.execution_profile.agent_fixture_shadow:v1" : "fin01.execution_profile.p36_local_deterministic:v1")} />
      <ConfigSection icon={<Bot size={16} />} label={copy("执行模式", "Execution mode")} value={profile === "agent_fixture_shadow" ? copy("LangGraph Fixture-Shadow（非真实 Agent 质量）", "LangGraph fixture-shadow (not real agent quality)") : copy("本地确定性分析器", "Local deterministic analyzer")} />
      <ConfigSection icon={<Globe2 size={16} />} label={copy("检索", "Retrieval")} value={bundle.research ? "Local RAG + SQL + Graph" : copy("尚未准备", "Not prepared")} />
      <ConfigSection icon={<Wrench size={16} />} label={copy("技能", "Skills")} value="P36 AI Infrastructure" />
      <ConfigSection icon={<Network size={16} />} label={copy("知识图谱", "Knowledge graph")} value={bundle.research?.cells.some((cell) => cell.retrieval_lane === "research_graph") ? copy("研究关系图已连接", "Research graph connected") : copy("未连接", "Not connected")} />
      <ConfigSection icon={<GitBranch size={16} />} label={copy("编排", "Orchestration")} value={copy("检索 → 数字 → 判断 → Writer", "Retrieval → numeric → judgment → writer")} />
      {run ? <dl className="next-run-identity"><div><dt>Run</dt><dd>{run.research_run_id}</dd></div><div><dt>Attempt</dt><dd>{run.attempt_id}</dd></div><div><dt>WorkUnit</dt><dd>{run.work_unit_id}</dd></div></dl> : null}
      <div className="next-config-boundary">
        <ShieldCheck size={17} />
        <div><b>{copy("当前边界", "Current boundary")}</b><span>{copy("Fixture-only；不含私有思维链；无模型、网络、外部工具或业务写入", "Fixture-only; no private chain of thought, model, network, external tool, or business writes")}</span></div>
      </div>
      <dl className="next-config-counts">
        <div><dt>{copy("模型调用", "Model calls")}</dt><dd>{numberField(executionCounts, "model_calls") ?? bundle.analysis?.execution_counts.model_calls ?? 0}</dd></div>
        <div><dt>{copy("外部工具", "External tools")}</dt><dd>{numberField(executionCounts, "external_tool_calls") ?? 0}</dd></div>
        <div><dt>{copy("业务写入", "Business writes")}</dt><dd>{numberField(executionCounts, "business_writes") ?? bundle.analysis?.execution_counts.case_mutation_calls ?? 0}</dd></div>
      </dl>
    </aside>
  );
}

function ConfigSection({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <section className="next-config-section"><p>{icon}{label}<ChevronDown size={14} /></p><strong>{value}</strong></section>;
}

function EvidenceSurface({ bundle }: { bundle: CaseBundle }) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  const researchCells = bundle.research?.cells ?? [];
  return (
    <section className="next-document-surface">
      <header className="next-surface-heading">
        <div><p>{copy("证据工作区", "Evidence workspace")}</p><h2>{copy("证据矩阵", "Evidence matrix")}</h2><span>{copy("按判断角色比较候选、精确事实与未关闭缺口。", "Compare candidates, exact facts, and open gaps by judgment role.")}</span></div>
        <div className="next-stat-strip is-compact">
          <span><small>{copy("候选", "Candidates")}</small><b>{bundle.research?.candidate_count ?? 0}</b></span>
          <span><small>{copy("精确事实", "Exact facts")}</small><b>{bundle.analysis?.numeric.facts.length ?? bundle.numeric?.facts.length ?? 0}</b></span>
          <span><small>{copy("缺口", "Gaps")}</small><b className="is-risk">{countGaps(bundle)}</b></span>
        </div>
      </header>
      <div className="next-evidence-grid">
        {researchCells.map((cell, index) => (
          <article key={cell.cell_key} className="next-evidence-row">
            <header><span>{String(index + 1).padStart(2, "0")}</span><div><p>{labelToken(cell.evidence_role)}</p><h3>{localizeFixtureText(cell.decision_question)}</h3></div><em className={cell.typed_gap ? "is-gap" : ""}>{cell.typed_gap ? copy("存在缺口", "Gap") : copy("候选已就绪", "Ready")}</em></header>
            <div className="next-evidence-candidates">
              {cell.candidates.map((candidate) => (
                <section key={candidate.candidate_id}>
                  <p>{candidate.source_name} · {candidate.published_at}</p>
                  <strong>{localizeFixtureText(candidate.title)}</strong>
                  <span>{localizeFixtureText(candidate.excerpt)}</span>
                  <footer><b>{candidate.retrieval_lane}</b><em>{candidate.exact_value_authority ? copy("精确值权威", "Exact-value authority") : copy("判断候选", "Judgment candidate")}</em></footer>
                </section>
              ))}
              {!cell.candidates.length ? <p className="next-empty-copy">{copy("当前没有候选证据。", "No evidence candidates are available.")}</p> : null}
            </div>
            {cell.typed_gap ? <div className="next-gap-note"><AlertCircle size={15} />{localizeFixtureText(cell.typed_gap)}</div> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function WorkpaperSurface({ bundle }: { bundle: CaseBundle }) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  const presentation = s3PresentationPack(bundle);
  if (presentation) return <S3ExactWorkpaperSurface bundle={bundle} presentation={presentation} />;
  const judgments = bundle.analysis?.judgments ?? bundle.workpaper?.judgments.map((item) => ({
    judgment_id: item.judgment_id,
    evidence_role: item.evidence_role,
    decision_question: item.decision_question,
    judgment_zh_cn: item.judgment,
    counter_thesis_zh_cn: item.counter_thesis,
    what_would_change_en: item.what_would_change,
    evidence_refs: item.evidence_refs,
    numeric_refs: item.numeric_refs,
    remaining_gaps: item.remaining_gaps,
    confidence: item.confidence,
  })) ?? [];
  return (
    <section className="next-document-surface next-workpaper">
      <header className="next-surface-heading">
        <div><p>{copy("研究底稿", "Research workpaper")}</p><h2>{copy("判断、依据与反证", "Judgments, basis, and counterevidence")}</h2></div>
        <span className="next-stage-chip">{bundle.analysis?.workpaper.senior_r2_status ?? copy("待 Senior R2", "Awaiting Senior R2")}</span>
      </header>
      <div className="next-workpaper-layout">
        <nav>
          {judgments.map((judgment, index) => <a key={judgment.judgment_id} href={`#wp-${judgment.judgment_id}`}>{String(index + 1).padStart(2, "0")} {labelToken(judgment.evidence_role)}</a>)}
        </nav>
        <article className="next-workpaper-document">
          <header><small>{copy("内部研究底稿", "Internal research workpaper")}</small><h1>{localizeFixtureText(bundle.caseProjection?.query ?? "P36")}</h1><p>{copy("用于形成判断与人工复核；不是发布版本。", "Prepared for judgment formation and human review; not a release version.")}</p></header>
          {judgments.map((judgment, index) => (
            <section key={judgment.judgment_id} id={`wp-${judgment.judgment_id}`}>
              <p>{String(index + 1).padStart(2, "0")} · {labelToken(judgment.evidence_role)} · {labelToken(judgment.confidence)}</p>
              <h2>{localizeFixtureText(judgment.decision_question)}</h2>
              <strong>{localizeFixtureText(judgment.judgment_zh_cn)}</strong>
              <div className="next-workpaper-columns">
                <span><small>{copy("反证与边界", "Counterevidence and boundary")}</small>{localizeFixtureText(judgment.counter_thesis_zh_cn)}</span>
                <span><small>{copy("什么会改变判断", "What would change")}</small>{localizeFixtureText(judgment.what_would_change_en)}</span>
              </div>
              <footer>{judgment.evidence_refs.length} {copy("条证据", "evidence refs")} · {judgment.numeric_refs.length} {copy("项数字", "numeric refs")} · {judgment.remaining_gaps.length} {copy("个缺口", "gaps")}</footer>
            </section>
          ))}
        </article>
      </div>
    </section>
  );
}

function S3ExactWorkpaperSurface({ bundle, presentation }: { bundle: CaseBundle; presentation: S3ThreeCellPresentationPackView }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  return (
    <section className="next-document-surface next-workpaper next-s3-workpaper">
      <header className="next-surface-heading">
        <div><p>{copy("精确三 Cell 底稿", "Exact three-cell workpaper")}</p><h2>{copy("判断、事实、图谱缺口与返修路径", "Judgment, facts, graph gaps, and repair routes")}</h2><span>{copy("所有内容绑定同一 ResearchRun；为什么、缺口与 WWC 只读取现有 Artifact，不自动发起新研究。", "Everything is bound to one ResearchRun; why, gaps, and WWC read existing artifacts without starting new research.")}</span></div>
        <span className="next-stage-chip">{presentation.workpaper.status}</span>
      </header>
      <div className="next-s3-binding-strip">
        <span><small>Run</small><code>{presentation.research_run_id}</code></span>
        <span><small>Workpaper</small><code>{presentation.workpaper.artifact_ref}</code></span>
        <span><small>Pack digest</small><code>{presentation.presentation_pack_digest}</code></span>
      </div>
      <div className="next-workpaper-layout">
        <nav>{presentation.workpaper.cell_sections.map((cell, index) => <a key={cell.cell_version_ref} href={`#s3-wp-${cell.program_cell_id}`}>{String(index + 1).padStart(2, "0")} {cellHeading(cell.program_cell_id, copy)}</a>)}</nav>
        <article className="next-workpaper-document">
          <header><small>{copy("内部有界研究底稿", "Internal bounded research workpaper")}</small><h1>{localizeFixtureText(bundle.caseProjection?.query ?? "NVDA")}</h1><p>{copy("机器完整性投影已形成；Human Review 尚未执行。", "The machine-integrity projection is ready; human review has not been performed.")}</p></header>
          {presentation.workpaper.cell_sections.map((cell, index) => (
            <section key={cell.cell_version_ref} id={`s3-wp-${cell.program_cell_id}`} className="next-s3-cell-section">
              <p>{String(index + 1).padStart(2, "0")} · {cellHeading(cell.program_cell_id, copy)} · {cell.review_status}</p>
              <h2>{localizeFixtureText(cell.decision_question)}</h2>
              <strong>{localizeFixtureText(cell.direct_answer)}</strong>
              <div className="next-s3-cell-facts">
                <span><small>{copy("事实层", "Fact layer")}</small>{cell.fact_statements.length ? cell.fact_statements.map((fact) => <b key={fact}>{localizeFixtureText(fact)}</b>) : <b>{copy("无已晋升事实", "No promoted facts")}</b>}</span>
                <span><small>Evidence / Numeric</small><b>{cell.evidence_refs.length} Evidence · {cell.numeric_refs.length} Numeric</b><code>{cell.specialist_judgment_ref}</code></span>
              </div>
              <details className="next-s3-drilldown" open>
                <summary><Network size={16} />{copy("Graph drill-down 与业务边界", "Graph drill-down and business boundary")}</summary>
                <dl><div><dt>Graph</dt><dd>{cell.graph_drilldown.graph_edge_projection_ref}</dd></div><div><dt>{copy("权限", "Authority")}</dt><dd>{cell.graph_drilldown.graph_authority} · {cell.graph_drilldown.graph_status}</dd></div><div><dt>{copy("自动新研究", "Automatic new research")}</dt><dd>{String(cell.graph_drilldown.automatic_new_research)}</dd></div></dl>
              </details>
              <div className="next-workpaper-columns next-s3-decision-grid">
                <span><small>{copy("缺口 / Cannot infer", "Gaps / cannot infer")}</small>{cell.gaps.map((gap) => <b key={gap}>{gap}</b>)}</span>
                <span><small>{copy("什么会改变判断", "What would change")}</small>{cell.what_would_change.map((item) => <b key={item}>{localizeFixtureText(item)}</b>)}</span>
              </div>
              <footer><span>{copy("返修", "Repair")}: {cell.repair_ticket_refs.join(" · ")}</span><span>{copy("停止语义", "Stop semantic")}: {cell.stop_semantic}</span><span>Claim: {cell.surface_claim_ref}</span></footer>
            </section>
          ))}
        </article>
      </div>
    </section>
  );
}

function ReportSurface({ bundle }: { bundle: CaseBundle }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const presentation = s3PresentationPack(bundle);
  if (presentation) return <S3ExactReportSurface presentation={presentation} />;
  const writer = bundle.analysis?.writer;
  const deliverable = bundle.deliverable;
  const sections = writer?.sections.map((section) => ({ id: section.section_id, heading: section.heading_zh_cn, paragraphs: [section.content_zh_cn] }))
    ?? deliverable?.sections.map((section) => ({ id: section.section_id, heading: section.heading, paragraphs: section.lines }))
    ?? [];
  return (
    <section className="next-document-surface next-report">
      <header className="next-surface-heading">
        <div><p>{copy("研究结论", "Research outcome")}</p><h2>{copy("内部报告预览", "Internal report preview")}</h2></div>
        <div className="next-heading-actions"><span className="next-alpha-chip">NO-SOURCE WRITER</span><span className="next-stage-chip">{copy("待 Senior R2", "Awaiting Senior R2")}</span></div>
      </header>
      <article className="next-report-document">
        <header><p>P36 · AI INFRASTRUCTURE</p><h1>{localizeFixtureText(writer?.title_zh_cn ?? deliverable?.title ?? bundle.caseProjection?.query ?? "P36")}</h1><span>{copy("内部草稿 · 不构成投资建议或发布结论", "Internal draft · not investment advice or a released conclusion")}</span></header>
        <section className="next-report-executive">
          <small>{copy("核心回答", "Executive answer")}</small>
          <strong>{localizeFixtureText(bundle.analysis?.judgments[0]?.judgment_zh_cn ?? copy("尚未形成核心回答。", "No executive answer is available yet."))}</strong>
        </section>
        {sections.map((section, index) => (
          <section key={section.id}>
            <p>{String(index + 1).padStart(2, "0")}</p>
            <h2>{localizeFixtureText(section.heading)}</h2>
            {section.paragraphs.map((line, lineIndex) => <p key={lineIndex}>{localizeFixtureText(line)}</p>)}
          </section>
        ))}
        <footer><ShieldCheck size={17} />{copy("Writer 未访问来源；报告只消费已冻结底稿。", "The writer did not access sources; this report only consumes the frozen workpaper.")}</footer>
      </article>
    </section>
  );
}

function S3ExactReportSurface({ presentation }: { presentation: S3ThreeCellPresentationPackView }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  return (
    <section className="next-document-surface next-report next-s3-report">
      <header className="next-surface-heading">
        <div><p>{copy("同一 Run 研究结论", "Same-run research outcome")}</p><h2>{copy("三 Cell 内部报告", "Three-cell internal report")}</h2><span>{copy("Writer 只消费已裁决 heads；没有 source、retrieval、外部工具或 raw Candidate 权限。", "The writer consumes adjudicated heads only and has no source, retrieval, external-tool, or raw-candidate authority.")}</span></div>
        <div className="next-heading-actions"><span className="next-alpha-chip">NO-SOURCE · NO-RETRIEVAL</span><span className="next-stage-chip">HUMAN REVIEW NOT PERFORMED</span></div>
      </header>
      <div className="next-s3-binding-strip">
        <span><small>Report</small><code>{presentation.report.artifact_ref}</code></span>
        <span><small>Workpaper</small><code>{presentation.report.workpaper_artifact_ref}</code></span>
        <span><small>Trace</small><code>{presentation.trace_review.artifact_ref}</code></span>
      </div>
      <article className="next-report-document">
        <header><p>NVDA · THREE-CELL R2 CANDIDATE</p><h1>{localizeFixtureText(presentation.report.title)}</h1><span>{copy("内部有界草稿 · 不构成 Alpha、投资建议或发布结论", "Internal bounded draft · not Alpha, investment advice, or a release conclusion")}</span></header>
        <section className="next-report-executive"><small>{copy("跨 Cell 核心回答", "Cross-cell executive answer")}</small><strong>{localizeFixtureText(presentation.report.executive_answer)}</strong></section>
        {presentation.report.sections.map((section, index) => (
          <section key={section.section_id}>
            <p>{String(index + 1).padStart(2, "0")} · {cellHeading(section.program_cell_id, copy)}</p>
            <h2>{localizeFixtureText(section.heading)}</h2>
            <p>{localizeFixtureText(section.content)}</p>
            <div className="next-s3-report-refs"><code>Claim {section.surface_claim_ref}</code><code>Judgment {section.specialist_judgment_ref}</code><span>{section.evidence_refs.length} Evidence · {section.numeric_refs.length} Numeric</span><span>{section.boundary}</span></div>
          </section>
        ))}
        <section className="next-s3-report-gaps"><h2>{copy("仍未解决的实质缺口", "Unresolved material gaps")}</h2>{presentation.report.presentation_gaps.map((gap) => <p key={gap}>{gap}</p>)}</section>
        <footer><ShieldCheck size={17} />{copy("确定性 Writer 投影未调用模型；报告与底稿共享 exact Claim、Judgment 和 Artifact refs。", "The deterministic writer projection made no model call; report and workpaper share exact Claim, Judgment, and Artifact refs.")}</footer>
      </article>
    </section>
  );
}

function ReviewSurface({ bundle, caseId }: { bundle: CaseBundle; caseId: string }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const presentation = s3PresentationPack(bundle);
  const [sessions, setSessions] = useState(bundle.baseline);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  if (presentation) return <S3ExactReviewSurface presentation={presentation} />;
  const latest = sessions?.sessions.at(-1) ?? null;

  async function startReview() {
    setStarting(true);
    setError("");
    try {
      const session = await baselineApi.start(caseId, "human_senior_internal", uniqueKey("baseline"));
      setSessions((current) => ({
        schema_version: current?.schema_version ?? "human_baseline_session_list_v1",
        case_id: caseId,
        sessions: [...(current?.sessions ?? []), session],
        counts: {
          session_count: (current?.counts.session_count ?? 0) + 1,
          completed_review_count: current?.counts.completed_review_count ?? 0,
        },
        boundary: current?.boundary ?? "internal_human_baseline_only",
      }));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setStarting(false);
    }
  }

  return (
    <section className="next-document-surface next-review">
      <header className="next-surface-heading">
        <div><p>HUMAN SENIOR REVIEW</p><h2>{copy("精确人工复核", "Exact human review")}</h2><span>{copy("基于冻结的证据、数字、底稿与 Writer 摘要记录人工判断。", "Record a human decision over frozen evidence, numbers, workpaper, and writer output.")}</span></div>
        <span className="next-stage-chip">{latest ? reviewStatus(latest, copy) : copy("尚未开始", "Not started")}</span>
      </header>
      <div className="next-review-steps">
        <span className="is-active"><b>1</b>{copy("分析师基线", "Analyst baseline")}</span>
        <i />
        <span className={latest?.analyst_submission ? "is-active" : ""}><b>2</b>Senior Review</span>
        <i />
        <span className={latest?.final_review_digest ? "is-active" : ""}><b>3</b>{copy("精确记录", "Exact record")}</span>
      </div>
      {!latest ? (
        <div className="next-review-start">
          <FileCheck2 size={34} />
          <h3>{copy("开始本次真实任务基线", "Start this real task baseline")}</h3>
          <p>{copy("系统将绑定当前 research、analysis、workpaper 与 writer digest；开始后不替你填写判断。", "The system will bind the current research, analysis, workpaper, and writer digests; it will not fill in your judgment.")}</p>
          <button type="button" className="next-primary-button" onClick={() => void startReview()} disabled={starting}>{starting ? <LoaderCircle size={16} /> : <Play size={16} />}{copy("开始评审", "Start review")}</button>
          {error ? <p className="next-form-error">{error}</p> : null}
        </div>
      ) : latest.status === "in_progress" ? (
        <AnalystReviewForm session={latest} caseId={caseId} onUpdated={(session) => setSessions(replaceSession(sessions, session))} />
      ) : latest.status === "analyst_submitted" ? (
        <SeniorReviewForm session={latest} caseId={caseId} onUpdated={(session) => setSessions(replaceSession(sessions, session))} />
      ) : (
        <div className="next-review-record">
          <CheckCircle2 size={34} />
          <h3>{copy("精确人工复核已记录", "Exact human review recorded")}</h3>
          <dl><div><dt>{copy("决策", "Decision")}</dt><dd>{latest.senior_review?.decision}</dd></div><div><dt>{copy("最终摘要", "Final digest")}</dt><dd>{latest.final_review_digest}</dd></div><div><dt>{copy("评语", "Comment")}</dt><dd>{localizeFixtureText(latest.senior_review?.review_comment ?? "")}</dd></div></dl>
        </div>
      )}
    </section>
  );
}

function S3ExactReviewSurface({ presentation }: { presentation: S3ThreeCellPresentationPackView }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const binding = presentation.trace_review.review_binding;
  return (
    <section className="next-document-surface next-review next-s3-review">
      <header className="next-surface-heading">
        <div><p>EXACT REVIEW TARGET</p><h2>{copy("三 Cell 机器核验与人工复核绑定", "Three-cell machine verification and human-review binding")}</h2><span>{copy("机器核验不等于人工接受；当前只准备 exact review target，没有代签 Human Review。", "Machine verification is not human acceptance; only the exact review target is prepared, with no human decision signed.")}</span></div>
        <span className="next-stage-chip">{binding.human_review_status}</span>
      </header>
      <div className="next-s3-review-binding">
        <dl><div><dt>Profile</dt><dd>{binding.execution_profile_version_ref}</dd></div><div><dt>Input head digest</dt><dd>{binding.input_head_digest}</dd></div><div><dt>Analysis as-of</dt><dd>{binding.analysis_as_of}</dd></div><div><dt>Verifier input digest</dt><dd>{binding.verifier_input_digest}</dd></div><div><dt>{copy("机器决策", "Machine decision")}</dt><dd>{binding.verifier_decision}</dd></div><div><dt>{copy("人工决策", "Human decision")}</dt><dd>{binding.human_decision}</dd></div></dl>
      </div>
      <section className="next-s3-findings"><h3>{copy("分层 Verifier findings", "Layered verifier findings")}</h3>{binding.findings.map((finding) => <article key={finding.finding_id} className={finding.status === "pass" ? "is-pass" : "is-warning"}><span>{finding.layer}</span><b>{finding.status}</b><p>{localizeFixtureText(finding.message)}</p><code>{finding.earliest_owner_ref}</code></article>)}</section>
      <section className="next-s3-review-targets"><h3>{copy("逐 Cell 审阅目标", "Cell-level review targets")}</h3>{binding.review_targets.map((target) => <article key={target.review_target_id}><header><div><p>{cellHeading(target.program_cell_id, copy)}</p><h4>{target.review_status}</h4></div><span>{target.source_grade}</span></header><dl><div><dt>Claim</dt><dd>{target.surface_claim_ref}</dd></div><div><dt>Judgment</dt><dd>{target.specialist_judgment_ref}</dd></div><div><dt>Numeric sanity</dt><dd>{target.numeric_sanity_status}</dd></div><div><dt>{copy("事实类型", "Fact type")}</dt><dd>{target.official_or_estimate_flag}</dd></div><div><dt>{copy("停止语义", "Stop semantic")}</dt><dd>{target.stop_semantic}</dd></div><div><dt>{copy("返修", "Repair")}</dt><dd>{target.repair_ticket_refs.join(" · ")}</dd></div></dl><div className="next-s3-review-actions">{target.allowed_review_actions.map((action) => <span key={action}>{action}</span>)}</div></article>)}</section>
      <footer className="next-s3-review-stop"><ShieldCheck size={18} /><div><strong>{copy("Human Review 尚未执行", "Human review has not been performed")}</strong><p>{copy("本任务不写入 accepted/rejected 等动作；这些动作必须在 exact digest 确认后由真实 reviewer 显式提交。", "This task writes no accepted/rejected action; a real reviewer must explicitly submit one after confirming exact digests.")}</p></div></footer>
    </section>
  );
}

function AnalystReviewForm({ session, caseId, onUpdated }: { session: HumanBaselineSession; caseId: string; onUpdated: (session: HumanBaselineSession) => void }) {
  const { copy } = useWorkbenchLocale();
  const [form, setForm] = useState({ strongest: "", limitation: "", numeric: "", weakest: "", modification: "", usefulness: 3, reason: "", ui: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const updated = await baselineApi.submitAnalyst(caseId, session.session_id, {
        strongest_source: form.strongest,
        material_limitation: form.limitation,
        numeric_verification: form.numeric,
        weakest_judgment: form.weakest,
        required_modification: form.modification,
        writer_usefulness_score: form.usefulness,
        writer_usefulness_reason: form.reason,
        time_to_find_source_seconds: 0,
        time_to_verify_numeric_seconds: 0,
        time_to_identify_weakest_judgment_seconds: 0,
        time_to_review_writer_seconds: 0,
        repeated_work_count: 0,
        blocking_ui_issue: form.ui,
        idempotency_key: uniqueKey("analyst"),
      });
      onUpdated(updated);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }
  return (
    <form className="next-review-form" onSubmit={(event) => void submit(event)}>
      <ReviewField label={copy("最强证据及其限制", "Strongest evidence and its limitation")} value={form.strongest} onChange={(strongest) => setForm({ ...form, strongest })} />
      <ReviewField label={copy("最重要的实质限制", "Most material limitation")} value={form.limitation} onChange={(limitation) => setForm({ ...form, limitation })} />
      <ReviewField label={copy("数字复算过程与结果", "Numeric verification and result")} value={form.numeric} onChange={(numeric) => setForm({ ...form, numeric })} />
      <ReviewField label={copy("最弱判断", "Weakest judgment")} value={form.weakest} onChange={(weakest) => setForm({ ...form, weakest })} />
      <ReviewField label={copy("必须修改的内容", "Required modification")} value={form.modification} onChange={(modification) => setForm({ ...form, modification })} />
      <label className="next-score-field"><span>{copy("Writer 有用性（1-5）", "Writer usefulness (1-5)")}</span><input type="number" min={1} max={5} value={form.usefulness} onChange={(event) => setForm({ ...form, usefulness: Number(event.target.value) })} /></label>
      <ReviewField label={copy("评分理由", "Rating reason")} value={form.reason} onChange={(reason) => setForm({ ...form, reason })} />
      <ReviewField label={copy("阻断性的界面问题（可留空）", "Blocking UI issue (optional)")} value={form.ui} onChange={(ui) => setForm({ ...form, ui })} required={false} />
      {error ? <p className="next-form-error">{error}</p> : null}
      <button type="submit" className="next-primary-button" disabled={saving}>{saving ? <LoaderCircle size={16} /> : <Check size={16} />}{copy("提交分析师基线", "Submit analyst baseline")}</button>
    </form>
  );
}

function SeniorReviewForm({ session, caseId, onUpdated }: { session: HumanBaselineSession; caseId: string; onUpdated: (session: HumanBaselineSession) => void }) {
  const { copy } = useWorkbenchLocale();
  const [decision, setDecision] = useState<"approve" | "conditional_approve" | "return_for_follow_up">("conditional_approve");
  const [comment, setComment] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [scores, setScores] = useState({ research: 3, evidence: 3, reviewability: 3 });
  const [checks, setChecks] = useState({ numeric: false, gaps: false, digest: false });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const updated = await baselineApi.submitSenior(caseId, session.session_id, {
        reviewer_ref: "human_senior_internal",
        reviewer_role: "senior_analyst",
        decision,
        research_quality_score: scores.research,
        evidence_quality_score: scores.evidence,
        senior_reviewability_score: scores.reviewability,
        numeric_reproducibility_confirmed: checks.numeric,
        gap_boundaries_preserved: checks.gaps,
        exact_digest_confirmed: checks.digest,
        review_comment: comment,
        bounded_follow_up: followUp.split("\n").map((item) => item.trim()).filter(Boolean),
        idempotency_key: uniqueKey("senior"),
      });
      onUpdated(updated);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }
  return (
    <form className="next-review-form next-senior-form" onSubmit={(event) => void submit(event)}>
      <label><span>{copy("复核决策", "Review decision")}</span><select value={decision} onChange={(event) => setDecision(event.target.value as typeof decision)}><option value="approve">approve</option><option value="conditional_approve">conditional approve</option><option value="return_for_follow_up">return for follow-up</option></select></label>
      <div className="next-score-grid">
        <ScoreInput label={copy("研究质量", "Research quality")} value={scores.research} onChange={(research) => setScores({ ...scores, research })} />
        <ScoreInput label={copy("证据质量", "Evidence quality")} value={scores.evidence} onChange={(evidence) => setScores({ ...scores, evidence })} />
        <ScoreInput label={copy("可复核性", "Reviewability")} value={scores.reviewability} onChange={(reviewability) => setScores({ ...scores, reviewability })} />
      </div>
      <div className="next-review-checks">
        <CheckInput label={copy("数字可复算", "Numeric reproducibility confirmed")} checked={checks.numeric} onChange={(numeric) => setChecks({ ...checks, numeric })} />
        <CheckInput label={copy("缺口边界被保留", "Gap boundaries preserved")} checked={checks.gaps} onChange={(gaps) => setChecks({ ...checks, gaps })} />
        <CheckInput label={copy("精确 digest 已确认", "Exact digest confirmed")} checked={checks.digest} onChange={(digest) => setChecks({ ...checks, digest })} />
      </div>
      <ReviewField label={copy("Senior Review 评语", "Senior review comment")} value={comment} onChange={setComment} />
      <ReviewField label={copy("受限后续事项（每行一项）", "Bounded follow-up (one per line)")} value={followUp} onChange={setFollowUp} required={false} />
      {error ? <p className="next-form-error">{error}</p> : null}
      <button type="submit" className="next-primary-button" disabled={saving || !checks.digest}>{saving ? <LoaderCircle size={16} /> : <ShieldCheck size={16} />}{copy("记录精确人工复核", "Record exact human review")}</button>
    </form>
  );
}

function ReviewField({ label, value, onChange, required = true }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return <label><span>{label}</span><textarea required={required} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function ScoreInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label><span>{label}</span><input type="number" min={1} max={5} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function CheckInput({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span>{label}</span></label>;
}

function InspectSurface({ bundle }: { bundle: CaseBundle }) {
  const { copy } = useWorkbenchLocale();
  const runs = bundle.runProjection?.runs ?? [];
  const [selectedRunId, setSelectedRunId] = useState<string | null>(() => runs.find(isAgentFixtureRun)?.research_run_id ?? runs[0]?.research_run_id ?? null);
  const selectedRun = runs.find((run) => run.research_run_id === selectedRunId) ?? runs[0];
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  useEffect(() => {
    setSelectedArtifactId((current) => selectedRun?.artifacts.some((artifact) => artifact.artifact_version_id === current) ? current : selectedRun?.artifacts[0]?.artifact_version_id ?? null);
  }, [selectedRun]);
  const selectedArtifact = selectedRun?.artifacts.find((artifact) => artifact.artifact_version_id === selectedArtifactId) ?? selectedRun?.artifacts[0];
  const objects = [
    ["Case", bundle.caseProjection?.case_id, bundle.caseProjection?.case_version],
    ["DecisionSurface", bundle.plan?.contract_version_id, bundle.plan?.contract_version],
    ["ResearchPreview", bundle.research?.preview_digest, bundle.research?.case_version],
    ["AnalysisPreview", bundle.analysis?.analysis_digest, bundle.analysis?.case_version],
    ["Workpaper", bundle.analysis?.workpaper.content_digest ?? bundle.workpaper?.content_digest, bundle.workpaper?.workpaper_version],
    ["Writer", bundle.analysis?.writer.content_digest ?? bundle.deliverable?.content_digest, bundle.deliverable?.artifact_version],
    ["Trace", bundle.trace?.manifest_id, bundle.trace?.artifact_version],
  ];
  return (
    <section className="next-document-surface next-inspect">
      <header className="next-surface-heading"><div><p>{copy("调试模式", "Inspect mode")}</p><h2>{copy("运行对象与版本绑定", "Run objects and version bindings")}</h2></div><span className="next-stage-chip">READ ONLY</span></header>
      <section className="next-exact-run-inspector">
        <header><div><h3>{copy("Canonical Run 投影", "Canonical run projection")}</h3><p>{copy("以下内容来自同一 Run/Attempt 的不可变事件与 Artifact；不展示私有思维链。", "The immutable events and artifacts below share one Run/Attempt; private chain of thought is not exposed.")}</p></div><span>{bundle.runProjection?.private_chain_of_thought_included === false ? copy("私有思维链：未包含", "Private chain of thought: excluded") : copy("投影不可用", "Projection unavailable")}</span></header>
        {runs.length ? <>
          <div className="next-run-tabs">{runs.map((run) => <button type="button" key={run.research_run_id} className={run.research_run_id === selectedRun?.research_run_id ? "is-active" : ""} onClick={() => setSelectedRunId(run.research_run_id)}><b>{profileLabel(run, copy)}</b><span>{run.state}</span><code>{run.research_run_id}</code></button>)}</div>
          {selectedRun ? <>
            <dl className={`next-run-facts ${selectedRun.state === "failed" ? "is-failed" : ""}`}>
              <div><dt>Profile</dt><dd>{selectedRun.execution_profile_version_ref}</dd></div>
              <div><dt>RunVersion</dt><dd>{selectedRun.research_run_version_id}</dd></div>
              <div><dt>Attempt</dt><dd>{selectedRun.attempt_id}</dd></div>
              <div><dt>{copy("真实停止原因", "Exact stop reason")}</dt><dd>{selectedRun.terminal_reason ?? copy("尚未终止", "Not terminal")}</dd></div>
            </dl>
            <div className="next-artifact-inspector">
              <nav aria-label={copy("Exact artifacts", "Exact artifacts")}>
                <h4>{copy("Exact artifacts", "Exact artifacts")} <span>{selectedRun.artifacts.length}</span></h4>
                {selectedRun.artifacts.map((artifact) => <button type="button" key={artifact.artifact_version_id} className={artifact.artifact_version_id === selectedArtifact?.artifact_version_id ? "is-active" : ""} onClick={() => setSelectedArtifactId(artifact.artifact_version_id)}><b>{artifactTypeLabel(artifact.artifact_type, copy)}</b><code>{artifact.artifact_version_id}</code><span>{artifact.current_status} · {artifact.object_digest.slice(0, 12)}</span></button>)}
                {!selectedRun.artifacts.length ? <p>{selectedRun.state === "failed" ? copy("失败 Run 没有 Artifact；未复用确定性输出。", "Failed run has no artifact and did not reuse deterministic output.") : copy("尚未形成 Artifact。", "No artifact is available yet.")}</p> : null}
              </nav>
              <ArtifactDetail artifact={selectedArtifact} />
            </div>
          </> : null}
        </> : <p className="next-empty-copy">{copy("当前 Case 尚无 canonical ResearchRun。", "This case has no canonical ResearchRun yet.")}</p>}
      </section>
      <div className="next-inspect-grid">
        <section><h3>{copy("对象链", "Object chain")}</h3>{objects.map(([label, digest, version]) => <div key={String(label)}><span>{label}</span><b>{digest ?? copy("未形成", "Not available")}</b><em>{version === undefined ? "—" : `v${version}`}</em></div>)}</section>
        <section><h3>{copy("执行计数", "Execution counts")}</h3>{Object.entries({ ...(bundle.research?.execution_counts ?? {}), ...(bundle.analysis?.execution_counts ?? {}) }).map(([key, value]) => <div key={key}><span>{key}</span><b>{value}</b></div>)}</section>
        <section><h3>{copy("硬边界", "Hard boundaries")}</h3>{Object.entries(bundle.analysis?.hard_boundaries ?? bundle.workpaper?.hard_boundaries ?? {}).map(([key, value]) => <div key={key}><span>{key}</span><b>{String(value)}</b></div>)}</section>
        <section><h3>{copy("可选视图错误", "Optional view failures")}</h3>{bundle.failures.length ? bundle.failures.map((failure) => <div key={failure}><AlertCircle size={14} /><span>{failure}</span></div>) : <p className="next-empty-copy">{copy("没有读取错误。", "No read errors.")}</p>}</section>
      </div>
    </section>
  );
}

function ArtifactDetail({ artifact }: { artifact?: ResearchRunArtifactView }) {
  const { copy } = useWorkbenchLocale();
  if (!artifact) return <section className="next-artifact-detail"><p className="next-empty-copy">{copy("选择一个 Artifact 查看 exact payload。", "Select an artifact to inspect its exact payload.")}</p></section>;
  const s4CaseRuntime = projectS4CaseRuntime(artifact);
  return <section className="next-artifact-detail"><header><div><h4>{artifactTypeLabel(artifact.artifact_type, copy)}</h4><code>{artifact.artifact_version_id}</code></div><span className={artifact.payload_exact ? "is-exact" : "is-redacted"}>{artifact.payload_exact ? copy("payload 与 digest 精确对应", "Payload exactly matches digest") : copy("私有字段已遮蔽", "Private fields redacted")}</span></header><dl><div><dt>SHA-256</dt><dd>{artifact.object_digest}</dd></div><div><dt>Producer Attempt</dt><dd>{artifact.producer_attempt_id}</dd></div><div><dt>Input refs</dt><dd>{artifact.input_refs.join(" · ") || "—"}</dd></div>{s4CaseRuntime ? <><div><dt>S4 Case / Method</dt><dd>{s4CaseRuntime.case_ticker} · {s4CaseRuntime.method_id}</dd></div><div><dt>Issuer / Binding</dt><dd>{s4CaseRuntime.issuer_identifier} · {s4CaseRuntime.runtime_binding_digest.slice(0, 12)}</dd></div><div><dt>Runtime maturity</dt><dd>{copy("确定性注入；付费产物与 Human Review 未完成", "Deterministically injected; paid artifact and Human Review pending")}</dd></div></> : null}</dl><pre>{formatJson(artifact.payload)}</pre></section>;
}

export function projectS4CaseRuntime(
  artifact: ResearchRunArtifactView,
): S4CaseRuntimeProjection | undefined {
  const value = artifact.payload.s4_case_runtime;
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const row = value as Record<string, unknown>;
  if (
    (row.case_ticker !== "DELL" && row.case_ticker !== "MU")
    || typeof row.runtime_binding_digest !== "string"
    || !/^[0-9a-f]{64}$/.test(row.runtime_binding_digest)
    || typeof row.issuer_identifier !== "string"
    || typeof row.case_profile_ref !== "string"
    || typeof row.method_id !== "string"
    || typeof row.case_identity_namespace !== "string"
    || row.paid_artifact_proven !== false
    || row.human_review_completed !== false
  ) return undefined;
  return row as S4CaseRuntimeProjection;
}

function useCaseBundle(caseId: string | null, online: boolean, revision = 0): BundleState {
  const [state, setState] = useState<BundleState>({ kind: "idle" });
  useEffect(() => {
    if (!caseId) {
      setState({ kind: "idle" });
      return;
    }
    if (!online) {
      setState({ kind: "error", message: "Local research service is offline." });
      return;
    }
    let cancelled = false;
    setState({ kind: "loading" });
    void loadCaseBundle(caseId).then((data) => {
      if (!cancelled) setState({ kind: "ready", data });
    }).catch((error) => {
      if (!cancelled) setState({ kind: "error", message: errorMessage(error) });
    });
    return () => { cancelled = true; };
  }, [caseId, online, revision]);
  return state;
}

async function loadCaseBundle(caseId: string): Promise<CaseBundle> {
  const [caseProjection, plan, workUnits, activity, runProjection, research, analysis, evidence, numeric, workpaper, deliverable, trace, baseline] = await Promise.all([
    capture("case", () => caseApi.getCase(caseId)),
    capture("planning", () => planningApi.getDecisionSurface(caseId)),
    capture("work-units", () => executionApi.listWorkUnits(caseId)),
    capture("activity", () => executionApi.getActivityTrace(caseId)),
    capture("execution-projection", () => executionApi.getResearchRunProjection(caseId)),
    capture("research", () => evidenceApi.getLocalResearchPreview(caseId)),
    capture("analysis", () => evidenceApi.getLocalAnalysisPreview(caseId)),
    capture("evidence", () => evidenceApi.getEvidenceWorkbench(caseId)),
    capture("numeric", () => integrityApi.getNumericWorkbench(caseId)),
    capture("workpaper", () => integrityApi.getWorkpaper(caseId)),
    capture("deliverable", () => deliverablesApi.getDeliverableHead(caseId)),
    capture("trace", () => deliverablesApi.getCaseTrace(caseId)),
    capture("human-baseline", () => baselineApi.list(caseId)),
  ]);
  const results = [caseProjection, plan, workUnits, activity, runProjection, research, analysis, evidence, numeric, workpaper, deliverable, trace, baseline];
  const failures = results.filter((result): result is Extract<Captured<unknown>, { ok: false }> => !result.ok).map((result) => `${result.label}: ${result.message}`);
  if (!caseProjection.ok && !research.ok && !analysis.ok) throw new Error(failures.join(" · "));
  return {
    caseProjection: value(caseProjection),
    plan: value(plan),
    workUnits: value(workUnits),
    activity: value(activity),
    runProjection: value(runProjection),
    research: value(research),
    analysis: value(analysis),
    evidence: value(evidence),
    numeric: value(numeric),
    workpaper: value(workpaper),
    deliverable: value(deliverable),
    trace: value(trace),
    baseline: value(baseline),
    failures,
  };
}

async function capture<T>(label: string, call: () => Promise<T>): Promise<Captured<T>> {
  try {
    return { ok: true, value: await call() };
  } catch (error) {
    return { ok: false, label, message: errorMessage(error) };
  }
}

function value<T>(captured: Captured<T>): T | undefined {
  return captured.ok ? captured.value : undefined;
}

function useNextRoute(): [NextRoute, (route: NextRoute) => void] {
  const [route, setRoute] = useState<NextRoute>(() => decodeNextRoute(window.location.pathname));
  useEffect(() => {
    const update = () => setRoute(decodeNextRoute(window.location.pathname));
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  const navigate = useCallback((next: NextRoute) => {
    window.history.pushState({}, "", pathForNextRoute(next));
    setRoute(next);
  }, []);
  return [route, navigate];
}

function decodeNextRoute(pathname: string): NextRoute {
  const match = /^\/next\/cases\/([^/]+)\/(run|evidence|workpaper|review|report|inspect)\/?$/.exec(pathname);
  if (match) return { kind: "case", caseId: decodeURIComponent(match[1]), surface: match[2] as NextSurface };
  return { kind: "tasks" };
}

function pathForNextRoute(route: NextRoute): string {
  return route.kind === "tasks" ? "/next/tasks" : `/next/cases/${encodeURIComponent(route.caseId)}/${route.surface}`;
}

function buildRunEvents(bundle: CaseBundle): Array<{ label: string; detail: string; meta?: string; time?: string; status: "done" | "active" | "waiting" }> {
  const events: Array<{ label: string; detail: string; meta?: string; time?: string; status: "done" | "active" | "waiting" }> = [];
  for (const event of bundle.activity?.events ?? []) {
    events.push({ label: event.event_type, detail: event.typed_stop || "Lifecycle event recorded", time: event.occurred_at, status: "done" });
  }
  if (bundle.research) events.push({ label: "RAG / SQL / Graph", detail: `${bundle.research.candidate_count} candidates across ${bundle.research.selected_cell_count} cells`, meta: bundle.research.preview_digest, status: "done" });
  if (bundle.analysis?.numeric) events.push({ label: "Parser & Numeric", detail: `${bundle.analysis.numeric.facts.length} exact facts and ${bundle.analysis.numeric.derived_metrics.length} derived metrics`, status: "done" });
  if (bundle.analysis?.repairs) events.push({ label: "Evidence Gate & Repair", detail: `${bundle.analysis.repairs.length} bounded repair decisions; ${countGaps(bundle)} open gaps retained`, status: "done" });
  if (bundle.analysis?.judgments) events.push({ label: "Domain Judgment", detail: `${bundle.analysis.judgments.length} structured judgments formed`, status: "done" });
  if (bundle.analysis?.writer) events.push({ label: "Writer no-source", detail: bundle.analysis.writer.title_zh_cn, meta: bundle.analysis.writer.content_digest, status: "done" });
  events.push({ label: "Human Senior Review", detail: bundle.baseline?.counts.completed_review_count ? "Exact human review recorded" : "Awaiting exact human review", status: bundle.baseline?.counts.completed_review_count ? "done" : "active" });
  return events;
}

function runEventLabel(label: string, copy: (zh: string, en: string) => string): string {
  const labels: Record<string, [string, string]> = {
    WORK_UNIT_CREATED: ["研究工作单已创建", "Research work unit created"],
    WORK_UNIT_STARTED: ["研究工作单已启动", "Research work unit started"],
    ATTEMPT_STARTED: ["执行 Attempt 已启动", "Execution attempt started"],
    RESEARCH_RUN_STARTED: ["Canonical Run 已启动", "Canonical run started"],
    AGENT_DEFINITION_VERSIONS_SELECTED: ["Agent 定义版本已选择", "Agent definition versions selected"],
    SKILL_PACK_CONSUMPTION_RECORDED: ["Skill Pack 消费已记录", "Skill-pack consumption recorded"],
    LANGGRAPH_FIXTURE_SHADOW_VALIDATED: ["LangGraph Fixture-Shadow 已验证", "LangGraph fixture-shadow validated"],
    RESEARCH_LEAD_FIXTURE_COMPLETED: ["Research Lead Fixture 已完成", "Research Lead fixture completed"],
    SPECIALIST_FIXTURE_COMPLETED: ["Specialist Fixture 已完成", "Specialist fixture completed"],
    TOOL_FIXTURE_OBSERVATION_RECORDED: ["Tool Fixture 观测已记录", "Tool fixture observation recorded"],
    GRAPH_FIXTURE_OBSERVATION_RECORDED: ["Graph Fixture 观测已记录", "Graph fixture observation recorded"],
    WRITER_FIXTURE_COMPLETED: ["Writer Fixture 已完成", "Writer fixture completed"],
    VERIFIER_FIXTURE_COMPLETED: ["Verifier Fixture 已完成", "Verifier fixture completed"],
    RESEARCH_RUN_COMPLETED: ["Canonical Run 已完成", "Canonical run completed"],
    RESEARCH_RUN_FAILED: ["Canonical Run 失败", "Canonical run failed"],
    ARTIFACT_VERSION_CREATED: ["不可变 Artifact 已提交", "Immutable artifact committed"],
    ATTEMPT_COMPLETED: ["执行 Attempt 已完成", "Execution attempt completed"],
    ATTEMPT_FAILED: ["执行 Attempt 失败", "Execution attempt failed"],
    WORK_UNIT_COMPLETED: ["研究工作单已完成", "Research work unit completed"],
    WORK_UNIT_FAILED: ["研究工作单失败", "Research work unit failed"],
    EVIDENCE_FIXTURE_COMPILED: ["证据候选已整理", "Evidence candidates compiled"],
    EVIDENCE_REPAIR_REQUESTED: ["证据补充已请求", "Evidence repair requested"],
    EVIDENCE_REPAIR_COMPLETED: ["证据补充已完成", "Evidence repair completed"],
    NUMERIC_FIXTURE_COMPILED: ["数字事实已复算", "Numeric facts compiled"],
    WORKPAPER_FIXTURE_COMPILED: ["研究底稿已形成", "Research workpaper compiled"],
    LEAD_REVIEW_COMPLETED: ["Lead Review 已完成", "Lead review completed"],
    "RAG / SQL / Graph": ["RAG / SQL / Graph 检索", "RAG / SQL / Graph retrieval"],
    "Parser & Numeric": ["解析与数字复算", "Parser & numeric"],
    "Evidence Gate & Repair": ["证据门与受限修复", "Evidence gate & bounded repair"],
    "Domain Judgment": ["领域判断", "Domain judgment"],
    "Writer no-source": ["无来源 Writer", "Writer no-source"],
    "Human Senior Review": ["人工 Senior Review", "Human Senior Review"],
  };
  const known = labels[label];
  return known ? copy(known[0], known[1]) : label.replaceAll("_", " ");
}

function isAgentFixtureRun(run: ResearchRunProjectionItem): boolean {
  return run.execution_profile_version_ref.includes("agent_fixture_shadow");
}

function isAgentTraceEvent(eventType: string): boolean {
  return [
    "AGENT_DEFINITION_VERSIONS_SELECTED",
    "SKILL_PACK_CONSUMPTION_RECORDED",
    "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
    "RESEARCH_LEAD_FIXTURE_COMPLETED",
    "SPECIALIST_FIXTURE_COMPLETED",
    "TOOL_FIXTURE_OBSERVATION_RECORDED",
    "GRAPH_FIXTURE_OBSERVATION_RECORDED",
    "WRITER_FIXTURE_COMPLETED",
    "VERIFIER_FIXTURE_COMPLETED",
  ].includes(eventType);
}

function profileLabel(run: ResearchRunProjectionItem, copy: (zh: string, en: string) => string): string {
  return isAgentFixtureRun(run) ? copy("Agent 编排影子（Fixture）", "Agent orchestration shadow (fixture)") : copy("本地确定性预览", "Local deterministic preview");
}

function runStateLabel(state: string | undefined, legacyComplete: boolean, copy: (zh: string, en: string) => string): string {
  if (state === "succeeded") return copy("Run 成功", "Run succeeded");
  if (state === "failed") return copy("Run 失败", "Run failed");
  if (state === "running") return copy("Run 运行中", "Run running");
  if (legacyComplete) return copy("确定性预览已就绪", "Deterministic preview ready");
  return copy("尚未运行", "Not run");
}

function structuredEventSummary(eventType: string, details: Record<string, unknown>, copy: (zh: string, en: string) => string): string {
  if (eventType === "AGENT_DEFINITION_VERSIONS_SELECTED") return copy(`选择 ${arrayLength(details.agent_definition_versions)} 个 content-addressed Agent 版本`, `Selected ${arrayLength(details.agent_definition_versions)} content-addressed Agent versions`);
  if (eventType === "SKILL_PACK_CONSUMPTION_RECORDED") return copy(`记录 ${arrayLength(details.skill_pack_versions)} 个 Skill Pack 版本消费`, `Recorded consumption of ${arrayLength(details.skill_pack_versions)} skill-pack versions`);
  if (eventType === "LANGGRAPH_FIXTURE_SHADOW_VALIDATED") return copy(`${arrayLength(details.graph_nodes_executed)} 个图节点；状态 ${String(details.activation_validation_status ?? "unknown")}`, `${arrayLength(details.graph_nodes_executed)} graph nodes; status ${String(details.activation_validation_status ?? "unknown")}`);
  if (eventType === "RESEARCH_LEAD_FIXTURE_COMPLETED") return copy(`Lead ${String(details.agent_id ?? "research_lead")} 已完成 bounded handoff`, `Lead ${String(details.agent_id ?? "research_lead")} completed the bounded handoff`);
  if (eventType === "SPECIALIST_FIXTURE_COMPLETED") return copy(`Specialist ${String(details.agent_id ?? "unknown")} 已提交结构化判断`, `Specialist ${String(details.agent_id ?? "unknown")} submitted a structured judgment`);
  if (eventType === "TOOL_FIXTURE_OBSERVATION_RECORDED") return copy("记录 1 次 fixture tool observation；外部工具调用为 0", "Recorded one fixture tool observation; external tool calls remain zero");
  if (eventType === "GRAPH_FIXTURE_OBSERVATION_RECORDED") return copy("记录 bounded graph observation", "Recorded a bounded graph observation");
  if (eventType === "WRITER_FIXTURE_COMPLETED") return copy("Writer 只消费绑定底稿；source/tool calls 为 0", "Writer consumed only the bound workpaper; source/tool calls are zero");
  if (eventType === "VERIFIER_FIXTURE_COMPLETED") return copy(`Verifier 状态 ${String(details.status ?? "unknown")}；人工复核未执行`, `Verifier status ${String(details.status ?? "unknown")}; human review not performed`);
  if (/FAILED$/.test(eventType)) return copy(`失败类型：${String(details.failure_type ?? details.terminal_reason ?? "typed_failure")}`, `Failure type: ${String(details.failure_type ?? details.terminal_reason ?? "typed_failure")}`);
  return copy("Canonical lifecycle event 已记录；展开可检查结构化字段。", "Canonical lifecycle event recorded; expand to inspect structured fields.");
}

function artifactTypeLabel(type: string, copy: (zh: string, en: string) => string): string {
  const labels: Record<string, [string, string]> = {
    deterministic_research_result: ["确定性研究结果", "Deterministic research result"],
    agent_fixture_shadow_result: ["Agent Fixture 主清单", "Agent fixture manifest"],
    agent_fixture_evidence: ["Evidence", "Evidence"],
    agent_fixture_numeric: ["Numeric", "Numeric"],
    agent_fixture_judgment: ["Judgment", "Judgment"],
    agent_fixture_workpaper: ["Workpaper", "Workpaper"],
    agent_fixture_report: ["Report", "Report"],
    agent_fixture_trace: ["Trace", "Trace"],
    s3_three_cell_workpaper: ["三 Cell Workpaper", "Three-cell workpaper"],
    s3_three_cell_report: ["三 Cell Report", "Three-cell report"],
    s3_three_cell_trace_review: ["Trace / Review", "Trace / review"],
  };
  const label = labels[type];
  return label ? copy(label[0], label[1]) : type;
}

function s3PresentationPack(bundle: CaseBundle): S3ThreeCellPresentationPackView | undefined {
  const run = [...(bundle.runProjection?.runs ?? [])].reverse().find((item) => item.state === "succeeded" && item.execution_profile_version_ref.includes("p36_local_deterministic"));
  const artifact = run?.artifacts.find((item) => item.artifact_type === "deterministic_research_result");
  const pack = artifact?.payload.s3_three_cell_presentation_pack;
  if (typeof pack !== "object" || pack === null || Array.isArray(pack)) return undefined;
  const candidate = pack as Partial<S3ThreeCellPresentationPackView>;
  if (!candidate.presentation_pack_digest || !candidate.workpaper || !candidate.report || !candidate.trace_review) return undefined;
  return candidate as S3ThreeCellPresentationPackView;
}

function cellHeading(cellId: string, copy: (zh: string, en: string) => string): string {
  const labels: Record<string, [string, string]> = {
    demand_authenticity_and_sustainability: ["需求真实性与持续性", "Demand authenticity and durability"],
    value_and_profit_capture: ["价值与利润捕获", "Value and profit capture"],
    bottleneck_counterevidence_and_what_would_change: ["瓶颈、反证与 WWC", "Bottlenecks, counterevidence, and WWC"],
  };
  const label = labels[cellId];
  return label ? copy(label[0], label[1]) : cellId;
}

function runExecutionCounts(run?: ResearchRunProjectionItem): Record<string, unknown> {
  const event = run?.events.find((item) => item.event_type === "LANGGRAPH_FIXTURE_SHADOW_VALIDATED");
  const counts = event?.details.execution_counts;
  return typeof counts === "object" && counts !== null && !Array.isArray(counts) ? counts as Record<string, unknown> : {};
}

function numberField(value: Record<string, unknown>, key: string): number | undefined {
  return typeof value[key] === "number" ? value[key] as number : undefined;
}

function arrayLength(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function countGaps(bundle: CaseBundle): number {
  if (bundle.analysis) return bundle.analysis.judgments.reduce((total, judgment) => total + judgment.remaining_gaps.length, 0);
  if (bundle.evidence) return bundle.evidence.summary.gap_count;
  if (bundle.research) return bundle.research.cells.filter((cell) => Boolean(cell.typed_gap)).length;
  return 0;
}

function caseStage(bundle: CaseBundle, copy: (zh: string, en: string) => string): string {
  if (bundle.baseline?.counts.completed_review_count) return copy("人工复核已完成", "Human review complete");
  if (bundle.analysis) return copy("等待人工复核", "Awaiting human review");
  if (bundle.workUnits?.work_units.some((unit) => /running|pending/.test(unit.state))) return copy("运行中", "Running");
  return copy("已准备", "Ready");
}

function reviewStatus(session: HumanBaselineSession, copy: (zh: string, en: string) => string): string {
  if (session.status === "exact_human_senior_review_recorded") return copy("精确记录已完成", "Exact record complete");
  if (session.status === "analyst_submitted") return copy("等待 Senior Review", "Awaiting Senior Review");
  return copy("分析师基线进行中", "Analyst baseline in progress");
}

function replaceSession(current: HumanBaselineSessionList | undefined, session: HumanBaselineSession): HumanBaselineSessionList {
  const sessions = (current?.sessions ?? []).map((item) => item.session_id === session.session_id ? session : item);
  if (!sessions.some((item) => item.session_id === session.session_id)) sessions.push(session);
  return {
    schema_version: current?.schema_version ?? "human_baseline_session_list_v1",
    case_id: session.case_id,
    sessions,
    counts: { session_count: sessions.length, completed_review_count: sessions.filter((item) => item.status === "exact_human_senior_review_recorded").length },
    boundary: current?.boundary ?? session.boundary,
  };
}

function countMatching(items: TaskCenterRow[], pattern: RegExp): number {
  return items.filter((item) => pattern.test(item.status)).length;
}

function uniqueKey(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function LoadingLine({ label }: { label: string }) {
  return <div className="next-loading-line"><LoaderCircle size={17} />{label}</div>;
}

function ErrorLine({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="next-error-line"><AlertCircle size={17} /><span>{message}</span>{onRetry ? <button type="button" onClick={onRetry}><RefreshCcw size={15} />Retry</button> : null}</div>;
}
