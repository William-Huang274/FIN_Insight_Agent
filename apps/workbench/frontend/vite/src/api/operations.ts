export type SystemStatus = {
  status: "ok" | "degraded";
  service: string;
  version: string;
  checks: Record<string, string>;
  paths: Record<string, unknown>;
  store: Record<string, unknown>;
};

export type StoredProfile = {
  profile_id: string;
  display_name: string;
  source_policy: string;
  model_name?: string | null;
  updated_at: string;
};

export type StoredSourceBundle = {
  bundle_id: string;
  display_name: string;
  market: string;
  coverage_theme: string;
  ticker_count: number;
  as_of_date?: string | null;
  status: string;
  updated_at: string;
};

export type RunJob = {
  job_id: string;
  job_type: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  profile_id?: string | null;
  trace_id?: string | null;
  metadata?: Record<string, unknown>;
};

export type EvalCatalogItem = {
  eval_id: string;
  label?: string;
  description?: string;
  runner?: string;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}

export class OperationsApiClient {
  status(): Promise<SystemStatus> {
    return requestJson<SystemStatus>("/api/operations/status");
  }

  profiles(): Promise<StoredProfile[]> {
    return requestJson<{ profiles: StoredProfile[] }>("/api/operations/profiles").then((value) => value.profiles);
  }

  sourceBundles(): Promise<StoredSourceBundle[]> {
    return requestJson<{ bundles: StoredSourceBundle[] }>("/api/operations/source-bundles").then((value) => value.bundles);
  }

  runs(): Promise<RunJob[]> {
    return requestJson<{ runs: RunJob[] }>("/api/operations/runs").then((value) => value.runs);
  }

  evals(): Promise<EvalCatalogItem[]> {
    return requestJson<{ evals: EvalCatalogItem[] }>("/api/operations/evals").then((value) => value.evals);
  }

  startSmoke(): Promise<RunJob> {
    return requestJson<{ job: RunJob }>("/api/operations/runs/smoke", {
      method: "POST",
      body: JSON.stringify({}),
    }).then((value) => value.job);
  }

  cancelRun(jobId: string): Promise<Record<string, unknown>> {
    return requestJson<Record<string, unknown>>(`/api/operations/runs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: "operator requested cancellation" }),
    });
  }
}
