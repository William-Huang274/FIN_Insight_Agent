import { CASES_PATH, FixtureCaseContext } from "./cases";

export const P36_COMPILER_POLICY_REF = "fixture:p36-ten-cell-v1";
export const P36_PACK_SELECTION_REF = "fixture:p36-ai-infrastructure-v2";

export type CompileDecisionSurfaceCommand = {
  expected_case_version: number;
  expected_summary_version: number;
  compiler_policy_ref: typeof P36_COMPILER_POLICY_REF;
  pack_selection_ref: typeof P36_PACK_SELECTION_REF;
  actor_ref: string;
  idempotency_key: string;
};

export type DecisionSurfaceRevision = {
  cell_id: string;
  what_would_change: string;
  stop_rule?: string;
};

export type ReviseDecisionSurfaceCommand = {
  expected_case_version: number;
  expected_decision_surface_contract_version: number;
  expected_checkpoint_version: number;
  changes: DecisionSurfaceRevision[];
  actor_ref: string;
  idempotency_key: string;
};

export type PlanningCheckpointDecision = "accept" | "return";

export type PlanningCheckpointDecisionCommand = {
  decision: PlanningCheckpointDecision;
  expected_case_version: number;
  expected_decision_surface_contract_version: number;
  expected_checkpoint_version: number;
  actor_ref: string;
  idempotency_key: string;
};

export type EvidenceSlotView = {
  evidence_slot_id: string;
  evidence_role: string;
  entity_scope: string[];
  period_scope: string;
  source_policy_ref: string;
  required: boolean;
};

export type DecisionSurfaceCellView = {
  cell_id: string;
  cell_version: number;
  decision_question: string;
  owner: string;
  materiality: string;
  stop_rule: string;
  what_would_change: string;
  evidence_slots: EvidenceSlotView[];
};

export type DecisionSurfaceReviewStatus = "draft" | "awaiting_review" | "accepted" | "returned";

export type DecisionSurfaceView = {
  case_id: string;
  contract_id: string;
  contract_version: number;
  contract_version_id: string;
  checkpoint_version: number;
  review_status: DecisionSurfaceReviewStatus;
  cells: DecisionSurfaceCellView[];
};

type ErrorEnvelope = {
  error?: {
    error_code?: string;
    message?: string;
    status_code?: number;
    trace_id?: string;
  };
  detail?: unknown;
};

export class PlanningApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly traceId: string | undefined;
  readonly detail: unknown;

  constructor(input: { code: string; message: string; statusCode: number; traceId?: string; detail?: unknown }) {
    super(input.message);
    this.name = "PlanningApiError";
    this.code = input.code;
    this.statusCode = input.statusCode;
    this.traceId = input.traceId;
    this.detail = input.detail;
  }
}

export const DEFAULT_FIXTURE_PLANNING_CONTEXT: FixtureCaseContext = {
  tenantId: "fixture_internal",
  projectId: "workbench_internal",
  actorId: "analyst_internal",
  permissions: ["case:read", "case:create", "planning:read", "planning:write", "planning:review"],
};

export class PlanningApiClient {
  constructor(private readonly context: FixtureCaseContext = DEFAULT_FIXTURE_PLANNING_CONTEXT) {}

  get actorRef(): string {
    return this.context.actorId;
  }

  async compileDecisionSurface(caseId: string, command: CompileDecisionSurfaceCommand): Promise<DecisionSurfaceView> {
    return this.request<DecisionSurfaceView>(`${casePath(caseId)}/planning/compile`, mutationInit("POST", command));
  }

  async getDecisionSurface(caseId: string): Promise<DecisionSurfaceView> {
    return this.request<DecisionSurfaceView>(`${casePath(caseId)}/decision-surface`);
  }

  async reviseDecisionSurface(caseId: string, command: ReviseDecisionSurfaceCommand): Promise<DecisionSurfaceView> {
    return this.request<DecisionSurfaceView>(`${casePath(caseId)}/decision-surface`, mutationInit("PATCH", command));
  }

  async reviewPlanningCheckpoint(caseId: string, command: PlanningCheckpointDecisionCommand): Promise<DecisionSurfaceView> {
    return this.request<DecisionSurfaceView>(`${casePath(caseId)}/planning/checkpoint`, mutationInit("POST", command));
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
      throw new PlanningApiError({
        code: "network_unavailable",
        message: "The fixture planning API is unavailable.",
        statusCode: 0,
        detail: error,
      });
    }

    const text = await response.text();
    const payload = text ? parsePayload(text) : {};
    if (!response.ok) {
      throw toPlanningApiError(response.status, payload);
    }
    return payload as T;
  }
}

function casePath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}`;
}

function mutationInit(method: "POST" | "PATCH", command: { idempotency_key: string }): RequestInit {
  return {
    method,
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

function toPlanningApiError(statusCode: number, payload: unknown): PlanningApiError {
  const envelope = isErrorEnvelope(payload) ? payload : {};
  const error = envelope.error;
  return new PlanningApiError({
    code: error?.error_code ?? `http_${statusCode}`,
    message: error?.message ?? detailMessage(envelope.detail) ?? "Planning request failed.",
    statusCode,
    traceId: error?.trace_id,
    detail: envelope.detail,
  });
}

function detailMessage(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (typeof detail !== "object" || detail === null) return undefined;
  const reason = (detail as { reason?: unknown }).reason;
  return typeof reason === "string" ? reason : undefined;
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return typeof value === "object" && value !== null;
}
