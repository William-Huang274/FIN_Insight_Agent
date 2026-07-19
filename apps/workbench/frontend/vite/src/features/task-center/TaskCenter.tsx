import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  CirclePlus,
  ListFilter,
  RefreshCcw,
  Search,
} from "lucide-react";

import {
  CaseApiClient,
  CaseApiError,
  CaseWorkspaceProjection,
  CreateCaseDraftCommand,
  TaskCenterProjection,
} from "../../api/cases";
import {
  EvidenceApiClient,
  LocalAnalysisPreviewView,
  LocalResearchPreviewView,
} from "../../api/evidence";
import { RemoteStatus, RemoteStatusKind } from "../../shared/RemoteStatus";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";

type TaskCenterProps = {
  online: boolean;
  onNewCase: () => void;
  onOpenCase: (caseId: string) => void;
};

type NewCaseProps = {
  online: boolean;
  onBack: () => void;
  onCreated: (caseId: string) => void;
};

type RemoteResult<T> =
  | { kind: "loading" }
  | { kind: "ready"; data: T }
  | { kind: "offline"; message: string }
  | { kind: Exclude<RemoteStatusKind, "loading" | "empty" | "reconnecting">; message: string };

type IdempotentAttempt = { fingerprint: string; key: string };

const caseApi = new CaseApiClient();
const evidenceApi = new EvidenceApiClient();

type ResearchSnapshot = {
  research: LocalResearchPreviewView;
  analysis: LocalAnalysisPreviewView;
};

type SnapshotState =
  | { kind: "idle" | "loading" | "unavailable" }
  | { kind: "ready"; data: ResearchSnapshot };

