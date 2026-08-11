export const CASES_PATH = "/api/v1/cases";

export type CreateCaseDraftCommand = {
  query: string;
  as_of: string;
  language: string;
  source_policy_ref: string;
  idempotency_key: string;
};

export type TaskCenterRow = {
  case_id: string;
  case_version: number;
  query: string;
  status: string;
  updated_at: string;
};

export type TaskCenterProjection = {
  items: TaskCenterRow[];
  next_cursor: string | null;
};

export type CaseWorkspaceProjection = {
  case_id: string;
  case_version: number;
  summary_version: number;
  query: string;
  as_of: string;
  language: string;
  planning_checkpoint_state: string;
};

export type FixtureCaseContext = {
  tenantId: string;
  projectId: string;
  actorId: string;
  permissions: readonly string[];
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

export class CaseApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly traceId: string | undefined;
  readonly detail: unknown;

  constructor(input: { code: string; message: string; statusCode: number; traceId?: string; detail?: unknown }) {
    super(input.message);
    this.name = "CaseApiError";
    this.code = input.code;
    this.statusCode = input.statusCode;
    this.traceId = input.traceId;
    this.detail = input.detail;
  }
}

export const DEFAULT_FIXTURE_CASE_CONTEXT: FixtureCaseContext = {
  tenantId: "fixture_internal",
  projectId: "workbench_internal",
  actorId: "analyst_internal",
  permissions: ["case:read", "case:create"],
};

export class CaseApiClient {
  constructor(private readonly context: FixtureCaseContext = DEFAULT_FIXTURE_CASE_CONTEXT) {}

  async createCase(command: CreateCaseDraftCommand): Promise<CaseWorkspaceProjection> {
    return this.request<CaseWorkspaceProjection>(CASES_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(command),
    });
  }

  async listCases(): Promise<TaskCenterProjection> {
    return this.request<TaskCenterProjection>(CASES_PATH);
  }

  async getCase(caseId: string, expectedCaseVersion?: number): Promise<CaseWorkspaceProjection> {
    const headers = new Headers();
    if (expectedCaseVersion !== undefined) {
      headers.set("X-Fin-Case-Expected-Version", String(expectedCaseVersion));
    }
    return this.request<CaseWorkspaceProjection>(`${CASES_PATH}/${encodeURIComponent(caseId)}`, { headers });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    headers.set("X-Fin-Case-Tenant", this.context.tenantId);
    headers.set("X-Fin-Case-Project", this.context.projectId);
    headers.set("X-Fin-Case-Actor", this.context.actorId);
    headers.set("X-Fin-Case-Permissions", this.context.permissions.join(","));

    const response = await fetch(path, { ...init, headers });
    const payload = (await response.json()) as unknown;
    if (!response.ok) {
      throw toCaseApiError(response.status, payload);
    }
    return payload as T;
  }
}

function toCaseApiError(statusCode: number, payload: unknown): CaseApiError {
  const envelope = isErrorEnvelope(payload) ? payload : {};
  const error = envelope.error;
  return new CaseApiError({
    code: error?.error_code ?? `http_${statusCode}`,
    message: error?.message ?? "Case request failed.",
    statusCode,
    traceId: error?.trace_id,
    detail: envelope.detail,
  });
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return typeof value === "object" && value !== null;
}
