import { Client } from "@langchain/langgraph-sdk";

export type Event = {
  kind: "stage" | "model" | "tool" | "task";
  actor: string;
  event: string;
  call_id?: string;
  status?: string;
  error_type?: string;
  tool?: string;
  model?: string;
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  cache_hit_tokens?: number;
  reasoning_tokens?: number;
  elapsed_ms?: number;
  recorded_at?: string;
  run_id?: string;
  task_id?: string;
  objective?: string;
  dependency_ids?: string[];
  correction_round?: number;
  paper_id?: string;
  responsible_paper_ids?: string[];
};
export type Source = {
  source_id: string;
  title?: string;
  source_url?: string;
  citation_urls?: string[];
  ticker?: string;
  metric_id?: string;
  period_end?: string;
  numeric_fact_authority?: boolean;
  result_state?: string;
  authority_note?: string;
  text?: string;
  value_decimal?: string;
  unit?: string;
  next_offset?: number;
  notice?: string;
  arithmetic_verified?: boolean;
  financial_semantics_verified?: boolean;
  calculation?: {
    expression: string;
    value_decimal?: string;
    result_unit?: string;
    rationale?: string;
    arithmetic_verified?: boolean;
    financial_semantics_verified?: boolean;
    operand_source_aliases?: Record<string, string>;
    operands: Record<string, { source_id?: string; value_decimal?: string; unit?: string;
      ticker?: string; metric_id?: string; period_start?: string; period_end?: string; authority?: string;
      quote?: string; literal?: string; source_provenance?: { ticker?: string; fiscal_period?: string; unit?: string } }>;
  };
};
export type ExecutionOptions = { mode: "standard" | "auto" | "selected" | "single"; model: "default" | "deepseek-v4-flash" | "deepseek-v4-pro"; branch_ids: string[] };
export const defaultExecution: ExecutionOptions = { mode: "auto", model: "default", branch_ids: [] };
export type Citation = {
  claim: {
    statement: string;
    kind: string;
    citation_quotes?: Record<string, string | string[]>;
  };
  sources: Source[];
};
export type Finding = {
  finding_id: string;
  severity: string;
  report_quote: string;
  diagnosis: string;
  requested_change: string;
  responsibility?: "writer" | "research" | "data_tool" | "human";
  paper_ids?: string[];
};
export type Session = {
  execution?: ExecutionOptions;
  can_upload?: boolean;
  report_digest?: string;
  cumulative_usage?: { native_runs: number; known_cny: number; recorded_requests: number; reported_requests: number;
    unknown_or_pending_requests: number; unpriced_requests: number; input_tokens: number; output_tokens: number;
    total_tokens: number; cache_hit_tokens: number; cache_miss_tokens: number; unknown_cache_requests: number; unknown_elapsed_requests: number;
    elapsed_ms: number; missing_audit_runs: number; partial_audit: boolean; notice: string };
  is_draft?: boolean;
  attachments?: { document_id: string; name: string; kind: string; bytes: number; sections: number; needs_vision: boolean }[];
  thread_id: string;
  title: string;
  status: string;
  updated_at?: string;
  phase?: string;
  question?: string;
  case_profile?: string;
  research_as_of?: string;
  snapshot_id?: string;
  research_stop_reason?: string;
  research_synthesis?: { title?: string; narrative_markdown?: string };
  synthesis_review?: { summary: string; findings: Finding[]; unresolved_data_requests: string[] };
  workpaper_reviews?: { actor: string; summary: string; findings: {
    finding_id: string; paper_id: string; severity: string; problematic_quote: string;
    diagnosis: string; requested_change: string;
  }[] }[];
  responsibility_history?: { actor: string; correction_round: number }[];
  research_tasks?: { task_id: string; owner_role?: string; objective: string; dependency_ids: string[]; status: string }[];
  report_version?: number;
  can_respond?: boolean;
  can_accept?: boolean;
  can_abandon_question?: boolean;
  can_continue_remaining?: boolean;
  research_attempt_history?: { run_id: string | null; phase: string; outcomes: { task_id: string; status: string }[] }[];
  research_guidance?: { message: string; created_at: string }[];
  report?: {
    charts?: { title: string; interpretation: string; unit: string; points: { label: string; series: string; value: number; source_id: string; provenance: unknown }[] }[];
    title: string;
    narrative_markdown: string;
    citations: Record<string, Citation>;
  };
  report_review?: {
    summary: string;
    findings: Finding[];
    unresolved_data_requests: string[];
  };
  conversation?: {
    role: string;
    content: string;
    citations?: Record<string, Citation>;
  }[];
  model_events?: Event[];
  runs?: { run_id: string; status: string; created_at: string; human_action?: string; request_message?: string; answer_mode?: string; execution?: ExecutionOptions; elapsed_ms?: number; model_calls_requested?: number; revision_target?: RevisionTarget;
    cost_estimate?: { known_cny: number; priced_requests: number; unknown_or_pending_requests: number; price_as_of: string; notice: string };
    usage?: { recorded_requests: number; reported_requests: number; unknown_or_pending_requests: number;
      input_tokens: number; output_tokens: number; total_tokens: number; cache_hit_tokens?: number; cache_miss_tokens?: number;
      unknown_cache_requests?: number; elapsed_ms?: number; partial_audit: boolean } | null }[];
};
export type ResearchConfiguration = {
  branch_topics?: { branch_id: string; objective: string }[];
  fresh_research_enabled: boolean;
  legacy_review_enabled?: boolean;
  title?: string;
  default_question?: string;
  research_as_of?: string;
  notice?: string;
  cost_expectation_cny?: { rough_low: number; rough_high: number };
};

