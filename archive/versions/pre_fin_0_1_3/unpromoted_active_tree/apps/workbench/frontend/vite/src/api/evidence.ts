import { CASES_PATH, FixtureCaseContext } from "./cases";

export type EvidenceCandidateState = "candidate" | "context_only" | "rejected";
export type EvidenceGapState = "typed_gap" | "repair_requested";
export type EvidenceWorkbenchStatus = "not_prepared" | "prepared";

export type CompileEvidenceFixtureCommand = {
  expected_workspace_version: number;
  actor_ref: string;
  idempotency_key: string;
};

export type RejectEvidenceCandidateCommand = {
  expected_workspace_version: number;
  reason: string;
  actor_ref: string;
  idempotency_key: string;
};

export type RequestEvidenceRepairCommand = {
  expected_workspace_version: number;
  reason: string;
  actor_ref: string;
  idempotency_key: string;
};

export type ExecuteEvidenceRepairCommand = {
  expected_workspace_version: number;
  actor_ref: string;
  idempotency_key: string;
};

export type EvidenceWorkbenchSummary = {
  candidate_count: number;
  context_only_count: number;
  rejected_count: number;
  gap_count: number;
  repair_requested_count: number;
  repair_completed_count: number;
};

export type EvidenceRepairOutcomeView = {
  repair_outcome_id: string;
  evidence_slot_id: string;
  status: string;
  candidate_id: string;
  route_id: string;
  outcome_boundary: string;
  completed_at: string;
};

export type EvidenceCandidateView = {
  candidate_id: string;
  evidence_slot_id: string;
  state: EvidenceCandidateState;
  candidate_kind: string;
  title: string;
  excerpt: string;
  source_name: string;
  source_type: string;
  published_at: string;
  citation: string;
  authority_label: string;
  source_authority_rank: number;
  applicability_boundary: string;
  document_id: string;
  document_version: string;
  section_or_table_ref: string;
  source_policy_ref: string;
  route_id: string;
  source_role: string;
  entity_ref: string;
  period_ref: string;
  rejection_reason?: string | null;
  reviewed_at?: string | null;
};

export type EvidenceGapView = {
  gap_id: string;
  evidence_slot_id: string;
  state: EvidenceGapState;
  gap_code: string;
  title: string;
  detail: string;
  stop_rule: string;
  repair_reason?: string | null;
  requested_at?: string | null;
};

export type EvidenceCellSectionView = {
  cell_id: string;
  decision_question: string;
  owner: string;
  materiality: string;
  evidence_slot_id: string;
  evidence_role: string;
  request_id: string;
  bundle_status: string;
  candidates: EvidenceCandidateView[];
  typed_gap?: EvidenceGapView | null;
};

export type EvidenceWorkbenchView = {
  case_id: string;
  workspace_version: number;
  case_version: number;
  decision_surface_contract_version: number;
  checkpoint_version: number;
  work_unit_id: string;
  work_unit_version: number;
  status: EvidenceWorkbenchStatus;
  prepared_at?: string | null;
  summary: EvidenceWorkbenchSummary;
  cells: EvidenceCellSectionView[];
  repair_outcomes: EvidenceRepairOutcomeView[];
};

export type LocalResearchCandidateView = {
  candidate_id: string;
  retrieval_lane: "object_bm25" | "gold_fact_sql" | "research_graph";
  rank: number;
  score: number | null;
  ticker: string;
  title: string;
  excerpt: string;
  source_name: string;
  source_type: string;
  published_at: string;
  citation_url: string;
  citation_span: string;
  evidence_ref: string;
  authority_mode: string;
  claim_boundary: string;
  exact_value_authority: boolean;
  numeric_eligible: boolean;
  metric_family?: string;
  value?: string;
  unit?: string;
  period?: string;
  writer_citable: false;
  promotion_status: "candidate_not_promoted";
};

export type LocalResearchCellView = {
  cell_key: string;
  evidence_role: string;
  decision_question: string;
  retrieval_lane: LocalResearchCandidateView["retrieval_lane"];
  status: "candidate_ready" | "typed_gap";
  typed_gap: string | null;
  candidates: LocalResearchCandidateView[];
};

