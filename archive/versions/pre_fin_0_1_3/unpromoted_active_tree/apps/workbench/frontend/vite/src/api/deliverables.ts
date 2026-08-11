import { CASES_PATH, FixtureCaseContext } from "./cases";

export type DeliverableRenderer = "html" | "markdown";
export type DeliverableReviewDecision = "comment" | "return_for_repair" | "accept_fixture_preview";
export type TraceDirection = "claim_to_source" | "source_to_claim";
export type TraceNodeType = "material_claim" | "evidence_candidate" | "numeric_fact" | "repair_outcome" | "explicit_gap";

export type MaterialClaimView = {
  claim_id: string;
  cell_id: string;
  claim_text: string;
  claim_kind: string;
  evidence_refs: string[];
  numeric_refs: string[];
  repair_outcome_refs: string[];
  gap_refs: string[];
};

export type DeliverableSectionView = {
  section_id: string;
  heading: string;
  lines: string[];
  claim_ids: string[];
};

export type DeliverableRenderingView = {
  content: string;
  content_digest: string;
  canonical_presentation_digest: string;
};

export type DeliverableReviewActionView = {
  review_action_id: string;
  review_action_version_id: string;
  action_type: DeliverableReviewDecision;
  reason: string;
  terminal: boolean;
  actor_ref: string;
  reviewed_at: string;
  artifact_version_id: string;
  artifact_version: number;
  content_digest: string;
  canonical_presentation_digest: string;
};

export type DeliverablePreviewView = {
  case_id: string;
  deliverable_id: string;
  artifact_version_id: string;
  artifact_version: number;
  content_digest: string;
  canonical_presentation_digest: string;
  status: string;
  title: string;
  sections: DeliverableSectionView[];
  material_claims: MaterialClaimView[];
  renderings: Record<DeliverableRenderer, DeliverableRenderingView>;
  review_actions: DeliverableReviewActionView[];
  hard_boundaries: Record<string, number | string>;
};

export type TraceNodeView = {
  node_id: string;
  node_type: TraceNodeType;
  display_label: string;
  reference: string;
};

export type TraceEdgeView = {
  from_node_id: string;
  to_node_id: string;
};

export type DeliverableTraceView = {
  case_id: string;
  manifest_id: string;
  artifact_version_id: string;
  artifact_version: number;
  artifact_content_digest: string;
  canonical_presentation_digest: string;
  nodes: TraceNodeView[];
  edges: TraceEdgeView[];
  claim_to_source: Record<string, string[]>;
  source_to_claim: Record<string, string[]>;
  redaction_summary: Record<string, number | string>;
};

export type CompileDeliverablePreviewCommand = {
  expected_workpaper_version: number;
  expected_workpaper_content_digest: string;
  writer_admission_id: string;
  actor_ref: string;
  idempotency_key: string;
};

export type ReviewDeliverableVersionCommand = {
  expected_artifact_version: number;
  expected_content_digest: string;
  expected_canonical_presentation_digest: string;
  action_type: DeliverableReviewDecision;
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

export class DeliverablesApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly traceId: string | undefined;
  readonly detail: unknown;

  constructor(input: { code: string; message: string; statusCode: number; traceId?: string; detail?: unknown }) {
    super(input.message);
    this.name = "DeliverablesApiError";
    this.code = input.code;
    this.statusCode = input.statusCode;
    this.traceId = input.traceId;
    this.detail = input.detail;
  }
}

export const DEFAULT_FIXTURE_DELIVERABLES_CONTEXT: FixtureCaseContext = {
  tenantId: "fixture_internal",
  projectId: "workbench_internal",
  actorId: "analyst_internal",
  permissions: ["deliverable:read", "deliverable:write", "deliverable_review:decide", "trace:read"],
};

export class DeliverablesApiClient {
  constructor(private readonly context: FixtureCaseContext = DEFAULT_FIXTURE_DELIVERABLES_CONTEXT) {}

  get actorRef(): string {
    return this.context.actorId;
  }

  getDeliverableHead(caseId: string): Promise<DeliverablePreviewView> {
    return this.request<DeliverablePreviewView>(deliverablesPath(caseId));
  }

  compileDeliverablePreviewFixture(caseId: string, command: CompileDeliverablePreviewCommand): Promise<DeliverablePreviewView> {
    return this.request<DeliverablePreviewView>(deliverablesPath(caseId), mutationInit(command));
  }

  createDeliverableReviewAction(deliverableId: string, artifactVersion: number, command: ReviewDeliverableVersionCommand): Promise<DeliverablePreviewView> {
    return this.request<DeliverablePreviewView>(artifactReviewActionsPath(deliverableId, artifactVersion), mutationInit(command));
  }

  getCaseTrace(caseId: string): Promise<DeliverableTraceView> {
    return this.request<DeliverableTraceView>(caseTracePath(caseId));
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
      throw new DeliverablesApiError({
        code: "network_unavailable",
        message: "The deliverable API is unavailable.",
        statusCode: 0,
        detail: error,
      });
    }

    const text = await response.text();
    const payload = text ? parsePayload(text) : {};
    if (!response.ok) throw toDeliverablesApiError(response.status, payload);
    return payload as T;
  }
}

function deliverablesPath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}/deliverables`;
}

function artifactReviewActionsPath(deliverableId: string, artifactVersion: number): string {
  return `/api/v1/artifacts/${encodeURIComponent(deliverableId)}/versions/${encodeURIComponent(String(artifactVersion))}/review-actions`;
}

function caseTracePath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}/trace`;
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

function toDeliverablesApiError(statusCode: number, payload: unknown): DeliverablesApiError {
  const envelope = errorEnvelope(payload);
  const nested = errorEnvelope(envelope.detail);
  const error = envelope.error ?? nested.error;
  return new DeliverablesApiError({
    code: error?.error_code ?? envelope.code ?? nested.code ?? `http_${statusCode}`,
    message: error?.message ?? envelope.message ?? nested.message ?? detailMessage(envelope.detail) ?? "Deliverable request failed.",
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
