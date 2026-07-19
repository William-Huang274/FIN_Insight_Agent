import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BarChart3,
  BookOpenText,
  Building2,
  Calculator,
  ChevronRight,
  ClipboardCheck,
  Compass,
  FileSearch,
  FileText,
  FlaskConical,
  Languages,
  LayoutDashboard,
  ListChecks,
  PanelRight,
  RefreshCcw,
  Search,
  Send,
  Settings,
  Users,
  Wifi,
  WifiOff,
  UserCheck,
} from "lucide-react";

import { CaseApiClient, CaseApiError, TaskCenterRow } from "../api/cases";
import { DeliverablePreviewView, DeliverablesApiClient, DeliverablesApiError } from "../api/deliverables";
import {
  EvidenceApiClient,
  EvidenceApiError,
  EvidenceWorkbenchView,
  LocalAnalysisPreviewView,
  LocalResearchPreviewView,
} from "../api/evidence";
import { useWorkbenchLocale } from "../i18n/WorkbenchLocale";

export type CaseRouteKind =
  | "caseOverview"
  | "decisionSurface"
  | "evidence"
  | "numbers"
  | "workpaper"
  | "deliverable"
  | "activity"
  | "humanBaseline";

type ChromeTopbarProps = {
  online: boolean;
  onTasks: () => void;
  onOpenCase: (caseId: string) => void;
};

type GlobalProductNavProps = {
  active: "tasks" | "newCase" | "case";
  activeCaseKind: CaseRouteKind | null;
  caseAvailable: boolean;
  onTasks: () => void;
  onNewCase: () => void;
  onNavigateCase: (kind: CaseRouteKind) => void;
  onLegacy: () => void;
};

type TaskQueueRailProps = {
  activeCaseId: string;
  onOpenCase: (caseId: string) => void;
};

type CompactCaseTabsProps = {
  activeKind: CaseRouteKind;
  onNavigate: (kind: CaseRouteKind) => void;
};

type CaseContextDrawerProps = {
  caseId: string;
};

type ReadonlyState<T> =
  | { kind: "loading" }
  | { kind: "ready"; data: T }
  | { kind: "empty" }
  | { kind: "unavailable" };

type QueueState =
  | { kind: "loading" }
  | { kind: "ready"; items: TaskCenterRow[] }
  | { kind: "empty" }
  | { kind: "unavailable" };

const caseApi = new CaseApiClient();
const evidenceApi = new EvidenceApiClient();
const deliverablesApi = new DeliverablesApiClient();

function useDesktopRailOpen() {
  const [open, setOpen] = useState(() =>
    typeof window === "undefined" ? true : window.matchMedia("(min-width: 901px)").matches,
  );

  useEffect(() => {
    const media = window.matchMedia("(min-width: 901px)");
    const syncWithViewport = () => setOpen(media.matches);
    media.addEventListener("change", syncWithViewport);
    return () => media.removeEventListener("change", syncWithViewport);
  }, []);

  return [open, setOpen] as const;
}

export function AnalystTopbar({ online, onTasks, onOpenCase }: ChromeTopbarProps) {
  const { copy, locale, setLocale } = useWorkbenchLocale();

  return (
    <header className="analyst-topbar">
      <button type="button" className="analyst-brand" onClick={onTasks}>
        <span className="analyst-brand-mark" aria-hidden="true">F</span>
        <span>FinSight Workbench</span>
      </button>
      <TaskSearch onOpenCase={onOpenCase} />
      <div className="analyst-topbar-tools">
        <span className="analyst-demo-status" title={copy("当前仅使用内部演示数据，不代表真实投研结论", "Internal demo data only; not a real research conclusion")}>
          <span>INTERNAL ALPHA</span>
        </span>
        <div className="analyst-language-control" aria-label={copy("界面语言", "Interface language")}>
          <Languages size={15} aria-hidden="true" />
          <button type="button" className={locale === "zh-CN" ? "is-active" : undefined} aria-pressed={locale === "zh-CN"} onClick={() => setLocale("zh-CN")}>中文</button>
          <button type="button" className={locale === "en" ? "is-active" : undefined} aria-pressed={locale === "en"} onClick={() => setLocale("en")}>EN</button>
        </div>
        <span className={`analyst-connection ${online ? "is-online" : "is-offline"}`} aria-live="polite" title={online ? copy("演示数据已连接", "Demo data connected") : copy("连接已中断", "Connection interrupted")}>
          {online ? <Wifi size={15} aria-hidden="true" /> : <WifiOff size={15} aria-hidden="true" />}
          <span>{online ? copy("数据源 3 / 3", "Sources 3 / 3") : copy("连接已中断", "Connection interrupted")}</span>
        </span>
        <span className="analyst-avatar" aria-label={copy("当前用户 RA", "Current user RA")}>RA</span>
      </div>
    </header>
  );
}

