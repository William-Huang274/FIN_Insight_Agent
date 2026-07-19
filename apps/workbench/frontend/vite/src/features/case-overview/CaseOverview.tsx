import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  ArrowRight,
  Braces,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  CircleDot,
  ExternalLink,
  FileCheck2,
  FileSearch,
  RefreshCcw,
  ShieldAlert,
} from "lucide-react";

import { CaseApiClient, CaseApiError, CaseWorkspaceProjection } from "../../api/cases";
import {
  EvidenceApiClient,
  LocalAnalysisJudgmentView,
  LocalAnalysisPreviewView,
  LocalResearchCellView,
  LocalResearchPreviewView,
} from "../../api/evidence";
import {
  CompileDecisionSurfaceCommand,
  DecisionSurfaceView,
  P36_COMPILER_POLICY_REF,
  P36_PACK_SELECTION_REF,
  PlanningApiClient,
  PlanningApiError,
} from "../../api/planning";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { RemoteStatus, RemoteStatusKind } from "../../shared/RemoteStatus";

type CaseOverviewProps = {
  caseId: string;
  online: boolean;
  onBack: () => void;
  onOpenDecisionSurface: () => void;
  onOpenEvidence: () => void;
  onOpenActivity: () => void;
};

type RemoteResult<T> =
  | { kind: "loading" }
  | { kind: "ready"; data: T }
  | { kind: "empty" }
  | { kind: "offline"; message: string }
  | { kind: Exclude<RemoteStatusKind, "loading" | "empty" | "reconnecting">; message: string };

type LocalChainResult =
  | { kind: "loading" }
  | { kind: "ready"; research: LocalResearchPreviewView; analysis: LocalAnalysisPreviewView }
  | { kind: "unavailable" }
  | { kind: "offline"; message: string };

type MutationResult = { kind: "idle" | "loading" } | { kind: "offline"; message: string } | FailureResult;
type FailureResult = { kind: "error" | "permission" | "stale" | "conflict"; message: string };
type IdempotentAttempt = { fingerprint: string; key: string };
type Copy = (zhCN: string, en: string) => string;

const caseApi = new CaseApiClient();
const planningApi = new PlanningApiClient();
const evidenceApi = new EvidenceApiClient();
const PRIORITY_ROLES = [
  "demand_signal",
  "revenue_capture",
  "thesis_counterevidence",
  "server_oem_orders",
  "server_oem_margin_cash",
  "advanced_packaging_capacity",
  "hbm_supply_pricing",
  "semicap_capex_cycle",
  "export_policy_risk",
  "customer_concentration",
];

