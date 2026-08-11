import { CASES_PATH, FixtureCaseContext } from "./cases";

export type HumanBaselineArtifactBinding = {
  case_id: string;
  case_version: number;
  research_preview_digest: string;
  analysis_digest: string;
  workpaper_digest: string;
  writer_digest: string;
  artifact_binding_digest: string;
};

export type AnalystBaselineSubmission = {
  strongest_source: string;
  material_limitation: string;
  numeric_verification: string;
  weakest_judgment: string;
  required_modification: string;
  writer_usefulness_score: number;
  writer_usefulness_reason: string;
  time_to_find_source_seconds: number;
  time_to_verify_numeric_seconds: number;
  time_to_identify_weakest_judgment_seconds: number;
  time_to_review_writer_seconds: number;
  repeated_work_count: number;
  blocking_ui_issue: string;
  idempotency_key: string;
};

export type SeniorReviewSubmission = {
  reviewer_ref: string;
  reviewer_role: "senior_analyst" | "domain_reviewer";
  decision: "approve" | "conditional_approve" | "return_for_follow_up";
  research_quality_score: number;
  evidence_quality_score: number;
  senior_reviewability_score: number;
  numeric_reproducibility_confirmed: boolean;
  gap_boundaries_preserved: boolean;
  exact_digest_confirmed: boolean;
  review_comment: string;
  bounded_follow_up: string[];
  idempotency_key: string;
};

export type HumanBaselineSession = {
  schema_version: string;
  session_id: string;
  case_id: string;
  participant_ref: string;
  status: "in_progress" | "analyst_submitted" | "exact_human_senior_review_recorded";
  artifact_binding: HumanBaselineArtifactBinding;
  artifact_binding_digest: string;
  analyst_submission: Omit<AnalystBaselineSubmission, "idempotency_key"> | null;
  senior_review: Omit<SeniorReviewSubmission, "idempotency_key"> | null;
  final_review_digest: string | null;
  started_at: string;
  analyst_submitted_at: string | null;
  senior_reviewed_at: string | null;
  updated_at: string;
  events: Array<{
    event_id: string;
    event_type: string;
    actor_ref: string;
    payload_digest: string;
    created_at: string;
  }>;
  execution_counts: Record<string, number>;
  boundary: string;
};

export type HumanBaselineSessionList = {
  schema_version: string;
  case_id: string;
  sessions: HumanBaselineSession[];
  counts: { session_count: number; completed_review_count: number };
  boundary: string;
};

export class HumanBaselineApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly detail: unknown;

  constructor(code: string, message: string, statusCode: number, detail?: unknown) {
    super(message);
    this.name = "HumanBaselineApiError";
    this.code = code;
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

const BASELINE_CONTEXT: FixtureCaseContext = {
  tenantId: "fixture_internal",
  projectId: "workbench_internal",
  actorId: "analyst_internal",
  permissions: [
    "case:read",
    "evidence:read",
    "baseline:read",
    "baseline:write",
    "baseline:review",
  ],
};

export class HumanBaselineApiClient {
  constructor(private readonly context: FixtureCaseContext = BASELINE_CONTEXT) {}

  list(caseId: string): Promise<HumanBaselineSessionList> {
    return this.request<HumanBaselineSessionList>(sessionsPath(caseId));
  }

  start(caseId: string, participantRef: string, idempotencyKey: string): Promise<HumanBaselineSession> {
    return this.request<HumanBaselineSession>(sessionsPath(caseId), {
      method: "POST",
      body: JSON.stringify({ participant_ref: participantRef, idempotency_key: idempotencyKey }),
    });
  }

  submitAnalyst(
    caseId: string,
    sessionId: string,
    submission: AnalystBaselineSubmission,
  ): Promise<HumanBaselineSession> {
    return this.request<HumanBaselineSession>(
      `${sessionsPath(caseId)}/${encodeURIComponent(sessionId)}/analyst-submission`,
      { method: "POST", body: JSON.stringify(submission) },
    );
  }

  submitSenior(
    caseId: string,
    sessionId: string,
    submission: SeniorReviewSubmission,
  ): Promise<HumanBaselineSession> {
    return this.request<HumanBaselineSession>(
      `${sessionsPath(caseId)}/${encodeURIComponent(sessionId)}/senior-review`,
      { method: "POST", body: JSON.stringify(submission) },
    );
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    headers.set("X-Fin-Case-Tenant", this.context.tenantId);
    headers.set("X-Fin-Case-Project", this.context.projectId);
    headers.set("X-Fin-Case-Actor", this.context.actorId);
    headers.set("X-Fin-Case-Permissions", this.context.permissions.join(","));
    let response: Response;
    try {
      response = await fetch(path, { ...init, headers });
    } catch (error) {
      throw new HumanBaselineApiError("network_unavailable", "Human baseline API is unavailable.", 0, error);
    }
    const text = await response.text();
    const payload = text ? JSON.parse(text) as Record<string, unknown> : {};
    if (!response.ok) {
      const detail = payload.detail as Record<string, unknown> | undefined;
      throw new HumanBaselineApiError(
        String(detail?.reason ?? `http_${response.status}`),
        String(detail?.reason ?? "Human baseline request failed."),
        response.status,
        detail,
      );
    }
    return payload as T;
  }
}

function sessionsPath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}/human-baseline/sessions`;
}
