import { CASES_PATH, FixtureCaseContext } from "./cases";

export const P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE = "p36_evidence_fixture_entry";
export const AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE = "agent_fixture_shadow_entry";
export const FIXTURE_NO_LEASE_FENCING_TOKEN = "fixture-no-lease";

export type CreateWorkUnitCommand = {
  work_unit_type: typeof P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE | typeof AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE;
  expected_case_version: number;
  input_head_digest: string;
  actor_ref: string;
  idempotency_key: string;
};

export type CancelWorkUnitCommand = {
  expected_work_unit_version: number;
  expected_state_version: number;
  fencing_token: typeof FIXTURE_NO_LEASE_FENCING_TOKEN;
  actor_ref: string;
  idempotency_key: string;
};

export type WorkUnitState = "pending" | "cancelled" | string;

export type WorkUnitExecutionItem = {
  work_unit_id: string;
  work_unit_version: number;
  state_version: number;
  state: WorkUnitState;
  input_head_digest: string;
};

export type WorkUnitExecutionView = {
  case_id: string;
  work_units: WorkUnitExecutionItem[];
};

export type ActivityEvent = {
  event_id: string;
  sequence: number;
  event_type: string;
  occurred_at: string;
  typed_stop?: string | null;
};

export type ActivityTraceView = {
  case_id: string;
  case_version: number;
  events: ActivityEvent[];
};

export type ResearchRunEventView = {
  event_id: string;
  sequence: number;
  event_type: string;
  occurred_at: string;
  causation_event_id?: string | null;
  details: Record<string, unknown>;
  redacted_fields: string[];
  private_chain_of_thought_included: false;
};

export type ResearchRunArtifactView = {
  artifact_version_id: string;
  artifact_type: string;
  producer_attempt_id: string;
  current_status: string;
  object_digest: string;
  input_refs: string[];
  payload: Record<string, unknown>;
  payload_exact: boolean;
  redacted_fields: string[];
};

export type S4CaseRuntimeProjection = {
  runtime_binding_digest: string;
  case_ticker: "DELL" | "MU";
  issuer_identifier: string;
  case_profile_ref: string;
  method_id: string;
  case_identity_namespace: string;
  paid_artifact_proven: false;
  human_review_completed: false;
};

export type ResearchRunProjectionItem = {
  research_run_id: string;
  research_run_version_id: string;
  work_unit_id: string;
  work_unit_type: string;
  attempt_id: string;
  execution_profile_version_ref: string;
  state: string;
  started_at: string;
  ended_at?: string | null;
  terminal_reason?: string | null;
  output_refs: string[];
  events: ResearchRunEventView[];
  artifacts: ResearchRunArtifactView[];
};

export type ResearchRunProjectionView = {
  case_id: string;
  runs: ResearchRunProjectionItem[];
  private_chain_of_thought_included: false;
};

export type S3PresentationSurfaceClaimView = {
  surface_claim_version_ref: string;
  program_cell_id: string;
  claim_text: string;
  specialist_judgment_ref: string;
  fact_statements: string[];
  evidence_refs: string[];
  numeric_refs: string[];
  graph_context_refs: string[];
  gap_codes: string[];
  what_would_change: string[];
  repair_ticket_refs: string[];
  stop_semantic: string;
  source_grade: string;
  numeric_sanity_status: string;
  official_or_estimate_flag: string;
};

export type S3PresentationWorkpaperCellView = {
  program_cell_id: string;
  cell_version_ref: string;
  surface_claim_ref: string;
  specialist_judgment_ref: string;
  decision_question: string;
  direct_answer: string;
  fact_statements: string[];
  evidence_refs: string[];
  numeric_refs: string[];
  graph_drilldown: {
    graph_edge_projection_ref: string;
    graph_authority: string;
    graph_status: string;
    source_followup_refs: string[];
    typed_gaps: string[];
    automatic_new_research: false;
  };
  gaps: string[];
  what_would_change: string[];
  repair_ticket_refs: string[];
  stop_semantic: string;
  review_status: string;
};