function TaskSearch({ onOpenCase }: { onOpenCase: (caseId: string) => void }) {
  const { copy, localizeFixtureText } = useWorkbenchLocale();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<QueueState>({ kind: "loading" });
  const [expanded, setExpanded] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    try {
      const projection = await caseApi.listCases();
      setState(projection.items.length ? { kind: "ready", items: projection.items } : { kind: "empty" });
    } catch {
      setState({ kind: "unavailable" });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setExpanded(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, []);

  const results = useMemo(() => {
    if (state.kind !== "ready") return [];
    const normalized = query.trim().toLowerCase();
    if (!normalized) return state.items.slice(0, 6);
    return state.items.filter((item) => `${item.case_id} ${item.query} ${item.status}`.toLowerCase().includes(normalized)).slice(0, 6);
  }, [query, state]);

  const updateQuery = (event: ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
    setExpanded(true);
  };

  return (
    <div ref={containerRef} className="analyst-task-search">
      <Search size={17} aria-hidden="true" />
      <input
        value={query}
        onChange={updateQuery}
        onFocus={() => setExpanded(true)}
        placeholder={copy("搜索研究任务或案例", "Search research tasks or cases")}
        aria-label={copy("搜索研究任务或案例", "Search research tasks or cases")}
        aria-controls="analyst-task-search-results"
        aria-expanded={expanded}
      />
      {expanded ? (
        <div id="analyst-task-search-results" className="analyst-search-results" role="listbox">
          {state.kind === "loading" ? <p>{copy("正在加载研究任务...", "Loading research tasks...")}</p> : null}
          {state.kind === "unavailable" ? <p>{copy("当前无法读取研究任务。", "Research tasks are not available right now.")}</p> : null}
          {state.kind === "empty" ? <p>{copy("暂无可搜索的研究任务。", "No research tasks are available.")}</p> : null}
          {state.kind === "ready" && results.length === 0 ? <p>{copy("没有匹配的研究任务。", "No matching research tasks.")}</p> : null}
          {results.map((item) => (
            <button
              type="button"
              role="option"
              key={item.case_id}
              onClick={() => {
                setExpanded(false);
                setQuery("");
                onOpenCase(item.case_id);
              }}
            >
              <span>
                <strong>{localizeFixtureText(item.query) || copy("未命名研究", "Untitled research")}</strong>
                <small>{item.case_id}</small>
              </span>
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function GlobalProductNav({ active, activeCaseKind, caseAvailable, onTasks, onNewCase, onNavigateCase, onLegacy }: GlobalProductNavProps) {
  const { copy } = useWorkbenchLocale();
  const caseTitle = caseAvailable
    ? undefined
    : copy("先选择并打开一个研究任务", "Select and open a research task first");
  return (
    <aside className="analyst-global-nav" aria-label={copy("产品导航", "Product navigation")}>
      <div className="analyst-nav-group">
        <p>{copy("分析师工作区", "Analyst workspace")}</p>
        <button type="button" className={active === "tasks" ? "is-active" : undefined} onClick={onTasks}>
          <ListChecks size={16} aria-hidden="true" />
          <span>{copy("研究任务", "Research tasks")}</span>
        </button>
        <button type="button" className={activeCaseKind === "workpaper" ? "is-active" : undefined} disabled={!caseAvailable} title={caseTitle} onClick={() => onNavigateCase("workpaper")}>
          <FileText size={16} aria-hidden="true" />
          <span>{copy("工作底稿", "Workpapers")}</span>
        </button>
        <button type="button" className={activeCaseKind === "evidence" ? "is-active" : undefined} disabled={!caseAvailable} title={caseTitle} onClick={() => onNavigateCase("evidence")}>
          <FileSearch size={16} aria-hidden="true" />
          <span>{copy("证据库", "Evidence")}</span>
        </button>
        <button type="button" className={activeCaseKind === "humanBaseline" ? "is-active" : undefined} disabled={!caseAvailable} title={caseTitle} onClick={() => onNavigateCase("humanBaseline")}>
          <Users size={16} aria-hidden="true" />
          <span>{copy("复核", "Review")}</span>
        </button>
        <button type="button" className={activeCaseKind === "deliverable" ? "is-active" : undefined} disabled={!caseAvailable} title={caseTitle} onClick={() => onNavigateCase("deliverable")}>
          <Send size={16} aria-hidden="true" />
          <span>{copy("交付物", "Deliverables")}</span>
        </button>
      </div>
      <div className="analyst-nav-group analyst-nav-assets">
        <p>{copy("研究资产", "Research assets")}</p>
        <button type="button" disabled title={copy("FIN 0.1 后续版本", "Planned after FIN 0.1")}>
          <Building2 size={16} aria-hidden="true" />
          <span>{copy("公司与主题", "Companies & topics")}</span>
        </button>
        <button type="button" disabled title={copy("FIN 0.1 后续版本", "Planned after FIN 0.1")}>
          <BarChart3 size={16} aria-hidden="true" />
          <span>{copy("指标库", "Metrics")}</span>
        </button>
      </div>
      <div className="analyst-nav-group analyst-nav-secondary">
        <button type="button" className={active === "newCase" ? "is-active" : undefined} onClick={onNewCase}>
          <BookOpenText size={16} aria-hidden="true" />
          <span>{copy("发起研究", "Start research")}</span>
        </button>
        <button type="button" onClick={onLegacy}>
          <FlaskConical size={16} aria-hidden="true" />
          <span>{copy("研究方法", "Research methods")}</span>
        </button>
        <button type="button" disabled title={copy("FIN 0.1 后续版本", "Planned after FIN 0.1")}>
          <Settings size={16} aria-hidden="true" />
          <span>{copy("个人设置", "Settings")}</span>
        </button>
      </div>
    </aside>
  );
}

export function TaskQueueRail({ activeCaseId, onOpenCase }: TaskQueueRailProps) {
  const { copy, formatDateTime, labelToken, localizeFixtureText } = useWorkbenchLocale();
  const [filter, setFilter] = useState("");
  const [state, setState] = useState<QueueState>({ kind: "loading" });
  const [railOpen, setRailOpen] = useDesktopRailOpen();

  const load = useCallback(async () => {
    try {
      const projection = await caseApi.listCases();
      setState(projection.items.length ? { kind: "ready", items: projection.items } : { kind: "empty" });
    } catch {
      setState({ kind: "unavailable" });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleItems = useMemo(() => {
    if (state.kind !== "ready") return [];
    const normalized = filter.trim().toLowerCase();
    return normalized
      ? state.items.filter((item) => `${item.case_id} ${item.query} ${item.status}`.toLowerCase().includes(normalized))
      : state.items;
  }, [filter, state]);

  return (
    <aside className="analyst-task-rail" aria-label={copy("任务队列", "Task queue")}>
      <details open={railOpen} onToggle={(event) => setRailOpen(event.currentTarget.open)} className="analyst-rail-details">
        <summary>
          <span>{copy("任务队列", "Task queue")}</span>
          <span className="analyst-rail-count">{state.kind === "ready" ? state.items.length : ""}</span>
        </summary>
        <div className="analyst-rail-body">
          <label className="analyst-rail-search">
            <Search size={15} aria-hidden="true" />
            <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={copy("筛选任务", "Filter tasks")} aria-label={copy("筛选任务", "Filter tasks")} />
          </label>
          <button type="button" className="analyst-rail-refresh" onClick={() => void load()} title={copy("刷新任务队列", "Refresh task queue")} aria-label={copy("刷新任务队列", "Refresh task queue")}>
            <RefreshCcw size={15} aria-hidden="true" />
          </button>
          <div className="analyst-task-list">
            {state.kind === "loading" ? <p>{copy("正在读取任务...", "Loading tasks...")}</p> : null}
            {state.kind === "unavailable" ? <p>{copy("当前无法读取任务队列。", "Task queue is unavailable right now.")}</p> : null}
            {state.kind === "empty" ? <p>{copy("暂无研究任务。", "No research tasks yet.")}</p> : null}
            {state.kind === "ready" && visibleItems.length === 0 ? <p>{copy("没有匹配任务。", "No matching tasks.")}</p> : null}
            {visibleItems.map((item) => (
              <button type="button" key={item.case_id} className={item.case_id === activeCaseId ? "is-active" : undefined} onClick={() => onOpenCase(item.case_id)}>
                <span className="analyst-task-state"><i aria-hidden="true" />{labelToken(item.status)}</span>
                <strong>{localizeFixtureText(item.query) || copy("未命名研究", "Untitled research")}</strong>
                <small>{formatDateTime(item.updated_at)}</small>
              </button>
            ))}
          </div>
        </div>
      </details>
    </aside>
  );
}

export function CompactCaseTabs({ activeKind, onNavigate }: CompactCaseTabsProps) {
  const { copy } = useWorkbenchLocale();
  const items: Array<{ kind: CaseRouteKind; label: string; Icon: typeof LayoutDashboard }> = [
    { kind: "caseOverview", label: copy("概览", "Overview"), Icon: LayoutDashboard },
    { kind: "decisionSurface", label: copy("研究问题", "Research questions"), Icon: Compass },
    { kind: "evidence", label: copy("证据", "Evidence"), Icon: FileSearch },
    { kind: "numbers", label: copy("数字", "Numbers"), Icon: Calculator },
    { kind: "workpaper", label: copy("底稿", "Workpaper"), Icon: ClipboardCheck },
    { kind: "deliverable", label: copy("结论", "Deliverable"), Icon: FileText },
    { kind: "activity", label: copy("记录", "Trace"), Icon: Activity },
    { kind: "humanBaseline", label: copy("基线评测", "Baseline"), Icon: UserCheck },
  ];
  return (
    <nav className="analyst-case-tabs" aria-label={copy("研究工作区", "Research workspace")}>
      {items.map(({ kind, label, Icon }) => (
        <button type="button" key={kind} className={activeKind === kind ? "is-active" : undefined} aria-current={activeKind === kind ? "page" : undefined} onClick={() => onNavigate(kind)}>
          <Icon size={15} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

export function CaseContextDrawer({ caseId }: CaseContextDrawerProps) {
  const { copy, labelToken, localizeFixtureText } = useWorkbenchLocale();
  const [activePanel, setActivePanel] = useState<"evidence" | "review">("evidence");
  const [evidence, setEvidence] = useState<ReadonlyState<EvidenceWorkbenchView>>({ kind: "loading" });
  const [deliverable, setDeliverable] = useState<ReadonlyState<DeliverablePreviewView>>({ kind: "loading" });
  const [localChain, setLocalChain] = useState<ReadonlyState<{ research: LocalResearchPreviewView; analysis: LocalAnalysisPreviewView }>>({ kind: "loading" });
  const [drawerOpen, setDrawerOpen] = useDesktopRailOpen();

  const load = useCallback(async () => {
    setEvidence({ kind: "loading" });
    setDeliverable({ kind: "loading" });
    setLocalChain({ kind: "loading" });
    const [evidenceResult, deliverableResult, localChainResult] = await Promise.allSettled([
      evidenceApi.getEvidenceWorkbench(caseId),
      deliverablesApi.getDeliverableHead(caseId),
      Promise.all([
        evidenceApi.getLocalResearchPreview(caseId),
        evidenceApi.getLocalAnalysisPreview(caseId),
      ]),
    ]);
    setEvidence(readonlyResult(evidenceResult, isEvidenceUnavailable));
    setDeliverable(readonlyResult(deliverableResult, isDeliverableUnavailable));
    setLocalChain(localChainResult.status === "fulfilled"
      ? { kind: "ready", data: { research: localChainResult.value[0], analysis: localChainResult.value[1] } }
      : { kind: "unavailable" });
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const legacyFirstCandidate = evidence.kind === "ready"
    ? evidence.data.cells.flatMap((cell) => cell.candidates).find((candidate) => candidate.state !== "rejected")
    : undefined;
  const localFirstCandidate = localChain.kind === "ready"
    ? localChain.data.research.cells.flatMap((cell) => cell.candidates)[0]
    : undefined;
  const candidateCount = localChain.kind === "ready"
    ? localChain.data.research.candidate_count
    : evidence.kind === "ready" ? evidence.data.summary.candidate_count : 0;
  const exactFactCount = localChain.kind === "ready" ? localChain.data.analysis.numeric.facts.length : 0;
  const reviewBoundaryCount = localChain.kind === "ready"
    ? localChain.data.analysis.judgments.filter((judgment) => judgment.remaining_gaps.length > 0).length
    : evidence.kind === "ready" ? evidence.data.summary.gap_count : 0;
  const latestReview = deliverable.kind === "ready" ? deliverable.data.review_actions.at(-1) : undefined;

  return (
    <aside className="analyst-context-drawer" aria-label={copy("证据与复核上下文", "Evidence and reviewer context")}>
      <details open={drawerOpen} onToggle={(event) => setDrawerOpen(event.currentTarget.open)} className="analyst-rail-details">
        <summary>
          <span>{copy("研究上下文", "Research context")}</span>
          <PanelRight size={15} aria-hidden="true" />
        </summary>
        <div className="analyst-context-body">
          <div className="analyst-context-tabs" role="tablist" aria-label={copy("研究上下文", "Research context")}>
            <button type="button" role="tab" aria-selected={activePanel === "evidence"} className={activePanel === "evidence" ? "is-active" : undefined} onClick={() => setActivePanel("evidence")}>
              {copy("证据", "Evidence")}
              {candidateCount ? <span>{candidateCount}</span> : null}
            </button>
            <button type="button" role="tab" aria-selected={activePanel === "review"} className={activePanel === "review" ? "is-active" : undefined} onClick={() => setActivePanel("review")}>
              {copy("复核", "Reviewer")}
              {reviewBoundaryCount || deliverable.kind === "ready" ? <span>{reviewBoundaryCount + (deliverable.kind === "ready" ? deliverable.data.review_actions.length : 0)}</span> : null}
            </button>
            <button type="button" className="analyst-context-refresh" onClick={() => void load()} title={copy("刷新研究上下文", "Refresh research context")} aria-label={copy("刷新研究上下文", "Refresh research context")}>
              <RefreshCcw size={14} aria-hidden="true" />
            </button>
          </div>
          {activePanel === "evidence" ? (
            <section className="analyst-context-panel" role="tabpanel">
              {evidence.kind === "loading" && localChain.kind === "loading" ? <p>{copy("正在载入证据...", "Loading evidence...")}</p> : null}
              {(evidence.kind === "empty" || evidence.kind === "unavailable") && localChain.kind !== "ready" ? <EmptyContext label={copy("证据尚未准备", "Evidence is not prepared")} detail={copy("当前案例没有可读取的证据台账，不会改动研究状态。", "This case has no readable evidence ledger. No research state was changed.")} /> : null}
              {localChain.kind === "ready" ? (
                <>
                  <dl className="analyst-context-metrics">
                    <div><dt>{copy("候选证据", "Candidates")}</dt><dd>{candidateCount}</dd></div>
                    <div><dt>{copy("精确事实", "Exact facts")}</dt><dd>{exactFactCount}</dd></div>
                    <div><dt>{copy("判断边界", "Limits")}</dt><dd className={reviewBoundaryCount ? "has-gap" : undefined}>{reviewBoundaryCount}</dd></div>
                  </dl>
                  {localFirstCandidate ? (
                    <article className="analyst-context-card">
                      <small>{labelToken(localFirstCandidate.retrieval_lane)}</small>
                      <strong>{localizeFixtureText(localFirstCandidate.title)}</strong>
                      <p>{localizeFixtureText(localFirstCandidate.excerpt)}</p>
                      <span>{localFirstCandidate.source_name}</span>
                    </article>
                  ) : <EmptyContext label={copy("尚无可用候选证据", "No usable evidence candidate")} detail={copy("当前证据台账保留了明确的来源缺口。", "The evidence ledger retains its explicit source gap.")} />}
                  <div className="analyst-context-limit-list">
                    {localChain.data.analysis.judgments.filter((judgment) => judgment.remaining_gaps.length).slice(0, 2).map((judgment) => (
                      <div key={judgment.judgment_id}>
                        <strong>{labelToken(judgment.evidence_role)}</strong>
                        <p>{localizeFixtureText(judgment.remaining_gaps[0])}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : evidence.kind === "ready" ? (
                <>
                  <dl className="analyst-context-metrics">
                    <div><dt>{copy("候选证据", "Candidates")}</dt><dd>{evidence.data.summary.candidate_count}</dd></div>
                    <div><dt>{copy("证据缺口", "Gaps")}</dt><dd className={evidence.data.summary.gap_count ? "has-gap" : undefined}>{evidence.data.summary.gap_count}</dd></div>
                    <div><dt>{copy("已补充", "Repaired")}</dt><dd>{evidence.data.summary.repair_completed_count}</dd></div>
                  </dl>
                  {legacyFirstCandidate ? <article className="analyst-context-card"><small>{labelToken(legacyFirstCandidate.source_role)}</small><strong>{localizeFixtureText(legacyFirstCandidate.title)}</strong><p>{localizeFixtureText(legacyFirstCandidate.excerpt)}</p><span>{legacyFirstCandidate.source_name}</span></article> : null}
                </>
              ) : null}
            </section>
          ) : (
            <section className="analyst-context-panel" role="tabpanel">
              {deliverable.kind === "loading" && localChain.kind === "loading" ? <p>{copy("正在载入复核上下文...", "Loading reviewer context...")}</p> : null}
              {localChain.kind === "ready" ? (
                <article className="analyst-review-head">
                  <small>Senior R2</small>
                  <strong>{labelToken(localChain.data.analysis.workpaper.senior_r2_status)}</strong>
                  <span>{copy(`${reviewBoundaryCount} 个判断边界待逐项确认`, `${reviewBoundaryCount} judgment limits await review`)}</span>
                </article>
              ) : null}
              {(deliverable.kind === "empty" || deliverable.kind === "unavailable") && localChain.kind !== "ready" ? <EmptyContext label={copy("结论尚未准备", "Deliverable is not prepared")} detail={copy("当前案例没有可读取的结论或复核记录，不会改变任何版本。", "This case has no readable deliverable or review record. No version was changed.")} /> : null}
              {deliverable.kind === "ready" ? (
                <>
                  <article className="analyst-review-head">
                    <small>{copy("当前结论", "Current deliverable")}</small>
                    <strong>{localizeFixtureText(deliverable.data.title)}</strong>
                    <span>{copy(`版本 ${deliverable.data.artifact_version}`, `Version ${deliverable.data.artifact_version}`)}</span>
                  </article>
                  {latestReview ? (
                    <article className="analyst-context-card">
                      <small>{copy("最新复核", "Latest review")}</small>
                      <strong>{labelToken(latestReview.action_type)}</strong>
                      <p>{localizeFixtureText(latestReview.reason)}</p>
                    </article>
                  ) : <EmptyContext label={copy("暂无复核动作", "No reviewer action")} detail={copy("当前结论尚未记录任何只读复核动作。", "No read-only reviewer action is recorded for the current deliverable.")} />}
                </>
              ) : null}
            </section>
          )}
        </div>
      </details>
    </aside>
  );
}

function EmptyContext({ label, detail }: { label: string; detail: string }) {
  return <div className="analyst-context-empty"><strong>{label}</strong><p>{detail}</p></div>;
}

function readonlyResult<T>(result: PromiseSettledResult<T>, isUnavailable: (reason: unknown) => boolean): ReadonlyState<T> {
  if (result.status === "fulfilled") return { kind: "ready", data: result.value };
  return isUnavailable(result.reason) ? { kind: "empty" } : { kind: "unavailable" };
}

function isEvidenceUnavailable(reason: unknown): boolean {
  return reason instanceof EvidenceApiError && (reason.statusCode === 404 || reason.code === "not_prepared" || reason.code === "case_not_found");
}

function isDeliverableUnavailable(reason: unknown): boolean {
  return reason instanceof DeliverablesApiError && (reason.statusCode === 404 || reason.code === "not_prepared" || reason.code === "case_not_found");
}

export function isCaseReadUnavailable(reason: unknown): boolean {
  return reason instanceof CaseApiError && (reason.statusCode === 404 || reason.code === "case_not_found");
}
