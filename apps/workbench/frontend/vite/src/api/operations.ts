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

export type ComplexDocumentQuality = {
  schema_version: string;
  status: string;
  display_scope: string;
  product_case_enrollment: boolean;
  source: {
    ticker: string;
    issuer_name: string;
    document_type: string;
    title: string;
    publication_date: string;
    page_count: number;
    selected_page_numbers: number[];
  };
  document_quality: {
    status: string;
    complete_document_page_count_verified: boolean;
    extraction_modes: Record<string, number>;
    page_statuses: Record<string, number>;
    table_region_count: number;
    footnote_count: number;
    low_confidence_material_token_count: number;
    forced_ocr_pages: number[];
  };
  financial_objects: {
    object_count: number;
    object_type_counts: Record<string, number>;
    cross_page_relation_count: number;
    numeric_fact_authority_granted: boolean;
  };
  candidate_decision_summary: Record<string, number>;
  coverage_summary: {
    coverage_state: string;
    accepted_evidence_count: number;
    reviewed_not_recalled_count: number;
    typed_boundary_count: number;
    true_public_information_gap_count: number;
  };
  hard_boundaries: Record<string, boolean>;
  stage_acceptance: Record<string, boolean>;
  business_result: Record<string, boolean | string>;
  result_digest: string;
};

export type RetrievalQuality = {
  schema_version: string;
  status: string;
  slice_id: string;
  summary: {
    positive_atom_count: number;
    combined_union_positive_atom_count: number;
    financial_shortlist_positive_top10_count: number;
    financial_shortlist_hard_negative_top10_count: number;
    vs1_reviewed_objects_in_candidate_pool: number;
    vs2_reviewed_objects_in_candidate_pool: number;
    judged_composite_positive_compatible_rate: number;
    judged_composite_hard_negative_suppression_rate: number;
    accepted_object_count: number;
    needs_review_candidate_count: number;
    all_candidates_have_persistent_decisions: boolean;
    vs3_vertical_slice_integrated: boolean;
  };
  gate_results: Record<string, boolean>;
  atom_summaries: Array<Record<string, unknown>>;
  decision: Record<string, unknown>;
  business_findings: string[];
  authority: Record<string, unknown>;
  result_digest: string;
};

export type SupplementCaseQuality = {
  case_key: string;
  slice_id: string;
  coverage_delta: {
    predecessor_evidence_count: number;
    successor_evidence_count: number;
    retired_broad_or_legacy_evidence_count: number;
    added_capture_bound_claim_count: number;
    predecessor_gap_count: number;
    successor_gap_count: number;
    narrowed_gap_count: number;
    added_gap_count?: number;
    closed_gap_count: number;
  };
  proposition_rows: Array<{
    atom_id: string;
    coverage_state: string;
    positive_reviewed_object_count: number;
    positive_accepted_object_count: number;
    hard_negative_accepted_object_ids: string[];
    proposition_ready: boolean;
    known: string[];
    unknown: string[];
  }>;
  gate_results: Record<string, boolean | number>;
  decision: Record<string, unknown>;
  business_findings: string[];
  authority: Record<string, unknown>;
  result_digest: string;
};

export type SupplementQuality = {
  schema_version: string;
  status: string;
  case_summaries: SupplementCaseQuality[];
  decision: Record<string, unknown>;
  summary_set_digest: string;
};

export type SourceIntakeRoute = {
  route_id: string;
  case_key: string;
  issuer_name: string;
  document_type: string;
  title: string;
  publication_date: string;
  source_url: string;
  discovery_url?: string | null;
  byte_ceiling: number;
  automatic_enabled: boolean;
  automatic_adapter_id?: string | null;
  operator_upload_enabled: boolean;
  promotion_status: "source_only_not_evidence";
};

export type SourceIntakeAttempt = {
  attempt_id: string;
  recorded_at: string;
  route_id: string;
  case_key: string;
  title: string;
  publication_date: string;
  acquisition_method: "operator_upload" | "automatic_adapter";
  adapter_id: string;
  status: "captured_ready_for_parse" | "captured_rejected" | "acquisition_failed";
  failure_code?: string | null;
  raw_object_sha256?: string | null;
  raw_object_bytes: number;
  raw_object_reused: boolean;
  pdf_page_count: number;
  promotion_status: "source_only_not_evidence";
  transport?: {
    http_status?: number | null;
    failure_category?: string | null;
  } | null;
  network_path?: {
    transparent_tun_likely?: boolean;
    route_interface?: string | null;
    diagnostic_boundary?: string;
  } | null;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && typeof init?.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    ...init,
    headers,
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

  complexDocumentQuality(): Promise<ComplexDocumentQuality> {
    return requestJson<ComplexDocumentQuality>(
      "/api/operations/s1/complex-document-quality",
    );
  }

  retrievalQuality(): Promise<RetrievalQuality> {
    return requestJson<RetrievalQuality>(
      "/api/operations/s1/retrieval-quality",
    );
  }

  supplementQuality(): Promise<SupplementQuality> {
    return requestJson<SupplementQuality>(
      "/api/operations/s1/supplement-quality",
    );
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

  sourceIntakeRoutes(): Promise<SourceIntakeRoute[]> {
    return requestJson<{ routes: SourceIntakeRoute[] }>("/api/operations/source-intake/routes").then((value) => value.routes);
  }

  sourceIntakeAttempts(): Promise<SourceIntakeAttempt[]> {
    return requestJson<{ attempts: SourceIntakeAttempt[] }>("/api/operations/source-intake/attempts").then((value) => value.attempts);
  }

  uploadSource(routeId: string, file: File): Promise<SourceIntakeAttempt> {
    return requestJson<{ attempt: SourceIntakeAttempt }>(`/api/operations/source-intake/uploads/${encodeURIComponent(routeId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/pdf" },
      body: file,
    }).then((value) => value.attempt);
  }

  acquireSourceAutomatically(routeId: string): Promise<SourceIntakeAttempt> {
    return requestJson<{ attempt: SourceIntakeAttempt }>(`/api/operations/source-intake/automatic/${encodeURIComponent(routeId)}`, {
      method: "POST",
      body: JSON.stringify({}),
    }).then((value) => value.attempt);
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