export type LocalResearchPreviewView = {
  preview_digest: string;
  case_id: string;
  case_version: number;
  query: string;
  as_of: string;
  research_mode: "bounded_local_read_only";
  status: "candidate_preview_ready";
  selected_cell_count: number;
  candidate_count: number;
  cells: LocalResearchCellView[];
  source_inventory: Array<{
    source_id: string;
    schema_version: string;
    record_count: number;
    snapshot_digest: string;
  }>;
  execution_counts: Record<string, number>;
  boundary: string;
};

export type LocalAnalysisFactView = {
  candidate_id: string;
  metric_family: string;
  label: string;
  value: string;
  unit: string;
  period: string;
  source_ref: string;
  exact_value_authority: boolean;
};

export type LocalAnalysisDerivedMetricView = {
  metric: string;
  label: string;
  value: string;
  unit: string;
  formula: string;
  input_candidate_ids: string[];
};

export type LocalAnalysisRepairView = {
  repair_id: string;
  evidence_role: string;
  decision: string;
  reason: string;
  candidate_refs: string[];
  remaining_gap: string;
  external_execution: false;
  promotion_authorized: false;
};

export type LocalAnalysisJudgmentView = {
  judgment_id: string;
  cell_key: string;
  evidence_role: string;
  decision_question: string;
  confidence: string;
  judgment_zh_cn: string;
  judgment_en: string;
  evidence_refs: string[];
  numeric_refs: string[];
  repair_ref: string;
  counter_thesis_zh_cn: string;
  what_would_change_en: string;
  remaining_gaps: string[];
  status: string;
};

export type LocalAnalysisPreviewView = {
  analysis_digest: string;
  case_id: string;
  case_version: number;
  source_preview_digest: string;
  analysis_mode: "bounded_local_deterministic_preview";
  status: "internal_analysis_preview_ready";
  numeric: {
    status: string;
    facts: LocalAnalysisFactView[];
    derived_metrics: LocalAnalysisDerivedMetricView[];
    typed_gaps: string[];
    writer_citable: false;
  };
  repairs: LocalAnalysisRepairView[];
  judgments: LocalAnalysisJudgmentView[];
  workpaper: {
    content_digest: string;
    status: string;
    senior_r2_status: string;
    sections: Array<Record<string, unknown>>;
  };
  writer: {
    content_digest: string;
    mode: "deterministic_no_source_internal_composer";
    status: string;
    title_zh_cn: string;
    title_en: string;
    sections: Array<{
      section_id: string;
      evidence_role: string;
      judgment_ref: string;
      heading_zh_cn: string;
      content_zh_cn: string;
      content_en: string;
    }>;
    input_workpaper_digest: string;
    source_preview_digest: string;
    source_access_calls: 0;
    model_calls: 0;
    release_admitted: false;
  };
  execution_counts: Record<string, number>;
  hard_boundaries: Record<string, number>;
  boundary: string;
};

const localResearchPreviewInFlight = new Map<string, Promise<LocalResearchPreviewView>>();
const localAnalysisPreviewInFlight = new Map<string, Promise<LocalAnalysisPreviewView>>();

type EvidenceWireCandidate = {
  candidate_id: string;
  display_state: EvidenceCandidateState;
  candidate_kind: string;
  title: string;
  excerpt: string;
  source_name: string;
  source_type: string;
  published_at: string;
  citation: string;
  authority_label: string;
  source_authority_rank: number;
  applicability_boundary: string;
  document_id: string;
  document_version: string;
  section_or_table_ref: string;
  source_policy_ref: string;
  route_id: string;
  source_role: string;
  entity_ref: string;
  period_ref: string;
  review_reason?: string | null;
};

type EvidenceWireSlot = {
  cell_id: string;
  decision_question: string;
  owner: string;
  required: boolean;
  evidence_slot_id: string;
  evidence_role: string;
  request_id: string;
  bundle_id: string;
  bundle_status: string;
  display_state: "candidate" | EvidenceGapState;
  typed_gap_codes: string[];
  candidates: EvidenceWireCandidate[];
};

type EvidenceWireReviewAction = {
  action_type: "reject_candidate" | "request_repair";
  evidence_slot_id: string;
  candidate_id?: string | null;
  reason: string;
  recorded_at: string;
};