export function TaskCenter({ online, onNewCase, onOpenCase }: TaskCenterProps) {
  const { copy, formatDateTime, labelToken, localizeFixtureText } = useWorkbenchLocale();
  const [remote, setRemote] = useState<RemoteResult<TaskCenterProjection>>({ kind: "loading" });
  const [statusFilter, setStatusFilter] = useState("all");
  const [taskView, setTaskView] = useState<"mine" | "review" | "blocked" | "completed">("mine");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");
  const [queryFilter, setQueryFilter] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotState>({ kind: "idle" });

  const load = useCallback(async () => {
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: copy("当前无法连接演示数据，恢复连接后会自动加载研究任务。", "Demo data is unavailable. Research cases will reload after reconnection.") });
      return;
    }
    setRemote({ kind: "loading" });
    try {
      setRemote({ kind: "ready", data: await caseApi.listCases() });
    } catch (error) {
      setRemote(caseFailure(error));
    }
  }, [copy, online]);

  useEffect(() => {
    void load();
  }, [load]);

  const items = remote.kind === "ready" ? remote.data.items : [];
  const statuses = useMemo(
    () => Array.from(new Set(items.map((item) => item.status))).sort((left, right) => left.localeCompare(right)),
    [items],
  );
  const visibleItems = useMemo(
    () => {
      const normalized = queryFilter.trim().toLowerCase();
      return items.filter((item) => {
        const normalizedStatus = item.status.toLowerCase();
        const viewMatches = taskView === "mine"
          || (taskView === "review" && normalizedStatus.includes("review"))
          || (taskView === "blocked" && (normalizedStatus.includes("block") || normalizedStatus.includes("fail")))
          || (taskView === "completed" && (normalizedStatus.includes("complete") || normalizedStatus.includes("accept")));
        const statusMatches = statusFilter === "all" || item.status === statusFilter;
        const queryMatches = !normalized || `${item.query} ${item.case_id}`.toLowerCase().includes(normalized);
        return viewMatches && statusMatches && queryMatches;
      }).sort((left, right) => {
        const delta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
        return sortOrder === "newest" ? delta : -delta;
      });
    },
    [items, queryFilter, sortOrder, statusFilter, taskView],
  );

  useEffect(() => {
    if (!visibleItems.length) {
      setSelectedCaseId(null);
      return;
    }
    if (!selectedCaseId || !visibleItems.some((item) => item.case_id === selectedCaseId)) {
      setSelectedCaseId(visibleItems[0].case_id);
    }
  }, [selectedCaseId, visibleItems]);

  useEffect(() => {
    if (!selectedCaseId || !online || !navigator.onLine) {
      setSnapshot({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setSnapshot({ kind: "loading" });
    void Promise.all([
      evidenceApi.getLocalResearchPreview(selectedCaseId),
      evidenceApi.getLocalAnalysisPreview(selectedCaseId),
    ]).then(([research, analysis]) => {
      if (!cancelled) setSnapshot({ kind: "ready", data: { research, analysis } });
    }).catch(() => {
      if (!cancelled) setSnapshot({ kind: "unavailable" });
    });
    return () => { cancelled = true; };
  }, [online, selectedCaseId]);

  const selected = items.find((item) => item.case_id === selectedCaseId) ?? null;
  const viewCounts = useMemo(() => ({
    mine: items.length,
    review: items.filter((item) => item.status.toLowerCase().includes("review")).length,
    blocked: items.filter((item) => /block|fail/.test(item.status.toLowerCase())).length,
    completed: items.filter((item) => /complete|accept/.test(item.status.toLowerCase())).length,
  }), [items]);

  return (
    <section className="p02-workspace p02-research-library task-center-workspace" aria-label={copy("研究任务", "Research cases")}>
      <div className="p02-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("研究工作区", "Research workspace")}</p>
          <h1>{copy("研究任务", "Research cases")}</h1>
          <p className="p02-page-intro">{copy("从研究问题进入证据、数字、底稿和结论，不需要理解后台执行对象。", "Move from a research question to evidence, numbers, workpaper, and outcome without navigating backend objects.")}</p>
        </div>
        <div className="p02-page-actions">
          <button type="button" className="p02-icon-button" title={copy("刷新研究任务", "Refresh research cases")} aria-label={copy("刷新研究任务", "Refresh research cases")} onClick={() => void load()}>
            <RefreshCcw size={17} aria-hidden="true" />
          </button>
          <button type="button" className="p02-primary-button" onClick={onNewCase}>
            <CirclePlus size={17} aria-hidden="true" />
            {copy("发起研究", "Start research")}
          </button>
        </div>
      </div>

      {remote.kind === "loading" ? <RemoteStatus kind="loading" /> : null}
      {remote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} /> : null}
      {isFailure(remote) ? <RemoteStatus kind={remote.kind} message={remote.message} onRetry={() => void load()} /> : null}
      {remote.kind === "ready" && remote.data.items.length === 0 ? <RemoteStatus kind="empty" /> : null}
      {remote.kind === "ready" && remote.data.items.length > 0 ? (
        <div className={`task-center-board ${selected ? "" : "is-empty"}`}>
          <section className="task-center-ledger" aria-label={copy("研究任务台账", "Research task ledger")}>
            <nav className="task-center-tabs" aria-label={copy("任务视图", "Task views")}>
              {([
                ["mine", copy("我的任务", "My tasks")],
                ["review", copy("待复核", "For review")],
                ["blocked", copy("存在阻断", "Blocked")],
                ["completed", copy("最近完成", "Recently completed")],
              ] as const).map(([key, label]) => (
                <button key={key} type="button" className={taskView === key ? "is-active" : undefined} onClick={() => setTaskView(key)}>
                  {label}<span>{viewCounts[key]}</span>
                </button>
              ))}
            </nav>
            <div className="task-center-toolbar">
              <label className="task-center-search">
                <Search size={16} aria-hidden="true" />
                <input value={queryFilter} onChange={(event) => setQueryFilter(event.target.value)} placeholder={copy("搜索任务或公司", "Search tasks or companies")} />
              </label>
              <label className="p02-filter-control">
                <ListFilter size={15} aria-hidden="true" />
                <select value={statusFilter} aria-label={copy("状态", "Status")} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="all">{copy("状态：全部", "Status: all")}</option>
                  {statuses.map((status) => <option key={status} value={status}>{labelToken(status)}</option>)}
                </select>
              </label>
              <label className="p02-filter-control">
                <select value={sortOrder} aria-label={copy("排序", "Sort")} onChange={(event) => setSortOrder(event.target.value as "newest" | "oldest")}>
                  <option value="newest">{copy("排序：最近更新", "Sort: recently updated")}</option>
                  <option value="oldest">{copy("排序：最早更新", "Sort: oldest updated")}</option>
                </select>
              </label>
              <span className="p02-result-count">{copy(`${visibleItems.length} 个任务`, `${visibleItems.length} tasks`)}</span>
            </div>
            <div className="task-center-list" role="list" aria-label={copy("研究任务", "Research cases")}>
              <div className="task-center-table-head" aria-hidden="true">
                <span>{copy("研究问题", "Research question")}</span>
                <span>{copy("优先级", "Priority")}</span>
                <span>{copy("阶段", "Stage")}</span>
                <span>{copy("研究进度", "Progress")}</span>
                <span>{copy("证据", "Evidence")}</span>
                <span>{copy("缺口", "Gaps")}</span>
                <span>{copy("下一步", "Next")}</span>
              </div>
              {visibleItems.length === 0 ? (
                <section className="task-center-empty" aria-live="polite">
                  <strong>{copy("当前视图没有研究任务", "No research tasks in this view")}</strong>
                  <p>{copy("切换任务视图，或清除搜索和状态条件。", "Switch task views or clear the search and status filters.")}</p>
                  <button type="button" className="p02-secondary-button" onClick={() => {
                    setTaskView("mine");
                    setStatusFilter("all");
                    setQueryFilter("");
                  }}>{copy("返回我的任务", "Back to my tasks")}</button>
                </section>
              ) : null}
              {visibleItems.map((item) => {
                const isSelected = selectedCaseId === item.case_id;
                const selectedSnapshot = isSelected && snapshot.kind === "ready" ? snapshot.data : null;
                const totalCells = selectedSnapshot?.research.selected_cell_count ?? 0;
                const completedCells = selectedSnapshot?.analysis.judgments.length ?? 0;
                const remainingGaps = selectedSnapshot ? countJudgmentGaps(selectedSnapshot.analysis) : 0;
                const completion = totalCells ? Math.min(100, Math.round((completedCells / totalCells) * 100)) : 0;
                return (
                  <button
                    key={item.case_id}
                    type="button"
                    role="listitem"
                    className={`task-center-row ${isSelected ? "is-active" : ""}`}
                    onClick={() => setSelectedCaseId(item.case_id)}
                  >
                    <span className="task-center-task-cell">
                      <strong><b>{/P36/i.test(item.query) ? "P36" : copy("研究", "Research")}</b>{item.query ? localizeFixtureText(item.query) : copy("未命名研究", "Untitled research")}</strong>
                      <small>{item.case_id.slice(0, 18)} · v{item.case_version} · {formatDateTime(item.updated_at)}</small>
                    </span>
                    <span className="task-center-priority">{/P36|AI 基础设施|AI infrastructure/i.test(item.query) ? copy("高", "High") : copy("常规", "Normal")}</span>
                    <span className={`task-center-stage ${selectedSnapshot ? "is-review" : ""}`}>{selectedSnapshot ? copy("待复核", "For review") : labelToken(item.status)}</span>
                    <span className="task-center-row-progress">
                      <b>{selectedSnapshot ? `${completedCells} / ${totalCells} cells` : copy("准备中", "Preparing")}</b>
                      <i aria-hidden="true"><em style={{ width: `${completion}%` }} /></i>
                    </span>
                    <span className="task-center-number">{selectedSnapshot ? <><b>{selectedSnapshot.research.candidate_count}</b><small>{selectedSnapshot.analysis.numeric.facts.length} {copy("项精确事实", "exact facts")}</small></> : "—"}</span>
                    <span className={`task-center-number ${remainingGaps ? "has-gap" : ""}`}>{selectedSnapshot ? <b>{remainingGaps}</b> : "—"}</span>
                    <span className="task-center-next">{selectedSnapshot ? copy("完成 Senior R2", "Complete Senior R2") : copy("打开任务", "Open task")}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {selected ? (
            <aside className="task-center-inspector" aria-label={copy("所选研究摘要", "Selected research summary")}>
              <>
                <header>
                  <div><p className="p02-eyebrow">P36 · AI INFRASTRUCTURE</p><h2>{localizeFixtureText(selected.query)}</h2></div>
                  <span>{snapshot.kind === "ready" ? copy("待复核", "For review") : labelToken(selected.status)}</span>
                </header>
                {snapshot.kind === "loading" ? <div className="task-center-snapshot-loading">{copy("正在读取本地研究链…", "Loading the local research chain…")}</div> : null}
                {snapshot.kind === "unavailable" ? (
                  <div className="task-center-snapshot-empty">
                    <strong>{copy("研究链尚未准备", "Research chain not prepared")}</strong>
                    <p>{copy("Case 可以继续打开；证据、数字或底稿尚未形成可读预览。", "The Case can still be opened; Evidence, Numbers, or Workpaper is not ready yet.")}</p>
                  </div>
                ) : null}
                {snapshot.kind === "ready" ? (
                  <ResearchSnapshotPanel
                    snapshot={snapshot.data}
                    copy={copy}
                    localizeFixtureText={localizeFixtureText}
                  />
                ) : null}
                <button type="button" className="p02-primary-button task-center-open" onClick={() => onOpenCase(selected.case_id)}>
                  {copy("进入研究工作台", "Open research workbench")}<ArrowRight size={16} aria-hidden="true" />
                </button>
              </>
            </aside>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function ResearchSnapshotPanel({ snapshot, copy, localizeFixtureText }: {
  snapshot: ResearchSnapshot;
  copy: (zhCN: string, en: string) => string;
  localizeFixtureText: (value: string) => string;
}) {
  const gaps = countJudgmentGaps(snapshot.analysis);
  const completion = snapshot.research.selected_cell_count
    ? Math.min(100, Math.round((snapshot.analysis.judgments.length / snapshot.research.selected_cell_count) * 100))
    : 0;
  const laneCounts = snapshot.research.cells.flatMap((cell) => cell.candidates).reduce<Record<string, number>>((counts, candidate) => {
    counts[candidate.retrieval_lane] = (counts[candidate.retrieval_lane] ?? 0) + 1;
    return counts;
  }, {});
  const qualityRows = [
    { label: copy("精确事实", "Exact facts"), value: snapshot.analysis.numeric.facts.length, tone: "exact" },
    { label: copy("结构化候选", "Structured candidates"), value: laneCounts.gold_fact_sql ?? 0, tone: "structured" },
    { label: copy("关系图证据", "Graph evidence"), value: laneCounts.research_graph ?? 0, tone: "graph" },
  ];
  const maxQuality = Math.max(1, ...qualityRows.map((row) => row.value));
  const leadJudgment = snapshot.analysis.judgments[0];
  return (
    <>
      <section className="task-center-thesis">
        <span>{copy("当前判断", "Current judgment")}</span>
        <strong>{leadJudgment ? leadJudgment.judgment_zh_cn : copy("研究链已准备，等待 Senior R2 复核。", "Research chain prepared and awaiting Senior R2.")}</strong>
        {leadJudgment ? <p>{localizeFixtureText(leadJudgment.remaining_gaps[0] ?? leadJudgment.counter_thesis_zh_cn)}</p> : null}
      </section>
      <dl className="task-center-metrics">
        <div><dt>{copy("研究完成度", "Completion")}</dt><dd>{completion}%</dd><i aria-hidden="true"><em style={{ width: `${completion}%` }} /></i></div>
        <div><dt>{copy("证据候选", "Candidates")}</dt><dd>{snapshot.research.candidate_count}</dd><small>{snapshot.analysis.numeric.facts.length} {copy("个精确事实", "exact facts")}</small></div>
        <div><dt>{copy("开放缺口", "Open gaps")}</dt><dd className={gaps ? "has-gap" : undefined}>{gaps}</dd><small>{copy("需人工确认", "need human review")}</small></div>
      </dl>
      <section className="task-center-cell-preview">
        <h3>{copy("活跃研究单元", "Active research units")}</h3>
        {snapshot.analysis.judgments.slice(0, 6).map((judgment, index) => (
          <div key={judgment.judgment_id}>
            <small>{String(index + 1).padStart(2, "0")}</small>
            <p>{localizeFixtureText(judgment.decision_question)}</p>
            <b className={judgment.remaining_gaps.length ? "needs-review" : "is-ready"}>{judgment.remaining_gaps.length ? copy("需补证", "Review") : copy("已证实", "Ready")}</b>
          </div>
        ))}
      </section>
      <section className="task-center-quality">
        <h3>{copy("证据质量", "Evidence quality")}</h3>
        {qualityRows.map((row) => (
          <div key={row.label}><span>{row.label}</span><i aria-hidden="true"><em className={row.tone} style={{ width: `${Math.max(8, Math.round((row.value / maxQuality) * 100))}%` }} /></i><b>{row.value}</b></div>
        ))}
      </section>
      <section className="task-center-gaps">
        <h3>{copy("关键缺口与动作", "Key gaps and actions")}</h3>
        {snapshot.analysis.judgments.filter((judgment) => judgment.remaining_gaps.length).slice(0, 2).map((judgment) => (
          <div key={judgment.judgment_id}><AlertTriangle size={14} aria-hidden="true" /><span><strong>{localizeFixtureText(judgment.decision_question)}</strong><small>{localizeFixtureText(judgment.remaining_gaps[0])}</small></span></div>
        ))}
        {!gaps ? <div><CheckCircle2 size={14} aria-hidden="true" /><span><strong>{copy("当前没有开放缺口", "No open gaps")}</strong></span></div> : null}
      </section>
      <p className="task-center-exact">Preview <code>{snapshot.research.preview_digest.slice(0, 12)}</code> · Analysis <code>{snapshot.analysis.analysis_digest.slice(0, 12)}</code></p>
    </>
  );
}

function countJudgmentGaps(analysis: LocalAnalysisPreviewView): number {
  return new Set([
    ...analysis.numeric.typed_gaps,
    ...analysis.judgments.flatMap((judgment) => judgment.remaining_gaps),
  ].filter(Boolean)).size;
}

export function NewCase({ online, onBack, onCreated }: NewCaseProps) {
  const { copy, locale } = useWorkbenchLocale();
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState(locale);
  const [asOf, setAsOf] = useState(() => new Date().toISOString());
  const [remote, setRemote] = useState<RemoteResult<CaseWorkspaceProjection> | null>(null);
  const attemptRef = useRef<IdempotentAttempt | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!online || !navigator.onLine) {
      setRemote({ kind: "offline", message: copy("当前无法连接演示数据，请恢复连接后再创建研究。", "Demo data is unavailable. Reconnect before creating this research case.") });
      return;
    }
    const fingerprint = JSON.stringify({ query, asOf, language });
    const command: CreateCaseDraftCommand = {
      query,
      as_of: asOf,
      language,
      source_policy_ref: "fixture:internal",
      idempotency_key: keyForAttempt(attemptRef, fingerprint),
    };
    setRemote({ kind: "loading" });
    try {
      const workspace = await caseApi.createCase(command);
      attemptRef.current = null;
      onCreated(workspace.case_id);
    } catch (error) {
      setRemote(caseFailure(error));
    }
  }

  return (
    <section className="p02-workspace p02-form-layout" aria-label={copy("发起研究", "Start research")}>
      <button type="button" className="p02-back-button" onClick={onBack}>
        <ArrowLeft size={16} aria-hidden="true" />
        {copy("研究任务", "Research cases")}
      </button>
      <div className="p02-page-heading">
        <div>
          <p className="p02-eyebrow">{copy("内部演示", "Internal demo")}</p>
          <h1>{copy("发起一项研究", "Start a research case")}</h1>
          <p className="p02-page-intro">{copy("先写清楚需要回答的投资问题，系统会据此拆分研究问题和证据要求。", "Begin with the investment question; the workbench will frame research questions and evidence needs from it.")}</p>
        </div>
      </div>
      <form className="p02-case-form" onSubmit={(event) => void submit(event)}>
        <label>
          {copy("研究问题", "Research question")}
          <textarea value={query} onChange={(event) => setQuery(event.target.value)} required rows={5} placeholder={copy("例如：AI 基础设施需求是否正在转化为可持续的收入、利润与现金流？主要反证是什么？", "For example: Is AI infrastructure demand translating into durable revenue, profit, and cash flow, and what could disprove the thesis?")} />
        </label>
        <div className="p02-form-grid">
          <label>
            {copy("研究截止时间", "As of")}
            <input type="datetime-local" value={asOf.slice(0, 16)} onChange={(event) => setAsOf(new Date(event.target.value).toISOString())} required />
          </label>
          <label>
            {copy("研究输出语言", "Research output language")}
            <select value={language} onChange={(event) => setLanguage(event.target.value as "zh-CN" | "en")}>
              <option value="zh-CN">简体中文</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>
        <div className="p02-form-footer">
          <button type="button" className="p02-secondary-button" onClick={onBack}>{copy("取消", "Cancel")}</button>
          <button type="submit" className="p02-primary-button" disabled={remote?.kind === "loading" || !online}>
            <CirclePlus size={17} aria-hidden="true" />
            {copy("创建研究", "Create research")}
          </button>
        </div>
      </form>
      {remote?.kind === "loading" ? <RemoteStatus kind="loading" /> : null}
      {remote?.kind === "offline" ? <RemoteStatus kind="reconnecting" message={remote.message} /> : null}
      {remote && isFailure(remote) ? <RemoteStatus kind={remote.kind} message={remote.message} /> : null}
    </section>
  );
}

function caseFailure(error: unknown): Extract<RemoteResult<never>, { kind: "error" | "permission" | "stale" | "conflict" }> {
  if (error instanceof CaseApiError) {
    const kind = error.code === "permission_denied" || error.statusCode === 403
      ? "permission"
      : error.code === "version_conflict" || error.code === "idempotency_conflict"
        ? "conflict"
        : error.code.includes("stale") || error.code.includes("superseded")
          ? "stale"
          : "error";
    return { kind, message: error.traceId ? `${error.message} Trace: ${error.traceId}` : error.message };
  }
  return { kind: "error", message: "The fixture API did not return a usable case response." };
}

function isFailure<T>(remote: RemoteResult<T>): remote is Extract<RemoteResult<T>, { kind: "error" | "permission" | "stale" | "conflict" }> {
  return remote.kind === "error" || remote.kind === "permission" || remote.kind === "stale" || remote.kind === "conflict";
}

function keyForAttempt(ref: { current: IdempotentAttempt | null }, fingerprint: string): string {
  if (ref.current?.fingerprint === fingerprint) return ref.current.key;
  const key = `workbench-${crypto.randomUUID()}`;
  ref.current = { fingerprint, key };
  return key;
}
