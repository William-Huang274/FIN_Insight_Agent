export const CURRENT_PRODUCT_SURFACES = [
  "case",
  "run",
  "evidence",
  "numeric",
  "graph",
  "gaps",
  "workpaper",
  "report",
  "trace",
  "quality",
] as const;

export type CurrentProductSurface = (typeof CURRENT_PRODUCT_SURFACES)[number];

export type CurrentProductCase = {
  case_key: string;
  case_projection_digest: string;
  view_digest: string;
  ticker: string;
  as_of: string;
  natural_objective: string;
  status: string;
  accepted_product_scope: string;
  method_id: string | null;
  program_cell_ids: string[];
  counts: {
    evidence: number;
    numeric: number;
    typed_gaps: number;
    approved_graph_edges: number;
    business_artifacts: number;
  };
};

export type CurrentProductCaseList = {
  schema_version: string;
  projection_mode: "current";
  manifest_digest: string;
  items: CurrentProductCase[];
  next_cursor: null;
};

export type CurrentProductSurfaceResponse = {
  schema_version: string;
  projection_mode: "current";
  manifest_digest: string;
  case_key: string;
  case_projection_digest: string;
  surface: CurrentProductSurface;
  view_digest: string;
  data: Record<string, unknown>;
};

export type CurrentReturnRequest = {
  request_id: string;
  action_type: "return_for_repair";
  status: "repair_requested";
  case_key: string;
  target_surface: CurrentProductSurface;
  target_view_digest: string;
  target_ref: string;
  reason_code: CurrentRepairReason;
  reviewer_note: string;
  repair_owner: string;
  requested_resolution: string;
  actor_ref: string;
  requested_at: string;
  qualified_human_review: false;
  automatic_repair_execution: false;
};

export type CurrentRepairReason =
  | "missing_authority"
  | "numeric_scope_or_unit"
  | "unsupported_inference"
  | "missing_counterevidence"
  | "lineage_mismatch"
  | "delivery_clarity";

export type CurrentReviewControlState = {
  schema_version: string;
  projection_mode: "current";
  case_key: string;
  manifest_digest: string;
  case_projection_digest: string;
  event_count: number;
  head_event_digest: string | null;
  return_requests: CurrentReturnRequest[];
  replay_integrity: "pass";
  replay_digest: string;
  T07_handoff: {
    status: "ready_for_qualified_review" | "repair_required_before_qualified_review";
    handoff_digest: string;
    open_return_request_ids: string[];
    qualified_review_executed: false;
    NVDA_R3_executed: false;
  };
  hard_boundaries: Record<string, unknown>;
};

export type CurrentReturnForRepairCommand = {
  expected_manifest_digest: string;
  expected_case_projection_digest: string;
  target_surface: CurrentProductSurface;
  expected_target_view_digest: string;
  target_ref: string;
  reason_code: CurrentRepairReason;
  reviewer_note: string;
  actor_ref: string;
  idempotency_key: string;
};

export type CurrentReviewerPacket = {
  schema_version: string;
  projection_mode: "current";
  status: "ready_for_authenticated_qualified_human_review";
  case_key: "NVDA";
  exact_binding: Record<string, unknown> & { view_digests: Record<CurrentProductSurface, string> };
  review_checklist: Array<Record<string, unknown> & { check_id: string; instruction: string; review_status: string }>;
  review_burden: Record<string, number | null>;
  sections: Record<string, unknown>;
  decision_boundary: Record<string, unknown>;
  hard_boundaries: Record<string, unknown>;
  packet_digest: string;
};

export type QualifiedReviewState = {
  schema_version: string;
  case_key: "NVDA";
  session: {
    session_id: string;
    reviewer_ref: string;
    reviewer_role: string;
    permission: string;
    authenticated: true;
    credential_plaintext_persisted: false;
  };
  exact_binding: Record<string, string>;
  decision: Record<string, unknown> | null;
  event_replay: { integrity: "pass"; event_count: number; head_event_digest: string | null };
  acceptance: {
    authenticated_reviewer_identity: boolean;
    qualified_human_review: boolean;
    NVDA_R3: boolean;
    release_qualified: false;
  };
  state_digest: string;
};

export type QualifiedReviewDecisionCommand = {
  action: "accept_exact_version" | "return_for_repair";
  reviewer_note: string;
  idempotency_key: string;
  target_surface?: CurrentProductSurface;
  expected_target_view_digest?: string;
  reason_code?: string;
};

export const CURRENT_INTERNAL_ACTOR = "current_internal_operator";

const CURRENT_HEADERS = {
  "X-Fin-Product-Mode": "current",
  "X-Fin-Current-Actor": CURRENT_INTERNAL_ACTOR,
  "X-Fin-Case-Permissions": "current_product:read,current_product:request_repair",
};

export class CurrentProductApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "CurrentProductApiError";
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: "GET",
    headers: CURRENT_HEADERS,
    signal,
  });
  if (!response.ok) {
    let detail = `current_product_request_failed_${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
    } catch {
      // Preserve the typed HTTP status even when the server has no JSON body.
    }
    throw new CurrentProductApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { ...CURRENT_HEADERS, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = `current_product_request_failed_${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
    } catch {
      // Preserve the typed HTTP status even when the server has no JSON body.
    }
    throw new CurrentProductApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

async function qualifiedJson<T>(path: string, credential: string, method: "GET" | "POST", body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: {
      Authorization: `Bearer ${credential}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    let detail = `qualified_review_request_failed_${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
    } catch {
      // Never include the bearer credential in errors or retry metadata.
    }
    throw new CurrentProductApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function listCurrentProductCases(signal?: AbortSignal): Promise<CurrentProductCaseList> {
  return getJson<CurrentProductCaseList>("/api/v1/current-product/cases", signal);
}

export function getCurrentProductSurface(
  caseKey: string,
  surface: CurrentProductSurface,
  signal?: AbortSignal,
): Promise<CurrentProductSurfaceResponse> {
  return getJson<CurrentProductSurfaceResponse>(
    `/api/v1/current-product/cases/${encodeURIComponent(caseKey)}/${surface}`,
    signal,
  );
}

export function getCurrentReviewControl(
  caseKey: string,
  signal?: AbortSignal,
): Promise<CurrentReviewControlState> {
  return getJson<CurrentReviewControlState>(
    `/api/v1/current-product/cases/${encodeURIComponent(caseKey)}/review-control`,
    signal,
  );
}

export function requestCurrentReturnForRepair(
  caseKey: string,
  command: CurrentReturnForRepairCommand,
): Promise<CurrentReviewControlState> {
  return postJson<CurrentReviewControlState>(
    `/api/v1/current-product/cases/${encodeURIComponent(caseKey)}/return-requests`,
    command,
  );
}

export function getCurrentReviewerPacket(
  caseKey: string,
  signal?: AbortSignal,
): Promise<CurrentReviewerPacket> {
  return getJson<CurrentReviewerPacket>(
    `/api/v1/current-product/cases/${encodeURIComponent(caseKey)}/reviewer-packet`,
    signal,
  );
}

export function getQualifiedReviewState(credential: string): Promise<QualifiedReviewState> {
  return qualifiedJson<QualifiedReviewState>(
    "/api/v1/current-product/cases/NVDA/qualified-review",
    credential,
    "GET",
  );
}

export function submitQualifiedReviewDecision(
  credential: string,
  command: QualifiedReviewDecisionCommand,
): Promise<QualifiedReviewState> {
  return qualifiedJson<QualifiedReviewState>(
    "/api/v1/current-product/cases/NVDA/qualified-review/decisions",
    credential,
    "POST",
    command,
  );
}
