import type { Citation, Source } from "../api/reportSessions";

// Shared legacy branch aliases; unknown/new branches keep a descriptive prefix.
export const branchName: Record<string, string> = { Q1: "收入、利润与现金", Q2: "客户需求质量", Q3: "量价与产品组合",
  Q4: "架构更新与交付", Q5: "供应链与成本", Q6: "模型与算力需求", Q7: "出口管制", Q8: "同行竞争", Q9: "反证与替代解释" };

/** Display aliases only. Canonical identifiers remain intact for all requests. */
export const claimTitle = (id: string, citations: Record<string, Citation>) =>
  citations[id]?.claim.statement?.trim() || `研究判断（引用编号 ${id}）`;
export const claimLabel = (id: string, citations: Record<string, Citation>) =>
  `研究判断：${claimTitle(id, citations)}`;
export const sourceKind = (source: Source) => ({
  source_bound_passage: "原文摘录", reviewed_evidence: "已审阅资料", numeric_fact: "财务数据",
  non_authoritative_metric: "来源绑定计算", typed_gap: "数据边界记录",
} as Record<string, string>)[source.result_state || ""] || "研究来源";
export const sourceTitle = (source: Source) =>
  source.title && source.title !== source.source_id ? source.title : source.ticker || source.metric_id ? [source.ticker, source.metric_id, source.period_end].filter(Boolean).join(" · ") : `${sourceKind(source)}（来源编号 ${source.source_id}）`;
