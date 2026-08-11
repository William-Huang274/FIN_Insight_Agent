export type ResearchSubject = {
  entity_id: string;
  issuer_id: string;
  legal_name: string;
  ticker: string;
  exchange: string;
  as_of: string;
  aliases: string[];
};

export type EvidenceSummary = {
  status: string;
  accepted_evidence_items: number;
  direct_evidence_items: number;
  bounded_context_items: number;
  rejected_items: number;
  residual_gaps: number;
  source_materials: number;
};

export type PackBinding = {
  binding_state: "identity_and_digest_bound";
  case_id: string;
  case_version: number;
  case_subject_digest: string;
  pack_case_key: string;
  evidence_pack_result_digest: string;
  pack_artifact_digest: string;
  pack_payload_digest: string;
  research_as_of: string;
  binding_digest: string;
};

export type ResearchCaseSummary = {
  case_id: string;
  case_version: number;
  case_key: string;
  subject: ResearchSubject;
  subject_digest: string;
  research_as_of: string;
  language: string;
  pack_binding: PackBinding;
  evidence_summary: EvidenceSummary;
  available_surfaces: Array<"overview" | "evidence">;
  evidence_object_ready: boolean;
};

export type ResearchCaseList = {
  status: "identity_bound_research_case_catalog_ready";
  product_mode: "current";
  primary_route: "/workspace";
  evidence_pack_result_digest: string;
  items: ResearchCaseSummary[];
  evidence_objects_ready: boolean;
  unavailable_case_keys: string[];
  surface_policy: Record<string, unknown>;
  known_boundary: string;
  projection_digest: string;
};

export type ResearchCaseDetail = ResearchCaseSummary & {
  status: "identity_bound_research_case_ready";
  research_context: {
    research_as_of: string;
    language: string;
    research_question: string;
  };
  evidence_pack_uri: string;
  known_boundary: string;
  projection_digest: string;
};

export type SlotBinding = {
  slot_id: string;
  facet_ids?: string[];
  qualification_id?: string;
  business_meaning_zh?: string;
  claim_boundary_zh?: string;
};

export type EvidenceItem = {
  target_id: string;
  source_record_id: string;
  object_type: string;
  disposition: string;
  evidence_role?: string;
  publication_date?: string;
  source_reporting_period_end?: string;
  research_as_of?: string;
  relationship_directions?: string[];
  slot_bindings?: SlotBinding[];
  numeric_use_boundary?: string;
  causal_attribution_authorized?: boolean;
  writer_citable?: boolean;
  evidence_item_digest: string;
  structured_metric?: Record<string, unknown>;
  source: {
    material_ref: string;
    source_record_id: string;
    evidence_owner_ticker: string;
    source_tier: string;
    source_type: string;
    source_url: string;
    publication_date?: string;
    period_end?: string;
    license_scope?: string;
    redistributable?: boolean;
    source_text_digest: string;
    reviewed_source_excerpt: string;
    excerpt_truncated: boolean;
    excerpt_use_boundary: string;
  };
};

export type ResidualGap = {
  gap_id: string;
  gap_code: string;
  slot_id?: string;
  facet_id?: string;
  attempted_lane_ids?: string[];
  business_reason_zh?: string;
  supplement_direction_zh?: string;
};

export type ResearchEvidenceView = {
  status: "identity_bound_reviewed_evidence_ready";
  case_id: string;
  case_version: number;
  case_key: string;
  subject: ResearchSubject;
  subject_digest: string;
  research_context: ResearchCaseDetail["research_context"];
  pack_binding: PackBinding;
  evidence_items: EvidenceItem[];
  rejected_items: Array<Record<string, unknown>>;
  residual_gaps: ResidualGap[];
  consumer_contract: Record<string, unknown>;
  hard_boundaries: Record<string, unknown>;
  known_boundary: string;
  projection_digest: string;
};

const headers = {
  "X-Fin-Product-Mode": "current",
  "X-Fin-Case-Permissions": "current_product:read",
};

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { headers, signal });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}

export class ResearchWorkspaceApiClient {
  listCases(signal?: AbortSignal): Promise<ResearchCaseList> {
    return getJson<ResearchCaseList>("/api/v1/research-cases", signal);
  }

  getCase(caseId: string, signal?: AbortSignal): Promise<ResearchCaseDetail> {
    return getJson<ResearchCaseDetail>(
      `/api/v1/research-cases/${encodeURIComponent(caseId)}`,
      signal,
    );
  }

  getEvidence(caseId: string, signal?: AbortSignal): Promise<ResearchEvidenceView> {
    return getJson<ResearchEvidenceView>(
      `/api/v1/research-cases/${encodeURIComponent(caseId)}/evidence`,
      signal,
    );
  }
}