export function CaseOverview({ caseId, online, onBack, onOpenDecisionSurface, onOpenEvidence, onOpenActivity }: CaseOverviewProps) {
  const { copy, formatDateTime, labelToken, locale, localizeFixtureText } = useWorkbenchLocale();
  const [workspaceRemote, setWorkspaceRemote] = useState<RemoteResult<CaseWorkspaceProjection>>({ kind: "loading" });
  const [surfaceRemote, setSurfaceRemote] = useState<RemoteResult<DecisionSurfaceView>>({ kind: "loading" });
  const [localChainRemote, setLocalChainRemote] = useState<LocalChainResult>({ kind: "loading" });
  const [compileRemote, setCompileRemote] = useState<MutationResult>({ kind: "idle" });
  const [showAllCells, setShowAllCells] = useState(false);
  const [expandedCellKey, setExpandedCellKey] = useState<string | null>(null);
  const versionRef = useRef<number | undefined>(undefined);
  const compileAttemptRef = useRef<IdempotentAttempt | null>(null);
  const expandedInitializedRef = useRef(false);
  const copyRef = useRef<Copy>(copy);
  copyRef.current = copy;

  const load = useCallback(async (validateVersion: boolean) => {
    if (!online || !navigator.onLine) {
      const offline = { kind: "offline" as const, message: copyRef.current("连接不可用。请重新连接以从 API 恢复此案例。", "Connection is unavailable. Reconnect to restore this Case from the API.") };
      setWorkspaceRemote(offline);
      setSurfaceRemote(offline);
      setLocalChainRemote(offline);
      return;
    }
    setWorkspaceRemote({ kind: "loading" });
    setSurfaceRemote({ kind: "loading" });
    setLocalChainRemote({ kind: "loading" });
    setCompileRemote({ kind: "idle" });
    try {
      const workspace = await caseApi.getCase(caseId, validateVersion ? versionRef.current : undefined);
      versionRef.current = workspace.case_version;
      setWorkspaceRemote({ kind: "ready", data: workspace });

      const surfaceLoad = planningApi.getDecisionSurface(caseId).then(
        (surface) => setSurfaceRemote({ kind: "ready", data: surface }),
        (error) => setSurfaceRemote(isPlanningMissing(error) ? { kind: "empty" } : planningFailure(error, copyRef.current)),
      );
      const localChainLoad = Promise.all([
        evidenceApi.getLocalResearchPreview(caseId),
        evidenceApi.getLocalAnalysisPreview(caseId),
      ]).then(
        ([research, analysis]) => setLocalChainRemote({ kind: "ready", research, analysis }),
        () => setLocalChainRemote({ kind: "unavailable" }),
      );
      await Promise.allSettled([surfaceLoad, localChainLoad]);
    } catch (error) {
      setWorkspaceRemote(caseFailure(error, copyRef.current));
      setSurfaceRemote({ kind: "error", message: copyRef.current("案例重新加载前，研究计划数据不可用。", "Research-plan data is unavailable until the Case reloads.") });
      setLocalChainRemote({ kind: "unavailable" });
    }
  }, [caseId, online]);

  useEffect(() => {
    expandedInitializedRef.current = false;
    setExpandedCellKey(null);
    setShowAllCells(false);
    void load(false);
  }, [caseId, load]);

  const workspace = workspaceRemote.kind === "ready" ? workspaceRemote.data : null;
  const surface = surfaceRemote.kind === "ready" ? surfaceRemote.data : null;
  const localChain = localChainRemote.kind === "ready" ? localChainRemote : null;
  const sortedCells = useMemo(() => {
    if (!localChain) return [];
    const rank = new Map(PRIORITY_ROLES.map((role, index) => [role, index]));
    return [...localChain.research.cells].sort(
      (left, right) => (rank.get(left.evidence_role) ?? 99) - (rank.get(right.evidence_role) ?? 99),
    );
  }, [localChain]);

  useEffect(() => {
    if (!expandedInitializedRef.current && sortedCells.length) {
      setExpandedCellKey(sortedCells[0].cell_key);
      expandedInitializedRef.current = true;
    }
  }, [sortedCells]);

  async function compilePlan() {
    if (!workspace) return;
    if (!online || !navigator.onLine) {
      setCompileRemote({ kind: "offline", message: copyRef.current("连接不可用。请重新连接后再生成研究单元。", "Connection is unavailable. Reconnect before compiling the research cells.") });
      return;
    }
    const fingerprint = `${workspace.case_version}:${workspace.summary_version}:${P36_COMPILER_POLICY_REF}:${P36_PACK_SELECTION_REF}`;
    const command: CompileDecisionSurfaceCommand = {
      expected_case_version: workspace.case_version,
      expected_summary_version: workspace.summary_version,
      compiler_policy_ref: P36_COMPILER_POLICY_REF,
      pack_selection_ref: P36_PACK_SELECTION_REF,
      actor_ref: planningApi.actorRef,
      idempotency_key: keyForAttempt(compileAttemptRef, fingerprint),
    };
    setCompileRemote({ kind: "loading" });
    try {
      await planningApi.compileDecisionSurface(caseId, command);
      compileAttemptRef.current = null;
      setCompileRemote({ kind: "idle" });
      onOpenDecisionSurface();
    } catch (error) {
      setCompileRemote(planningFailure(error, copyRef.current));
    }
  }

  return (
    <section className="p02-workspace p02-detail" aria-label={copy("研究概览", "Research overview")}>
      <button type="button" className="p02-back-button" onClick={onBack}>
        <ArrowLeft size={16} aria-hidden="true" />
        {copy("研究任务", "Research cases")}
      </button>
      <div className="p02-page-heading research-case-heading">
        <div>
          <p className="p02-eyebrow">{copy("P36 · AI 基础设施研究", "P36 · AI infrastructure research")}</p>
          <h1>{workspace ? localizeFixtureText(workspace.query) : copy("正在载入研究问题", "Loading research question")}</h1>
          <p className="p02-heading-meta">
            {caseId}{workspace ? ` · ${copy("截至", "As of")} ${formatDateTime(workspace.as_of)}` : ""}
          </p>
        </div>
        <div className="p02-page-actions">
          <button type="button" className="p02-secondary-button" onClick={onOpenEvidence}>
            <FileSearch size={16} aria-hidden="true" />
            {copy("证据工作台", "Evidence workbench")}
          </button>
          <button type="button" className="p02-secondary-button" onClick={onOpenActivity}>
            <ActivityIcon size={16} aria-hidden="true" />
            {copy("研究记录", "Research trace")}
          </button>
          <button type="button" className="p02-icon-button" title={copy("刷新案例", "Refresh case")} aria-label={copy("刷新案例", "Refresh case")} onClick={() => void load(true)}>
            <RefreshCcw size={17} aria-hidden="true" />
          </button>
        </div>
      </div>

      {workspaceRemote.kind === "loading" ? <RemoteStatus kind="loading" /> : null}
      {workspaceRemote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={workspaceRemote.message} /> : null}
      {isFailure(workspaceRemote) ? <RemoteStatus kind={workspaceRemote.kind} message={workspaceRemote.message} onRetry={() => void load(false)} /> : null}

      {workspace && localChainRemote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在装载研究判断、精确数字和证据上下文。", "Loading judgments, exact numbers, and evidence context.")} /> : null}
      {workspace && localChainRemote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={localChainRemote.message} /> : null}

      {workspace && localChain ? (
        <ResearchCommandCenter
          research={localChain.research}
          analysis={localChain.analysis}
          cells={sortedCells}
          showAllCells={showAllCells}
          expandedCellKey={expandedCellKey}
          locale={locale}
          copy={copy}
          labelToken={labelToken}
          localizeFixtureText={localizeFixtureText}
          onToggleAll={() => setShowAllCells((current) => !current)}
          onToggleCell={(cellKey) => setExpandedCellKey((current) => current === cellKey ? null : cellKey)}
          onOpenEvidence={onOpenEvidence}
        />
      ) : null}

      {workspace && localChainRemote.kind === "unavailable" ? (
        <PlanningFallback
          surfaceRemote={surfaceRemote}
          surface={surface}
          compileRemote={compileRemote}
          online={online}
          copy={copy}
          labelToken={labelToken}
          localizeFixtureText={localizeFixtureText}
          onRetry={() => void load(false)}
          onCompile={() => void compilePlan()}
          onOpenDecisionSurface={onOpenDecisionSurface}
        />
      ) : null}

      {workspace ? (
        <dl className="research-case-footnote" aria-label={copy("案例版本", "Case version")}>
          <div><dt>{copy("案例", "Case")}</dt><dd>v{workspace.case_version}</dd></div>
          <div><dt>{copy("研究计划", "Research plan")}</dt><dd>{labelToken(workspace.planning_checkpoint_state)}</dd></div>
          <div><dt>{copy("发布状态", "Release status")}</dt><dd>{copy("内部候选 · 未获发布准入", "Internal candidate · not release admitted")}</dd></div>
        </dl>
      ) : null}
    </section>
  );
}

type ResearchCommandCenterProps = {
  research: LocalResearchPreviewView;
  analysis: LocalAnalysisPreviewView;
  cells: LocalResearchCellView[];
  showAllCells: boolean;
  expandedCellKey: string | null;
  locale: "zh-CN" | "en";
  copy: Copy;
  labelToken: (value: string) => string;
  localizeFixtureText: (value: string) => string;
  onToggleAll: () => void;
  onToggleCell: (cellKey: string) => void;
  onOpenEvidence: () => void;
};

function ResearchCommandCenter({
  research,
  analysis,
  cells,
  showAllCells,
  expandedCellKey,
  locale,
  copy,
  labelToken,
  localizeFixtureText,
  onToggleAll,
  onToggleCell,
  onOpenEvidence,
}: ResearchCommandCenterProps) {
  const judgmentsByCell = new Map(analysis.judgments.map((judgment) => [judgment.cell_key, judgment]));
  const demandJudgment = analysis.judgments.find((judgment) => judgment.evidence_role === "demand_signal") ?? analysis.judgments[0];
  const revenueJudgment = analysis.judgments.find((judgment) => judgment.evidence_role === "revenue_capture");
  const displayedCells = showAllCells ? cells : cells.slice(0, 6);
  const remainingGaps = uniqueStrings([
    ...analysis.numeric.typed_gaps,
    ...research.cells.flatMap((cell) => cell.typed_gap ? [cell.typed_gap] : []),
    ...analysis.judgments.flatMap((judgment) => judgment.remaining_gaps),
  ]);
  const revenue = analysis.numeric.facts.find((fact) => fact.metric_family === "revenue");
  const grossMargin = analysis.numeric.derived_metrics.find((metric) => metric.metric === "gross_margin");
  const operatingMargin = analysis.numeric.derived_metrics.find((metric) => metric.metric === "operating_margin");
  const nextCell = cells
    .map((cell) => ({ cell, judgment: judgmentsByCell.get(cell.cell_key) }))
    .find(({ cell, judgment }) => cell.status === "typed_gap" || judgment?.confidence === "low" || Boolean(judgment?.remaining_gaps.length));

  return (
    <div className="research-command-center">
      <section className="research-command-summary" aria-labelledby="research-current-thesis">
        <div className="research-thesis-block">
          <header>
            <div>
              <p className="p02-eyebrow">{copy("当前研究判断", "Current research judgment")}</p>
              <h2 id="research-current-thesis">{copy("需求转化已出现，但结论仍有明确边界", "Demand conversion is visible, with explicit limits")}</h2>
            </div>
            <span className="research-review-state"><FileCheck2 size={14} aria-hidden="true" />{copy("待 Senior R2", "Senior R2 pending")}</span>
          </header>
          <p>{demandJudgment ? judgmentText(demandJudgment, locale) : copy("当前研究链尚未形成候选判断。", "The current research chain has not produced a candidate judgment.")}</p>
          {revenueJudgment ? <p className="research-thesis-support">{judgmentText(revenueJudgment, locale)}</p> : null}
          <footer><ShieldAlert size={14} aria-hidden="true" />{copy("候选判断仅供内部研究；证据尚未晋升，未获得发布准入。", "Candidate judgments are internal only; evidence is not promoted and release is not admitted.")}</footer>
        </div>
        <dl className="research-command-metrics">
          <Metric label={copy("收入", "Revenue")} value={revenue ? compactMetric(revenue.value, revenue.unit, locale) : "-"} detail={revenue?.period ?? copy("待核验", "Pending")} />
          <Metric label={copy("毛利率", "Gross margin")} value={grossMargin ? `${grossMargin.value}%` : "-"} detail={copy("精确事实派生", "Derived from exact facts")} />
          <Metric label={copy("营业利润率", "Operating margin")} value={operatingMargin ? `${operatingMargin.value}%` : "-"} detail={copy("精确事实派生", "Derived from exact facts")} />
          <Metric label={copy("研究证据", "Research evidence")} value={String(research.candidate_count)} detail={copy(`${analysis.numeric.facts.length} 个精确事实`, `${analysis.numeric.facts.length} exact facts`)} />
          <Metric label={copy("待复核边界", "Review boundaries")} value={String(remainingGaps.length)} detail={copy("不等同于失败", "Not equivalent to failure")} emphasis={remainingGaps.length > 0} />
        </dl>
      </section>

      <section className="research-unit-section" aria-labelledby="research-unit-heading">
        <div className="research-unit-toolbar">
          <div>
            <p className="p02-eyebrow">DecisionSurface</p>
            <h2 id="research-unit-heading">{copy("研究单元与判断链", "Research units and judgment chain")}</h2>
            <p>{copy("展开单元查看候选判断、反证、证据和仍需确认的边界。", "Expand a unit to inspect its candidate judgment, counterevidence, evidence, and remaining limits.")}</p>
          </div>
          {cells.length > 6 ? (
            <button type="button" className="research-unit-toggle" onClick={onToggleAll}>
              {showAllCells ? copy("只看优先单元", "Priority units") : copy(`查看全部 ${cells.length} 个单元`, `View all ${cells.length} units`)}
              {showAllCells ? <ChevronUp size={15} aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}
            </button>
          ) : null}
        </div>

        <div className="research-unit-stack">
          {displayedCells.map((cell, index) => (
            <ResearchUnit
              key={cell.cell_key}
              cell={cell}
              judgment={judgmentsByCell.get(cell.cell_key)}
              index={index}
              expanded={expandedCellKey === cell.cell_key}
              locale={locale}
              copy={copy}
              labelToken={labelToken}
              localizeFixtureText={localizeFixtureText}
              onToggle={() => onToggleCell(cell.cell_key)}
              onOpenEvidence={onOpenEvidence}
            />
          ))}
        </div>
      </section>

      <section className="research-next-action" aria-label={copy("建议下一步", "Suggested next step")}>
        <div className="research-next-icon"><ArrowRight size={18} aria-hidden="true" /></div>
        <div>
          <p className="p02-eyebrow">{copy("下一步", "Next step")}</p>
          <h2>{nextCell ? copy(`补强「${labelToken(nextCell.cell.evidence_role)}」并完成 Senior R2 复核`, `Strengthen “${labelToken(nextCell.cell.evidence_role)}” and complete senior R2`) : copy("进入 Senior R2 复核", "Proceed to senior R2 review")}</h2>
          <p>{nextCell?.judgment?.remaining_gaps[0] ? localizeFixtureText(nextCell.judgment.remaining_gaps[0]) : copy("当前精确事实和候选证据已就绪，下一步应验证判断边界，而不是继续扩张研究范围。", "Exact facts and candidate evidence are ready. Validate judgment limits next instead of expanding scope.")}</p>
        </div>
        <button type="button" className="p02-primary-button" onClick={onOpenEvidence}>
          <FileSearch size={16} aria-hidden="true" />
          {copy("进入证据工作台", "Open evidence workbench")}
        </button>
      </section>

      <p className="research-chain-boundary">{localizeFixtureText(analysis.boundary)}</p>
    </div>
  );
}

function Metric({ label, value, detail, emphasis = false }: { label: string; value: string; detail: string; emphasis?: boolean }) {
  return <div className={emphasis ? "has-emphasis" : undefined}><dt>{label}</dt><dd>{value}</dd><small>{detail}</small></div>;
}

function ResearchUnit({
  cell,
  judgment,
  index,
  expanded,
  locale,
  copy,
  labelToken,
  localizeFixtureText,
  onToggle,
  onOpenEvidence,
}: {
  cell: LocalResearchCellView;
  judgment?: LocalAnalysisJudgmentView;
  index: number;
  expanded: boolean;
  locale: "zh-CN" | "en";
  copy: Copy;
  labelToken: (value: string) => string;
  localizeFixtureText: (value: string) => string;
  onToggle: () => void;
  onOpenEvidence: () => void;
}) {
  const hasBoundary = cell.status === "typed_gap" || Boolean(judgment?.remaining_gaps.length);
  const confidence = judgment?.confidence ?? "pending";

  return (
    <article className={`research-unit ${expanded ? "is-expanded" : ""}`}>
      <button type="button" className="research-unit-header" aria-expanded={expanded} onClick={onToggle}>
        <span className={`research-unit-index is-${confidence}`} aria-hidden="true">
          {confidence === "high" ? <CheckCircle2 size={18} /> : confidence === "low" ? <CircleAlert size={18} /> : <CircleDot size={18} />}
          <small>{String(index + 1).padStart(2, "0")}</small>
        </span>
        <span className="research-unit-title">
          <strong>{labelToken(cell.evidence_role)}</strong>
          <span>{judgment ? judgmentText(judgment, locale) : localizeFixtureText(cell.decision_question)}</span>
        </span>
        <span className={`research-unit-state is-${confidence}`}>
          {copy(`${labelToken(confidence)}置信候选`, `${labelToken(confidence)} confidence candidate`)}
        </span>
        <span className="research-unit-count">{copy(`${cell.candidates.length} 条证据`, `${cell.candidates.length} evidence`)}</span>
        {expanded ? <ChevronUp size={17} aria-hidden="true" /> : <ChevronDown size={17} aria-hidden="true" />}
      </button>

      {expanded ? (
        <div className="research-unit-body">
          <div className="research-unit-question">
            <span>{copy("决策问题", "Decision question")}</span>
            <p>{localizeFixtureText(cell.decision_question)}</p>
          </div>
          <div className="research-unit-argument-grid">
            <div>
              <span>{copy("当前判断", "Current judgment")}</span>
              <p>{judgment ? judgmentText(judgment, locale) : copy("尚未形成候选判断。", "No candidate judgment yet.")}</p>
            </div>
            <div>
              <span>{copy("反证与边界", "Counterevidence and limits")}</span>
              <p>{judgment ? (locale === "zh-CN" ? judgment.counter_thesis_zh_cn : judgment.what_would_change_en) : cell.typed_gap ?? copy("待复核。", "Pending review.")}</p>
            </div>
          </div>
          <div className="research-unit-evidence">
            <div className="research-unit-subheading">
              <span>{copy("优先候选证据", "Priority candidate evidence")}</span>
              {hasBoundary ? <em><ShieldAlert size={13} aria-hidden="true" />{copy("保留明确边界", "Explicit limit retained")}</em> : null}
            </div>
            <ol>
              {cell.candidates.slice(0, 2).map((candidate) => (
                <li key={candidate.candidate_id}>
                  <div>
                    <small>{candidate.source_name} · {candidate.published_at}</small>
                    <strong>{localizeFixtureText(candidate.title)}</strong>
                    <p>{localizeFixtureText(candidate.excerpt)}</p>
                  </div>
                  {candidate.citation_url ? (
                    <a href={candidate.citation_url} target="_blank" rel="noreferrer" title={copy("打开来源", "Open source")} aria-label={copy("打开来源", "Open source")}>
                      <ExternalLink size={15} aria-hidden="true" />
                    </a>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
          <footer>
            <p>{localizeFixtureText(judgment?.remaining_gaps[0] ?? cell.typed_gap ?? copy("没有记录新的结构化缺口，仍需 Senior R2 判断证据是否足够。", "No new typed gap is recorded; senior R2 must still judge evidence sufficiency."))}</p>
            <button type="button" onClick={onOpenEvidence}>{copy("查看完整证据", "Open full evidence")}<ArrowRight size={14} aria-hidden="true" /></button>
          </footer>
        </div>
      ) : null}
    </article>
  );
}

function PlanningFallback({
  surfaceRemote,
  surface,
  compileRemote,
  online,
  copy,
  labelToken,
  localizeFixtureText,
  onRetry,
  onCompile,
  onOpenDecisionSurface,
}: {
  surfaceRemote: RemoteResult<DecisionSurfaceView>;
  surface: DecisionSurfaceView | null;
  compileRemote: MutationResult;
  online: boolean;
  copy: Copy;
  labelToken: (value: string) => string;
  localizeFixtureText: (value: string) => string;
  onRetry: () => void;
  onCompile: () => void;
  onOpenDecisionSurface: () => void;
}) {
  return (
    <section className="p02-plan-section" aria-labelledby="p02-plan-heading">
      <div className="p02-section-heading">
        <div><p className="p02-eyebrow">{copy("研究计划", "Research plan")}</p><h2 id="p02-plan-heading">{copy("研究问题", "Research questions")}</h2></div>
        {surface ? <button type="button" className="p02-secondary-button" onClick={onOpenDecisionSurface}><ExternalLink size={16} aria-hidden="true" />{copy("查看研究单元", "Open research cells")}</button> : null}
      </div>

      {surfaceRemote.kind === "loading" ? <RemoteStatus kind="loading" message={copy("正在加载研究计划。", "Loading research plan.")} /> : null}
      {surfaceRemote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={surfaceRemote.message} /> : null}
      {isFailure(surfaceRemote) ? <RemoteStatus kind={surfaceRemote.kind} message={surfaceRemote.message} onRetry={onRetry} /> : null}

      {surfaceRemote.kind === "empty" ? (
        <div className="p02-empty-panel">
          <div><h3>{copy("暂无研究单元", "No research cells")}</h3><p>{copy("当前研究尚未生成研究单元。", "This research case has not prepared research cells yet.")}</p></div>
          <button type="button" className="p02-primary-button" disabled={!online || compileRemote.kind === "loading"} onClick={onCompile}>
            <Braces size={16} aria-hidden="true" />{compileRemote.kind === "loading" ? copy("正在生成", "Preparing") : copy("生成研究单元", "Prepare research cells")}
          </button>
        </div>
      ) : null}

      {surface ? (
        <div className="p02-cell-list" aria-label={copy("研究单元", "Research cells")}>
          {surface.cells.map((cell, index) => (
            <article className="p02-cell" key={cell.cell_id}>
              <header className="p02-cell-header">
                <div className="p02-cell-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</div>
                <div className="p02-cell-title"><h2>{localizeFixtureText(cell.decision_question)}</h2><div className="p02-cell-kicker"><span>{labelToken(cell.owner)}</span><span>{copy(`${cell.evidence_slots.filter((slot) => slot.required).length} 个必需证据槽`, `${cell.evidence_slots.filter((slot) => slot.required).length} required evidence slots`)}</span></div></div>
              </header>
            </article>
          ))}
        </div>
      ) : null}

      {compileRemote.kind === "offline" ? <RemoteStatus kind="reconnecting" message={compileRemote.message} /> : null}
      {isMutationFailure(compileRemote) ? <RemoteStatus kind={compileRemote.kind} message={compileRemote.message} onRetry={onCompile} /> : null}
    </section>
  );
}

function judgmentText(judgment: LocalAnalysisJudgmentView, locale: "zh-CN" | "en"): string {
  return locale === "zh-CN" ? judgment.judgment_zh_cn : judgment.judgment_en;
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function compactMetric(value: string, unit: string, locale: "zh-CN" | "en"): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return `${value} ${unit}`;
  if (unit === "USD") {
    return new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
      style: "currency",
      currency: "USD",
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(numeric);
  }
  return new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", { notation: "compact", maximumFractionDigits: 1 }).format(numeric);
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

function isFailure<T>(remote: RemoteResult<T>): remote is Extract<RemoteResult<T>, FailureResult> {
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
