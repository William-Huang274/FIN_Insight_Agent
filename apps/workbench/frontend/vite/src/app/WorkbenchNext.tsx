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
import { ActivityTraceView, ExecutionApiClient, WorkUnitExecutionView } from "../api/execution";
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
  const bundle = useCaseBundle(route.caseId, online, revision);
  const refresh = () => setRevision((current) => current + 1);
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
          {route.surface === "run" ? <RunSurface bundle={bundle.data} caseId={route.caseId} navigate={navigate} /> : null}
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

function RunSurface({ bundle, caseId, navigate }: { bundle: CaseBundle; caseId: string; navigate: (route: NextRoute) => void }) {
  const { copy, localizeFixtureText, formatDateTime } = useWorkbenchLocale();
  const events = buildRunEvents(bundle);
  const last = events.at(-1);
  const isComplete = Boolean(bundle.analysis);
  return (
    <div className="next-run-layout">
      <section className="next-run-thread">
        <header className="next-surface-heading">
          <div><p>{copy("Agent 研究", "Agent research")}</p><h2>{copy("研究运行", "Research run")}</h2></div>
          <span className={`next-run-status ${isComplete ? "is-review" : ""}`}>{isComplete ? copy("等待人工复核", "Awaiting human review") : copy("准备中", "Preparing")}</span>
        </header>
        <article className="next-user-prompt">
          <span>RA</span>
          <div><small>{copy("研究问题", "Research question")}</small><p>{localizeFixtureText(bundle.caseProjection?.query ?? caseId)}</p></div>
        </article>
        <div className="next-event-stream">
          {events.map((event, index) => (
            <article key={`${event.label}-${index}`} className={`next-run-event ${event.status}`}>
              <span className="next-event-icon">{event.status === "done" ? <Check size={15} /> : event.status === "active" ? <LoaderCircle size={15} /> : <CircleDot size={14} />}</span>
              <div>
                <header><b>{runEventLabel(event.label, copy)}</b><time>{event.time ? formatDateTime(event.time) : ""}</time></header>
                <p>{event.detail}</p>
                {event.meta ? <small>{event.meta}</small> : null}
              </div>
            </article>
          ))}
        </div>
        {last ? (
          <section className="next-run-outcome">
            <ShieldCheck size={20} aria-hidden="true" />
            <div><small>{copy("当前输出", "Current output")}</small><strong>{last.detail}</strong></div>
            <button type="button" onClick={() => navigate({ kind: "case", caseId, surface: isComplete ? "review" : "evidence" })}>{isComplete ? copy("进入 Senior Review", "Open senior review") : copy("查看证据", "Open evidence")}<ArrowRight size={15} /></button>
          </section>
        ) : null}
        <div className="next-run-composer">
          <textarea placeholder={copy("补充研究问题或要求 Agent 继续核验…", "Add a research question or ask the agent to verify further…")} disabled />
          <button type="button" disabled><Play size={16} />{copy("运行请求未准入", "Run request not admitted")}</button>
        </div>
      </section>
      <RunConfiguration bundle={bundle} />
    </div>
  );
}

