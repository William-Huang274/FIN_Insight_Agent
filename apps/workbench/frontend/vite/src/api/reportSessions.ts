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
};
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
  runs?: { run_id: string; status: string; created_at: string; human_action?: string; answer_mode?: string;
    cost_estimate?: { known_cny: number; priced_requests: number; unknown_or_pending_requests: number; price_as_of: string; notice: string };
    usage?: { recorded_requests: number; reported_requests: number; unknown_or_pending_requests: number;
      input_tokens: number; output_tokens: number; total_tokens: number; partial_audit: boolean } | null }[];
};
export type ResearchConfiguration = {
  fresh_research_enabled: boolean;
  title?: string;
  default_question?: string;
  research_as_of?: string;
  notice?: string;
  cost_expectation_cny?: { rough_low: number; rough_high: number };
};

const base = "/api/v1/research-sessions";
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
  create: (body: { mode?: "review" | "research"; title?: string; question?: string; defer_start?: boolean } = {}) =>
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
  action: (id: string, action: string, message: string, answerMode: "quick" | "deep" = "deep") =>
    request<{ run_id: string }>(`${base}/${id}/actions`, { action, message, answer_mode: answerMode }),
  cancel: (id: string, run: string) =>
    request(`${base}/${id}/runs/${run}/cancel`, {}),
  abandonQuestion: (id: string) =>
    request<{ run_id: string }>(`${base}/${id}/abandon-question`, {}),
  source: (id: string, source: string, offset = 0) =>
    request<Source>(
      `${base}/${id}/source?source_id=${encodeURIComponent(source)}&offset=${offset}`,
    ),
};
// Official stream client; mutations use the narrow BFF, never arbitrary native inputs.
export const streamClient = new Client({
  apiUrl: `${window.location.origin}/api/v1/agent`,
});
