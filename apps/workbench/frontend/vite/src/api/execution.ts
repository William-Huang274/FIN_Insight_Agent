import { CASES_PATH, FixtureCaseContext } from "./cases";

export const P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE = "p36_evidence_fixture_entry";
export const FIXTURE_NO_LEASE_FENCING_TOKEN = "fixture-no-lease";

export type CreateWorkUnitCommand = {
  work_unit_type: typeof P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE;
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