function RunConfiguration({ bundle }: { bundle: CaseBundle }) {
  const { copy } = useWorkbenchLocale();
  return (
    <aside className="next-run-config">
      <header><Settings2 size={18} /><h2>{copy("运行配置", "Run configuration")}</h2></header>
      <ConfigSection icon={<Bot size={16} />} label={copy("模型", "Model")} value={bundle.analysis ? copy("本地确定性分析器", "Local deterministic analyzer") : copy("尚未选择", "Not selected")} />
      <ConfigSection icon={<Globe2 size={16} />} label={copy("检索", "Retrieval")} value={bundle.research ? "Local RAG + SQL + Graph" : copy("尚未准备", "Not prepared")} />
      <ConfigSection icon={<Wrench size={16} />} label={copy("技能", "Skills")} value="P36 AI Infrastructure" />
      <ConfigSection icon={<Network size={16} />} label={copy("知识图谱", "Knowledge graph")} value={bundle.research?.cells.some((cell) => cell.retrieval_lane === "research_graph") ? copy("研究关系图已连接", "Research graph connected") : copy("未连接", "Not connected")} />
      <ConfigSection icon={<GitBranch size={16} />} label={copy("编排", "Orchestration")} value={copy("检索 → 数字 → 判断 → Writer", "Retrieval → numeric → judgment → writer")} />
      <div className="next-config-boundary">
        <ShieldCheck size={17} />
        <div><b>{copy("当前边界", "Current boundary")}</b><span>{copy("只读、本地候选、无模型调用、无业务写入", "Read-only local candidates; no model calls or business writes")}</span></div>
      </div>
      <dl className="next-config-counts">
        <div><dt>{copy("模型调用", "Model calls")}</dt><dd>{bundle.analysis?.execution_counts.model_calls ?? 0}</dd></div>
        <div><dt>{copy("外部检索", "External retrieval")}</dt><dd>{bundle.research?.execution_counts.external_calls ?? 0}</dd></div>
        <div><dt>{copy("业务写入", "Business writes")}</dt><dd>{bundle.analysis?.execution_counts.case_mutation_calls ?? 0}</dd></div>
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

function ReportSurface({ bundle }: { bundle: CaseBundle }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
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

function ReviewSurface({ bundle, caseId }: { bundle: CaseBundle; caseId: string }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const [sessions, setSessions] = useState(bundle.baseline);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
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
      <div className="next-inspect-grid">
        <section><h3>{copy("对象链", "Object chain")}</h3>{objects.map(([label, digest, version]) => <div key={String(label)}><span>{label}</span><b>{digest ?? copy("未形成", "Not available")}</b><em>{version === undefined ? "—" : `v${version}`}</em></div>)}</section>
        <section><h3>{copy("执行计数", "Execution counts")}</h3>{Object.entries({ ...(bundle.research?.execution_counts ?? {}), ...(bundle.analysis?.execution_counts ?? {}) }).map(([key, value]) => <div key={key}><span>{key}</span><b>{value}</b></div>)}</section>
        <section><h3>{copy("硬边界", "Hard boundaries")}</h3>{Object.entries(bundle.analysis?.hard_boundaries ?? bundle.workpaper?.hard_boundaries ?? {}).map(([key, value]) => <div key={key}><span>{key}</span><b>{String(value)}</b></div>)}</section>
        <section><h3>{copy("可选视图错误", "Optional view failures")}</h3>{bundle.failures.length ? bundle.failures.map((failure) => <div key={failure}><AlertCircle size={14} /><span>{failure}</span></div>) : <p className="next-empty-copy">{copy("没有读取错误。", "No read errors.")}</p>}</section>
      </div>
    </section>
  );
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
  const [caseProjection, plan, workUnits, activity, research, analysis, evidence, numeric, workpaper, deliverable, trace, baseline] = await Promise.all([
    capture("case", () => caseApi.getCase(caseId)),
    capture("planning", () => planningApi.getDecisionSurface(caseId)),
    capture("work-units", () => executionApi.listWorkUnits(caseId)),
    capture("activity", () => executionApi.getActivityTrace(caseId)),
    capture("research", () => evidenceApi.getLocalResearchPreview(caseId)),
    capture("analysis", () => evidenceApi.getLocalAnalysisPreview(caseId)),
    capture("evidence", () => evidenceApi.getEvidenceWorkbench(caseId)),
    capture("numeric", () => integrityApi.getNumericWorkbench(caseId)),
    capture("workpaper", () => integrityApi.getWorkpaper(caseId)),
    capture("deliverable", () => deliverablesApi.getDeliverableHead(caseId)),
    capture("trace", () => deliverablesApi.getCaseTrace(caseId)),
    capture("human-baseline", () => baselineApi.list(caseId)),
  ]);
  const results = [caseProjection, plan, workUnits, activity, research, analysis, evidence, numeric, workpaper, deliverable, trace, baseline];
  const failures = results.filter((result): result is Extract<Captured<unknown>, { ok: false }> => !result.ok).map((result) => `${result.label}: ${result.message}`);
  if (!caseProjection.ok && !research.ok && !analysis.ok) throw new Error(failures.join(" · "));
  return {
    caseProjection: value(caseProjection),
    plan: value(plan),
    workUnits: value(workUnits),
    activity: value(activity),
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
