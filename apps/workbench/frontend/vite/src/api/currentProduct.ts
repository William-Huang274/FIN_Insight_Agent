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

const CURRENT_HEADERS = {
  "X-Fin-Product-Mode": "current",
  "X-Fin-Case-Permissions": "current_product:read",
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