type EvidenceWireRepairOutcome = {
  repair_outcome_id: string;
  evidence_slot_id: string;
  request_review_action_id: string;
  attempt_no: number;
  attempt_state: string;
  route_id: string;
  candidate_id: string;
  completed_at: string;
  external_call_count: number;
  tool_invocation_count: number;
  boundary: string;
};

type EvidenceWireView = {
  case_id: string;
  workspace_version: number;
  status: string;
  work_unit_id: string;
  counts: {
    candidate_count: number;
    context_only_count: number;
    rejected_count: number;
    typed_gap_count: number;
    repair_requested_count: number;
    repair_completed_count: number;
  };
  slots: EvidenceWireSlot[];
  review_actions: EvidenceWireReviewAction[];
  repair_outcomes: EvidenceWireRepairOutcome[];
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

export class EvidenceApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly traceId: string | undefined;
  readonly detail: unknown;

  constructor(input: { code: string; message: string; statusCode: number; traceId?: string; detail?: unknown }) {
    super(input.message);
    this.name = "EvidenceApiError";
    this.code = input.code;
    this.statusCode = input.statusCode;
    this.traceId = input.traceId;
    this.detail = input.detail;
  }
}

export const DEFAULT_FIXTURE_EVIDENCE_CONTEXT: FixtureCaseContext = {
  tenantId: "fixture_internal",
  projectId: "workbench_internal",
  actorId: "analyst_internal",
  permissions: [
    "case:read",
    "planning:read",
    "execution:read",
    "evidence:read",
    "evidence:write",
    "evidence:review",
    "evidence:repair",
    "numeric:read",
  ],
};

export class EvidenceApiClient {
  constructor(private readonly context: FixtureCaseContext = DEFAULT_FIXTURE_EVIDENCE_CONTEXT) {}

  get actorRef(): string {
    return this.context.actorId;
  }

  async getEvidenceWorkbench(caseId: string): Promise<EvidenceWorkbenchView> {
    return normalizeEvidenceWorkbench(await this.request<EvidenceWireView>(evidencePath(caseId)));
  }

  async getLocalResearchPreview(caseId: string): Promise<LocalResearchPreviewView> {
    return shareInFlight(
      localResearchPreviewInFlight,
      `${this.context.tenantId}:${this.context.projectId}:${this.context.actorId}:${caseId}`,
      () => this.request<LocalResearchPreviewView>(
        `${CASES_PATH}/${encodeURIComponent(caseId)}/local-research-preview`,
      ),
    );
  }

  async getLocalAnalysisPreview(caseId: string): Promise<LocalAnalysisPreviewView> {
    return shareInFlight(
      localAnalysisPreviewInFlight,
      `${this.context.tenantId}:${this.context.projectId}:${this.context.actorId}:${caseId}`,
      () => this.request<LocalAnalysisPreviewView>(
        `${CASES_PATH}/${encodeURIComponent(caseId)}/local-analysis-preview`,
      ),
    );
  }

  async compileEvidenceFixture(caseId: string, command: CompileEvidenceFixtureCommand): Promise<EvidenceWorkbenchView> {
    return normalizeEvidenceWorkbench(
      await this.request<EvidenceWireView>(`${evidencePath(caseId)}/compile`, mutationInit(command)),
    );
  }

  async rejectEvidenceCandidate(
    caseId: string,
    candidateId: string,
    command: RejectEvidenceCandidateCommand,
  ): Promise<EvidenceWorkbenchView> {
    return normalizeEvidenceWorkbench(
      await this.request<EvidenceWireView>(
        `${evidencePath(caseId)}/candidates/${encodeURIComponent(candidateId)}/reject`,
        mutationInit(command),
      ),
    );
  }

  async requestEvidenceRepair(
    caseId: string,
    evidenceSlotId: string,
    command: RequestEvidenceRepairCommand,
  ): Promise<EvidenceWorkbenchView> {
    return normalizeEvidenceWorkbench(
      await this.request<EvidenceWireView>(
        `${evidencePath(caseId)}/slots/${encodeURIComponent(evidenceSlotId)}/request-repair`,
        mutationInit(command),
      ),
    );
  }

