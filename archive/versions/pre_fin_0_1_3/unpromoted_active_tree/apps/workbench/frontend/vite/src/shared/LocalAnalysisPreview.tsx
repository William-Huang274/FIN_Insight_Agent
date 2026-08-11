import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Calculator,
  CheckCircle2,
  ClipboardCheck,
  Database,
  ExternalLink,
  FileText,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";

import {
  EvidenceApiClient,
  LocalAnalysisJudgmentView,
  LocalAnalysisPreviewView,
  LocalResearchCandidateView,
  LocalResearchPreviewView,
} from "../api/evidence";
import { useWorkbenchLocale } from "../i18n/WorkbenchLocale";
import { RemoteStatus } from "./RemoteStatus";

type LocalAnalysisPreviewProps = {
  caseId: string;
  online: boolean;
  view: "numeric" | "workpaper" | "writer";
};

type Copy = (zhCN: string, en: string) => string;

const api = new EvidenceApiClient();

const WHAT_WOULD_CHANGE_ZH: Record<string, string> = {
  demand_signal: "后续多个季度的订单、发货、利用率与客户部署数据在同一口径下继续支持需求增长，且预测偏差没有扩大。",
  revenue_capture: "分部口径的收入、毛利和现金流能够与 AI 基础设施业务直接勾稽，并在多个报告期保持一致。",
  thesis_counterevidence: "代工、存储和设备约束出现可核验的产能、交期、利用率或价格证据，并能证明其对收入或利润形成因果影响。",
  server_oem_orders: "同一 AI 服务器口径下的订单、积压、发货和收入定义能够逐项勾稽。",
  server_oem_margin_cash: "同一期间的 AI 服务器收入、毛利、库存和经营现金流能够按一致定义核对。",
  advanced_packaging_capacity: "晶圆厂官方披露的产能、利用率、分配、交期与价格在同一期间共同证明先进封装约束。",
  hbm_supply_pricing: "HBM 位元供给、合同价格、产能爬坡和客户组合在多个期间共同支持紧张度与利润持续性。",
  semicap_capex_cycle: "主要设备厂商的当期订单、积压、利用率、区域结构和客户资本开支信号方向一致。",
  export_policy_risk: "适用的官方规则、生效日期、产品阈值、许可结果和受影响收入可以在同一口径下核验。",
  customer_concentration: "后续披露中的直接客户比例、终端客户归属、采购时点和续购行为保持一致。",
};

