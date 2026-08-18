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
  available_surfaces: Array<"overview" | "evidence" | "retrieval">;
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

export type S1CanonicalSpineView = {
  schema_version: "fin_ia_s1_workbench_lineage_projection_v1_0";
  status: "canonical_s1_lineage_ready";
  recorded_at: string;
  case_key: string;
  research_as_of: string;
  proposition_id: string;
  readiness_state: string;
  candidate_decision_summary: {
    accepted: number;
    rejected: number;
    unjudged: number;
    needs_review: number;
  };
  coverage_summary: {
    coverage_state: string;
    accepted_evidence_count: number;
    reviewed_not_recalled_count: number;
    unresolved_gap_count: number;
    true_public_information_gap_count: number;
  };
  decision_rows: Array<{
    candidate_ref: string;
    source_record_id: string;
    rank: number;
    evidence_owner_ticker: string;
    source_type: string;
    publication_date: string;
    decision_state: "accepted" | "rejected" | "unjudged" | "needs_review";
    reason_codes: string[];
    decision_authority: string;
    accepted_evidence_item_digests: string[];
    decision_digest: string;
  }>;
  gap_eligibility_receipts: Array<{
    gap_id: string;
    gap_code: string;
    classification: string;
    eligible_as_true_public_information_gap: boolean;
    disposition: string;
    receipt_digest: string;
  }>;
  pack_binding: {
    case_key: string;
    artifact_digest: string;
    pack_payload_digest: string;
  };
  hard_boundaries: {
    candidate_is_not_evidence: boolean;
    rank_never_grants_evidence_authority: boolean;
    unexecuted_route_is_not_public_information_gap: boolean;
    complete_product_conclusion_ready: boolean;
    S1_qualified_stable: boolean;
  };
  workbench_projection_digest: string;
};

export type S1ProductReadinessRequest = {
  request_id: string;
  slot_id: string;
  facet_id: string;
  business_question_zh: string;
  readiness_state: string;
  material_scope_ready: boolean;
  requirement_count: number;
  requirement_state_counts: Record<string, number>;
  candidate_decision_counts: {
    accepted: number;
    needs_human_review: number;
    rejected: number;
    unjudged: number;
  };
  numeric_authority_state: {
    state: string;
    request_count: number;
    resolved_count: number;
    typed_gap_count: number;
    typed_conflict_count: number;
  };
  unexecuted_or_unavailable_routes: string[];
  candidate_review_summary: {
    review_item_count: number;
    human_review_required_count: number;
    issue_class_counts: Record<string, number>;
    request_review_digest: string;
  };
  candidate_review_items: S1CandidateReviewItem[];
};

export type S1CandidateReviewItem = {
  review_item_ref: string;
  review_item_digest: string;
  review_scope: "requirement_bound" | "material_review_context";
  source_lineage_digest: string;
  subject_ticker: string;
  evidence_owner_ticker: string;
  object_kind: string;
  requirement_contexts: Array<{
    requirement_id: string;
    facet_id: string;
    role: string;
    product_ids: string[];
    metric_ids: string[];
    target_entities: string[];
    candidate_set_complete_in_bounded_union: boolean;
    missing_required_product_ids: string[];
    missing_required_metric_ids: string[];
  }>;
  advisory_evidence_role: {
    compatibility: string;
    labels: string[];
    reason_codes: string[];
    advisory_only: true;
  };
  rank_trace: {
    raw_union_rank?: number | null;
    financial_rank?: number | null;
    review_priority_rank?: number | null;
    final_output_rank?: number | null;
  };
  route_membership: string[];
  decision_state: "accepted" | "needs_human_review";
  reason_codes: string[];
  issue_classes: string[];
  next_legal_action: string;
  human_review_required: boolean;
  candidate_is_not_evidence: true;
  candidate_text_promoted: false;
  new_evidence_created: false;
  numeric_authority: false;
  source: {
    company: string;
    source_type: string;
    source_tier: string;
    publication_date: string;
    period_end: string;
    section: string;
    subsection?: string;
    source_url: string;
    surface_digest: string;
    bounded_excerpt: string;
  };
};