const base = "/api/v1/research-sessions";
export type ReportVersion = { version: number; checkpoint_id: string; created_at?: string; title: string; reason: string };
export type RevisionTarget = { request_id: string; citation_id: string; base_version: number; base_digest: string; base_checkpoint: string };
export type ReportSnapshot = { report: NonNullable<Session["report"]>; report_version: number; checkpoint_id: string; reason?: string; report_digest?: string };
export type ReportDiff = { before_version: number; after_version: number; reason: string; diff: string; charts_changed: boolean; citations_changed: boolean };
async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", "X-Workbench-Request": "1" },
    method: body === undefined ? "GET" : "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : `请求未完成 (${response.status})`,
    );
  return result as T;
}
export const sessionsApi = {
  config: () => request<ResearchConfiguration>("/api/v1/research-session-config"),
  list: () => request<Session[]>(base),
  create: (body: { mode?: "review" | "research"; title?: string; question?: string; defer_start?: boolean; studio_assistant_id?:string; execution?: ExecutionOptions } = {}) =>
    request<{ thread_id: string; run_id: string | null }>(base, body),
  start: (id: string) => request<{ run_id: string }>(`${base}/${id}/start`, {}),
  guidance: (id: string, message: string) => request(`${base}/${id}/guidance`, { message }),
  acknowledgeIncomplete: (id: string) => request(`${base}/${id}/acknowledge-incomplete`, {}),
  continueRemaining: (id: string) => request(`${base}/${id}/continue-remaining`, {}),
  upload: async (id: string, file: File) => {
    const response = await fetch(`${base}/${id}/attachments`, { method: "POST", body: file,
      headers: { "X-Workbench-Request": "1", "X-Filename": encodeURIComponent(file.name), "Content-Type": "application/octet-stream" } });
    const value = await response.json();
    if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : "资料上传失败，研究尚未开始");
    return value;
  },
  state: (id: string) => request<Session>(`${base}/${id}`),
  versions: (id: string, before?: string) => request<{ versions: ReportVersion[]; next_cursor: string | null }>(`${base}/${id}/report-versions${before ? `?before=${encodeURIComponent(before)}` : ""}`),
  version: (id: string, checkpoint: string) => request<ReportSnapshot>(`${base}/${id}/report-versions/${encodeURIComponent(checkpoint)}`),
  diff: (id: string, before: string) => request<ReportDiff>(`${base}/${id}/report-diff?before=${encodeURIComponent(before)}`),
  action: (id: string, action: string, message: string, answerMode: "quick" | "deep" = "deep", target?: RevisionTarget, execution?: ExecutionOptions) =>
    request<{ run_id: string }>(`${base}/${id}/actions`, { action, message, answer_mode: answerMode, ...(target ? { target } : {}), ...(execution ? { execution } : {}) }),
  cancel: (id: string, run: string) =>
    request(`${base}/${id}/runs/${run}/cancel`, {}),
  abandonQuestion: (id: string) =>
    request<{ run_id: string }>(`${base}/${id}/abandon-question`, {}),
  source: (id: string, source: string, offset = 0, checkpoint?: string) =>
    request<Source>(
      `${base}/${id}/source?source_id=${encodeURIComponent(source)}&offset=${offset}${checkpoint ? `&checkpoint_id=${encodeURIComponent(checkpoint)}` : ""}`,
    ),
};
// Official stream client; mutations use the narrow BFF, never arbitrary native inputs.
export const streamClient = new Client({
  apiUrl: `${window.location.origin}/api/v1/agent`,
});
