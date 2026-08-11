import { CASES_PATH, FixtureCaseContext } from "./cases";

export type CompileNumericFixtureCommand = {
  expected_evidence_workspace_version: number;
  actor_ref: string;
  idempotency_key: string;
};

export type NumericFactView = {
  cell_id: string;
  evidence_slot_id: string;
  candidate_id: string;
  parser_candidate_id: string;
  normalized_fact_id: string;
  numeric_trace_id: string;
  promotion_decision_id: string;
  entity_ref: string;
  period: string;
  row_label: string;
  normalized_value: string;
  output_value: string;
  unit: string;
  scale_multiplier: number;
  source_coordinate: string;
  metric_definition_ref: string;
  program_steps: string[];
  promotion_status: string;
  promotion_scope: string;
  writer_citable: boolean;
  boundary: string;
};

export type NumericWorkbenchView = {
  case_id: string;
  numeric_workspace_id: string;
  numeric_workspace_version: number;
  evidence_workspace_id: string;
  evidence_workspace_version: number;
  status: string;
  facts: NumericFactView[];
  counts: Record<string, number>;
  hard_boundaries: Record<string, number | string>;
};

export type CompileWorkpaperFixtureCommand = {
  expected_numeric_workspace_version: number;
  actor_ref: string;
  idempotency_key: string;
};

export type WorkpaperJudgmentView = {
  judgment_id: string;
  cell_id: string;
  evidence_role: string;
  decision_question: string;
  owner_role: string;
  judgment_status: string;
  confidence: string;
  judgment: string;
  evidence_refs: string[];
  numeric_refs: string[];
  repair_outcome_refs: string[];
  counter_thesis: string;
  what_would_change: string;
  remaining_gaps: string[];
};

export type LeadReviewDecision = "admit_fixture_writer_preview" | "return_for_repair";

export type LeadReviewView = {
  lead_review_id: string;
  workpaper_version: number;
  content_digest: string;
  decision: LeadReviewDecision;
  reason: string;
  actor_ref: string;
  reviewed_at: string;
};

export type WriterAdmissionView = {
  writer_admission_id: string;
  status: string;
  scope: string;
  fixture_only: boolean;
  writer_execution_authorized: boolean;
  boundary: string;
  admitted_at: string;
};

export type WorkpaperView = {
  case_id: string;
  workpaper_id: string;
  workpaper_version: number;
  content_digest: string;
  status: string;
  evidence_workspace_id: string;
  evidence_workspace_version: number;
  numeric_workspace_id: string;
  numeric_workspace_version: number;
  judgments: WorkpaperJudgmentView[];
  lead_review: LeadReviewView | null;
  writer_admission: WriterAdmissionView | null;
  hard_boundaries: Record<string, number | string>;
};

export type CompleteLeadReviewCommand = {
  expected_workpaper_version: number;
  expected_content_digest: string;
  decision: LeadReviewDecision;
  reason: string;
  actor_ref: string;
  idempotency_key: string;
};

type ErrorEnvelope = {
  error?: {
    error_code?: string;
    message?: string;
    status_code?: number;
    trace_id?: string;
  };
  code?: string;
  message?: string;
  correlation_id?: string;
  detail?: unknown;
};

export class IntegrityApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly traceId: string | undefined;
  readonly detail: unknown;

  constructor(input: { code: string; message: string; statusCode: number; traceId?: string; detail?: unknown }) {
    super(input.message);
    this.name = "IntegrityApiError";
    this.code = input.code;
    this.statusCode = input.statusCode;
    this.traceId = input.traceId;
    this.detail = input.detail;
  }
}

export const DEFAULT_FIXTURE_INTEGRITY_CONTEXT: FixtureCaseContext = {
  tenantId: "fixture_internal",
  projectId: "workbench_internal",
  actorId: "analyst_internal",
  permissions: [
    "evidence:read",
    "numeric:read",
    "numeric:write",
    "workpaper:read",
    "workpaper:write",
    "lead_review:decide",
  ],
};

export class IntegrityApiClient {
  constructor(private readonly context: FixtureCaseContext = DEFAULT_FIXTURE_INTEGRITY_CONTEXT) {}

  get actorRef(): string {
    return this.context.actorId;
  }

  getNumericWorkbench(caseId: string): Promise<NumericWorkbenchView> {
    return this.request<NumericWorkbenchView>(numericPath(caseId));
  }

  compileNumericFixture(caseId: string, command: CompileNumericFixtureCommand): Promise<NumericWorkbenchView> {
    return this.request<NumericWorkbenchView>(`${numericPath(caseId)}/compile`, mutationInit(command));
  }

  getWorkpaper(caseId: string): Promise<WorkpaperView> {
    return this.request<WorkpaperView>(workpaperPath(caseId));
  }

  compileWorkpaperFixture(caseId: string, command: CompileWorkpaperFixtureCommand): Promise<WorkpaperView> {
    return this.request<WorkpaperView>(`${workpaperPath(caseId)}/compile`, mutationInit(command));
  }

  completeLeadReview(caseId: string, command: CompleteLeadReviewCommand): Promise<WorkpaperView> {
    return this.request<WorkpaperView>(`${workpaperPath(caseId)}/lead-review`, mutationInit(command));
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    headers.set("X-Fin-Case-Tenant", this.context.tenantId);
    headers.set("X-Fin-Case-Project", this.context.projectId);
    headers.set("X-Fin-Case-Actor", this.context.actorId);
    headers.set("X-Fin-Case-Permissions", this.context.permissions.join(","));

    let response: Response;
    try {
      response = await fetch(path, { ...init, headers });
    } catch (error) {
      throw new IntegrityApiError({
        code: "network_unavailable",
        message: "The fixture integrity API is unavailable.",
        statusCode: 0,
        detail: error,
      });
    }

    const text = await response.text();
    const payload = text ? parsePayload(text) : {};
    if (!response.ok) throw toIntegrityApiError(response.status, payload);
    return payload as T;
  }
}

function numericPath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}/integrity/numeric`;
}

function workpaperPath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}/workpaper`;
}

function mutationInit(command: { idempotency_key: string }): RequestInit {
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": command.idempotency_key,
    },
    body: JSON.stringify(command),
  };
}

function parsePayload(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

function toIntegrityApiError(statusCode: number, payload: unknown): IntegrityApiError {
  const envelope = errorEnvelope(payload);
  const nested = errorEnvelope(envelope.detail);
  const error = envelope.error ?? nested.error;
  return new IntegrityApiError({
    code: error?.error_code ?? envelope.code ?? nested.code ?? `http_${statusCode}`,
    message: error?.message ?? envelope.message ?? nested.message ?? detailMessage(envelope.detail) ?? "Integrity request failed.",
    statusCode,
    traceId: error?.trace_id ?? envelope.correlation_id ?? nested.correlation_id,
    detail: envelope.detail,
  });
}

function detailMessage(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (typeof detail !== "object" || detail === null) return undefined;
  const reason = (detail as { reason?: unknown }).reason;
  return typeof reason === "string" ? reason : undefined;
}

function errorEnvelope(value: unknown): ErrorEnvelope {
  return typeof value === "object" && value !== null ? value as ErrorEnvelope : {};
}