export type S1ProductReadinessView = {
  schema_version: "fin_ia_s1_current_product_readiness_result_v1_1";
  status: "current_product_pack_readiness_materialized";
  recorded_at: string;
  prepared_from_commit: string;
  case_key: string;
  readiness_state: string;
  request_count: number;
  request_state_counts: Record<string, number>;
  candidate_count: number;
  accepted_reviewed_evidence_count: number;
  gap_eligibility_receipt_count: number;
  declared_pack_gap_receipt_count: number;
  candidate_review_packet_summary: {
    schema_version: "fin_ia_s1_product_candidate_review_packet_v1_0";
    status: "candidate_review_packet_materialized_no_promotion";
    review_item_count: number;
    human_review_required_count: number;
    issue_class_counts: Record<string, number>;
    review_packet_digest: string;
    private_packet_required_for_bounded_excerpt_projection: true;
  };
  requests: S1ProductReadinessRequest[];
  authority: {
    candidate_is_not_evidence: boolean;
    public_information_gap_authority: boolean;
    numeric_fact_authority_remains_with_S2: boolean;
    S1_qualification_claimed: boolean;
    product_publication: boolean;
  };
  known_boundary: string;
  result_digest: string;
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
  canonical_spine?: S1CanonicalSpineView | null;
  product_readiness?: S1ProductReadinessView | null;
  known_boundary: string;
  projection_digest: string;
};

export type RetrievalCandidate = {
  candidate_state: "candidate_not_evidence";
  source_record_id: string;
  evidence_owner_ticker: string;
  subject_ticker: string;
  relationship_direction: string;
  source_role: string;
  subject_mention_state: string;
  source_type: string;
  publication_date: string;
  subsection: string;
  source_url: string;
  matched_terms: string[];
  final_score: number;
  business_boundary_zh: string;
  excerpt: string;
};

export type RetrievalLane = {
  lane_id: string;
  slot_id: string;
  facet_id: string;
  business_question_zh: string;
  evidence_owner_tickers: string[];
  required_source_roles: string[];
  publication_date_lte: string;
  candidates: RetrievalCandidate[];
  missing_required_source_roles: string[];
  exclusion_counts: Record<string, number>;
};

export type ResearchRetrievalView = {
  status: "typed_local_retrieval_snapshot_ready";
  product_mode: "current";
  case_key: string;
  candidate_state: "candidate_not_evidence";
  query_plan_digest: string;
  result_digest: string;
  source_snapshot: {
    logical_id: string;
    records: number;
    case_scope_records: number;
    source_boundary: string;
  };
  summary: {
    lane_count: number;
    nonempty_lane_count: number;
    slot_count: number;
    unique_candidates: number;
    slots_missing_required_source_roles: Record<string, string[]>;
  };
  source_gap_summary: {
    reviewed_label_occurrences_missing_from_current_corpus: number;
    reviewed_label_occurrences_eligible_before_scoring: number;
    reviewed_label_occurrences_matched_after_scoring: number;
    interpretation_zh: string;
  };
  business_findings_zh: string[];
  ranking_comparison: null | {
    candidate_state: "candidate_not_evidence";
    same_object_population_count: number;
    route_summaries: Record<string, {
      qrel_count: number;
      mapped_current_target_count: number;
      typed_target_gap_count: number;
      recall_at_10_all_qrels: number;
      recall_at_10_mapped_targets: number;
      mrr_mapped_targets: number;
      automatic_business_error_counts_in_top3: Record<string, number>;
    }>;
    queries: Array<{
      query_id: string;
      evidence_slot_id: string;
      evidence_owner_ticker: string;
      routes: Record<string, {
        candidates: Array<{
          candidate_state: "candidate_not_evidence";
          rank: number;
          source_record_id: string;
          evidence_owner_ticker: string;
          source_type: string;
          publication_date: string;
          section: string;
          subsection: string;
          score: number;
          excerpt: string;
        }>;
      }>;
    }>;
    known_boundary: string;
    projection_digest: string;
  };
  canonical_spine?: S1CanonicalSpineView | null;
  lanes: RetrievalLane[];
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

  getRetrieval(caseKey: string, signal?: AbortSignal): Promise<ResearchRetrievalView> {
    return getJson<ResearchRetrievalView>(
      `/api/v1/research-cases/${encodeURIComponent(caseKey)}/retrieval`,
      signal,
    );
  }
}