export function LocalAnalysisPreview({ caseId, online, view }: LocalAnalysisPreviewProps) {
  const { copy, locale, labelToken } = useWorkbenchLocale();
  const [analysis, setAnalysis] = useState<LocalAnalysisPreviewView | null>(null);
  const [research, setResearch] = useState<LocalResearchPreviewView | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "offline" | "error">("loading");

  const load = useCallback(async () => {
    if (!online || !navigator.onLine) {
      setState("offline");
      return;
    }
    setState("loading");
    try {
      const [nextAnalysis, nextResearch] = await Promise.all([
        api.getLocalAnalysisPreview(caseId),
        api.getLocalResearchPreview(caseId),
      ]);
      setAnalysis(nextAnalysis);
      setResearch(nextResearch);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [caseId, online]);

  useEffect(() => {
    void load();
  }, [load]);

  const candidateById = useMemo(() => {
    const map = new Map<string, LocalResearchCandidateView>();
    research?.cells.forEach((cell) => cell.candidates.forEach((candidate) => map.set(candidate.candidate_id, candidate)));
    return map;
  }, [research]);

  if (state === "loading") {
    return <RemoteStatus kind="loading" message={copy("正在组装真实候选、数字、判断和结论。", "Assembling real candidates, numbers, judgments, and conclusions.")} />;
  }
  if (state === "offline") {
    return <RemoteStatus kind="reconnecting" message={copy("连接不可用，真实候选分析暂不可读。", "Connection is unavailable; real-candidate analysis cannot be read.")} onRetry={() => void load()} />;
  }
  if (state === "error" || !analysis || !research) {
    return <RemoteStatus kind="error" message={copy("真实候选分析预览不可用；夹具链仍可独立使用。", "The real-candidate analysis preview is unavailable; the fixture path remains independent.")} onRetry={() => void load()} />;
  }

  const title = {
    numeric: copy("真实数值分析", "Real numeric analysis"),
    workpaper: copy("真实候选研究底稿", "Real-candidate workpaper"),
    writer: copy("无来源 Writer 初稿", "No-source Writer draft"),
  }[view];
  const Icon = view === "numeric" ? Calculator : view === "workpaper" ? ClipboardCheck : FileText;
  const gaps = unique(analysis.judgments.flatMap((judgment) => judgment.remaining_gaps).filter(Boolean));
  const exactFactCount = analysis.numeric.facts.filter((fact) => fact.exact_value_authority).length;

  return (
    <section className={`p36-analysis-preview p36-analysis-${view}`} aria-labelledby={`p36-${view}-preview-heading`}>
      <div className="p36-analysis-heading">
        <div>
          <p className="p02-eyebrow">{copy("受限真实研究链", "Bounded real research path")}</p>
          <h2 id={`p36-${view}-preview-heading`}><Icon size={19} aria-hidden="true" /> {title}</h2>
          <p>{copy("已把真实候选、精确数字、反证、修复和剩余缺口联结为同一份可复核视图；当前仍等待 Senior R2。", "Real candidates, exact numbers, counterevidence, repairs, and remaining gaps are joined into one reviewable view; Senior R2 remains pending.")}</p>
        </div>
        <button type="button" className="p02-icon-button" title={copy("刷新真实分析", "Refresh real analysis")} aria-label={copy("刷新真实分析", "Refresh real analysis")} onClick={() => void load()}>
          <RefreshCcw size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="p36-analysis-boundary">
        <ShieldCheck size={17} aria-hidden="true" />
        <span>{copy("只读联结视图：无网络、无模型调用、无 Case 写入、无证据晋升；Reviewer 可查看来源，但 Writer 仍不读取来源。", "Read-only joined view: no network or model calls, Case writes, or evidence promotion. Reviewers can inspect sources, while Writer still does not access them.")}</span>
      </div>

      <dl className="p36-research-summary-strip">
        <div><dt>{copy("研究单元", "Research cells")}</dt><dd>{analysis.judgments.length}</dd></div>
        <div><dt>{copy("候选证据", "Candidates")}</dt><dd>{research.candidate_count}</dd></div>
        <div><dt>{copy("精确事实", "Exact facts")}</dt><dd>{exactFactCount}</dd></div>
        <div><dt>{copy("待复核边界", "Review gaps")}</dt><dd>{gaps.length}</dd></div>
      </dl>

      {view === "numeric" ? <NumericDocument analysis={analysis} copy={copy} locale={locale} /> : null}
      {view === "workpaper" ? (
        <WorkpaperDocument
          analysis={analysis}
          candidateById={candidateById}
          copy={copy}
          locale={locale}
          labelToken={labelToken}
        />
      ) : null}
      {view === "writer" ? (
        <WriterDocument
          analysis={analysis}
          candidateById={candidateById}
          copy={copy}
          locale={locale}
          labelToken={labelToken}
        />
      ) : null}

      <footer className="p36-analysis-footer">
        <span>{copy("分析摘要", "Analysis digest")}: <code>{analysis.analysis_digest.slice(0, 16)}</code></span>
        <span>{copy("底稿状态", "Workpaper status")}: {copy("等待 Senior R2", "Awaiting Senior R2")}</span>
      </footer>
    </section>
  );
}

function NumericDocument({ analysis, copy, locale }: { analysis: LocalAnalysisPreviewView; copy: Copy; locale: string }) {
  return (
    <div className="p36-numeric-grid">
      {analysis.numeric.derived_metrics.map((metric) => (
        <article key={metric.metric}>
          <span>{metric.metric === "gross_margin" ? copy("毛利率", "Gross margin") : copy("营业利润率", "Operating margin")}</span>
          <strong>{metric.value}%</strong>
          <code>{metric.formula}</code>
        </article>
      ))}
      {analysis.numeric.facts.map((fact) => (
        <article key={fact.candidate_id}>
          <span>{metricLabel(fact.metric_family, copy)}</span>
          <strong>{formatUsd(fact.value, locale)}</strong>
          <small>{fact.period} · {fact.unit}</small>
        </article>
      ))}
    </div>
  );
}

function WorkpaperDocument({ analysis, candidateById, copy, locale, labelToken }: {
  analysis: LocalAnalysisPreviewView;
  candidateById: Map<string, LocalResearchCandidateView>;
  copy: Copy;
  locale: string;
  labelToken: (value: string) => string;
}) {
  return (
    <article className="p36-workpaper-document">
      <header className="p36-document-header">
        <div>
          <span>{copy("内部研究底稿", "Internal research workpaper")}</span>
          <h3>{copy("P36 AI 基础设施需求、利润捕获与反证", "P36 AI infrastructure demand, profit capture, and counterevidence")}</h3>
          <p>{copy("每个研究单元同时保留研究问题、当前判断、证据基础、反证、修复结果、可改变判断的条件和剩余缺口。", "Each research unit preserves the question, current judgment, evidence basis, counterevidence, repair outcome, what would change, and remaining gaps.")}</p>
        </div>
        <code>{analysis.workpaper.content_digest.slice(0, 16)}</code>
      </header>

      <div className="p36-workpaper-sections">
        {analysis.judgments.map((judgment, index) => {
          const candidates = judgment.evidence_refs.map((ref) => candidateById.get(ref)).filter(isCandidate);
          const repair = analysis.repairs.find((item) => item.repair_id === judgment.repair_ref);
          return (
            <details key={judgment.judgment_id} className="p36-workpaper-section" open={index < 2}>
              <summary>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><strong>{labelToken(judgment.evidence_role)}</strong><small>{judgment.decision_question}</small></div>
                <em>{labelToken(judgment.confidence)}</em>
              </summary>
              <div className="p36-workpaper-body">
                <section className="p36-thesis-block">
                  <p className="p02-eyebrow">{copy("当前判断", "Current judgment")}</p>
                  <h4>{locale === "zh-CN" ? judgment.judgment_zh_cn : judgment.judgment_en}</h4>
                </section>

                <section className="p36-evidence-basis">
                  <div className="p36-subsection-heading"><Database size={16} /><h4>{copy("证据基础", "Evidence basis")}</h4><span>{candidates.length} {copy("条候选", "candidates")}</span></div>
                  <EvidenceRows candidates={candidates} copy={copy} />
                </section>

                {judgment.numeric_refs.length ? <NumericLineage analysis={analysis} copy={copy} locale={locale} /> : null}

                <div className="p36-reasoning-grid">
                  <section><p className="p02-eyebrow">{copy("反证与边界", "Counterevidence and boundary")}</p><p>{judgment.counter_thesis_zh_cn}</p></section>
                  <section><p className="p02-eyebrow">{copy("什么会改变判断", "What would change")}</p><p>{locale === "zh-CN" ? WHAT_WOULD_CHANGE_ZH[judgment.evidence_role] : judgment.what_would_change_en}</p></section>
                  <section><p className="p02-eyebrow">{copy("修复决定", "Repair decision")}</p><p>{repair ? repairLabel(repair.decision, copy) : copy("未记录", "Not recorded")}</p>{repair ? <small>{repair.reason}</small> : null}</section>
                  <section className="is-gap"><p className="p02-eyebrow">{copy("剩余缺口", "Remaining gap")}</p>{judgment.remaining_gaps.map((gap) => <p key={gap}>{gap}</p>)}</section>
                </div>
              </div>
            </details>
          );
        })}
      </div>
    </article>
  );
}

function WriterDocument({ analysis, candidateById, copy, locale, labelToken }: {
  analysis: LocalAnalysisPreviewView;
  candidateById: Map<string, LocalResearchCandidateView>;
  copy: Copy;
  locale: string;
  labelToken: (value: string) => string;
}) {
  const demand = analysis.judgments.find((item) => item.evidence_role === "demand_signal");
  const capture = analysis.judgments.find((item) => item.evidence_role === "revenue_capture");
  const counter = analysis.judgments.find((item) => item.evidence_role === "thesis_counterevidence");
  return (
    <article className="p36-writer-document">
      <header className="p36-document-header">
        <div><span>{copy("内部初稿", "Internal draft")}</span><h3>{locale === "zh-CN" ? analysis.writer.title_zh_cn : analysis.writer.title_en}</h3><p>{copy("面向 Senior R2 的研究初稿，不是发布版本。", "Research draft for Senior R2, not a release version.")}</p></div>
        <code>source_access_calls:{analysis.writer.source_access_calls}</code>
      </header>

      <section className="p36-executive-summary">
        <p className="p02-eyebrow">{copy("执行摘要", "Executive summary")}</p>
        <h4>{copy("需求转化已经出现，但利润持续性仍取决于价值归属、供给约束与集中度能否被进一步证实。", "Demand conversion is visible, while profit durability still depends on proving value capture, supply constraints, and concentration.")}</h4>
        <div>
          {demand ? <p><strong>{copy("需求", "Demand")}</strong>{locale === "zh-CN" ? demand.judgment_zh_cn : demand.judgment_en}</p> : null}
          {capture ? <p><strong>{copy("利润", "Profit")}</strong>{locale === "zh-CN" ? capture.judgment_zh_cn : capture.judgment_en}</p> : null}
          {counter ? <p><strong>{copy("反证", "Counterevidence")}</strong>{locale === "zh-CN" ? counter.judgment_zh_cn : counter.judgment_en}</p> : null}
        </div>
      </section>

      <NumericLineage analysis={analysis} copy={copy} locale={locale} compact />

      <div className="p36-writer-sections">
        {analysis.writer.sections.map((section, index) => {
          const judgment = analysis.judgments.find((item) => item.judgment_id === section.judgment_ref);
          const candidates = judgment?.evidence_refs.map((ref) => candidateById.get(ref)).filter(isCandidate) ?? [];
          return (
            <section key={section.section_id} className="p36-writer-section">
              <header><span>{String(index + 1).padStart(2, "0")}</span><div><p className="p02-eyebrow">{labelToken(section.evidence_role)}</p><h4>{locale === "zh-CN" ? section.heading_zh_cn : labelToken(section.evidence_role)}</h4></div></header>
              <p className="p36-writer-copy">{locale === "zh-CN" ? section.content_zh_cn : section.content_en}</p>
              {judgment ? (
                <div className="p36-writer-review-notes">
                  <section><strong>{copy("主要依据", "Evidence basis")}</strong>{candidates.slice(0, 2).map((candidate) => <span key={candidate.candidate_id}>{candidate.title} · {candidate.published_at}</span>)}</section>
                  <section><strong>{copy("结论边界", "Conclusion boundary")}</strong><span>{judgment.counter_thesis_zh_cn}</span></section>
                  <section className="is-gap"><strong>{copy("待验证", "To verify")}</strong><span>{judgment.remaining_gaps[0]}</span></section>
                </div>
              ) : null}
            </section>
          );
        })}
      </div>

      <section className="p36-writer-boundary-note">
        <AlertTriangle size={18} />
        <div><strong>{copy("发布前仍需完成", "Required before release")}</strong><p>{copy("Senior R2 必须核验每个重要判断的来源、数字和修改点；当前先进封装、semicap 时效性和利润归因仍是显式弱项。", "Senior R2 must verify the sources, numbers, and modification point for every material judgment. Advanced packaging, semicap freshness, and profit attribution remain explicit weaknesses.")}</p></div>
      </section>
    </article>
  );
}

function EvidenceRows({ candidates, copy }: { candidates: LocalResearchCandidateView[]; copy: Copy }) {
  if (!candidates.length) return <p className="p36-empty-copy">{copy("当前单元没有可展示的候选证据。", "No candidate evidence is available for this unit.")}</p>;
  return (
    <div className="p36-evidence-rows">
      {candidates.map((candidate) => (
        <article key={candidate.candidate_id}>
          <header><div><strong>{candidate.title}</strong><small>{candidate.ticker} · {candidate.source_type} · {candidate.published_at}</small></div><span>{candidate.source_name}</span></header>
          <p>{candidate.excerpt}</p>
          <footer><span><ShieldCheck size={13} />{candidate.claim_boundary}</span>{candidate.citation_url ? <a href={candidate.citation_url} target="_blank" rel="noreferrer" title={copy("打开原始来源", "Open original source")}><ExternalLink size={14} /></a> : null}</footer>
        </article>
      ))}
    </div>
  );
}

function NumericLineage({ analysis, copy, locale, compact = false }: { analysis: LocalAnalysisPreviewView; copy: Copy; locale: string; compact?: boolean }) {
  return (
    <section className={`p36-numeric-lineage ${compact ? "is-compact" : ""}`}>
      <div className="p36-subsection-heading"><Calculator size={16} /><h4>{copy("精确数字与复算", "Exact numbers and recalculation")}</h4><span><CheckCircle2 size={13} />{copy("可复算", "Reproducible")}</span></div>
      <div>
        {analysis.numeric.facts.map((fact) => <p key={fact.candidate_id}><span>{metricLabel(fact.metric_family, copy)}</span><strong>{formatUsd(fact.value, locale)}</strong><small>{fact.period}</small></p>)}
        {analysis.numeric.derived_metrics.map((metric) => <p key={metric.metric}><span>{metric.metric === "gross_margin" ? copy("毛利率", "Gross margin") : copy("营业利润率", "Operating margin")}</span><strong>{metric.value}%</strong><small>{metric.formula}</small></p>)}
      </div>
    </section>
  );
}

function metricLabel(metric: string, copy: Copy): string {
  if (metric === "revenue") return copy("收入", "Revenue");
  if (metric === "gross_profit") return copy("毛利润", "Gross profit");
  if (metric === "operating_income") return copy("营业利润", "Operating income");
  return metric;
}

function repairLabel(decision: string, copy: Copy): string {
  if (decision === "no_override") return copy("无需覆盖，保留来源边界", "No override; source boundary retained");
  return copy("已补充受限关系图背景，未晋升", "Bounded graph context attached without promotion");
}

function formatUsd(value: string, locale: string): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(numeric);
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function isCandidate(candidate: LocalResearchCandidateView | undefined): candidate is LocalResearchCandidateView {
  return Boolean(candidate);
}