export type S3ThreeCellPresentationPackView = {
  presentation_pack_version_ref: string;
  presentation_pack_digest: string;
  case_id: string;
  research_run_id: string;
  execution_profile_version_ref: string;
  surface_claims: S3PresentationSurfaceClaimView[];
  workpaper: {
    artifact_ref: string;
    workpaper_version_ref: string;
    workpaper_digest: string;
    status: string;
    cell_sections: S3PresentationWorkpaperCellView[];
  };
  report: {
    artifact_ref: string;
    report_version_ref: string;
    report_digest: string;
    workpaper_artifact_ref: string;
    title: string;
    executive_answer: string;
    sections: Array<{
      section_id: string;
      program_cell_id: string;
      heading: string;
      content: string;
      surface_claim_ref: string;
      specialist_judgment_ref: string;
      evidence_refs: string[];
      numeric_refs: string[];
      boundary: string;
    }>;
    presentation_gaps: string[];
    writer_source_authority: false;
    writer_retrieval_authority: false;
    writer_external_tool_authority: false;
    model_writer_executed: false;
  };
  trace_review: {
    artifact_ref: string;
    trace_version_ref: string;
    trace_digest: string;
    workpaper_artifact_ref: string;
    report_artifact_ref: string;
    nodes: Array<{ node_ref: string; node_type: string; label: string }>;
    edges: Array<{ edge_id: string; from_ref: string; to_ref: string; relation: string }>;
    review_binding: {
      verifier_input_digest: string;
      execution_profile_version_ref: string;
      input_head_digest: string;
      analysis_as_of: string;
      artifact_refs: string[];
      bound_content_digests: string[];
      verifier_decision: string;
      human_review_status: "not_performed";
      human_decision: "not_performed";
      exact_digest_confirmation: false;
      findings: Array<{
        finding_id: string;
        layer: string;
        severity: string;
        status: string;
        affected_refs: string[];
        earliest_owner_ref: string;
        message: string;
      }>;
      review_targets: Array<{
        review_target_id: string;
        program_cell_id: string;
        surface_claim_ref: string;
        specialist_judgment_ref: string;
        artifact_refs: string[];
        source_grade: string;
        numeric_sanity_status: string;
        official_or_estimate_flag: string;
        cannot_infer: string[];
        what_would_change: string[];
        repair_ticket_refs: string[];
        stop_semantic: string;
        allowed_review_actions: string[];
        review_status: "not_performed";
      }>;
    };
  };
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

export class ExecutionApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly traceId: string | undefined;
  readonly detail: unknown;

  constructor(input: { code: string; message: string; statusCode: number; traceId?: string; detail?: unknown }) {
    super(input.message);
    this.name = "ExecutionApiError";
    this.code = input.code;
    this.statusCode = input.statusCode;
    this.traceId = input.traceId;
    this.detail = input.detail;
  }
}

export const DEFAULT_FIXTURE_EXECUTION_CONTEXT: FixtureCaseContext = {
  tenantId: "fixture_internal",
  projectId: "workbench_internal",
  actorId: "analyst_internal",
  permissions: ["case:read", "planning:read", "execution:read", "execution:write", "activity:read"],
};

export class ExecutionApiClient {
  constructor(private readonly context: FixtureCaseContext = DEFAULT_FIXTURE_EXECUTION_CONTEXT) {}

  get actorRef(): string {
    return this.context.actorId;
  }

  async listWorkUnits(caseId: string): Promise<WorkUnitExecutionView> {
    return this.request<WorkUnitExecutionView>(`${casePath(caseId)}/work-units`);
  }

  async createWorkUnit(caseId: string, command: CreateWorkUnitCommand): Promise<WorkUnitExecutionView> {
    return this.request<WorkUnitExecutionView>(`${casePath(caseId)}/work-units`, mutationInit(command));
  }

  async cancelWorkUnit(caseId: string, workUnitId: string, command: CancelWorkUnitCommand): Promise<WorkUnitExecutionView> {
    return this.request<WorkUnitExecutionView>(
      `${casePath(caseId)}/work-units/${encodeURIComponent(workUnitId)}/cancel`,
      mutationInit(command),
    );
  }

  async getActivityTrace(caseId: string): Promise<ActivityTraceView> {
    return this.request<ActivityTraceView>(`${casePath(caseId)}/activity`);
  }

  async getResearchRunProjection(caseId: string): Promise<ResearchRunProjectionView> {
    return this.request<ResearchRunProjectionView>(`${casePath(caseId)}/execution-projection`);
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
      throw new ExecutionApiError({
        code: "network_unavailable",
        message: "The fixture execution API is unavailable.",
        statusCode: 0,
        detail: error,
      });
    }

    const text = await response.text();
    const payload = text ? parsePayload(text) : {};
    if (!response.ok) throw toExecutionApiError(response.status, payload);
    return payload as T;
  }
}

export async function decisionSurfaceInputHeadDigest(contractVersionId: string): Promise<string> {
  const canonicalJson = JSON.stringify([contractVersionId]);
  const encoded = new TextEncoder().encode(canonicalJson);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

function casePath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}`;
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

function toExecutionApiError(statusCode: number, payload: unknown): ExecutionApiError {
  const envelope = errorEnvelope(payload);
  const nested = errorEnvelope(envelope.detail);
  const error = envelope.error ?? nested.error;
  return new ExecutionApiError({
    code: error?.error_code ?? envelope.code ?? nested.code ?? `http_${statusCode}`,
    message: error?.message ?? envelope.message ?? nested.message ?? detailMessage(envelope.detail) ?? "Execution request failed.",
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