  async executeEvidenceRepair(
    caseId: string,
    evidenceSlotId: string,
    command: ExecuteEvidenceRepairCommand,
  ): Promise<EvidenceWorkbenchView> {
    return normalizeEvidenceWorkbench(
      await this.request<EvidenceWireView>(
        `${evidencePath(caseId)}/slots/${encodeURIComponent(evidenceSlotId)}/execute-repair`,
        mutationInit(command),
      ),
    );
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
      throw new EvidenceApiError({
        code: "network_unavailable",
        message: "The fixture Evidence API is unavailable.",
        statusCode: 0,
        detail: error,
      });
    }

    const text = await response.text();
    const payload = text ? parsePayload(text) : {};
    if (!response.ok) throw toEvidenceApiError(response.status, payload);
    return payload as T;
  }
}

function shareInFlight<T>(registry: Map<string, Promise<T>>, key: string, request: () => Promise<T>): Promise<T> {
  const current = registry.get(key);
  if (current) return current;
  const pending = request();
  registry.set(key, pending);
  const release = () => {
    if (registry.get(key) === pending) registry.delete(key);
  };
  void pending.then(release, release);
  return pending;
}

function normalizeEvidenceWorkbench(wire: EvidenceWireView): EvidenceWorkbenchView {
  const repairBySlot = new Map(
    wire.review_actions
      .filter((action) => action.action_type === "request_repair")
      .map((action) => [action.evidence_slot_id, action]),
  );
  return {
    case_id: wire.case_id,
    workspace_version: wire.workspace_version,
    case_version: 0,
    decision_surface_contract_version: 0,
    checkpoint_version: 0,
    work_unit_id: wire.work_unit_id,
    work_unit_version: 1,
    status: "prepared",
    summary: {
      candidate_count: wire.counts.candidate_count,
      context_only_count: wire.counts.context_only_count,
      rejected_count: wire.counts.rejected_count,
      gap_count: wire.counts.typed_gap_count,
      repair_requested_count: wire.counts.repair_requested_count,
      repair_completed_count: wire.counts.repair_completed_count,
    },
    repair_outcomes: wire.repair_outcomes.map((outcome) => ({
      repair_outcome_id: outcome.repair_outcome_id,
      evidence_slot_id: outcome.evidence_slot_id,
      status: outcome.attempt_state,
      candidate_id: outcome.candidate_id,
      route_id: outcome.route_id,
      outcome_boundary: outcome.boundary,
      completed_at: outcome.completed_at,
    })),
    cells: wire.slots.map((slot) => {
      const repair = repairBySlot.get(slot.evidence_slot_id);
      const gapCode = slot.typed_gap_codes[0];
      return {
        cell_id: slot.cell_id,
        decision_question: slot.decision_question,
        owner: slot.owner,
        materiality: slot.required ? "required" : "optional",
        evidence_slot_id: slot.evidence_slot_id,
        evidence_role: slot.evidence_role,
        request_id: slot.request_id,
        bundle_status: slot.bundle_status,
        candidates: slot.candidates.map((candidate) => ({
          ...candidate,
          evidence_slot_id: slot.evidence_slot_id,
          state: candidate.display_state,
          rejection_reason: candidate.review_reason,
        })),
        typed_gap: gapCode ? {
          gap_id: `${slot.bundle_id}:${gapCode}`,
          evidence_slot_id: slot.evidence_slot_id,
          state: repair ? "repair_requested" : "typed_gap",
          gap_code: gapCode,
          title: "No usable candidate",
          detail: "The bounded fixture route returned no candidate for this required evidence role.",
          stop_rule: "fixture_candidate_absent",
          repair_reason: repair?.reason,
          requested_at: repair?.recorded_at,
        } : null,
      };
    }),
  };
}

function evidencePath(caseId: string): string {
  return `${CASES_PATH}/${encodeURIComponent(caseId)}/evidence`;
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

function toEvidenceApiError(statusCode: number, payload: unknown): EvidenceApiError {
  const envelope = errorEnvelope(payload);
  const nested = errorEnvelope(envelope.detail);
  const error = envelope.error ?? nested.error;
  return new EvidenceApiError({
    code: error?.error_code ?? envelope.code ?? nested.code ?? `http_${statusCode}`,
    message: error?.message ?? envelope.message ?? nested.message ?? detailMessage(envelope.detail) ?? "Evidence request failed.",
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
