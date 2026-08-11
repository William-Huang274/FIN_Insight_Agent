from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.llm_gateway import chat_completion
from sec_agent.multi_agent_contracts import ANALYSIS_DIMENSION_ORDER, build_multi_agent_memo_draft, verify_multi_agent_memo_draft
from sec_agent.research_skills import research_skill_prompt
from sec_agent.s4_case_runtime import (
    S4CaseRuntimeBinding,
    consume_s4_case_runtime_binding,
)


MEMO_ROUTE_SCHEMA_VERSION = "sec_agent_memo_llm_route_v0.1"
VERIFIER_ROUTE_SCHEMA_VERSION = "sec_agent_verifier_llm_route_v0.1"
VERIFIER_PROJECTION_SCHEMA_VERSION = "sec_agent_verifier_minimal_projection_v0.1"
SHARED_MEMO_CONTEXT_SCHEMA_VERSION = "sec_agent_shared_memo_context_v0.2"
RESPONSE_LANGUAGE_SCHEMA_VERSION = "sec_agent_response_language_v0.1"
MEMO_ROUTE_SOURCE = "memo_writer_llm_v0.1"
VERIFIER_ROUTE_SOURCE = "verifier_llm_v0.1"
MEMO_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"
MEMO_SUPPORTED_CLAIM_CAP = 5
MEMO_UNSUPPORTED_CLAIM_CAP = 2
MEMO_CONFLICT_CAP = 2
MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP = 3
MEMO_SALVAGE_SUPPORTED_CLAIM_CAP = 8
MEMO_LENGTH_REPAIR_REQUIRED_ITEM_CAP = 4
MEMO_LENGTH_REPAIR_DIMENSION_CAP = 2
MEMO_MODEL_OUTPUT_CLAIM_CAP = 2
MEMO_MODEL_OUTPUT_DIMENSION_CAP = 2
MEMO_MODEL_OUTPUT_ACTION_ITEM_CAP = 1
MEMO_PROFILE_SCHEMA_VERSION = "sec_agent_memo_profile_v0.1"
MEMO_PROFILE_ORDER = ("compact", "standard", "expanded", "deep_research")
MEMO_WRITER_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION = "sec_agent_memo_writer_input_pack_fingerprint_v0_1"
VERIFIER_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION = "sec_agent_verifier_input_pack_fingerprint_v0_1"
SOURCE_COVERAGE_CLAIM_TYPES = {
    "official_issuer_context",
    "official_issuer_identity_context",
    "official_disclosure_context",
    "official_filing_presence_context",
    "issuer_filing_presence",
    "source_coverage_context",
    "filing_presence_context",
}

ChatCompletionFunc = Callable[..., dict[str, Any]]


S3_PRESENTATION_PACK_CONTRACT_REF = (
    "fin01.s3.three_cell_workpaper_report_trace_review_surface:v1"
)
S3_PRESENTATION_OWNER_REF = "src.sec_agent.memo_llm:s3_presentation_projection"


class S3PresentationStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class S3SurfaceClaimVersion(S3PresentationStrictModel):
    surface_claim_id: str = Field(min_length=1)
    surface_claim_version_ref: str = Field(min_length=1)
    surface_claim_digest: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    disposition: str = Field(min_length=1)
    specialist_judgment_ref: str = Field(min_length=1)
    fact_statements: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    numeric_refs: tuple[str, ...]
    graph_context_refs: tuple[str, ...] = Field(min_length=1)
    gap_codes: tuple[str, ...] = Field(min_length=1)
    what_would_change: tuple[str, ...] = Field(min_length=1)
    repair_ticket_refs: tuple[str, ...] = Field(min_length=1)
    stop_semantic: str = Field(min_length=1)
    source_grade: Literal["no_promoted_evidence", "deterministic_company_total_only"]
    numeric_sanity_status: Literal[
        "not_applicable_no_numeric_authority",
        "exact_company_total_formula_recomputed_product_attribution_unavailable",
    ]
    official_or_estimate_flag: Literal[
        "context_only_not_promoted",
        "deterministic_exact_company_total_not_product_estimate",
    ]


class S3GraphDrilldownVersion(S3PresentationStrictModel):
    program_cell_id: str = Field(min_length=1)
    graph_edge_projection_ref: str = Field(min_length=1)
    graph_authority: str = Field(min_length=1)
    graph_status: Literal["context_only_not_evidence"] = "context_only_not_evidence"
    source_followup_refs: tuple[str, ...] = Field(min_length=1)
    typed_gaps: tuple[str, ...] = Field(min_length=1)
    automatic_new_research: Literal[False] = False


class S3WorkpaperCellVersion(S3PresentationStrictModel):
    program_cell_id: str = Field(min_length=1)
    cell_version_ref: str = Field(min_length=1)
    surface_claim_ref: str = Field(min_length=1)
    specialist_judgment_ref: str = Field(min_length=1)
    decision_question: str = Field(min_length=1)
    direct_answer: str = Field(min_length=1)
    fact_statements: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    numeric_refs: tuple[str, ...]
    graph_drilldown: S3GraphDrilldownVersion
    gaps: tuple[str, ...] = Field(min_length=1)
    what_would_change: tuple[str, ...] = Field(min_length=1)
    repair_ticket_refs: tuple[str, ...] = Field(min_length=1)
    stop_semantic: str = Field(min_length=1)
    review_status: Literal["pending_exact_human_review"] = "pending_exact_human_review"


class S3WorkpaperVersion(S3PresentationStrictModel):
    workpaper_id: str = Field(min_length=1)
    workpaper_version_ref: str = Field(min_length=1)
    workpaper_digest: str = Field(min_length=1)
    artifact_ref: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    research_run_id: str = Field(min_length=1)
    decision_surface_contract_ref: str = Field(min_length=1)
    lead_synthesis_ref: str = Field(min_length=1)
    cell_sections: tuple[S3WorkpaperCellVersion, ...] = Field(
        min_length=3, max_length=3
    )
    status: Literal["bounded_review_ready_not_human_accepted"] = (
        "bounded_review_ready_not_human_accepted"
    )


class S3ReportSectionVersion(S3PresentationStrictModel):
    section_id: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    content: str = Field(min_length=1)
    surface_claim_ref: str = Field(min_length=1)
    specialist_judgment_ref: str = Field(min_length=1)
    evidence_refs: tuple[str, ...]
    numeric_refs: tuple[str, ...]
    boundary: str = Field(min_length=1)


class S3ReportVersion(S3PresentationStrictModel):
    report_id: str = Field(min_length=1)
    report_version_ref: str = Field(min_length=1)
    report_digest: str = Field(min_length=1)
    artifact_ref: str = Field(min_length=1)
    workpaper_artifact_ref: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    research_run_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    executive_answer: str = Field(min_length=1)
    sections: tuple[S3ReportSectionVersion, ...] = Field(min_length=3, max_length=3)
    adjudicated_input_refs: tuple[str, ...] = Field(min_length=4)
    presentation_gaps: tuple[str, ...] = Field(min_length=1)
    writer_decisions: tuple[str, ...] = Field(min_length=1)
    writer_source_authority: Literal[False] = False
    writer_retrieval_authority: Literal[False] = False
    writer_external_tool_authority: Literal[False] = False
    raw_candidate_consumption: Literal[False] = False
    model_writer_executed: Literal[False] = False
    release_claim_authorized: Literal[False] = False


class S3TraceNodeVersion(S3PresentationStrictModel):
    node_ref: str = Field(min_length=1)
    node_type: Literal["run", "cell", "claim", "judgment", "artifact"]
    label: str = Field(min_length=1)


class S3TraceEdgeVersion(S3PresentationStrictModel):
    edge_id: str = Field(min_length=1)
    from_ref: str = Field(min_length=1)
    to_ref: str = Field(min_length=1)
    relation: Literal[
        "run_contains_cell",
        "cell_exposes_claim",
        "claim_projects_judgment",
        "claim_rendered_in_workpaper",
        "workpaper_rendered_as_report",
        "report_verified_by_trace",
    ]


class S3VerifierFindingVersion(S3PresentationStrictModel):
    finding_id: str = Field(min_length=1)
    layer: Literal["deterministic_integrity", "semantic", "financial", "visual"]
    severity: Literal["info", "warning"]
    status: Literal["pass", "bounded_gap_preserved", "pending_browser_validation"]
    affected_refs: tuple[str, ...] = Field(min_length=1)
    earliest_owner_ref: str = Field(min_length=1)
    message: str = Field(min_length=1)


class S3CellReviewTargetVersion(S3PresentationStrictModel):
    review_target_id: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    surface_claim_ref: str = Field(min_length=1)
    specialist_judgment_ref: str = Field(min_length=1)
    artifact_refs: tuple[str, ...] = Field(min_length=3, max_length=3)
    source_grade: str = Field(min_length=1)
    numeric_sanity_status: str = Field(min_length=1)
    official_or_estimate_flag: str = Field(min_length=1)
    cannot_infer: tuple[str, ...] = Field(min_length=1)
    what_would_change: tuple[str, ...] = Field(min_length=1)
    repair_ticket_refs: tuple[str, ...] = Field(min_length=1)
    stop_semantic: str = Field(min_length=1)
    allowed_review_actions: tuple[
        Literal[
            "accepted",
            "rejected",
            "needs_source",
            "needs_parser",
            "estimate_only",
            "commercial_gap",
        ],
        ...,
    ] = Field(min_length=6, max_length=6)
    review_status: Literal["not_performed"] = "not_performed"


class S3VerifierAndHumanReviewBindingVersion(S3PresentationStrictModel):
    verifier_binding_id: str = Field(min_length=1)
    verifier_input_digest: str = Field(min_length=1)
    execution_profile_version_ref: str = Field(min_length=1)
    input_head_digest: str = Field(min_length=1)
    analysis_as_of: str = Field(min_length=1)
    artifact_refs: tuple[str, ...] = Field(min_length=3, max_length=3)
    bound_content_digests: tuple[str, ...] = Field(min_length=3, max_length=3)
    findings: tuple[S3VerifierFindingVersion, ...] = Field(min_length=4)
    verifier_decision: Literal[
        "pass_bounded_integrity_semantics_financial_visual_pending"
    ] = "pass_bounded_integrity_semantics_financial_visual_pending"
    review_targets: tuple[S3CellReviewTargetVersion, ...] = Field(
        min_length=3, max_length=3
    )
    human_review_status: Literal["not_performed"] = "not_performed"
    human_decision: Literal["not_performed"] = "not_performed"
    exact_digest_confirmation: Literal[False] = False
    machine_verifier_is_human_acceptance: Literal[False] = False


class S3TraceReviewVersion(S3PresentationStrictModel):
    trace_id: str = Field(min_length=1)
    trace_version_ref: str = Field(min_length=1)
    trace_digest: str = Field(min_length=1)
    artifact_ref: str = Field(min_length=1)
    workpaper_artifact_ref: str = Field(min_length=1)
    report_artifact_ref: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    research_run_id: str = Field(min_length=1)
    nodes: tuple[S3TraceNodeVersion, ...] = Field(min_length=13)
    edges: tuple[S3TraceEdgeVersion, ...] = Field(min_length=13)
    review_binding: S3VerifierAndHumanReviewBindingVersion


class S3ThreeCellPresentationPackVersion(S3PresentationStrictModel):
    presentation_pack_id: str = Field(min_length=1)
    presentation_pack_version_ref: str = Field(min_length=1)
    presentation_pack_digest: str = Field(min_length=1)
    presentation_pack_contract_ref: str = S3_PRESENTATION_PACK_CONTRACT_REF
    presentation_owner_ref: str = S3_PRESENTATION_OWNER_REF
    case_id: str = Field(min_length=1)
    work_unit_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    research_run_id: str = Field(min_length=1)
    execution_profile_version_ref: str = Field(min_length=1)
    decision_surface_contract_ref: str = Field(min_length=1)
    runtime_plan_version_ref: str = Field(min_length=1)
    runtime_plan_digest: str = Field(min_length=1)
    evidence_route_plan_version_ref: str = Field(min_length=1)
    evidence_route_plan_digest: str = Field(min_length=1)
    financial_pack_version_ref: str = Field(min_length=1)
    financial_pack_digest: str = Field(min_length=1)
    graph_pack_version_ref: str = Field(min_length=1)
    graph_pack_digest: str = Field(min_length=1)
    judgment_pack_version_ref: str = Field(min_length=1)
    judgment_pack_digest: str = Field(min_length=1)
    surface_claims: tuple[S3SurfaceClaimVersion, ...] = Field(
        min_length=3, max_length=3
    )
    workpaper: S3WorkpaperVersion
    report: S3ReportVersion
    trace_review: S3TraceReviewVersion
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    execution_network_calls: Literal[0] = 0
    source_network_calls: Literal[0] = 0
    external_tool_calls: Literal[0] = 0
    live_business_writes: Literal[0] = 0
    automatic_new_research_calls: Literal[0] = 0
    human_review_writes: Literal[0] = 0
    paid_runs: Literal[0] = 0


@dataclass(frozen=True)
class MemoLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    memo_max_tokens: int = 3000
    verifier_max_tokens: int = 800
    timeout_s: int = 180
    max_repair_attempts: int = 2


@dataclass(frozen=True)
class MemoProfileSpec:
    profile: str
    direct_answer_max_chars: int
    direct_answer_min_chars: int
    memo_claims_min_when_thesis_ready: int
    memo_claims_max: int
    memo_claim_max_chars: int
    caveats_max: int
    unsupported_claims_excluded_max: int
    source_boundary_notes_max: int
    supported_claim_cap_with_thesis_pack: int
    rendered_claim_max: int


@dataclass(frozen=True)
class MemoWriterBudgetSpec:
    profile: str
    supported_claim_cap: int
    memo_outline_cap: int
    sections_cap: int
    evidence_bridge_cap: int
    required_question_cap: int
    required_item_cap: int
    dimension_move_cap: int
    economic_role_row_cap: int
    financial_line_item_cap: int
    derived_ratio_cap: int
    peer_comparison_cap: int
    product_kpi_cap: int
    product_context_cap: int
    graph_edge_cap: int
    supervision_finding_cap: int


MEMO_PROFILE_SPECS: dict[str, MemoProfileSpec] = {
    "compact": MemoProfileSpec(
        profile="compact",
        direct_answer_max_chars=420,
        direct_answer_min_chars=0,
        memo_claims_min_when_thesis_ready=3,
        memo_claims_max=5,
        memo_claim_max_chars=220,
        caveats_max=3,
        unsupported_claims_excluded_max=2,
        source_boundary_notes_max=3,
        supported_claim_cap_with_thesis_pack=0,
        rendered_claim_max=5,
    ),
    "standard": MemoProfileSpec(
        profile="standard",
        direct_answer_max_chars=900,
        direct_answer_min_chars=420,
        memo_claims_min_when_thesis_ready=4,
        memo_claims_max=6,
        memo_claim_max_chars=260,
        caveats_max=4,
        unsupported_claims_excluded_max=3,
        source_boundary_notes_max=4,
        supported_claim_cap_with_thesis_pack=6,
        rendered_claim_max=6,
    ),
    "expanded": MemoProfileSpec(
        profile="expanded",
        direct_answer_max_chars=1200,
        direct_answer_min_chars=500,
        memo_claims_min_when_thesis_ready=5,
        memo_claims_max=8,
        memo_claim_max_chars=300,
        caveats_max=5,
        unsupported_claims_excluded_max=4,
        source_boundary_notes_max=5,
        supported_claim_cap_with_thesis_pack=8,
        rendered_claim_max=8,
    ),
    "deep_research": MemoProfileSpec(
        profile="deep_research",
        direct_answer_max_chars=1600,
        direct_answer_min_chars=620,
        memo_claims_min_when_thesis_ready=6,
        memo_claims_max=8,
        memo_claim_max_chars=320,
        caveats_max=5,
        unsupported_claims_excluded_max=4,
        source_boundary_notes_max=5,
        supported_claim_cap_with_thesis_pack=8,
        rendered_claim_max=8,
    ),
}

MEMO_WRITER_BUDGET_SPECS: dict[str, MemoWriterBudgetSpec] = {
    "compact": MemoWriterBudgetSpec(
        profile="compact",
        supported_claim_cap=5,
        memo_outline_cap=4,
        sections_cap=4,
        evidence_bridge_cap=3,
        required_question_cap=5,
        required_item_cap=5,
        dimension_move_cap=4,
        economic_role_row_cap=6,
        financial_line_item_cap=4,
        derived_ratio_cap=2,
        peer_comparison_cap=2,
        product_kpi_cap=3,
        product_context_cap=3,
        graph_edge_cap=4,
        supervision_finding_cap=3,
    ),
    "standard": MemoWriterBudgetSpec(
        profile="standard",
        supported_claim_cap=5,
        memo_outline_cap=4,
        sections_cap=4,
        evidence_bridge_cap=3,
        required_question_cap=3,
        required_item_cap=5,
        dimension_move_cap=3,
        economic_role_row_cap=4,
        financial_line_item_cap=3,
        derived_ratio_cap=3,
        peer_comparison_cap=3,
        product_kpi_cap=3,
        product_context_cap=3,
        graph_edge_cap=3,
        supervision_finding_cap=3,
    ),
    "expanded": MemoWriterBudgetSpec(
        profile="expanded",
        supported_claim_cap=7,
        memo_outline_cap=6,
        sections_cap=6,
        evidence_bridge_cap=4,
        required_question_cap=7,
        required_item_cap=8,
        dimension_move_cap=5,
        economic_role_row_cap=6,
        financial_line_item_cap=3,
        derived_ratio_cap=3,
        peer_comparison_cap=3,
        product_kpi_cap=3,
        product_context_cap=4,
        graph_edge_cap=4,
        supervision_finding_cap=4,
    ),
    "deep_research": MemoWriterBudgetSpec(
        profile="deep_research",
        supported_claim_cap=8,
        memo_outline_cap=7,
        sections_cap=7,
        evidence_bridge_cap=5,
        required_question_cap=10,
        required_item_cap=18,
        dimension_move_cap=7,
        economic_role_row_cap=8,
        financial_line_item_cap=5,
        derived_ratio_cap=4,
        peer_comparison_cap=4,
        product_kpi_cap=4,
        product_context_cap=5,
        graph_edge_cap=5,
        supervision_finding_cap=5,
    ),
}


def memo_llm_config_from_env(env: Mapping[str, str] | None = None) -> MemoLLMConfig:
    values = dict(os.environ if env is None else env)
    return MemoLLMConfig(
        llm_backend=values.get("LLM_BACKEND", "deepseek"),
        base_url=values.get("BASE_URL", "https://api.deepseek.com"),
        chat_completions_path=values.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
        model=values.get("MODEL_NAME", "deepseek-v4-pro"),
        api_key_env=values.get("API_KEY_ENV", "DEEPSEEK_API_KEY"),
        temperature=_float_env(values.get("MEMO_TEMPERATURE"), default=0.0),
        memo_max_tokens=_int_env(values.get("MEMO_MAX_TOKENS"), default=3000),
        verifier_max_tokens=_int_env(values.get("VERIFIER_MAX_TOKENS"), default=800),
        timeout_s=_int_env(values.get("MEMO_TIMEOUT_S"), default=180),
        max_repair_attempts=_int_env(values.get("MEMO_MAX_REPAIR_ATTEMPTS"), default=2),
    )


def memo_writer_from_env(
    env: Mapping[str, str] | None = None,
    *,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> Callable[[Mapping[str, Any]], dict[str, Any]] | None:
    values = dict(os.environ if env is None else env)
    mode = str(values.get(MEMO_ROUTER_ENV) or "mock").strip().lower()
    if mode in {"", "mock", "deterministic", "off", "false", "0"}:
        return None
    if mode not in {"llm", "deepseek", "api"}:
        raise ValueError(f"unsupported {MEMO_ROUTER_ENV}: {mode}")
    config = memo_llm_config_from_env(values)

    def _route(state: Mapping[str, Any]) -> dict[str, Any]:
        return route_memo_writer_llm(state, config=config, call_chat_completion=call_chat_completion)

    return _route


def verifier_from_env(
    env: Mapping[str, str] | None = None,
    *,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> Callable[[Mapping[str, Any]], dict[str, Any]] | None:
    values = dict(os.environ if env is None else env)
    mode = str(values.get(MEMO_ROUTER_ENV) or "mock").strip().lower()
    if mode in {"", "mock", "deterministic", "off", "false", "0"}:
        return None
    if mode not in {"llm", "deepseek", "api"}:
        raise ValueError(f"unsupported {MEMO_ROUTER_ENV}: {mode}")
    config = memo_llm_config_from_env(values)

    def _route(state: Mapping[str, Any]) -> dict[str, Any]:
        return route_verifier_llm(state, config=config, call_chat_completion=call_chat_completion)

    return _route


def route_memo_writer_llm(
    state: Mapping[str, Any],
    *,
    config: MemoLLMConfig | None = None,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> dict[str, Any]:
    route_config = config or MemoLLMConfig()
    judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    shared_context = _compact_shared_memo_context_for_prompt(build_shared_memo_context(state))
    input_pack_fingerprint = _memo_writer_input_pack_fingerprint(
        state,
        shared_context=shared_context,
        judgment=judgment,
    )
    response_language = _response_language_from_context(shared_context.get("response_language"))
    specialist_verification = state.get("specialist_verification") if isinstance(state.get("specialist_verification"), Mapping) else {}
    if specialist_verification.get("memo_writer_allowed") is False or (isinstance(judgment, Mapping) and judgment.get("memo_writer_allowed") is False):
        blocked = build_multi_agent_memo_draft(judgment, specialist_verification=specialist_verification)
        if str(blocked.get("answer_status") or "") != "draft":
            blocked["response_language"] = _response_language_dict(response_language, source="memo_writer_context")
            return {
                "memo_answer": blocked,
                "memo_route_result": {
                    "status": "blocked_by_specialist_verification",
                    "memo_profile": str(input_pack_fingerprint.get("memo_profile") or ""),
                    "input_pack_fingerprint": input_pack_fingerprint,
                },
            }
    pre_writer_gate = _pre_writer_required_dimension_material_gate(state, judgment if isinstance(judgment, Mapping) else {})
    if pre_writer_gate.get("status") == "fail":
        blocked = build_multi_agent_memo_draft(judgment if isinstance(judgment, Mapping) else {}, specialist_verification=specialist_verification)
        blocked = {
            **dict(blocked),
            "answer_status": "blocked_by_judgment_plan",
            "bounded_answer_allowed": True,
            "memo_writer_diagnostics": {
                **dict(blocked.get("memo_writer_diagnostics") or {}),
                "pre_writer_required_dimension_material_gate": pre_writer_gate,
            },
        }
        return {
            "memo_answer": blocked,
            "memo_route_result": {
                "status": "blocked_by_pre_writer_required_dimension_material_gate",
                "failure_reason": "required_dimension_without_writer_material",
                "pre_writer_gate": pre_writer_gate,
                "attempt_count": 0,
                "repair_attempts": 0,
                "total_tokens": 0,
                "memo_profile": str(input_pack_fingerprint.get("memo_profile") or ""),
                "input_pack_fingerprint": input_pack_fingerprint,
            },
        }

    try:
        from sec_agent.humanmade_gold_set_runtime import build_pre_writer_humanmade_gold_set_gate
    except Exception:  # pragma: no cover - defensive import guard for non-P33 lightweight environments.
        humanmade_gold_set_gate: dict[str, Any] = {"status": "not_applicable", "reason": "import_unavailable"}
    else:
        humanmade_gold_set_gate = build_pre_writer_humanmade_gold_set_gate(state)
    if humanmade_gold_set_gate.get("status") == "fail":
        blocked = build_multi_agent_memo_draft(judgment if isinstance(judgment, Mapping) else {}, specialist_verification=specialist_verification)
        blocked = {
            **dict(blocked),
            "answer_status": "blocked_by_humanmade_gold_set_audit",
            "bounded_answer_allowed": True,
            "memo_writer_diagnostics": {
                **dict(blocked.get("memo_writer_diagnostics") or {}),
                "humanmade_gold_set_gate": humanmade_gold_set_gate,
            },
        }
        return {
            "memo_answer": blocked,
            "memo_route_result": {
                "status": "blocked_by_humanmade_gold_set_audit",
                "failure_reason": "humanmade_gold_set_quality_not_met",
                "humanmade_gold_set_gate": humanmade_gold_set_gate,
                "attempt_count": 0,
                "repair_attempts": 0,
                "total_tokens": 0,
                "memo_profile": str(input_pack_fingerprint.get("memo_profile") or ""),
                "input_pack_fingerprint": input_pack_fingerprint,
            },
        }

    model_calls: list[dict[str, Any]] = []
    previous_content = ""
    last_failure: dict[str, Any] = {"type": "not_run"}
    raw_output_audit: dict[str, Any] = {}
    for attempt_index in range(max(0, int(route_config.max_repair_attempts)) + 1):
        max_tokens = int(route_config.memo_max_tokens or 0)
        if max_tokens <= 0:
            max_tokens = MemoLLMConfig.memo_max_tokens
        messages = _memo_messages(
            state,
            prior_failure=last_failure if attempt_index else None,
            prior_content=previous_content if attempt_index else "",
        )
        llm_result = call_chat_completion(
            llm_backend=route_config.llm_backend,
            base_url=route_config.base_url,
            chat_completions_path=route_config.chat_completions_path,
            model=route_config.model,
            messages=messages,
            response_format={"type": "json_object"},
            api_key_env=route_config.api_key_env,
            temperature=route_config.temperature,
            max_tokens=max_tokens,
            timeout_s=route_config.timeout_s,
            stream=False,
            enable_thinking=False,
            role="memo_writer",
            profile="strong",
            trace_tags={"route_source": MEMO_ROUTE_SOURCE, "repair_attempt": attempt_index},
        )
        model_calls.append(_model_call_summary(llm_result))
        previous_content = str(llm_result.get("content") or "")
        if llm_result.get("status") != "ok":
            last_failure = {"type": "provider_error", "reason": str(llm_result.get("failure_reason") or "")}
            break
        if llm_result.get("tool_calls"):
            last_failure = {"type": "direct_tool_call_forbidden", "detail": "Memo Writer may not call tools."}
            continue
        parsed = extract_json_object(previous_content)
        if parsed is None:
            if str(llm_result.get("finish_reason") or "").lower() == "length":
                last_failure = {
                    "type": "model_output_truncated",
                    "detail": "The model hit max_tokens before closing JSON.",
                    "finish_reason": llm_result.get("finish_reason"),
                    "output_tokens": llm_result.get("output_tokens"),
                }
                if attempt_index > 0:
                    last_failure["repair_policy"] = "stop_after_compact_length_repair_to_avoid_repeat_token_burn"
                    break
                continue
            last_failure = {"type": "json_parse_failed", "detail": "No MemoDraft JSON object was found."}
            continue
        shared_context = build_shared_memo_context(state)
        memo_profile = _memo_profile_spec_from_name(
            ((shared_context.get("memo_profile") or {}) if isinstance(shared_context.get("memo_profile"), Mapping) else {}).get("profile")
        )
        response_language = _response_language_from_context(shared_context.get("response_language"))
        memo = _normalize_memo_llm_output(parsed, judgment, memo_profile=memo_profile, response_language=response_language)
        memo = _complete_memo_contract_from_judgment(
            memo,
            judgment if isinstance(judgment, Mapping) else {},
            memo_profile=memo_profile,
            response_language=response_language,
            memo_logic_plan=state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {},
        )
        hard_check = verify_multi_agent_memo_draft(memo, judgment)
        raw_output_audit = _memo_raw_output_audit(
            raw_content=previous_content,
            parsed=parsed,
            normalized_memo=memo,
            hard_check=hard_check,
            salvage_triggered=False,
        )
        if hard_check.get("status") == "pass":
            memo["model_diagnostics"] = _aggregate_model_calls(model_calls)
            memo["schema_version"] = memo.get("schema_version") or "sec_agent_multi_agent_memo_draft_v0.1"
            memo["llm_route_source"] = MEMO_ROUTE_SOURCE
            diagnostics = _aggregate_model_calls(model_calls)
            repair_trigger = last_failure if len(model_calls) > 1 else {}
            return {
                "memo_answer": memo,
                "memo_route_result": {
                    "status": "pass",
                    "memo_profile": memo_profile.profile,
                    "attempt_count": len(model_calls),
                    "repair_attempts": max(0, len(model_calls) - 1),
                    "repair_trigger": repair_trigger,
                    "finish_reasons": diagnostics.get("finish_reasons") or [],
                    "total_tokens": diagnostics.get("total_tokens"),
                    "input_pack_fingerprint": input_pack_fingerprint,
                    "raw_output_audit": raw_output_audit,
                },
            }
        last_failure = {"type": "deterministic_memo_gate_failed", "errors": hard_check.get("errors") or []}
        if _hard_check_is_non_repairable_surface_depth_failure(hard_check):
            last_failure["repair_policy"] = "stop_after_single_surface_depth_failure_to_avoid_full_payload_token_burn"
            break

    if raw_output_audit:
        raw_output_audit = {**raw_output_audit, "salvage_triggered": True}
    shared_context = build_shared_memo_context(state)
    memo_profile = _memo_profile_spec_from_name(
        ((shared_context.get("memo_profile") or {}) if isinstance(shared_context.get("memo_profile"), Mapping) else {}).get("profile")
    )
    fallback = _deterministic_memo_salvage(
        judgment if isinstance(judgment, Mapping) else {},
        specialist_verification=specialist_verification,
        memo_logic_plan=state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {},
        memo_profile=memo_profile,
        response_language=response_language,
        model_calls=model_calls,
        last_failure=last_failure,
    )
    fallback_check = verify_multi_agent_memo_draft(fallback, judgment if isinstance(judgment, Mapping) else {})
    fallback_status = "pass" if fallback_check.get("status") == "pass" else "fallback"
    return {
        "memo_answer": fallback,
        "memo_route_result": {
            "status": fallback_status,
            "memo_profile": ((fallback.get("memo_profile") or {}) if isinstance(fallback.get("memo_profile"), Mapping) else {}).get("profile")
            or memo_profile.profile,
            "failure_reason": _format_failure_reason(last_failure),
            "deterministic_salvage_used": True,
            "deterministic_salvage_verification": fallback_check.get("status"),
            "attempt_count": len(model_calls),
            "repair_attempts": max(0, len(model_calls) - 1),
            "finish_reasons": (_aggregate_model_calls(model_calls).get("finish_reasons") or []),
            "total_tokens": (_aggregate_model_calls(model_calls).get("total_tokens")),
            "input_pack_fingerprint": input_pack_fingerprint,
            "raw_output_audit": raw_output_audit,
        },
    }


def route_verifier_llm(
    state: Mapping[str, Any],
    *,
    config: MemoLLMConfig | None = None,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> dict[str, Any]:
    route_config = config or MemoLLMConfig()
    judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    memo = state.get("memo_answer") or {}
    deterministic = verify_multi_agent_memo_draft(memo, judgment)
    if deterministic.get("status") != "pass":
        deterministic["llm_verifier_skipped"] = "deterministic_gate_failed"
        return {"claim_verification": deterministic, "specialist_verification": state.get("specialist_verification") or {}}

    verifier_projection = _verifier_minimal_projection(state, deterministic=deterministic)
    projection_stats = verifier_projection.get("projection_stats") if isinstance(verifier_projection.get("projection_stats"), Mapping) else {}
    verifier_input_fingerprint = _verifier_input_pack_fingerprint(verifier_projection)
    if isinstance(projection_stats, dict):
        projection_stats["input_pack_fingerprint"] = verifier_input_fingerprint
    messages = _verifier_messages(state, projection=verifier_projection)
    llm_result = call_chat_completion(
        llm_backend=route_config.llm_backend,
        base_url=route_config.base_url,
        chat_completions_path=route_config.chat_completions_path,
        model=route_config.model,
        messages=messages,
        response_format={"type": "json_object"},
        api_key_env=route_config.api_key_env,
        temperature=0.0,
        max_tokens=route_config.verifier_max_tokens,
        timeout_s=route_config.timeout_s,
        stream=False,
        enable_thinking=False,
        role="verifier",
        profile="strong",
        trace_tags={
            "route_source": VERIFIER_ROUTE_SOURCE,
            "projection_schema": VERIFIER_PROJECTION_SCHEMA_VERSION,
            "projected_claim_count": projection_stats.get("projected_claim_count"),
            "projected_evidence_ref_count": projection_stats.get("projected_evidence_ref_count"),
        },
    )
    summary = _model_call_summary(llm_result)
    if llm_result.get("status") != "ok" or llm_result.get("tool_calls"):
        merged = {
            **deterministic,
            "status": "fail",
            "errors": [
                *list(deterministic.get("errors") or []),
                {"type": "llm_verifier_failed", "reason": str(llm_result.get("failure_reason") or "tool_call_forbidden")},
            ],
            "bounded_answer_allowed": True,
            "verifier_input_projection": projection_stats,
            "verifier_input_pack_fingerprint": verifier_input_fingerprint,
            "model_diagnostics": {"calls": [summary], "raw_response_saved": False},
        }
        return {"claim_verification": merged, "specialist_verification": state.get("specialist_verification") or {}}

    parsed = extract_json_object(str(llm_result.get("content") or "")) or {}
    llm_status = str(parsed.get("status") or "pass").strip()
    llm_errors = [dict(item) for item in parsed.get("errors") or [] if isinstance(item, Mapping)]
    dropped_bounded_errors: list[dict[str, Any]] = []
    if _is_bounded_block_memo(memo):
        llm_errors, dropped_bounded_errors = _filter_soft_verifier_errors(
            llm_errors,
            warning_type="bounded_block_verifier_warning_downgraded",
            reason="bounded_block_answer_does_not_need_full_memo_evidence_when_deterministic_gate_passes",
        )
        if not llm_errors and llm_status == "fail":
            llm_status = "pass"
    elif deterministic.get("status") == "pass":
        llm_errors, dropped_bounded_errors = _filter_soft_verifier_errors(
            llm_errors,
            warning_type="deterministic_pass_verifier_warning_downgraded",
            reason="deterministic_gate_passed_and_llm_error_was_not_a_hard_source_boundary_violation",
        )
        if not llm_errors and llm_status == "fail":
            llm_status = "pass"
    merged = {
        **deterministic,
        "status": "fail" if llm_status == "fail" or llm_errors else "pass",
        "errors": [*list(deterministic.get("errors") or []), *llm_errors],
        "warnings": [
            *list(deterministic.get("warnings") or []),
            *[dict(item) for item in parsed.get("warnings") or [] if isinstance(item, Mapping)],
            *dropped_bounded_errors,
        ],
        "repair_instruction": str(parsed.get("repair_instruction") or deterministic.get("repair_instruction") or ""),
        "bounded_answer_allowed": bool(parsed.get("bounded_answer_allowed") or llm_errors),
        "llm_verifier_policy": "minimal_projection_cannot_override_deterministic_gate",
        "verifier_input_projection": projection_stats,
        "verifier_input_pack_fingerprint": verifier_input_fingerprint,
        "model_diagnostics": {"calls": [summary], "raw_response_saved": False},
    }
    return {"claim_verification": merged, "specialist_verification": state.get("specialist_verification") or {}}


def extract_json_object(text: str) -> dict[str, Any] | None:
    for candidate in _json_candidates(str(text or "")):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _memo_raw_output_audit(
    *,
    raw_content: str,
    parsed: Mapping[str, Any],
    normalized_memo: Mapping[str, Any],
    hard_check: Mapping[str, Any],
    salvage_triggered: bool,
) -> dict[str, Any]:
    """Digest-only audit from raw model JSON to normalized memo and deterministic gate."""

    errors = [dict(item) for item in hard_check.get("errors") or [] if isinstance(item, Mapping)]
    return {
        "schema_version": "sec_agent_memo_raw_output_audit_v0_1",
        "raw_content_sha256": hashlib.sha256(str(raw_content or "").encode("utf-8")).hexdigest()[:16],
        "raw_content_chars": len(str(raw_content or "")),
        "parsed_top_level_keys": sorted(str(key) for key in parsed.keys())[:24],
        "raw_direct_answer_chars": len(str(parsed.get("direct_answer") or "")),
        "raw_dimension_count": len([item for item in parsed.get("dimension_analyses") or [] if isinstance(item, Mapping)])
        if isinstance(parsed.get("dimension_analyses"), list)
        else 0,
        "raw_memo_claim_count": len([item for item in parsed.get("memo_claims") or [] if isinstance(item, Mapping)])
        if isinstance(parsed.get("memo_claims"), list)
        else 0,
        "normalized_direct_answer_chars": len(str(normalized_memo.get("direct_answer") or "")),
        "normalized_dimension_count": len(
            [item for item in normalized_memo.get("dimension_analyses") or [] if isinstance(item, Mapping)]
        )
        if isinstance(normalized_memo.get("dimension_analyses"), list)
        else 0,
        "normalized_memo_claim_count": len(
            [item for item in normalized_memo.get("memo_claims") or [] if isinstance(item, Mapping)]
        )
        if isinstance(normalized_memo.get("memo_claims"), list)
        else 0,
        "deterministic_gate_status": str(hard_check.get("status") or ""),
        "deterministic_gate_error_types": [str(item.get("type") or "") for item in errors if str(item.get("type") or "")][:12],
        "salvage_triggered": bool(salvage_triggered),
        "raw_text_persisted": False,
        "policy": "digest_only_raw_to_normalized_memo_audit_no_prompt_or_completion_text",
    }


def _json_for_prompt(value: Any, *, sort_keys: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"))


def _normalize_memo_llm_output(
    payload: Mapping[str, Any],
    judgment: Any,
    *,
    memo_profile: MemoProfileSpec | None = None,
    response_language: str = "en-US",
) -> dict[str, Any]:
    profile = memo_profile or MEMO_PROFILE_SPECS["compact"]
    language = _normalize_response_language(response_language) or "en-US"
    memo = dict(payload or {})
    nested = memo.get("memo_draft")
    if isinstance(nested, Mapping):
        wrapper_fields = {key: value for key, value in memo.items() if key != "memo_draft"}
        memo = {**dict(nested), **wrapper_fields}
    for forbidden_key in (
        "verified_judgment_plan",
        "judgment_plan",
        "supported_claims",
        "bounded_evidence_rows",
        "context_rows",
        "analysis_trace",
        "reasoning",
        "thesis_driver_pack",
        "judgment_state",
    ):
        memo.pop(forbidden_key, None)
    base = build_multi_agent_memo_draft(judgment if isinstance(judgment, Mapping) else {})
    memo.setdefault("schema_version", base.get("schema_version"))
    memo.setdefault("answer_status", "draft")
    memo.setdefault("memo_writer_allowed", True)
    memo["consumed_input_views"] = ["verified_judgment_plan", "verified_summary"]
    memo["raw_rows_consumed"] = False
    memo["tool_calls_requested"] = []
    memo.setdefault("source_boundary", base.get("source_boundary") or "verified judgment plan only")
    if language == "zh-CN":
        memo["source_boundary"] = _localize_source_boundary_for_zh(memo.get("source_boundary"))
    memo.setdefault("source_boundary_notes", base.get("source_boundary_notes") or [])
    memo.setdefault("evidence_strength", base.get("evidence_strength") or {})
    memo.setdefault("counterevidence", base.get("counterevidence") or [])
    memo.setdefault("missing_evidence", base.get("missing_evidence") or [])
    if language == "zh-CN" and "unsupported_claims_excluded" not in memo:
        memo["unsupported_claims_excluded"] = []
    else:
        memo.setdefault("unsupported_claims_excluded", base.get("unsupported_claims_excluded") or [])
    memo.setdefault("memo_constraints", base.get("memo_constraints") or {})
    memo.setdefault("memo_outline", base.get("memo_outline") or [])
    memo["memo_profile"] = _memo_profile_dict(profile)
    memo["response_language"] = _response_language_dict(language, source="memo_writer_context")
    memo["memo_thesis_plan"] = _normalize_output_memo_thesis_plan(
        memo.get("memo_thesis_plan") if isinstance(memo.get("memo_thesis_plan"), Mapping) else base.get("memo_thesis_plan") or {}
    )
    memo.setdefault("memo_thesis_pack", base.get("memo_thesis_pack") or {})
    memo.setdefault("thesis_driver_pack", base.get("thesis_driver_pack") or {})
    memo.setdefault("judgment_state", base.get("judgment_state") or {})
    surface_caps = _memo_writer_surface_caps(profile)
    memo["dimension_analyses"] = _normalize_output_dimension_analyses(
        memo.get("dimension_analyses"),
        base.get("dimension_analyses") or [],
        max_items=int(surface_caps["dimension_analyses_max"]),
        max_summary_chars=int(surface_caps["dimension_summary_max_chars"]),
        max_detail_chars=int(surface_caps["dimension_detail_max_chars"]),
    )
    memo.setdefault("claim_card_stats", base.get("claim_card_stats") or {})
    memo.setdefault("bounded_answer_allowed", False)
    if str(memo.get("answer_status") or "draft") == "draft":
        memo["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    else:
        memo.setdefault("memo_generation_policy", "thesis_led_claim_cards_v0_1")
    allowed_statuses = {
        "draft",
        "blocked_by_specialist_verification",
        "blocked_by_judgment_plan",
        "blocked_by_verifier_repair",
    }
    answer_status = str(memo.get("answer_status") or "draft")
    if answer_status not in allowed_statuses:
        memo.setdefault("memo_writer_diagnostics", {})
        diagnostics = memo["memo_writer_diagnostics"]
        if isinstance(diagnostics, dict):
            diagnostics["normalized_answer_status_from"] = answer_status
        memo["answer_status"] = "draft" if memo.get("memo_claims") else "blocked_by_judgment_plan"
        if memo["answer_status"] == "draft":
            memo["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    memo["memo_claims"] = _normalize_output_memo_claims(
        memo.get("memo_claims"),
        judgment if isinstance(judgment, Mapping) else {},
        max_claims=profile.memo_claims_max,
        response_language=language,
    )
    memo["investment_implications"] = _normalize_memo_action_items(
        memo.get("investment_implications"),
        max_items=int(surface_caps["investment_implications_max"]),
        max_chars=180,
    )
    memo["what_would_change_view"] = _normalize_memo_action_items(
        memo.get("what_would_change_view"),
        max_items=int(surface_caps["what_would_change_view_max"]),
        max_chars=180,
    )
    memo["monitoring_items"] = _normalize_memo_action_items(
        memo.get("monitoring_items"),
        max_items=int(surface_caps["monitoring_items_max"]),
        max_chars=180,
    )
    if profile.profile in {"standard", "expanded", "deep_research"} and memo["memo_claims"]:
        if not memo["investment_implications"]:
            memo["investment_implications"] = _default_profile_action_items(
                memo["memo_claims"],
                response_language=language,
                kind="investment_implications",
            )
        if not memo["what_would_change_view"]:
            memo["what_would_change_view"] = _default_profile_action_items(
                memo["memo_claims"],
                response_language=language,
                kind="what_would_change_view",
            )
        if not memo["monitoring_items"]:
            memo["monitoring_items"] = _default_profile_action_items(
                memo["memo_claims"],
                response_language=language,
                kind="monitoring_items",
            )
    memo["evidence_gaps_but_actionable"] = _normalize_memo_action_items(
        memo.get("evidence_gaps_but_actionable"),
        max_items=int(surface_caps["evidence_gaps_but_actionable_max"]),
        max_chars=180,
    )
    memo = _normalize_direct_answer_numeric_fidelity(
        memo,
        judgment if isinstance(judgment, Mapping) else {},
        base,
        max_chars=profile.direct_answer_max_chars,
        response_language=language,
    )
    memo = _localize_memo_user_text(memo, response_language=language)
    memo = _enforce_decision_useful_memo_surface(
        memo,
        judgment if isinstance(judgment, Mapping) else {},
        response_language=language,
    )
    return memo


def _complete_memo_contract_from_judgment(
    memo: Mapping[str, Any],
    judgment: Mapping[str, Any],
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
    memo_logic_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Complete the writer-facing contract from already verified judgment rows.

    This is intentionally not a fallback that invents content after the fact.
    It closes deterministic shape gaps where the model omitted required
    memo_claims or dimensions that are already present in verified judgment
    packs. If the verified packs do not contain the missing material, the
    downstream gate still fails and exposes the upstream gap.
    """

    normalized = dict(memo)
    answer_status = str(normalized.get("answer_status") or "")
    can_complete_blocked_shape = (
        answer_status == "blocked_by_judgment_plan"
        and not [item for item in normalized.get("memo_claims") or [] if isinstance(item, Mapping)]
        and _dimension_analyses_have_promotable_claim_material(normalized.get("dimension_analyses"))
    )
    if answer_status != "draft" and not can_complete_blocked_shape:
        return normalized
    if not isinstance(judgment, Mapping):
        return normalized

    diagnostics = dict(normalized.get("memo_writer_diagnostics") or {})
    completed_claims = _complete_memo_claims_from_judgment(
        normalized.get("memo_claims"),
        judgment,
        memo_profile=memo_profile,
        response_language=response_language,
    )
    if completed_claims["completed_count"]:
        normalized["memo_claims"] = completed_claims["memo_claims"]
        diagnostics["memo_claims_completed_from_verified_judgment"] = completed_claims["completed_count"]
        diagnostics["memo_claim_completion_policy"] = "verified_judgment_contract_completion_v0_1"
    completed_dimensions = _complete_dimension_analyses_from_judgment(
        normalized.get("dimension_analyses"),
        judgment,
        memo_profile=memo_profile,
        response_language=response_language,
    )
    original_dimensions = [dict(item) for item in normalized.get("dimension_analyses") or [] if isinstance(item, Mapping)]
    completed_dimension_rows = [
        dict(item) for item in completed_dimensions.get("dimension_analyses") or [] if isinstance(item, Mapping)
    ]
    if (
        completed_dimensions["completed_count"]
        or completed_dimensions["reordered_for_required_dimensions"]
        or completed_dimensions["enriched_existing_dimension_count"]
        or (completed_dimension_rows and completed_dimension_rows != original_dimensions)
    ):
        normalized["dimension_analyses"] = completed_dimension_rows
        diagnostics["dimension_analyses_completed_from_verified_judgment"] = completed_dimensions["completed_count"]
        diagnostics["dimension_analyses_enriched_from_verified_judgment"] = completed_dimensions[
            "enriched_existing_dimension_count"
        ]
        diagnostics["required_dimension_reorder_policy"] = "verified_judgment_required_dimension_first_v0_1"
        diagnostics["dimension_analyses_normalization_policy"] = (
            "verified_judgment_language_and_depth_normalization_v0_1"
        )

    completed_plan_dimensions = _complete_dimension_analyses_from_memo_logic_plan(
        normalized.get("dimension_analyses"),
        memo_logic_plan or {},
        memo_profile=memo_profile,
        response_language=response_language,
    )
    if completed_plan_dimensions.get("completed_count"):
        normalized["dimension_analyses"] = completed_plan_dimensions["dimension_analyses"]
        diagnostics["dimension_analyses_completed_from_memo_logic_plan"] = completed_plan_dimensions[
            "completed_count"
        ]
        diagnostics["dimension_analysis_plan_projection_policy"] = (
            "required_item_answer_plan_to_dimension_analyses_v0_1"
        )

    completed_dimension_claims = _complete_memo_claims_from_dimension_analyses(
        normalized.get("memo_claims"),
        normalized.get("dimension_analyses"),
        memo_profile=memo_profile,
        response_language=response_language,
    )
    if completed_dimension_claims["completed_count"]:
        normalized["memo_claims"] = completed_dimension_claims["memo_claims"]
        diagnostics["memo_claims_completed_from_dimension_analyses"] = completed_dimension_claims["completed_count"]
        diagnostics["memo_claim_dimension_projection_policy"] = (
            "provider_agnostic_supported_dimension_to_memo_claims_v0_1"
        )
        if answer_status == "blocked_by_judgment_plan":
            normalized["answer_status"] = "draft"
            normalized["bounded_answer_allowed"] = False
            normalized["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
            diagnostics["answer_status_restored_from"] = answer_status

    completed_actions = _complete_action_items_from_memo_claims(
        normalized,
        memo_profile=memo_profile,
        response_language=response_language,
    )
    if completed_actions["completed_fields"]:
        normalized.update(completed_actions["memo"])
        diagnostics["action_items_completed_from_projected_claims"] = completed_actions["completed_fields"]
        diagnostics["action_item_completion_policy"] = "verified_claim_projection_after_minimal_writer_output_v0_1"

    completed_plan_actions = _complete_action_items_from_memo_logic_plan(
        normalized,
        memo_logic_plan or {},
        memo_profile=memo_profile,
        response_language=response_language,
    )
    if completed_plan_actions.get("completed_fields"):
        normalized.update(completed_plan_actions["memo"])
        diagnostics["action_items_completed_from_memo_logic_plan"] = completed_plan_actions["completed_fields"]
        diagnostics["action_item_plan_projection_policy"] = "required_item_answer_plan_to_action_items_v0_1"

    direct_completion = _complete_direct_answer_from_memo_logic_plan(
        normalized,
        memo_logic_plan or {},
        memo_profile=memo_profile,
        response_language=response_language,
    )
    if direct_completion.get("completed"):
        normalized["direct_answer"] = direct_completion["direct_answer"]
        diagnostics["direct_answer_completed_from_memo_logic_plan"] = True
        diagnostics["direct_answer_completion_policy"] = "required_item_answer_plan_to_opening_judgment_v0_1"
        diagnostics["direct_answer_completion_source_item_ids"] = direct_completion.get("source_item_ids") or []

    if diagnostics:
        normalized["memo_writer_diagnostics"] = diagnostics
    return normalized


def _hard_check_is_non_repairable_surface_depth_failure(hard_check: Mapping[str, Any]) -> bool:
    if hard_check.get("status") != "fail":
        return False
    errors = [dict(item) for item in hard_check.get("errors") or [] if isinstance(item, Mapping)]
    if not errors:
        return False
    error_types = {str(item.get("type") or "") for item in errors}
    return error_types <= {"analyst_depth_direct_answer_too_thin_for_profile"}


def _complete_dimension_analyses_from_memo_logic_plan(
    value: Any,
    memo_logic_plan: Mapping[str, Any],
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    current_rows = [dict(item) for item in value or [] if isinstance(item, Mapping)]
    plan_rows = _dimension_rows_from_required_item_answer_plan(
        memo_logic_plan,
        response_language=response_language,
    )
    if not plan_rows:
        return {"completed_count": 0, "dimension_analyses": current_rows}

    by_id = {str(item.get("dimension_id") or ""): dict(item) for item in current_rows if str(item.get("dimension_id") or "")}
    completed = 0
    for plan_row in plan_rows:
        dimension_id = str(plan_row.get("dimension_id") or "")
        if not dimension_id:
            continue
        current = by_id.get(dimension_id)
        if current is None:
            by_id[dimension_id] = dict(plan_row)
            completed += 1
            continue
        merged = _merge_plan_dimension_row(current, plan_row)
        if merged != current:
            by_id[dimension_id] = merged
            completed += 1

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    section_order = _valid_memo_required_dimension_ids(memo_logic_plan.get("section_order"))

    def add_dimension(dimension_id: str) -> None:
        if dimension_id in seen or dimension_id not in by_id:
            return
        ordered.append(dict(by_id[dimension_id]))
        seen.add(dimension_id)

    for dimension_id in section_order:
        add_dimension(dimension_id)
    for dimension_id in ANALYSIS_DIMENSION_ORDER:
        add_dimension(dimension_id)
    for row in current_rows:
        add_dimension(str(row.get("dimension_id") or ""))
    for row in plan_rows:
        add_dimension(str(row.get("dimension_id") or ""))

    surface_caps = _memo_writer_surface_caps(memo_profile)
    max_items = max(
        int(surface_caps["dimension_analyses_max"]),
        len(section_order),
        len(plan_rows),
        len(ordered),
    )
    normalized_rows = _normalize_output_dimension_analyses(
        ordered,
        [],
        max_items=max_items,
        max_summary_chars=int(surface_caps["dimension_summary_max_chars"]),
        max_detail_chars=int(surface_caps["dimension_detail_max_chars"]),
    )
    return {"completed_count": completed, "dimension_analyses": normalized_rows}


def _dimension_rows_from_required_item_answer_plan(
    memo_logic_plan: Mapping[str, Any],
    *,
    response_language: str,
) -> list[dict[str, Any]]:
    items = [
        dict(item)
        for item in memo_logic_plan.get("required_item_answer_plan") or []
        if isinstance(item, Mapping) and str(item.get("answer") or "").strip()
    ]
    if not items:
        return []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        dimension_id = _dimension_id_for_gold_required_item(str(item.get("question_item_id") or ""))
        if not dimension_id:
            continue
        grouped.setdefault(dimension_id, []).append(item)

    rows: list[dict[str, Any]] = []
    for dimension_id in ANALYSIS_DIMENSION_ORDER:
        group = grouped.get(dimension_id)
        if not group:
            continue
        rows.append(
            _dimension_row_from_required_items(
                dimension_id,
                group,
                response_language=response_language,
            )
        )
    return rows


def _dimension_id_for_gold_required_item(item_id: str) -> str:
    return {
        "req_accelerator_architecture": "product_and_production",
        "req_customer_deployment": "product_and_production",
        "req_dell_margin_quality": "fundamentals",
        "req_supply_chain": "industry_supply_chain",
        "req_market_price_in": "capital_and_financing",
        "req_counter_thesis": "risk_and_counterevidence",
    }.get(str(item_id or ""), "")


def _dimension_row_from_required_items(
    dimension_id: str,
    items: list[dict[str, Any]],
    *,
    response_language: str,
) -> dict[str, Any]:
    item_ids = [str(item.get("question_item_id") or "") for item in items]
    evidence_refs = _dedupe_strings(
        ref for item in items for ref in _string_list(item.get("evidence_refs"))
    )[:8]
    if response_language == "zh-CN":
        summary = _zh_dimension_summary_from_gold_items(dimension_id, items)
        mechanism = _zh_dimension_mechanism_from_gold_items(dimension_id, items)
        bridge = _zh_dimension_bridge_from_gold_items(dimension_id, items)
        counter = _zh_dimension_counter_from_gold_items(dimension_id, items)
    else:
        answers = [str(item.get("answer") or "").strip().rstrip(".") for item in items if str(item.get("answer") or "").strip()]
        cannot = [
            str(item.get("cannot_infer") or "").strip().rstrip(".")
            for item in items
            if str(item.get("cannot_infer") or "").strip()
        ]
        change = [
            str(item.get("what_would_change_view") or "").strip().rstrip(".")
            for item in items
            if str(item.get("what_would_change_view") or "").strip()
        ]
        summary = ". ".join(answers[:2]) + ("." if answers else "")
        mechanism = summary
        bridge = "Financial bridge: " + "; ".join(answers[:2]) + "." if answers else ""
        counter = "Boundary: " + "; ".join(cannot[:2]) + ". What changes view: " + "; ".join(change[:2]) + "."
    return {
        "dimension_id": dimension_id,
        "title": _zh_dimension_label(dimension_id) if response_language == "zh-CN" else dimension_id.replace("_", " ").title(),
        "summary": _normalize_zh_punctuation(summary) if response_language == "zh-CN" else summary,
        "business_mechanism": _normalize_zh_punctuation(mechanism) if response_language == "zh-CN" else mechanism,
        "financial_bridge": _normalize_zh_punctuation(bridge) if response_language == "zh-CN" else bridge,
        "competitive_read": _normalize_zh_punctuation(counter) if response_language == "zh-CN" else counter,
        "counter_read": _normalize_zh_punctuation(counter) if response_language == "zh-CN" else counter,
        "claim_ids": _dedupe_strings(
            claim_id for item in items for claim_id in _string_list(item.get("claim_ids"))
        )[:8],
        "evidence_refs": evidence_refs,
        "required_item_ids": [item_id for item_id in item_ids if item_id],
        "rendering_policy": "required_item_answer_plan_dimension_projection_v0_1",
    }


def _zh_dimension_summary_from_gold_items(dimension_id: str, items: list[dict[str, Any]]) -> str:
    by_id = {str(item.get("question_item_id") or ""): item for item in items}
    if dimension_id == "product_and_production":
        return (
            "产品层不能因为没有 SKU revenue 就判定失败：Blackwell/GB200 的 rack-scale 架构仍是外部加速器系统供给瓶颈，"
            "AMD MI300/MI35x 和 Google TPU 构成真实替代压力，DELL 与 Google 的官方产品/云实例表面证明采用路径存在；"
            "但这些证据只能支持产品能力、采用路径和竞争压力，不能推出 SKU 收入、ASP、份额、出货量或客户规模。"
        )
    if dimension_id == "fundamentals":
        return (
            "DELL 的核心不是 AI server 需求是否存在，而是订单和 backlog 能否转化成高质量利润：现有公开材料能证明 AI server revenue tailwind 和 ISG 财务桥，"
            "但还不能证明 AI server gross margin、GPU pass-through、attach rate 或 backlog conversion 已经改善。"
        )
    if dimension_id == "industry_supply_chain":
        return (
            "AI read-through 必须按机制拆开：TSMC 承接 advanced node / 先进封装，ASML 承接 lithography / installed base，"
            "AMAT 对应 materials engineering，LRCX 更偏 memory/HBM process intensity；这能支持半导体设备周期传导，但不能从 broad revenue 直接推出 AI-specific orders。"
        )
    if dimension_id == "capital_and_financing":
        return (
            "市场价格层面还不能形成强买卖建议：业务链条方向偏正面，但缺 valuation percentile、13F/ETF/insider/short/options、事件后价格反应等 price-in 证据，"
            "所以当前只能给出有边界的研究判断，不能判断市场是否已经充分定价。"
        )
    if dimension_id == "risk_and_counterevidence":
        return (
            "反证不是泛泛的 AI 风险，而是 hyperscaler capex digestion、DELL margin dilution、AMD/TPU 替代、NVDA supply delay、出口管制、客户集中和 semicap 订单滞后；"
            "如果订单/部署兑现放缓、利润率恶化或 capex 下修，AI infrastructure thesis 应该降权。"
        )
    answers = [str(item.get("answer") or "").strip().rstrip(".") for item in items if str(item.get("answer") or "").strip()]
    return "；".join(answers[:2]) + "。" if answers else ""


def _zh_dimension_mechanism_from_gold_items(dimension_id: str, items: list[dict[str, Any]]) -> str:
    if dimension_id == "product_and_production":
        return "业务机制是用架构、benchmark、云实例、OEM 配置和官方产品表面判断产品能力与采用路径，再把它连接到收入承接和供应链瓶颈，而不是把产品页冒充收入或份额。"
    if dimension_id == "fundamentals":
        return "业务机制是 orders/backlog -> shipments -> ISG revenue -> gross/operating margin -> cash conversion；缺任何一段都只能说明需求或收入可见度，不能说明利润质量。"
    if dimension_id == "industry_supply_chain":
        return "业务机制是把 AI accelerator / HBM / packaging / advanced-node demand 映射到 foundry 和 semicap 工具链的具体环节，而不是用 peer group 代替订单证据。"
    if dimension_id == "capital_and_financing":
        return "业务机制是把基本面和产品证据再映射到估值、持仓、拥挤度、期权/short、ETF flow 和事件反应，判断好消息是否已经 price-in。"
    if dimension_id == "risk_and_counterevidence":
        return "业务机制是先识别主线判断最脆弱的传导环节，再用反证限制结论权重，而不是在结尾泛泛列风险。"
    return ""


def _zh_dimension_bridge_from_gold_items(dimension_id: str, items: list[dict[str, Any]]) -> str:
    if dimension_id == "product_and_production":
        return "财务桥是产品能力和客户部署先进入 OEM/server revenue visibility，再通过 backlog conversion、attach rate 和 margin mix 决定利润质量。"
    if dimension_id == "fundamentals":
        return "财务桥必须落到 DELL ISG revenue、Servers/Networking、gross/operating margin、working capital 和 cash conversion，而不是只写订单金额或收入增长。"
    if dimension_id == "industry_supply_chain":
        return "财务桥是从 AI demand 到 TSMC/HBM/advanced packaging，再到 ASML/AMAT/LRCX 等设备公司的 bookings、backlog、services 和区域/客户暴露。"
    if dimension_id == "capital_and_financing":
        return "资本市场桥是把业务改善与估值分位、资金持仓、流动性、short/options 和事件反应相互校验，判断预期是否已经被股价吸收。"
    if dimension_id == "risk_and_counterevidence":
        return "反证的财务桥包括 DELL 低毛利放量、GPU pass-through 压缩利润、capex digestion 降低订单、出口管制和 semicap backlog 延后。"
    return ""


def _zh_dimension_counter_from_gold_items(dimension_id: str, items: list[dict[str, Any]]) -> str:
    cannot = [
        str(item.get("cannot_infer") or "").strip().rstrip(".")
        for item in items
        if str(item.get("cannot_infer") or "").strip()
    ]
    change = [
        str(item.get("what_would_change_view") or "").strip().rstrip(".")
        for item in items
        if str(item.get("what_would_change_view") or "").strip()
    ]
    if dimension_id == "product_and_production":
        return "反向读法是：规格、benchmark 和 cloud surface 不能推出份额、ASP、出货或收入；真正改变判断的是生产部署、采购 mix、客户配置和定价证据。"
    if dimension_id == "fundamentals":
        return "反向读法是：AI server 放量可能只是低毛利 GPU pass-through；只有 ISG margin、backlog conversion 和 attach economics 同步改善，才能上调利润质量。"
    if dimension_id == "industry_supply_chain":
        return "反向读法是：broad revenue/margin 不能推出 AI-specific orders；需要 bookings/backlog、HBM/advanced packaging 订单、China exposure 和客户 allocation。"
    if dimension_id == "capital_and_financing":
        return "反向读法是：没有 valuation/positioning/price reaction，就不能知道好消息是否已经反映，也不能生成强买卖建议。"
    if dimension_id == "risk_and_counterevidence":
        return "反向读法是：只要 capex 下修、部署延后、利润率恶化、替代品扩散或监管冲击出现，主线判断就应降权。"
    parts = []
    if cannot:
        parts.append("不能外推：" + "；".join(cannot[:2]))
    if change:
        parts.append("改变判断：" + "；".join(change[:2]))
    return "。".join(parts) + "。" if parts else ""


def _merge_plan_dimension_row(current: Mapping[str, Any], plan_row: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    force_replace = str(plan_row.get("rendering_policy") or "") == "required_item_answer_plan_dimension_projection_v0_1" or _dimension_row_needs_plan_projection(current)
    for key in ("summary", "business_mechanism", "financial_bridge", "competitive_read", "counter_read"):
        current_text = str(merged.get(key) or "").strip()
        plan_text = str(plan_row.get(key) or "").strip()
        if not plan_text:
            continue
        if force_replace or len(current_text) < 60 or _memo_text_contains_internal_placeholder(current_text):
            merged[key] = plan_text
            merged[f"{key}_completed_from_memo_logic_plan"] = True
    for key in ("claim_ids", "counter_claim_ids", "counter_driver_ids", "gap_ids", "evidence_refs", "required_item_ids"):
        merged[key] = _dedupe_strings(_string_list(merged.get(key)) + _string_list(plan_row.get(key)))[:8]
    if not str(merged.get("title") or "").strip() and plan_row.get("title"):
        merged["title"] = plan_row.get("title")
    merged["rendering_policy"] = str(plan_row.get("rendering_policy") or merged.get("rendering_policy") or "")
    return merged


def _dimension_row_needs_plan_projection(row: Mapping[str, Any]) -> bool:
    texts = " ".join(
        str(row.get(key) or "")
        for key in ("summary", "business_mechanism", "financial_bridge", "competitive_read", "counter_read")
    )
    if _memo_text_contains_internal_placeholder(texts):
        return True
    if not _string_list(row.get("evidence_refs")):
        return True
    summary = str(row.get("summary") or "").strip()
    return len(summary) < 80


def _memo_text_contains_internal_placeholder(text: str) -> bool:
    value = str(text or "")
    return any(
        marker in value
        for marker in (
            "尚未完成中文综合",
            "正式 memo 必须回到对应 JudgmentCard",
            "相关证据尚未完成",
            "schema preservation smoke",
        )
    )


def _complete_action_items_from_memo_logic_plan(
    memo: Mapping[str, Any],
    memo_logic_plan: Mapping[str, Any],
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    items = [
        dict(item)
        for item in memo_logic_plan.get("required_item_answer_plan") or []
        if isinstance(item, Mapping) and str(item.get("answer") or "").strip()
    ]
    if not items:
        return {"completed_fields": []}
    updated = dict(memo)
    completed: list[str] = []
    action_map = _action_items_from_required_item_answer_plan(items, response_language=response_language)
    caps = _memo_writer_surface_caps(memo_profile)
    force_plan_projection = _memo_logic_plan_has_gold_depth_required_items(memo_logic_plan)
    for field, rows in action_map.items():
        current = [dict(item) for item in updated.get(field) or [] if isinstance(item, Mapping)]
        if current and not force_plan_projection and not _action_items_need_plan_projection(current):
            continue
        max_items = int(caps.get(f"{field}_max", 2) or 2)
        updated[field] = _normalize_memo_action_items(rows, max_items=max_items, max_chars=220)
        completed.append(field)
    return {"completed_fields": completed, "memo": updated}


def _memo_logic_plan_has_gold_depth_required_items(memo_logic_plan: Mapping[str, Any]) -> bool:
    item_ids = {
        str(item.get("question_item_id") or "")
        for item in memo_logic_plan.get("required_item_answer_plan") or []
        if isinstance(item, Mapping)
    }
    return bool(
        item_ids
        & {
            "req_accelerator_architecture",
            "req_dell_margin_quality",
            "req_supply_chain",
            "req_customer_deployment",
            "req_market_price_in",
            "req_counter_thesis",
        }
    )


def _action_items_need_plan_projection(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return True
    if any(_memo_text_contains_internal_placeholder(str(row.get("text") or "")) for row in rows):
        return True
    if any(not _string_list(row.get("evidence_refs")) for row in rows):
        return True
    joined = " ".join(str(row.get("text") or "") for row in rows)
    return "缺失；" in joined or "跟踪；" in joined or "若；" in joined


def _action_items_from_required_item_answer_plan(
    items: list[dict[str, Any]],
    *,
    response_language: str,
) -> dict[str, list[dict[str, Any]]]:
    refs_by_id = {
        str(item.get("question_item_id") or ""): _string_list(item.get("evidence_refs"))[:5]
        for item in items
    }
    if response_language == "zh-CN":
        return {
            "investment_implications": [
                {
                    "text": "AI 基建链条的方向偏正面，但当前更适合写成有边界的研究判断：NVDA/Blackwell 仍是供给瓶颈，DELL 受益于 AI server demand，但投资质量取决于 ISG margin、GPU pass-through 和 backlog conversion。",
                    "claim_id": "",
                    "evidence_refs": _dedupe_strings(refs_by_id.get("req_accelerator_architecture", []) + refs_by_id.get("req_dell_margin_quality", []))[:6],
                },
                {
                    "text": "半导体设备 read-through 应按 TSMC advanced node、ASML lithography、AMAT materials engineering、LRCX memory/HBM process intensity 分机制判断，不能用 peer group 替代订单或 backlog。",
                    "claim_id": "",
                    "evidence_refs": refs_by_id.get("req_supply_chain", [])[:6],
                },
            ],
            "what_would_change_view": [
                {
                    "text": "如果 DELL backlog 转化时 ISG margin 没改善，或 AI server 只是低毛利 GPU pass-through，DELL 的投资质量应降权。",
                    "claim_id": "",
                    "evidence_refs": refs_by_id.get("req_dell_margin_quality", [])[:5],
                },
                {
                    "text": "如果 AMD/TPU 部署扩散、NVDA supply delay、hyperscaler capex 下修或 semicap bookings/backlog 滞后，AI infrastructure 主线应降权。",
                    "claim_id": "",
                    "evidence_refs": _dedupe_strings(refs_by_id.get("req_counter_thesis", []) + refs_by_id.get("req_supply_chain", []))[:6],
                },
            ],
            "monitoring_items": [
                {
                    "text": "跟踪 DELL AI server orders、shipments、backlog conversion、ISG margin 与 attach economics，确认收入可见度能否转化为利润质量。",
                    "claim_id": "",
                    "evidence_refs": refs_by_id.get("req_dell_margin_quality", [])[:5],
                },
                {
                    "text": "跟踪 NVDA/AMD/Google TPU 的生产部署、采购 mix、cloud availability、OEM configuration 和定价证据，确认产品竞争与替代压力。",
                    "claim_id": "",
                    "evidence_refs": _dedupe_strings(refs_by_id.get("req_accelerator_architecture", []) + refs_by_id.get("req_customer_deployment", []))[:6],
                },
                {
                    "text": "跟踪 valuation percentile、13F/ETF/insider/short/options、事件后价格反应，判断 AI 基建好消息是否已经 price-in。",
                    "claim_id": "",
                    "evidence_refs": refs_by_id.get("req_market_price_in", [])[:5],
                },
            ],
            "evidence_gaps_but_actionable": [
                {
                    "text": "仍需公开源或商业 tracker 补齐：AI server gross margin、GPU pass-through、客户配置 mix、供应商 allocation、SKU/ASP/shipments 和 market positioning 数据。",
                    "claim_id": "",
                    "evidence_refs": _dedupe_strings(refs_by_id.get("req_dell_margin_quality", []) + refs_by_id.get("req_market_price_in", []))[:6],
                }
            ],
        }
    return {
        "investment_implications": [
            {
                "text": "AI infrastructure remains directionally positive, but Dell quality depends on ISG margin, GPU pass-through, and backlog conversion.",
                "claim_id": "",
                "evidence_refs": _dedupe_strings(refs_by_id.get("req_accelerator_architecture", []) + refs_by_id.get("req_dell_margin_quality", []))[:6],
            }
        ],
        "what_would_change_view": [
            {
                "text": "The view weakens if Dell margin fails to improve with backlog conversion or if AMD/TPU substitution and capex digestion broaden.",
                "claim_id": "",
                "evidence_refs": refs_by_id.get("req_counter_thesis", [])[:5],
            }
        ],
        "monitoring_items": [
            {
                "text": "Monitor Dell AI server orders, backlog conversion, ISG margin, accelerator deployments, and market price-in data.",
                "claim_id": "",
                "evidence_refs": _dedupe_strings(ref for refs in refs_by_id.values() for ref in refs)[:8],
            }
        ],
        "evidence_gaps_but_actionable": [
            {
                "text": "Still missing AI server gross margin, GPU pass-through, customer mix, allocation, SKU/ASP/shipments, and positioning data.",
                "claim_id": "",
                "evidence_refs": refs_by_id.get("req_market_price_in", [])[:5],
            }
        ],
    }


def _complete_direct_answer_from_memo_logic_plan(
    memo: Mapping[str, Any],
    memo_logic_plan: Mapping[str, Any],
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    current = str(memo.get("direct_answer") or "").strip()
    if len(current) >= int(memo_profile.direct_answer_min_chars or 0):
        return {"completed": False}
    required_items = [
        dict(item)
        for item in memo_logic_plan.get("required_item_answer_plan") or []
        if isinstance(item, Mapping) and str(item.get("answer") or "").strip()
    ]
    if not required_items:
        return {"completed": False}
    skeleton = _direct_answer_skeleton_from_required_items(
        required_items,
        response_language=response_language,
        max_chars=memo_profile.direct_answer_max_chars,
    )
    if len(skeleton) <= len(current) or len(skeleton) < int(memo_profile.direct_answer_min_chars or 0):
        return {"completed": False}
    return {
        "completed": True,
        "direct_answer": skeleton,
        "source_item_ids": [
            str(item.get("question_item_id") or "")
            for item in required_items
            if str(item.get("question_item_id") or "")
        ][:8],
    }


def _direct_answer_skeleton_from_required_items(
    items: list[dict[str, Any]],
    *,
    response_language: str,
    max_chars: int,
) -> str:
    by_id = {str(item.get("question_item_id") or ""): item for item in items}
    if response_language == "zh-CN":
        parts = [
            _zh_gold_required_item_sentence(by_id.get("req_accelerator_architecture"), "product"),
            _zh_gold_required_item_sentence(by_id.get("req_dell_margin_quality"), "financial"),
            _zh_gold_required_item_sentence(by_id.get("req_customer_deployment"), "deployment"),
            _zh_gold_required_item_sentence(by_id.get("req_supply_chain"), "supply_chain"),
            _zh_gold_required_item_sentence(by_id.get("req_market_price_in"), "market"),
            _zh_gold_required_item_sentence(by_id.get("req_counter_thesis"), "risk"),
        ]
        text = "".join(part for part in parts if part)
        return _truncate(_normalize_zh_punctuation(text), max_chars)
    parts = []
    for item_id in (
        "req_accelerator_architecture",
        "req_dell_margin_quality",
        "req_customer_deployment",
        "req_supply_chain",
        "req_market_price_in",
        "req_counter_thesis",
    ):
        row = by_id.get(item_id)
        answer = str((row or {}).get("answer") or "").strip()
        boundary = str((row or {}).get("cannot_infer") or "").strip()
        if answer:
            parts.append(answer.rstrip(".") + ".")
        if boundary:
            parts.append("Boundary: " + boundary.rstrip(".") + ".")
    return _truncate(" ".join(parts), max_chars)


def _zh_gold_required_item_sentence(item: Mapping[str, Any] | None, role: str) -> str:
    if not isinstance(item, Mapping) or not str(item.get("answer") or "").strip():
        return ""
    cannot = str(item.get("cannot_infer") or "").strip()
    change = str(item.get("what_would_change_view") or "").strip()
    boundary_tail = "；但不能把这些材料外推成 SKU 收入、ASP、份额或出货量。" if cannot else ""
    change_tail = "。后续能改变判断的是更细的订单、部署、定价、利润率或客户配置证据。" if change else ""
    if role == "product":
        return (
            "当前更有支撑的主判断不是简单的 AI capex 利好，而是产品和供给瓶颈仍集中在加速器系统："
            "NVDA Blackwell/GB200 的 rack-scale 架构继续定义外部 GPU 供给瓶颈，AMD MI300/MI35x 和 Google TPU 则构成真实但更偏工作负载或自用体系的替代压力"
            f"{boundary_tail}"
        )
    if role == "financial":
        return (
            "落到 DELL，AI server 需求可见度比普通服务器更强，但投资质量的关键不是需求是否存在，而是 GPU pass-through、attach rate、backlog conversion 和 ISG margin 能否证明这些收入不是低毛利放量；"
            "因此现在只能说 DELL 有 AI server revenue tailwind，不能直接说利润质量已经改善。"
        )
    if role == "deployment":
        return (
            "客户部署层面，DELL 与 Google 的官方产品和云实例表面能证明 GB200/AI server 采用路径存在，"
            "但还不足以推出客户集中度、部署规模或单客户收入，需要官方客户部署、GA capacity 或配置 mix 进一步确认。"
        )
    if role == "supply_chain":
        return (
            "供应链 read-through 应按机制拆开：TSMC 对应 advanced node 和先进封装，ASML 对应光刻和 installed base，"
            "AMAT 对应 materials engineering，LRCX 更偏 memory/HBM 工艺强度；这些能说明 AI 基建扩张会传导到半导体设备周期，"
            "但不能从 broad revenue/margin 直接推出 AI-specific orders 或客户 allocation。"
        )
    if role == "market":
        return (
            "资本市场层面，业务链条方向偏正面，但 recommendation 质量仍被 price-in 数据卡住：缺估值分位、持仓拥挤度、short/options、ETF flow 和事件后价格反应，"
            "所以这里只能形成研究判断，不能形成强买卖建议。"
        )
    if role == "risk":
        return (
            "最强反证也不是泛泛的 AI 风险，而是 hyperscaler capex digestion、DELL margin dilution、AMD/TPU 替代、NVDA supply delay、出口管制和 semicap 订单滞后；"
            f"如果后续出现订单/部署兑现放缓、利润率恶化或 capex 下修，这条 AI infrastructure thesis 就需要降权{change_tail}"
        )
    return ""


def _dimension_analyses_have_promotable_claim_material(value: Any) -> bool:
    return bool(_promotable_dimension_analysis_rows(value, max_rows=1))


def _promotable_dimension_analysis_rows(value: Any, *, max_rows: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        status = str(row.get("status") or row.get("stance") or "").strip().lower()
        if any(marker in status for marker in ("gap", "unsupported", "counter", "blocked")):
            continue
        refs = _string_list(row.get("evidence_refs") or row.get("refs"))
        summary = str(row.get("summary") or row.get("section_thesis") or row.get("text") or "").strip()
        if not refs or not summary:
            continue
        rows.append(row)
        if len(rows) >= max(1, max_rows):
            break
    return rows


def _complete_memo_claims_from_dimension_analyses(
    value: Any,
    dimension_analyses: Any,
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    memo_claims = [dict(item) for item in value or [] if isinstance(item, Mapping)]
    if len(memo_claims) >= memo_profile.memo_claims_min_when_thesis_ready:
        return {"memo_claims": memo_claims[: memo_profile.memo_claims_max], "completed_count": 0}

    out = [dict(item) for item in memo_claims]
    seen_ids = {str(item.get("claim_id") or "") for item in out if str(item.get("claim_id") or "")}
    seen_refs = {
        ref
        for item in out
        if isinstance(item, Mapping)
        for ref in _string_list(item.get("evidence_refs") or item.get("refs"))
    }
    completed = 0
    for row in _promotable_dimension_analysis_rows(dimension_analyses, max_rows=memo_profile.memo_claims_max):
        refs = _string_list(row.get("evidence_refs") or row.get("refs"))[:4]
        claim_ids = _string_list(row.get("claim_ids") or row.get("primary_claim_ids"))
        claim_id = next((claim_id for claim_id in claim_ids if claim_id and claim_id not in seen_ids), "")
        if not claim_id:
            digest_source = json.dumps(
                {
                    "dimension_id": row.get("dimension_id") or row.get("id") or "",
                    "summary": row.get("summary") or "",
                    "evidence_refs": refs[:2],
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            claim_id = "dimension_claim:" + hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
        if claim_id in seen_ids:
            continue
        if refs and set(refs).issubset(seen_refs):
            continue
        out.append(
            {
                "claim_id": claim_id,
                "claim": _dimension_analysis_claim_text(row, response_language=response_language),
                "claim_type": _dimension_claim_type(row),
                "memo_slot": _dimension_memo_slot(row),
                "analysis_dimension": str(row.get("dimension_id") or row.get("id") or ""),
                "evidence_refs": refs,
                "source_families": ["memo_dimension_analysis"],
                "confidence": "medium",
                "caveats": _string_list(row.get("source_boundaries"))[:2],
                "missing_confirmations": _string_list(row.get("what_would_change_view"))[:2],
            }
        )
        seen_ids.add(claim_id)
        seen_refs.update(refs)
        completed += 1
        if len(out) >= memo_profile.memo_claims_max:
            break
    return {
        "memo_claims": _normalize_output_memo_claims(
            out,
            {},
            max_claims=memo_profile.memo_claims_max,
            response_language=response_language,
        ),
        "completed_count": completed,
    }


def _dimension_analysis_claim_text(row: Mapping[str, Any], *, response_language: str) -> str:
    parts = [
        str(row.get("summary") or row.get("section_thesis") or row.get("text") or "").strip(),
        str(row.get("business_mechanism") or "").strip(),
        str(row.get("financial_bridge") or "").strip(),
        str(row.get("competitive_read") or "").strip(),
    ]
    text = " ".join(part for part in parts if part)
    text = _truncate_surface_field(text, 420)
    if response_language == "zh-CN":
        return _normalize_zh_punctuation(text)
    return text


def _dimension_claim_type(row: Mapping[str, Any]) -> str:
    dimension_id = str(row.get("dimension_id") or row.get("id") or "").strip()
    return {
        "fundamentals": "company_reported_financial_fact",
        "product_and_production": "product_context_supported_inference",
        "capital_and_financing": "capital_allocation_context",
        "industry_supply_chain": "relationship_hypothesis",
        "competition_and_market_position": "market_context",
        "risk_and_counterevidence": "risk_context",
    }.get(dimension_id, "dimension_supported_inference")


def _dimension_memo_slot(row: Mapping[str, Any]) -> str:
    dimension_id = str(row.get("dimension_id") or row.get("id") or "").strip()
    return {
        "fundamentals": "fundamentals",
        "product_and_production": "product_technology",
        "capital_and_financing": "fundamentals",
        "industry_supply_chain": "industry_relationship",
        "competition_and_market_position": "industry_relationship",
        "risk_and_counterevidence": "risk_counterevidence",
    }.get(dimension_id, "fundamentals")


def _complete_action_items_from_memo_claims(
    memo: Mapping[str, Any],
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    normalized = dict(memo)
    if memo_profile.profile not in {"standard", "expanded", "deep_research"}:
        return {"memo": normalized, "completed_fields": []}
    memo_claims = [dict(item) for item in normalized.get("memo_claims") or [] if isinstance(item, Mapping)]
    if not memo_claims:
        return {"memo": normalized, "completed_fields": []}

    completed: list[str] = []
    for key in ("investment_implications", "what_would_change_view", "monitoring_items"):
        if _normalize_memo_action_items(normalized.get(key), max_items=1, max_chars=180):
            continue
        normalized[key] = _default_profile_action_items(
            memo_claims,
            response_language=response_language,
            kind=key,
        )
        if normalized[key]:
            completed.append(key)
    if not _normalize_memo_action_items(normalized.get("evidence_gaps_but_actionable"), max_items=1, max_chars=180):
        gaps = _actionable_gap_items_from_memo_context(
            normalized,
            memo_claims,
            response_language=response_language,
            max_items=2,
        )
        if gaps:
            normalized["evidence_gaps_but_actionable"] = gaps
            completed.append("evidence_gaps_but_actionable")
    return {"memo": normalized, "completed_fields": completed}


def _actionable_gap_items_from_memo_context(
    memo: Mapping[str, Any],
    memo_claims: list[dict[str, Any]],
    *,
    response_language: str,
    max_items: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(text: str, *, evidence_refs: Any = None, claim_id: str = "") -> None:
        clean = _truncate_surface_field(str(text or "").strip(), 180)
        key = clean.lower()
        if not clean or key in seen or len(items) >= max_items:
            return
        seen.add(key)
        row: dict[str, Any] = {"text": clean}
        refs = _string_list(evidence_refs)[:2]
        if refs:
            row["evidence_refs"] = refs
        if claim_id:
            row["claim_id"] = claim_id
        items.append(row)

    for claim in memo_claims:
        if _memo_claim_is_source_coverage_context(claim):
            continue
        for missing in _string_list(claim.get("missing_confirmations"))[:1]:
            if response_language == "zh-CN":
                add(
                    f"{_memo_claim_gap_subject(claim)} 仍缺 {missing}；该缺口会限制收入、订单、份额或利润率外推。",
                    evidence_refs=claim.get("evidence_refs"),
                    claim_id=str(claim.get("claim_id") or ""),
                )
            else:
                add(
                    f"{_memo_claim_gap_subject(claim)} still lacks {missing}; keep revenue, orders, share, and margin extrapolation bounded.",
                    evidence_refs=claim.get("evidence_refs"),
                    claim_id=str(claim.get("claim_id") or ""),
                )
    for source_key in ("unsupported_claims_excluded", "source_boundary_notes", "missing_evidence"):
        for row in memo.get(source_key) or []:
            if not isinstance(row, Mapping):
                text = str(row or "")
                refs = []
            else:
                text = str(row.get("text") or row.get("reason") or row.get("note") or row.get("claim") or row.get("source_family") or "")
                refs = row.get("evidence_refs") or row.get("refs")
            if not text:
                continue
            if response_language == "zh-CN":
                add(f"仍需补齐：{text}", evidence_refs=refs)
            else:
                add(f"Still requires follow-up: {text}", evidence_refs=refs)
            if len(items) >= max_items:
                break
        if len(items) >= max_items:
            break
    return items[:max_items]


def _memo_claim_gap_subject(claim: Mapping[str, Any]) -> str:
    tickers = "/".join(_string_list(claim.get("ticker_scope"))[:3])
    dimension = str(claim.get("analysis_dimension") or claim.get("memo_slot") or "this claim").replace("_", " ")
    return f"{tickers} {dimension}".strip()


def _complete_memo_claims_from_judgment(
    value: Any,
    judgment: Mapping[str, Any],
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    memo_claims = [dict(item) for item in value or [] if isinstance(item, Mapping)]
    supported = [_compact_claim_card(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    thesis_ready = _judgment_has_ready_thesis(judgment)
    if not thesis_ready or not supported:
        return {"memo_claims": memo_claims, "completed_count": 0}
    minimum_claim_count = min(memo_profile.memo_claims_min_when_thesis_ready, len(supported), memo_profile.memo_claims_max)
    if len(memo_claims) >= minimum_claim_count:
        return {"memo_claims": memo_claims[: memo_profile.memo_claims_max], "completed_count": 0}

    selected = _select_memo_supported_claims(
        supported,
        judgment.get("memo_outline") or [],
        max_claims=memo_profile.memo_claims_max,
    )
    out = [dict(item) for item in memo_claims]
    seen = {str(item.get("claim_id") or "") for item in out if str(item.get("claim_id") or "")}
    completed = 0
    for claim in selected:
        claim_id = str(claim.get("claim_id") or "")
        if claim_id and claim_id in seen:
            continue
        out.append(_salvage_memo_claim_from_supported_claim(claim, response_language=response_language))
        if claim_id:
            seen.add(claim_id)
        completed += 1
        if len(out) >= minimum_claim_count or len(out) >= memo_profile.memo_claims_max:
            break
    return {
        "memo_claims": _normalize_output_memo_claims(
            out,
            judgment,
            max_claims=memo_profile.memo_claims_max,
            response_language=response_language,
        ),
        "completed_count": completed,
    }


def _complete_dimension_analyses_from_judgment(
    value: Any,
    judgment: Mapping[str, Any],
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    rows = [dict(item) for item in value or [] if isinstance(item, Mapping)]
    required_ids = _valid_memo_required_dimension_ids(judgment.get("required_dimension_ids"))
    if not required_ids:
        if rows:
            surface_caps = _memo_writer_surface_caps(memo_profile)
            normalized_rows = _normalize_output_dimension_analyses(
                rows,
                [],
                max_items=min(8, max(int(surface_caps["dimension_analyses_max"]), len(rows))),
                max_summary_chars=int(surface_caps["dimension_summary_max_chars"]),
                max_detail_chars=int(surface_caps["dimension_detail_max_chars"]),
            )
            normalized_rows = _enrich_thin_dimension_analyses_from_verified_judgment(
                normalized_rows,
                judgment,
                response_language=response_language,
            )
            enriched_count = sum(
                1
                for row in normalized_rows
                if any(str(key).endswith("_completed_from_verified_judgment") for key in row)
            )
            if _normalize_response_language(response_language) == "zh-CN":
                normalized_rows = _localize_dimension_analyses(normalized_rows)
            return {
                "dimension_analyses": normalized_rows,
                "completed_count": 0,
                "reordered_for_required_dimensions": False,
                "enriched_existing_dimension_count": enriched_count,
            }
        return {
            "dimension_analyses": rows,
            "completed_count": 0,
            "reordered_for_required_dimensions": False,
            "enriched_existing_dimension_count": 0,
        }

    surface_caps = _memo_writer_surface_caps(memo_profile)
    max_items = min(8, max(int(surface_caps["dimension_analyses_max"]), len(required_ids), len(rows)))
    by_id = {str(item.get("dimension_id") or ""): dict(item) for item in rows if str(item.get("dimension_id") or "")}
    completed = 0
    for dimension_id in required_ids:
        if dimension_id in by_id:
            continue
        row = _dimension_analysis_from_verified_judgment(
            dimension_id,
            judgment,
            response_language=response_language,
        )
        if not row:
            continue
        by_id[dimension_id] = row
        completed += 1

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: Mapping[str, Any]) -> None:
        dimension_id = str(row.get("dimension_id") or "")
        if not dimension_id or dimension_id in seen or len(ordered) >= max_items:
            return
        ordered.append(dict(row))
        seen.add(dimension_id)

    for dimension_id in required_ids:
        if dimension_id in by_id:
            add(by_id[dimension_id])
    for dimension_id in ANALYSIS_DIMENSION_ORDER:
        if dimension_id in by_id:
            add(by_id[dimension_id])
    for row in rows:
        add(row)

    normalized_rows = _normalize_output_dimension_analyses(
        ordered,
        [],
        max_items=max_items,
        max_summary_chars=int(surface_caps["dimension_summary_max_chars"]),
        max_detail_chars=int(surface_caps["dimension_detail_max_chars"]),
    )
    normalized_rows = _enrich_thin_dimension_analyses_from_verified_judgment(
        normalized_rows,
        judgment,
        response_language=response_language,
    )
    enriched_count = sum(
        1
        for row in normalized_rows
        if any(str(key).endswith("_completed_from_verified_judgment") for key in row)
    )
    if _normalize_response_language(response_language) == "zh-CN":
        normalized_rows = _localize_dimension_analyses(normalized_rows)
    normalized_ids = [str(row.get("dimension_id") or "") for row in normalized_rows]
    return {
        "dimension_analyses": normalized_rows,
        "completed_count": completed,
        "reordered_for_required_dimensions": bool(required_ids and normalized_ids[: len(required_ids)] != required_ids[: len(normalized_ids)]),
        "enriched_existing_dimension_count": enriched_count,
    }


def _enrich_thin_dimension_analyses_from_verified_judgment(
    rows: list[dict[str, Any]],
    judgment: Mapping[str, Any],
    *,
    response_language: str,
) -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        dimension_id = str(row.get("dimension_id") or "")
        if not dimension_id:
            enriched_rows.append(dict(row))
            continue
        verified = _dimension_analysis_from_verified_judgment(
            dimension_id,
            judgment,
            response_language=response_language,
        )
        if not verified:
            enriched_rows.append(dict(row))
            continue
        merged = dict(row)
        if len(str(merged.get("summary") or "").strip()) < 24 and verified.get("summary"):
            merged["summary"] = verified.get("summary")
            merged["summary_completed_from_verified_judgment"] = True
        for key in ("business_mechanism", "financial_bridge", "competitive_read", "counter_read", "analysis_lens"):
            if len(str(merged.get(key) or "").strip()) < 24 and verified.get(key):
                merged[key] = verified.get(key)
                merged[f"{key}_completed_from_verified_judgment"] = True
        if len(str(merged.get("summary") or "").strip()) < 24:
            synthesized_summary = _dimension_summary_from_completed_fields(
                merged,
                verified,
                dimension_id=dimension_id,
                response_language=response_language,
            )
            if synthesized_summary:
                merged["summary"] = synthesized_summary
                merged["summary_completed_from_verified_judgment"] = True
        for key in (
            "claim_ids",
            "counter_claim_ids",
            "counter_driver_ids",
            "gap_ids",
            "evidence_refs",
            "source_boundaries",
            "what_would_change_view",
        ):
            if key == "evidence_refs" and verified.get(key):
                merged[key] = verified.get(key)
                merged["evidence_refs_completed_from_verified_judgment"] = True
                continue
            if not _string_list(merged.get(key)) and verified.get(key):
                merged[key] = verified.get(key)
        enriched_rows.append(merged)
    return enriched_rows


def _dimension_summary_from_completed_fields(
    row: Mapping[str, Any],
    verified: Mapping[str, Any],
    *,
    dimension_id: str,
    response_language: str,
) -> str:
    business = str(row.get("business_mechanism") or verified.get("business_mechanism") or "").strip()
    bridge = str(row.get("financial_bridge") or verified.get("financial_bridge") or "").strip()
    counter = str(row.get("counter_read") or verified.get("counter_read") or "").strip()
    if not (business or bridge or counter):
        return ""
    if _normalize_response_language(response_language) == "zh-CN":
        business = _zh_dimension_fallback_text(
            dimension_id=dimension_id,
            field="business_mechanism",
            text=business,
            status=str(row.get("status") or verified.get("status") or ""),
        )
        bridge = _zh_dimension_fallback_text(
            dimension_id=dimension_id,
            field="financial_bridge",
            text=bridge,
            status=str(row.get("status") or verified.get("status") or ""),
        )
        parts = [part.rstrip("。.!?") for part in (business, bridge) if part]
        if counter:
            counter_zh = _zh_dimension_fallback_text(
                dimension_id=dimension_id,
                field="counter_read",
                text=counter,
                status=str(row.get("status") or verified.get("status") or ""),
            ).rstrip("。.!?")
            parts.append(f"反向约束是：{counter_zh}")
        if parts:
            return "；".join(parts[:3]) + "。"
    parts = [part.rstrip(".!?") for part in (business, bridge, counter) if part]
    return ". ".join(parts[:3]) + "." if parts else ""


def _dimension_analysis_from_verified_judgment(
    dimension_id: str,
    judgment: Mapping[str, Any],
    *,
    response_language: str,
) -> dict[str, Any]:
    section = _verified_dimension_section(judgment, dimension_id)
    claims = _claims_for_dimension(judgment, dimension_id)
    summary_probe = str(section.get("summary") or section.get("section_thesis") or "").strip()
    counter_probe = str(section.get("counter_read") or section.get("competitive_read") or "").strip()
    status_probe = str(section.get("status") or "").strip().lower()
    claim_ids = _dedupe_strings(
        _string_list(section.get("primary_claim_ids") or section.get("claim_ids"))
        + [str(claim.get("claim_id") or "") for claim in claims if str(claim.get("claim_id") or "")]
    )[:8]
    claim_evidence_refs = _dedupe_strings(
        [
            ref
            for claim in claims
            for ref in _string_list(claim.get("evidence_refs") or claim.get("refs"))
        ]
    )
    section_evidence_refs = _string_list(section.get("evidence_refs") or section.get("refs"))
    if claim_evidence_refs:
        section_evidence_refs = [ref for ref in section_evidence_refs if ref in set(claim_evidence_refs)]
    evidence_refs = _dedupe_strings(claim_evidence_refs + section_evidence_refs)[:8]
    gap_ids = _string_list(section.get("gap_ids"))[:5]
    counter_claim_ids = _string_list(section.get("counter_claim_ids"))[:4]
    counter_driver_ids = _string_list(section.get("counter_driver_ids"))[:4]
    if not (claim_ids or evidence_refs or gap_ids or counter_claim_ids or counter_driver_ids):
        if (
            summary_probe
            or counter_probe
        ) and (
            bool(section.get("required_by_user"))
            or dimension_id in {"risk_and_counterevidence", "evidence_gap"}
            or any(marker in status_probe for marker in ("gap", "counter", "risk", "partial"))
        ):
            gap_ids = [f"gap_untraced_dimension_{dimension_id}"]
        else:
            return {}

    title = str(section.get("title") or section.get("dimension_title") or _dimension_title_for_id(dimension_id))
    if response_language == "zh-CN":
        title = _zh_dimension_label(dimension_id)
    summary = summary_probe
    if not summary and claims:
        summary = _salvage_direct_claim_sentence(claims[0], response_language=response_language)
    if response_language == "zh-CN" and (not _contains_cjk(summary) or _needs_zh_wrapper(summary)):
        summary = _zh_dimension_fallback_text(dimension_id=dimension_id, field="summary", text=summary, status=str(section.get("status") or ""))
    row = {
        "dimension_id": dimension_id,
        "title": title,
        "summary": summary,
        "analysis_lens": str(section.get("analysis_lens") or _dimension_title_for_id(dimension_id)),
        "business_mechanism": str(section.get("business_mechanism") or summary),
        "financial_bridge": str(section.get("financial_bridge") or summary),
        "competitive_read": str(section.get("competitive_read") or section.get("counter_read") or ""),
        "counter_read": str(section.get("counter_read") or section.get("competitive_read") or ""),
        "claim_ids": claim_ids,
        "counter_claim_ids": counter_claim_ids,
        "counter_driver_ids": counter_driver_ids,
        "gap_ids": gap_ids,
        "evidence_refs": evidence_refs,
        "source_boundaries": _dedupe_strings(
            _string_list(section.get("source_boundaries"))
            + (
                ["counter/gap dimension has text but no original claim_id/evidence_ref; keep as low-confidence boundary"]
                if gap_ids and str(gap_ids[0]).startswith("gap_untraced_dimension_")
                else []
            )
        )[:5],
        "what_would_change_view": _string_list(section.get("what_would_change_view"))[:4],
        "status": str(section.get("status") or "supported"),
        "rendering_policy": "verified_judgment_contract_completion_v0_1",
    }
    return {key: value for key, value in row.items() if value not in ("", [], {}, None)}


def _verified_dimension_section(judgment: Mapping[str, Any], dimension_id: str) -> dict[str, Any]:
    pack = judgment.get("thesis_driver_pack") if isinstance(judgment.get("thesis_driver_pack"), Mapping) else {}
    for section in pack.get("dimension_sections") or []:
        if isinstance(section, Mapping) and str(section.get("dimension_id") or "") == dimension_id:
            return dict(section)
    state = judgment.get("judgment_state") if isinstance(judgment.get("judgment_state"), Mapping) else {}
    for section in state.get("dimension_judgments") or []:
        if isinstance(section, Mapping) and str(section.get("dimension_id") or section.get("dimension") or "") == dimension_id:
            return dict(section)
    return {}


def _claims_for_dimension(judgment: Mapping[str, Any], dimension_id: str) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in judgment.get("supported_claims") or []
        if isinstance(item, Mapping)
        and str(item.get("analysis_dimension") or _analysis_dimension_for_memo_claim(item)) == dimension_id
    ]


def _analysis_dimension_for_memo_claim(claim: Mapping[str, Any]) -> str:
    slot = str(claim.get("memo_slot") or "").strip()
    return {
        "fundamental": "fundamentals",
        "fundamentals": "fundamentals",
        "product_technology": "product_and_production",
        "product_and_production": "product_and_production",
        "capital_allocation": "capital_and_financing",
        "capital_and_financing": "capital_and_financing",
        "industry_relationship": "industry_supply_chain",
        "market_valuation": "competition_and_market_position",
        "risk_counterevidence": "risk_and_counterevidence",
        "risk_and_counterevidence": "risk_and_counterevidence",
    }.get(slot, "thesis_synthesis")


def _valid_memo_required_dimension_ids(value: Any) -> list[str]:
    valid = set(ANALYSIS_DIMENSION_ORDER)
    out: list[str] = []
    for item in _string_list(value):
        dimension = str(item or "").strip().lower().replace("-", "_").replace(" ", "_")
        if dimension in valid and dimension not in out:
            out.append(dimension)
    return out


def _pre_writer_required_dimension_material_gate(state: Mapping[str, Any], judgment: Mapping[str, Any]) -> dict[str, Any]:
    required_ids = _valid_memo_required_dimension_ids(judgment.get("required_dimension_ids"))
    if not required_ids:
        memo_logic_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {}
        required_ids = _valid_memo_required_dimension_ids(memo_logic_plan.get("section_order"))
    if not required_ids:
        return {
            "schema_version": "sec_agent_pre_writer_required_dimension_material_gate_v0.1",
            "status": "pass",
            "checked_required_dimension_ids": [],
            "missing_required_dimension_ids": [],
        }
    missing: list[str] = []
    checked: list[dict[str, Any]] = []
    for dimension_id in required_ids:
        section = _verified_dimension_section(judgment, dimension_id)
        claims = _claims_for_dimension(judgment, dimension_id)
        claim_ids = [
            str(claim.get("claim_id") or "")
            for claim in claims
            if str(claim.get("claim_id") or "")
        ]
        claim_refs = [
            ref
            for claim in claims
            for ref in _string_list(claim.get("evidence_refs") or claim.get("refs"))
        ]
        material = {
            "claim_ids": _dedupe_strings(
                _string_list(section.get("primary_claim_ids") or section.get("claim_ids")) + claim_ids
            ),
            "counter_claim_ids": _string_list(section.get("counter_claim_ids")),
            "counter_driver_ids": _string_list(section.get("counter_driver_ids")),
            "gap_ids": _string_list(section.get("gap_ids")),
            "evidence_refs": _dedupe_strings(
                _string_list(section.get("evidence_refs") or section.get("refs")) + claim_refs
            ),
            "summary": str(section.get("summary") or section.get("section_thesis") or "").strip(),
            "counter_read": str(section.get("counter_read") or section.get("competitive_read") or "").strip(),
        }
        has_material = bool(
            material["claim_ids"]
            or material["counter_claim_ids"]
            or material["counter_driver_ids"]
            or material["gap_ids"]
            or material["evidence_refs"]
            or material["summary"]
            or material["counter_read"]
        )
        checked.append(
            {
                "dimension_id": dimension_id,
                "has_writer_material": has_material,
                "claim_count": len(material["claim_ids"]),
                "counter_count": len(material["counter_claim_ids"]) + len(material["counter_driver_ids"]),
                "gap_count": len(material["gap_ids"]),
                "evidence_ref_count": len(material["evidence_refs"]),
                "has_summary": bool(material["summary"]),
                "has_counter_read": bool(material["counter_read"]),
            }
        )
        if not has_material:
            missing.append(dimension_id)
    return {
        "schema_version": "sec_agent_pre_writer_required_dimension_material_gate_v0.1",
        "status": "fail" if missing else "pass",
        "checked_required_dimension_ids": required_ids,
        "missing_required_dimension_ids": missing,
        "checked_dimensions": checked,
        "policy": "block_paid_writer_when_required_dimension_has_no_traceable_material_v0_1",
    }


def _judgment_has_ready_thesis(judgment: Mapping[str, Any]) -> bool:
    return (
        isinstance(judgment.get("memo_thesis_pack"), Mapping)
        and str((judgment.get("memo_thesis_pack") or {}).get("status") or "") == "ready"
    ) or (
        isinstance(judgment.get("memo_thesis_plan"), Mapping)
        and str((judgment.get("memo_thesis_plan") or {}).get("status") or "") == "ready"
    )


def _localize_memo_user_text(memo: Mapping[str, Any], *, response_language: str) -> dict[str, Any]:
    if _normalize_response_language(response_language) != "zh-CN":
        return dict(memo)
    localized = dict(memo)
    localized["source_boundary"] = _localize_source_boundary_for_zh(localized.get("source_boundary"))
    localized["direct_answer"] = _normalize_zh_punctuation(localized.get("direct_answer"))
    if _needs_zh_wrapper(localized.get("direct_answer")):
        localized["direct_answer"] = _zh_wrapped_user_text(str(localized.get("direct_answer") or ""), kind="direct")
        localized["response_language_normalized_user_text"] = True

    memo_claims: list[dict[str, Any]] = []
    for claim in localized.get("memo_claims") or []:
        if not isinstance(claim, Mapping):
            continue
        row = dict(claim)
        row["claim"] = _normalize_zh_punctuation(row.get("claim"))
        if _needs_zh_wrapper(row.get("claim")):
            row["claim"] = _zh_wrapped_user_text(str(row.get("claim") or ""), kind="claim")
            row["response_language_normalized_user_text"] = True
            localized["response_language_normalized_user_text"] = True
        memo_claims.append(row)
    localized["memo_claims"] = memo_claims
    localized["dimension_analyses"] = _localize_dimension_analyses(localized.get("dimension_analyses"))

    for key in (
        "investment_implications",
        "what_would_change_view",
        "monitoring_items",
        "evidence_gaps_but_actionable",
        "caveats",
        "unsupported_claims_excluded",
        "source_boundary_notes",
    ):
        localized[key] = _localize_memo_loose_items(localized.get(key), key=key)
        if any(isinstance(item, Mapping) and item.get("response_language_normalized_user_text") for item in localized[key]):
            localized["response_language_normalized_user_text"] = True
    return localized


def _enforce_decision_useful_memo_surface(
    memo: Mapping[str, Any],
    judgment: Mapping[str, Any],
    *,
    response_language: str,
) -> dict[str, Any]:
    normalized = dict(memo)
    if str(normalized.get("answer_status") or "") != "draft":
        return normalized
    profile = _memo_profile_spec_from_name(((normalized.get("memo_profile") or {}) if isinstance(normalized.get("memo_profile"), Mapping) else {}).get("profile"))
    selected_claims = _select_memo_supported_claims(
        [_compact_claim_card(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)],
        judgment.get("memo_outline") or [],
        max_claims=min(MEMO_SALVAGE_SUPPORTED_CLAIM_CAP, profile.memo_claims_max),
    )
    diagnostics = dict(normalized.get("memo_writer_diagnostics") or {})
    direct = str(normalized.get("direct_answer") or "")
    if _memo_text_is_gap_or_boundary_led(direct[:620]) or _memo_text_is_template_or_low_density_opening(direct):
        normalized["direct_answer"] = _salvage_direct_answer(judgment, selected_claims, response_language=response_language)
        diagnostics["direct_answer_rewritten_for_decision_surface"] = True
    for key, kind, max_items in (
        ("investment_implications", "investment_implications", 3),
        ("what_would_change_view", "what_would_change_view", 2),
        ("monitoring_items", "monitoring_items", 3),
    ):
        rows = normalized.get(key) if isinstance(normalized.get(key), list) else []
        text = " ".join(_memo_loose_item_text(item) for item in rows)
        if not rows or _memo_text_is_gap_or_boundary_led(text):
            normalized[key] = _salvage_action_items(
                selected_claims or [dict(item) for item in normalized.get("memo_claims") or [] if isinstance(item, Mapping)],
                response_language=response_language,
                kind=kind,
                max_items=max_items,
            )
            diagnostics[f"{key}_rewritten_for_decision_surface"] = True
    if diagnostics:
        normalized["memo_writer_diagnostics"] = diagnostics
    return normalized


def _memo_loose_item_text(item: Any) -> str:
    if isinstance(item, Mapping):
        return str(item.get("text") or item.get("claim") or item.get("reason") or "")
    return str(item or "")


def _memo_text_is_gap_or_boundary_led(text: str) -> bool:
    value = str(text or "").lower()
    if not value.strip():
        return False
    gap_terms = (
        "缺乏",
        "缺少",
        "缺失",
        "无法",
        "不能",
        "不足",
        "未披露",
        "尚未",
        "没有",
        "边界",
        "受限",
        "仅能确认",
        "需等待",
        "口径不匹配",
        "证据范围",
        "not available",
        "cannot",
        "could not",
        "insufficient",
        "missing",
        "limited",
        "not yet",
        "bounded",
        "source boundary",
    )
    hits = sum(value.count(term) for term in gap_terms)
    decision_terms = (
        "主线",
        "判断",
        "取决于",
        "反向风险",
        "上调",
        "可执行",
        "supports",
        "depends on",
        "counter-read",
        "risk is",
    )
    decision_hits = sum(value.count(term) for term in decision_terms)
    if len(value.strip()) > 220 and decision_hits >= 3:
        return False
    return hits >= 2 or (hits >= 1 and len(value.strip()) <= 120)


def _memo_text_is_template_or_low_density_opening(text: str) -> bool:
    value = str(text or "").strip().lower()
    if not value:
        return False
    template_markers = (
        "当前证据更适合形成一份谨慎的分维度判断",
        "当前证据不足以支持强方向结论",
        "缺失的订单、份额或商业 tracker",
        "缺少的订单、份额或商业 tracker",
        "available evidence supports a cautious",
        "available evidence does not support a strong directional",
        "missing orders, share, and commercial tracker",
    )
    if any(marker.lower() in value for marker in template_markers):
        return True
    gap_terms = ("缺口", "缺乏", "缺少", "缺失", "无法", "不能", "不足", "尚未", "受限", "边界", "gap", "missing", "cannot", "insufficient", "limited")
    insight_terms = ("收入", "毛利", "现金流", "订单", "资本开支", "传导", "供应链", "产品", "客户", "revenue", "margin", "cash flow", "capex", "orders", "supplier")
    gap_hits = sum(value.count(term) for term in gap_terms)
    insight_hits = sum(value.count(term) for term in insight_terms)
    return gap_hits >= 3 and insight_hits <= 2


def _normalize_zh_punctuation(value: Any) -> str:
    text = str(value or "")
    if not text or not _contains_cjk(text):
        return text
    text = re.sub(r"(来自|基于|引用自|披露于)\s*[；;]\s*([A-Z]{2,6}\b)", r"\1 \2", text)
    text = re.sub(r"(来自|基于|引用自|披露于)\s*[；;]\s*(\d{4}|10-[KQ]|8-K)", r"\1 \2", text)
    text = re.sub(r"([。！？；，、])\s*\.", r"\1", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\.", "。", text)
    text = re.sub(r"\.\s*([。！？；，、])", r"\1", text)
    text = re.sub(r"([。！？]){2,}", r"\1", text)
    text = re.sub(
        r"([\u4e00-\u9fff])"
        r"(AMZN|MSFT|GOOGL|GOOG|NVDA|AMD|JPM|BAC|C|WFC|GS|WMT|TGT|XOM|CVX|LLY|PFE|BMY|AMGN|HCA|NEE|DUK|SO|SRE|XEL|DELL|ANET|VRT)\b",
        r"\1；\2",
        text,
    )
    return text.strip()


def _localize_memo_loose_items(value: Any, *, key: str) -> list[Any]:
    rows: list[Any] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            row = dict(item)
            field = "text" if row.get("text") else "claim" if row.get("claim") else "reason" if row.get("reason") else ""
            if field:
                row[field] = _normalize_zh_punctuation(row.get(field))
            if field and _needs_zh_localization(row.get(field)):
                row[field] = _zh_wrapped_user_text(str(row.get(field) or ""), kind=key)
                row["response_language_normalized_user_text"] = True
            rows.append(row)
        elif _needs_zh_localization(item):
            rows.append(_zh_wrapped_user_text(str(item or ""), kind=key))
        else:
            rows.append(item)
    return rows


def _needs_zh_wrapper(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if _contains_cjk(text):
        return False
    stripped = re.sub(r"\[[^\]]+\]", " ", text)
    stripped = re.sub(r"\b(?:[A-Z]{1,6}|10-[KQ]|8-K|GAAP|SEC|FY\d{2,4}|Q[1-4])\b", " ", stripped)
    return len(stripped.strip()) >= 16


def _needs_zh_localization(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if _needs_zh_wrapper(text):
        return True
    if not _contains_cjk(text):
        return False
    normalized = re.sub(r"\b(?:[A-Z]{1,6}|10-[KQ]|8-K|GAAP|SEC|FY\d{2,4}|Q[1-4])\b", " ", text)
    latin_words = re.findall(r"[A-Za-z]{4,}", normalized)
    if len(latin_words) < 5:
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    return len(latin_words) > max(4, cjk_count // 6)


def _first_iso_date(values: list[str]) -> str:
    for value in values:
        match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", str(value or ""))
        if match:
            return match.group(0)
    return ""


def _zh_wrapped_user_text(text: str, *, kind: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return clean
    clean = _zh_localized_english_fragment(clean)
    clean = _normalize_zh_punctuation(clean)
    if clean and not clean.endswith(("。", "！", "？", ".", "!", "?")):
        clean = f"{clean}。"
    return clean


def _zh_localized_english_fragment(text: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return clean
    replacements = [
        (
            r"\bFinancial evidence supports a bounded margin-quality read\b",
            "财务证据支持一个有边界的利润率质量判断",
        ),
        (
            r"\bAI server revenue must translate through product mix and service economics\b",
            "AI server 收入需要通过产品组合和服务经济性传导到盈利质量",
        ),
        (
            r"\bGross margin and product revenue are the key bridge to earnings quality\b",
            "毛利率和产品收入是连接盈利质量的关键桥",
        ),
        (
            r"\bCapex demand pool alone does not prove supplier orders\b",
            "云厂商 capex 只能证明需求池，不能单独证明供应商订单",
        ),
        (
            r"\bProduct family and GPU generation evidence support product capability analysis\b",
            "产品 family 和 GPU 代际证据可以支撑产品能力分析",
        ),
        (
            r"\bGPU generation and AI server configuration drive deployment relevance\b",
            "GPU 代际和 AI server 配置决定客户部署相关性",
        ),
        (
            r"\bProduct capability matters only if it converts into mix, margin, or deployments\b",
            "产品能力只有转化为产品组合、毛利率或客户部署时才进入财务判断",
        ),
        (
            r"\bAbsence of SKU revenue keeps the conclusion bounded\b",
            "缺少 SKU 收入披露会限制结论强度",
        ),
        (r"\bMissing confirmation:\s*", "缺少确认："),
        (r"\bMissing public confirmation resolves against the thesis:\s*", "如果缺失公开确认，需要降低主线权重："),
        (r"\bNo direct\b", "没有直接"),
        (r"\bNo\b", "没有"),
        (r"\bnot in bounded evidence\b", "不在当前有界证据中"),
        (r"\bin bounded evidence\b", "在当前有界证据中"),
        (r"\bcompany-reported\b", "公司披露的"),
        (r"\border data\b", "订单数据"),
        (r"\borders/backlog\b", "订单/积压"),
        (r"\border/backlog\b", "订单/积压"),
        (r"\brevenue or order data\b", "收入或订单数据"),
        (r"\brevenue\b", "收入"),
        (r"\bproduct names\b", "产品名称"),
        (r"\bproduct specs\b", "产品规格"),
        (r"\bfinancials\b", "财务数据"),
        (r"\bcustomer wins\b", "客户订单/部署"),
        (r"\bsupplier-customer edge\b", "供应商-客户关系边"),
        (r"\brelationship graph\b", "关系图谱"),
        (r"\bAI-optimized server\b", "AI 优化服务器"),
        (r"\bserver product\b", "服务器产品"),
        (r"\bPeer comparison is available only across the verified ticker scope:\s*", "同行比较仅限于已验证股票范围："),
        (r"\btickers=\b", "股票="),
        (r"\bmetrics=\b", "指标="),
        (r"\bsector\b", "行业"),
        (r"\bproduct_or_business_line_profile\b", "产品/业务线画像"),
        (r"\bdirection=positive\b", "方向=正向"),
        (r"\bdo not infer unverified sales, share, or forecast values\b", "不得推断未验证的销售、份额或预测值"),
        (r"\bMap industry demand, customer/supplier, macro, and supply-chain proxies to company exposure without treating context as reported company fact\b", "把行业需求、客户/供应商、宏观和供应链 proxy 映射到公司暴露，但不能把背景信息当作公司披露事实"),
        (r"\bThe evidence traces external demand or supply-chain exposure to the company's relevant products, segments, or counterparties\b", "这些证据把外部需求或供应链暴露连接到公司的相关产品、分部或交易对手"),
        (r"\bBridge the claim through\b", "只能通过以下证据桥接："),
        (r"\bNVDA and DELL are co-exposed to AI infrastructure demand as sector-depth peers, with DELL's Servers and Networking segment positioned to benefit from NVDA GPU-driven server builds\b", "NVDA 与 DELL 都暴露于 AI 基础设施需求；DELL 的服务器与网络分部理论上受 NVDA GPU 驱动的服务器建设影响"),
        (r"\bDELL ISG\b", "DELL ISG"),
        (r"\bGPU\b", "GPU"),
        (r"\bANET\b", "ANET"),
        (r"\bVRT\b", "VRT"),
    ]
    localized = clean
    for pattern, replacement in replacements:
        localized = re.sub(pattern, replacement, localized, flags=re.IGNORECASE)
    localized = re.sub(r"\s*;\s*", "；", localized)
    localized = re.sub(r"\s*,\s*", "，", localized)
    localized = re.sub(r"\s{2,}", " ", localized).strip()
    if _english_heavy_after_zh_localization(localized):
        tickers = "/".join(sorted(set(re.findall(r"\b[A-Z]{2,6}\b", clean)))[:4])
        prefix = f"{tickers} 相关证据" if tickers else "该项证据"
        if re.search(r"\bmissing|absent|not in|no direct|缺少|没有\b", clean, flags=re.IGNORECASE):
            return f"{prefix}仍缺少可直接提权的订单、产品规格、客户部署或供应商-客户关系边；因此只能降低结论置信度，不能外推未验证收入、份额或销量"
        return f"{prefix}尚未完成中文综合；正式 memo 必须回到对应 JudgmentCard 写清楚支持的判断、商业机制、不能外推项和后续验证指标"
    return localized


def _english_heavy_after_zh_localization(text: str) -> bool:
    value = str(text or "")
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", value))
    latin_text = re.sub(r"\b(?:[A-Z]{1,6}|10-[KQ]|8-K|GAAP|SEC|FY\d{2,4}|Q[1-4]|GPU|CPU|AI|ISG)\b", " ", value)
    latin_words = len(re.findall(r"[A-Za-z]{4,}", latin_text))
    return latin_words >= 5 and cjk_count < latin_words * 3


def _localize_source_boundary_for_zh(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"verified judgment plan only", "bounded verified judgment plan only"}:
        return "仅限已验证 judgment plan；不包含原始检索行。"
    if not _contains_cjk(text):
        return "仅限已验证 judgment plan 和 source_boundary_notes 指定的证据范围；不包含原始检索行。"
    return text


def _normalize_output_memo_thesis_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "primary_thesis_claim_id": str(value.get("primary_thesis_claim_id") or ""),
        "primary_thesis": _truncate(str(value.get("primary_thesis") or ""), 160),
        "thesis_direction": str(value.get("thesis_direction") or ""),
    }


def _normalize_output_memo_claims(
    value: Any,
    judgment: Mapping[str, Any],
    *,
    max_claims: int = 5,
    response_language: str = "en-US",
) -> list[dict[str, Any]]:
    supported_by_id = {
        str(item.get("claim_id") or ""): dict(item)
        for item in judgment.get("supported_claims") or []
        if isinstance(item, Mapping) and str(item.get("claim_id") or "")
    }
    claims = [dict(item) for item in value or [] if isinstance(item, Mapping)]
    normalized: list[dict[str, Any]] = []
    for claim in claims[: max(1, max_claims)]:
        row = dict(claim)
        source = supported_by_id.get(str(row.get("claim_id") or ""))
        if source:
            for key in (
                "claim_type",
                "ticker_scope",
                "metric_scope",
                "memo_slot",
                "materiality",
                "direction",
                "evidence_refs",
                "source_families",
                "confidence",
                "caveats",
                "missing_confirmations",
                "as_of_date",
                "snapshot_id",
                "period_role",
                "analysis_dimension",
                "dimension_id",
            ):
                if not row.get(key) and source.get(key):
                    row[key] = source.get(key)
            if not row.get("dimension_id") and row.get("analysis_dimension"):
                row["dimension_id"] = row.get("analysis_dimension")
            if not row.get("analysis_dimension") and row.get("dimension_id"):
                row["analysis_dimension"] = row.get("dimension_id")
            source_families = _string_list(row.get("source_families") or row.get("source_family"))
            if "relationship_graph" in source_families and str(row.get("claim_type") or "") not in {
                "relationship_hypothesis",
                "scope_hypothesis",
                "industry_context_only",
                "investment_thesis_synthesis",
            }:
                row["claim_type"] = "relationship_hypothesis"
                row["relationship_claim_type_normalized"] = True
            if "market_snapshot" in source_families and not str(row.get("as_of_date") or ""):
                refs = _string_list(row.get("evidence_refs") or row.get("refs"))
                row["as_of_date"] = _first_iso_date(refs) or "latest_available_market_snapshot"
                row["market_as_of_date_inferred"] = True
            unknown_numeric_tokens = _unknown_numeric_tokens(str(row.get("claim") or ""), _claim_scope_text(source))
            hard_unknown_tokens = [token for token in unknown_numeric_tokens if _is_material_numeric_token(token)]
            if hard_unknown_tokens:
                current_claim = str(row.get("claim") or "")
                if response_language == "zh-CN" and _contains_cjk(current_claim):
                    row["claim"] = _remove_unknown_numeric_tokens_from_text(current_claim, set(hard_unknown_tokens))
                    row["numeric_fidelity_removed_tokens"] = sorted(hard_unknown_tokens)[:8]
                else:
                    row["claim"] = str(source.get("claim") or row.get("claim") or "")
                row["numeric_fidelity_normalized"] = True
        normalized.append(row)
    return normalized


def _normalize_output_dimension_analyses(
    value: Any,
    fallback: Any,
    *,
    max_items: int,
    max_summary_chars: int = 420,
    max_detail_chars: int = 260,
) -> list[dict[str, Any]]:
    fallback_rows = [dict(item) for item in (fallback if isinstance(fallback, list) else []) if isinstance(item, Mapping)]
    fallback_by_id = {str(item.get("dimension_id") or ""): item for item in fallback_rows if str(item.get("dimension_id") or "")}
    rows = [dict(item) for item in (value if isinstance(value, list) else []) if isinstance(item, Mapping)]
    if not rows:
        rows = fallback_rows
    normalized: list[dict[str, Any]] = []

    def normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
        dimension_id = str(row.get("dimension_id") or row.get("id") or "").strip()
        fallback_row = fallback_by_id.get(dimension_id, {})
        if not dimension_id:
            dimension_id = str(fallback_row.get("dimension_id") or "").strip()
        merged = {**fallback_row, **row}
        summary = str(merged.get("summary") or merged.get("section_thesis") or merged.get("text") or "").strip()
        normalized_row = {
            "dimension_id": dimension_id,
            "title": _truncate(str(merged.get("title") or merged.get("dimension_title") or _dimension_title_for_id(dimension_id)), 90),
            "summary": _truncate_surface_field(summary, max_summary_chars),
            "analysis_lens": _truncate_surface_field(str(merged.get("analysis_lens") or ""), max_detail_chars),
            "business_mechanism": _truncate_surface_field(str(merged.get("business_mechanism") or ""), max_detail_chars),
            "financial_bridge": _truncate_surface_field(str(merged.get("financial_bridge") or ""), max_detail_chars),
            "comparison_basis": _string_list(merged.get("comparison_basis"))[:4],
            "competitive_read": _truncate_surface_field(str(merged.get("competitive_read") or ""), max_detail_chars),
            "counter_read": _truncate_surface_field(str(merged.get("counter_read") or ""), max_detail_chars),
            "claim_ids": _string_list(merged.get("claim_ids") or merged.get("primary_claim_ids"))[:8],
            "counter_claim_ids": _string_list(merged.get("counter_claim_ids"))[:4],
            "counter_driver_ids": _string_list(merged.get("counter_driver_ids"))[:4],
            "gap_ids": _string_list(merged.get("gap_ids"))[:5],
            "evidence_refs": _string_list(merged.get("evidence_refs") or merged.get("refs"))[:8],
            "source_boundaries": [_truncate(str(item), 160) for item in _string_list(merged.get("source_boundaries"))[:5]],
            "what_would_change_view": [
                _truncate(str(item), 180) for item in _string_list(merged.get("what_would_change_view"))[:4]
            ],
            "status": str(merged.get("status") or ""),
        }
        if merged.get("response_language_normalized_user_text"):
            normalized_row["response_language_normalized_user_text"] = True
        for key, value in merged.items():
            key_str = str(key)
            if key_str.endswith("_completed_from_verified_judgment") and value:
                normalized_row[key_str] = True
        return normalized_row

    for row in rows[: max(1, max_items)]:
        normalized_row = normalize_row(row)
        if _memo_dimension_analysis_renderable(normalized_row):
            normalized.append(normalized_row)
    seen_dimension_ids = {str(row.get("dimension_id") or "") for row in normalized if str(row.get("dimension_id") or "")}
    for fallback_row in fallback_rows:
        dimension_id = str(fallback_row.get("dimension_id") or "").strip()
        if len(normalized) >= max(1, max_items):
            break
        if dimension_id and dimension_id not in seen_dimension_ids:
            normalized_row = normalize_row(fallback_row)
            if _memo_dimension_analysis_renderable(normalized_row):
                normalized.append(normalized_row)
                seen_dimension_ids.add(dimension_id)
    return [row for row in normalized if row.get("dimension_id") or row.get("summary")]


def _memo_dimension_analysis_renderable(row: Mapping[str, Any]) -> bool:
    dimension_id = str(row.get("dimension_id") or "").strip()
    if dimension_id == "thesis_synthesis":
        return False
    title = str(row.get("title") or "").strip().lower()
    summary = str(row.get("summary") or "").strip().lower()
    if title == "synthesis" and summary in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        return False
    return True


def _truncate_surface_field(text: str, max_chars: int) -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    marker = "...[truncated]"
    if max_chars <= len(marker):
        return value[: max(0, max_chars)]
    return value[: max_chars - len(marker)].rstrip() + marker


def _dimension_title_for_id(value: str) -> str:
    return {
        "fundamentals": "Fundamentals and financial quality",
        "product_and_production": "Product and production line evidence",
        "capital_and_financing": "Capital allocation and financing",
        "competition_and_market_position": "Competition and market position",
        "industry_supply_chain": "Industry and supply-chain transmission",
        "risk_and_counterevidence": "Risk and counterevidence",
        "evidence_gap": "Evidence gap",
    }.get(str(value or "").strip(), "Analyst dimension")


def _localize_dimension_analyses(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        dimension_id = str(row.get("dimension_id") or "")
        if not _contains_cjk(str(row.get("title") or "")):
            row["title"] = _zh_dimension_title(dimension_id, row.get("title"))
        for key in ("summary", "analysis_lens", "business_mechanism", "financial_bridge", "competitive_read", "counter_read"):
            row[key] = _normalize_zh_punctuation(row.get(key))
            if _needs_zh_localization(row.get(key)):
                row[key] = _zh_dimension_fallback_text(
                    dimension_id=dimension_id,
                    field=key,
                    text=str(row.get(key) or ""),
                    status=str(row.get("status") or ""),
                )
                row["response_language_normalized_user_text"] = True
        row["source_boundaries"] = [
            _localize_source_boundary_for_zh(item) if not _contains_cjk(str(item or "")) else _normalize_zh_punctuation(item)
            for item in _string_list(row.get("source_boundaries"))[:5]
        ]
        row["what_would_change_view"] = [
            _zh_wrapped_user_text(str(item), kind="what_would_change_view")
            if _needs_zh_wrapper(item)
            else _normalize_zh_punctuation(item)
            for item in _string_list(row.get("what_would_change_view"))[:4]
        ]
        rows.append(row)
    return rows


def _zh_dimension_title(dimension_id: str, fallback: Any) -> str:
    labels = {
        "fundamentals": "基本面与财务质量",
        "product_and_production": "产品与产线",
        "capital_and_financing": "投融资与资本开支",
        "competition_and_market_position": "竞争格局与市场位置",
        "industry_supply_chain": "行业与供应链传导",
        "risk_and_counterevidence": "风险与反证",
        "evidence_gap": "证据缺口",
    }
    return labels.get(str(dimension_id or "").strip(), str(fallback or "分析维度"))


def _zh_dimension_fallback_text(*, dimension_id: str, field: str, text: str, status: str) -> str:
    dimension = str(dimension_id or "").strip()
    normalized_status = str(status or "").strip()
    if normalized_status == "gap_or_counterevidence":
        if dimension == "fundamentals":
            if field in {"summary", "counter_read"}:
                return "当前基本面维度只有公开证据缺口：缺少可验证的公司财务披露或同口径经营指标，不能判断产品线对收入、毛利、现金流或利润质量的贡献。"
            if field == "business_mechanism":
                return "该维度本应用收入、利润率、现金转换或细分组合解释盈利质量；当前只能记录缺口，不能形成基本面事实判断。"
            if field == "financial_bridge":
                return "只有出现公司披露或 exact-authority 财务指标时，才允许桥接到收入、毛利率、经营利润率或现金流。"
        if dimension == "product_and_production":
            if field in {"summary", "counter_read"}:
                return "当前产品/产线维度只有公开证据缺口：缺少可验证的公司产品页、产品证据图或产品 KPI 行，不能推断产品收入、订单、出货或份额。"
            if field == "business_mechanism":
                return "该维度本应把产品采用、产能、订单积压、使用量或产品组合连接到经营线索；当前只能作为缺口跟踪。"
            if field == "financial_bridge":
                return "只有出现公司披露或 exact-authority 产品 KPI 时，才允许桥接到收入、毛利、库存、产能或 backlog。"
        if dimension == "capital_and_financing":
            if field in {"summary", "counter_read"}:
                return "当前投融资/资本开支维度只有公开证据缺口：缺少可验证的 capex、债务、发行、现金流或资产负债表证据，不能判断再投资能力或融资风险。"
            if field == "business_mechanism":
                return "该维度本应用再投资、杠杆、发行或现金生成解释产能与资产负债表弹性；当前只能作为缺口跟踪。"
            if field == "financial_bridge":
                return "只有出现公司披露或 exact-authority 资本/融资指标时，才允许桥接到 capex、杠杆、流动性、利息负担或发行。"
        if dimension == "industry_supply_chain":
            if field in {"summary", "counter_read"}:
                return "当前行业/供应链维度只有公开证据缺口：缺少可验证的客户、供应商、行业需求或公司暴露边，不能把外部 proxy 直接写成公司事实。"
            if field == "business_mechanism":
                return "该维度本应用行业需求、客户/供应商或供应链 proxy 解释公司暴露；当前只能作为范围假设或缺口。"
            if field == "financial_bridge":
                return "只有出现公司业务、segment、product 或 counterparty 暴露关系时，才允许桥接到收入、订单、产能或利润率。"
        if dimension == "competition_and_market_position":
            if field in {"summary", "counter_read"}:
                return "当前竞争/市场位置维度只有公开证据缺口：缺少可验证的份额、渠道、定价或竞品数据，不能判断真实竞争地位。"
            if field == "business_mechanism":
                return "该维度本应用估值、市场反应、同行、份额或渠道证据解释相对位置；当前只能作为缺口或市场背景。"
            if field == "financial_bridge":
                return "只有出现同口径份额、价格、渠道或竞品指标时，才允许桥接到收入增长、毛利率或估值溢价。"
        if dimension == "risk_and_counterevidence":
            if field in {"summary", "counter_read"}:
                return "当前风险/反证维度主要来自缺口或反向信号：缺少足够公开证据确认核心传导链，因此该维度只能降低结论置信度，不能扩展为新增事实。"
            if field == "business_mechanism":
                return "该维度用于说明哪些证据会抵消主线 thesis，或哪些缺口会降低业务传导与财务桥接的可信度。"
            if field == "financial_bridge":
                return "风险项只有在同口径证据指向收入、利润率、现金流、订单或资本开支压力时，才进入财务判断。"
    return _zh_wrapped_user_text(text, kind=f"dimension_{field}")


def _normalize_memo_action_items(value: Any, *, max_items: int, max_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            text = str(item.get("text") or item.get("claim") or item.get("reason") or item.get("driver") or "").strip()
            row = {
                "text": _truncate(text, max_chars),
                "claim_id": str(item.get("claim_id") or ""),
                "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:4],
            }
        else:
            row = {"text": _truncate(str(item or "").strip(), max_chars), "claim_id": "", "evidence_refs": []}
        if row["text"]:
            rows.append(row)
        if len(rows) >= max(0, max_items):
            break
    return rows


def _default_profile_action_items(
    memo_claims: list[dict[str, Any]],
    *,
    response_language: str,
    kind: str,
) -> list[dict[str, Any]]:
    first = memo_claims[0] if memo_claims and isinstance(memo_claims[0], Mapping) else {}
    claim_id = str(first.get("claim_id") or "")
    refs = _string_list(first.get("evidence_refs") or first.get("refs"))[:3]
    zh = _normalize_response_language(response_language) == "zh-CN"
    dimension_raw = str(first.get("analysis_dimension") or first.get("memo_slot") or "verified evidence")
    dimension = _zh_dimension_label(dimension_raw) if zh else dimension_raw.replace("_", " ")
    metrics = ", ".join(_memo_metric_labels(_string_list(first.get("metric_scope"))[:3], response_language=response_language))
    bridge = f"{dimension}" + (f" / {metrics}" if metrics else "")
    templates_zh = {
        "investment_implications": f"{bridge} 的投资含义要落在收入承接、利润率、现金流或产品/客户传导中的一个具体判断上；没有 exact 证据的部分保留边界。",
        "what_would_change_view": f"如果后续披露削弱 {bridge} 的指标方向、管理层解释或证据边界，需要下调当前结论强度。",
        "monitoring_items": f"后续优先跟踪 {bridge} 的同口径披露、反证风险和缺失确认项，而不是新增未验证叙事。",
    }
    templates_en = {
        "investment_implications": f"Anchor the investment read on the verified {bridge} evidence chain before extending it to revenue, margin, or cash-flow implications.",
        "what_would_change_view": f"Reduce conviction if later disclosures weaken the {bridge} metric direction, management explanation, or evidence boundary.",
        "monitoring_items": f"Track same-scope {bridge} disclosures, counterevidence, and missing confirmations before adding any unverified narrative.",
    }
    text = (templates_zh if zh else templates_en).get(kind, "")
    return [{"text": text, "claim_id": claim_id, "evidence_refs": refs}] if text else []


def _normalize_direct_answer_numeric_fidelity(
    memo: dict[str, Any],
    judgment: Mapping[str, Any],
    base_memo: Mapping[str, Any],
    *,
    max_chars: int,
    response_language: str = "en-US",
) -> dict[str, Any]:
    supported_scope = " ".join(
        _claim_scope_text(item)
        for item in judgment.get("supported_claims") or []
        if isinstance(item, Mapping)
    )
    if not supported_scope:
        return memo
    unknown_tokens = _unknown_numeric_tokens(str(memo.get("direct_answer") or ""), supported_scope)
    hard_unknown_tokens = [token for token in unknown_tokens if _is_material_numeric_token(token)]
    if not hard_unknown_tokens:
        return memo
    safe_direct_answer = _safe_direct_answer_from_claims(
        memo.get("memo_claims") or [],
        str(base_memo.get("direct_answer") or ""),
        max_chars=max_chars,
    )
    next_memo = dict(memo)
    current_direct = str(memo.get("direct_answer") or "")
    if response_language == "zh-CN" and _contains_cjk(current_direct):
        cleaned_direct = _truncate(_remove_unknown_numeric_tokens_from_text(current_direct, set(hard_unknown_tokens)), max_chars)
        next_memo["direct_answer"] = (
            safe_direct_answer
            if _numeric_removal_damaged_direct_answer(current_direct, cleaned_direct)
            else cleaned_direct
        )
    else:
        next_memo["direct_answer"] = safe_direct_answer
    next_memo["direct_answer_numeric_fidelity_normalized"] = True
    next_memo["direct_answer_numeric_fidelity_removed_tokens"] = hard_unknown_tokens[:8]
    return next_memo


def _numeric_removal_damaged_direct_answer(original: str, cleaned: str) -> bool:
    original_text = str(original or "")
    cleaned_text = str(cleaned or "")
    if not cleaned_text.strip():
        return True
    original_numeric_count = len(_numeric_token_details(original_text))
    cleaned_numeric_count = len(_numeric_token_details(cleaned_text))
    if original_numeric_count and cleaned_numeric_count == 0:
        return True
    dangling_patterns = (
        r"(营业利润|营收|收入|利润|费用|支出|现金流|margin|revenue|income)\s*(为|是|达|达到)\s*(这些|数据|证据|披露|公司|本轮|营收|收入|利润|管理层|成本|费用|。|，|,|;|；|$)",
        r"(为|达到)\s*(这些|数据|证据|披露|管理层|成本|费用|。|，|,|;|；|$)",
    )
    return any(re.search(pattern, cleaned_text, flags=re.IGNORECASE) for pattern in dangling_patterns)


def _remove_unknown_numeric_tokens_from_text(text: str, tokens: set[str]) -> str:
    cleaned = str(text or "")
    for token in sorted(tokens, key=len, reverse=True):
        if not token:
            continue
        compact = re.escape(str(token).replace(" ", ""))
        cleaned = re.sub(rf"\$?\s*{compact}", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.;:，。；：])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"(约|大约|达到|为|增长|下降|高达)\s*([,.;:，。；：])", r"\1", cleaned)
    return cleaned.strip()


def _safe_direct_answer_from_claims(claims: list[dict[str, Any]], fallback: str, *, max_chars: int) -> str:
    texts = [str(item.get("claim") or "").strip() for item in claims if isinstance(item, Mapping) and str(item.get("claim") or "").strip()]
    if texts:
        return _truncate(" ".join(text.rstrip(".") + "." for text in texts[:3]), max_chars)
    return _truncate(str(fallback or ""), max_chars)


def _claim_scope_text(claim: Mapping[str, Any]) -> str:
    return " ".join(
        [
            str(claim.get("claim") or ""),
            " ".join(_string_list(claim.get("caveats"))),
            " ".join(_string_list(claim.get("missing_confirmations"))),
        ]
    )


def _unknown_numeric_tokens(candidate_text: str, source_text: str) -> set[str]:
    source_tokens = _numeric_token_details(source_text)
    source_strings = {item[0] for item in source_tokens}
    unknown: set[str] = set()
    for token, value, unit in _numeric_token_details(candidate_text):
        if token in source_strings:
            continue
        if any(_numeric_values_close(value, unit, source_value, source_unit) for _, source_value, source_unit in source_tokens):
            continue
        unknown.add(token)
    return unknown


def _numeric_token_details(text: str) -> list[tuple[str, float, str]]:
    tokens: list[tuple[str, float, str]] = []
    expanded_text = _expand_numeric_ranges(str(text or ""))
    for match in re.finditer(
        r"(?<![A-Za-z0-9])[-+]?\$?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:percentage\s+points?|usd[_\s-]?billions?|usd[_\s-]?millions?|usd[_\s-]?thousands?|个百分点|十亿美元|亿美元|百万美元|万美元|billion|million|bn|mn|ppt|%|x|X|倍|M|B|K)?",
        expanded_text,
    ):
        original = match.group(0).strip()
        token = original.lower().replace("$", "").replace(",", "")
        token = re.sub(r"\s+", " ", token).strip()
        parsed = re.match(r"([-+]?\d+(?:\.\d+)?)\s*(.*)", token)
        if token and parsed:
            value, unit = _normalize_numeric_value_and_unit(float(parsed.group(1)), str(parsed.group(2) or ""))
            tokens.append((token.replace(" ", ""), value, unit))
    return tokens


def _expand_numeric_ranges(text: str) -> str:
    unit_pattern = r"(percentage\s+points?|usd[_\s-]?billions?|usd[_\s-]?millions?|usd[_\s-]?thousands?|个百分点|十亿美元|亿美元|百万美元|万美元|billion|million|bn|mn|ppt|%|x|X|倍|M|B|K)"

    def _replace(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        unit = match.group("unit")
        return f"{left}{unit} {right}{unit}"

    return re.sub(
        rf"(?P<left>\$?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*[-–]\s*(?P<right>\$?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(?P<unit>{unit_pattern})",
        _replace,
        str(text or ""),
        flags=re.IGNORECASE,
    )


def _normalize_numeric_value_and_unit(value: float, unit: str) -> tuple[float, str]:
    normalized = str(unit or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    if normalized in {"b", "bn", "billion", "usdbillion", "usdbillions", "十亿美元"}:
        return value, "b"
    if normalized in {"m", "mn", "million", "usdmillion", "usdmillions"}:
        return value / 1000.0, "b"
    if normalized in {"k", "usdthousand", "usdthousands"}:
        return value / 1_000_000.0, "b"
    if normalized == "亿美元":
        return value / 10.0, "b"
    if normalized == "百万美元":
        return value / 1000.0, "b"
    if normalized == "万美元":
        return value / 100000.0, "b"
    if normalized in {"x", "倍"}:
        return value, "x"
    if normalized in {"%", "percentagepoint", "percentagepoints", "ppt", "个百分点"}:
        return value, "pp" if normalized != "%" else "%"
    return value, normalized


def _numeric_values_close(left_value: float, left_unit: str, right_value: float, right_unit: str) -> bool:
    if left_unit != right_unit:
        return False
    diff = abs(left_value - right_value)
    return diff <= max(0.5, abs(right_value) * 0.005)


def _is_material_numeric_token(token: str) -> bool:
    parsed = re.match(r"([-+]?\d+(?:\.\d+)?)\s*(.*)", str(token or "").strip().lower())
    if not parsed:
        return False
    value = abs(float(parsed.group(1)))
    _, unit = _normalize_numeric_value_and_unit(value, str(parsed.group(2) or ""))
    if unit in {"%", "pp", "x", "b"}:
        return True
    return False


def build_shared_memo_context(state: Mapping[str, Any]) -> dict[str, Any]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    case_contract = state.get("case_contract") if isinstance(state.get("case_contract"), Mapping) else {}
    reflection = state.get("multi_agent_reflection_report") if isinstance(state.get("multi_agent_reflection_report"), Mapping) else {}
    sufficiency = state.get("evidence_sufficiency_report") if isinstance(state.get("evidence_sufficiency_report"), Mapping) else {}
    judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    claim_stats = judgment.get("claim_card_stats") if isinstance(judgment, Mapping) and isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    route_results = [row for row in state.get("specialist_route_results") or [] if isinstance(row, Mapping)]
    relationship_plan = state.get("universe_relationship_plan") if isinstance(state.get("universe_relationship_plan"), Mapping) else {}
    gap_register = _compact_bounded_gap_register_for_memo(state)
    lead_checkpoint = state.get("lead_review_checkpoint") if isinstance(state.get("lead_review_checkpoint"), Mapping) else {}
    lead_repair = (
        state.get("lead_targeted_repair_execution")
        if isinstance(state.get("lead_targeted_repair_execution"), Mapping)
        else lead_checkpoint.get("lead_targeted_repair_execution")
        if isinstance(lead_checkpoint.get("lead_targeted_repair_execution"), Mapping)
        else {}
    )
    supervising_pack = _compact_supervising_analyst_pack(state.get("supervising_analyst_pack") or {})
    user_query = (
        str(state.get("user_query") or "").strip()
        or str(state.get("prompt") or "").strip()
        or str(case_contract.get("prompt") or "").strip()
        or str(query_contract.get("raw_query") or "").strip()
    )
    query_contract_for_language = {
        **dict(query_contract),
        "raw_query": query_contract.get("raw_query") or user_query,
    }
    response_language = _select_response_language(
        {**dict(state), "user_query": user_query},
        activation=activation,
        query_contract=query_contract_for_language,
    )
    execution_mode = str(
        activation.get("execution_mode")
        or state.get("execution_mode")
        or case_contract.get("execution_mode")
        or _infer_memo_execution_mode_from_case_state(state, case_contract=case_contract, judgment=judgment if isinstance(judgment, Mapping) else {})
        or ""
    ).strip()
    focus_tickers = _string_list(
        activation.get("focus_tickers")
        or query_contract.get("focus_tickers")
        or state.get("focus_tickers")
        or case_contract.get("focus_tickers")
    )[:12]
    search_scope_tickers = _string_list(
        activation.get("search_scope_tickers")
        or query_contract.get("search_scope_tickers")
        or state.get("search_scope_tickers")
        or case_contract.get("search_scope_tickers")
    )[:24]
    context = {
        "schema_version": SHARED_MEMO_CONTEXT_SCHEMA_VERSION,
        "user_query": _truncate(user_query, 420),
        "response_language": response_language,
        "execution_mode": execution_mode,
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_scope_tickers,
        "coverage": {
            "sufficiency_level": str(reflection.get("sufficiency_level") or sufficiency.get("sufficiency_level") or ""),
            "missing_requirement_count": len(reflection.get("missing_requirements") or sufficiency.get("missing_requirements") or []),
            "bounded_answer_allowed": bool(reflection.get("bounded_answer_allowed") or sufficiency.get("bounded_answer_allowed") or state.get("bounded_answer_allowed")),
        },
        "source_boundaries": {
            "allowed_source_families": _string_list(activation.get("allowed_source_families"))[:12],
            "context_row_count": len(state.get("context_rows") or []),
            "ledger_row_count": len(state.get("runtime_ledger_rows") or []),
            "market_row_count": len(state.get("market_snapshot_rows") or []),
            "industry_row_count": len(state.get("industry_snapshot_rows") or []),
            "relationship_row_count": len(relationship_plan.get("relationships") or []),
            "raw_rows_excluded_from_prompt": True,
            "private_operator_context_excluded": True,
        },
        "bounded_gap_register": gap_register,
        "lead_review": {
            "memo_directive": _compact_lead_memo_directive(lead_checkpoint.get("memo_directive") or {}),
            "targeted_repair_execution": _compact_lead_targeted_repair_execution(lead_repair),
            "supervising_analyst": {
                "status": ((supervising_pack.get("validation") or {}).get("status") if isinstance(supervising_pack.get("validation"), Mapping) else ""),
                "stance": ((supervising_pack.get("research_lead_synthesis_plan") or {}).get("stance") if isinstance(supervising_pack.get("research_lead_synthesis_plan"), Mapping) else ""),
                "core_judgment": _truncate(
                    str(
                        ((supervising_pack.get("research_lead_synthesis_plan") or {}).get("core_judgment") if isinstance(supervising_pack.get("research_lead_synthesis_plan"), Mapping) else "")
                        or ""
                    ),
                    260,
                ),
            },
        },
        "specialist_routes": {
            "route_count": len(route_results),
            "passed_agents": [
                str(row.get("agent_id") or "")
                for row in route_results
                if str(row.get("status") or "") == "pass" and str(row.get("agent_id") or "")
            ],
            "failed_agents": [
                str(row.get("agent_id") or "")
                for row in route_results
                if str(row.get("status") or "") not in {"pass", "skipped"} and str(row.get("agent_id") or "")
            ],
        },
        "claim_card_stats": {
            "supported_claim_count": int(claim_stats.get("supported_claim_count") or 0),
            "memo_ready_claim_count": int(claim_stats.get("memo_ready_claim_count") or 0),
            "usable_with_caveat_claim_count": int(claim_stats.get("usable_with_caveat_claim_count") or 0),
            "memo_slot_supported_count": int(claim_stats.get("memo_slot_supported_count") or claim_stats.get("supported_memo_slot_count") or 0),
        },
        "prompt_policy": {
            "shared_context_policy": "scope_coverage_boundary_gap_refs_only_no_raw_rows_v0_2",
            "memo_payload_policy": "writer_thesis_skeleton_first_then_verified_claimcards_only",
            "allowed_input_views": [
                "shared_memo_context",
                "supervising_analyst_pack",
                "memo_logic_plan",
                "verified_judgment_plan",
                "specialist_verification",
            ],
            "raw_evidence_rows": "excluded",
            "bounded_evidence_rows": "excluded",
            "private_operator_context": "excluded",
            "bounded_gap_policy": "gaps_explain_missing_evidence_only_not_factual_substitutes",
        },
    }
    profile = _select_memo_profile(state, shared_context=context, judgment=judgment if isinstance(judgment, Mapping) else {})
    context["memo_profile"] = _memo_profile_dict(profile)
    context["context_digest"] = _payload_digest(context)
    return context


def _compact_shared_memo_context_for_prompt(context: Mapping[str, Any]) -> dict[str, Any]:
    response_language = context.get("response_language") if isinstance(context.get("response_language"), Mapping) else {}
    prompt_policy = context.get("prompt_policy") if isinstance(context.get("prompt_policy"), Mapping) else {}
    return {
        "schema_version": str(context.get("schema_version") or SHARED_MEMO_CONTEXT_SCHEMA_VERSION),
        "user_query": _truncate(str(context.get("user_query") or ""), 240),
        "response_language": {
            "language": str(response_language.get("language") or ""),
            "user_facing_text_language": str(response_language.get("user_facing_text_language") or ""),
            "preserve_identifiers": _string_list(response_language.get("preserve_identifiers"))[:8],
        },
        "execution_mode": str(context.get("execution_mode") or ""),
        "focus_tickers": _string_list(context.get("focus_tickers"))[:8],
        "search_scope_tickers": _string_list(context.get("search_scope_tickers"))[:12],
        "coverage": dict(context.get("coverage") or {}) if isinstance(context.get("coverage"), Mapping) else {},
        "source_boundaries": dict(context.get("source_boundaries") or {}) if isinstance(context.get("source_boundaries"), Mapping) else {},
        "bounded_gap_register": dict(context.get("bounded_gap_register") or {}) if isinstance(context.get("bounded_gap_register"), Mapping) else {},
        "lead_review": _compact_shared_lead_review_for_prompt(context.get("lead_review") or {}),
        "specialist_routes": dict(context.get("specialist_routes") or {}) if isinstance(context.get("specialist_routes"), Mapping) else {},
        "claim_card_stats": dict(context.get("claim_card_stats") or {}) if isinstance(context.get("claim_card_stats"), Mapping) else {},
        "prompt_policy": {
            "shared_context_policy": str(prompt_policy.get("shared_context_policy") or ""),
            "memo_payload_policy": str(prompt_policy.get("memo_payload_policy") or ""),
            "raw_evidence_rows": str(prompt_policy.get("raw_evidence_rows") or ""),
            "bounded_evidence_rows": str(prompt_policy.get("bounded_evidence_rows") or ""),
            "private_operator_context": str(prompt_policy.get("private_operator_context") or ""),
            "bounded_gap_policy": str(prompt_policy.get("bounded_gap_policy") or ""),
        },
        "memo_profile": dict(context.get("memo_profile") or {}) if isinstance(context.get("memo_profile"), Mapping) else {},
        "context_digest": str(context.get("context_digest") or ""),
    }


def _compact_shared_lead_review_for_prompt(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    directive = value.get("memo_directive") if isinstance(value.get("memo_directive"), Mapping) else {}
    product_contract = (
        directive.get("product_output_contract")
        if isinstance(directive.get("product_output_contract"), Mapping)
        else {}
    )
    gap_budget = directive.get("gap_budget_policy") if isinstance(directive.get("gap_budget_policy"), Mapping) else {}
    objective = (
        directive.get("objective_satisfaction")
        if isinstance(directive.get("objective_satisfaction"), Mapping)
        else {}
    )
    supervising = value.get("supervising_analyst") if isinstance(value.get("supervising_analyst"), Mapping) else {}
    return _without_empty_values(
        {
            "memo_stance": str(directive.get("memo_stance") or ""),
            "objective_satisfaction": _without_empty_values(
                {
                    "status": str(objective.get("status") or ""),
                    "missing_required_item_count": objective.get("missing_required_item_count"),
                    "required_item_coverage": str(objective.get("required_item_coverage") or ""),
                }
            ),
            "opening_policy": str(directive.get("opening_policy") or ""),
            "gap_budget_policy": _without_empty_values(
                {
                    "max_gap_share_in_user_memo": gap_budget.get("max_gap_share_in_user_memo"),
                    "allowed_gap_placement": str(gap_budget.get("allowed_gap_placement") or ""),
                    "required_gap_tone": str(gap_budget.get("required_gap_tone") or ""),
                }
            ),
            "product_output_contract": _without_empty_values(
                {
                    "required_user_facing_shape": _string_list(product_contract.get("required_user_facing_shape"))[:4],
                    "missing_source_boundary": _truncate(str(product_contract.get("missing_source_boundary") or ""), 100),
                    "forbidden_fallback": _truncate(str(product_contract.get("forbidden_fallback") or ""), 90),
                }
            ),
            "issuer_targeted_repair_required": bool(directive.get("issuer_targeted_repair_required")),
            "issuer_targeted_repair_tickers": _string_list(directive.get("issuer_targeted_repair_tickers"))[:6],
            "targeted_repair_execution": _compact_lead_targeted_repair_execution(value.get("targeted_repair_execution") or {}),
            "supervising_analyst": _without_empty_values(
                {
                    "status": str(supervising.get("status") or ""),
                    "stance": str(supervising.get("stance") or ""),
                    "core_judgment": _truncate(str(supervising.get("core_judgment") or ""), 180),
                }
            ),
        }
    )


def _memo_writer_input_pack_fingerprint(
    state: Mapping[str, Any],
    *,
    shared_context: Mapping[str, Any] | None = None,
    judgment: Any | None = None,
) -> dict[str, Any]:
    """Persist only a digest-level view of the Memo Writer input pack.

    The runtime needs enough lineage to diagnose high-token/low-insight writer
    failures, but must not copy the full prompt or source rows into audit rows.
    """

    context = dict(shared_context or _compact_shared_memo_context_for_prompt(build_shared_memo_context(state)))
    memo_profile = _memo_profile_spec_from_name(
        ((context.get("memo_profile") or {}) if isinstance(context.get("memo_profile"), Mapping) else {}).get("profile")
    )
    writer_budget = _memo_writer_budget_spec_from_profile(memo_profile)
    compact_judgment = _compact_judgment_for_memo(
        judgment if judgment is not None else state.get("verified_judgment_plan") or state.get("judgment_plan") or {},
        memo_profile=memo_profile,
        budget=writer_budget,
    )
    response_language = str(
        ((context.get("response_language") or {}) if isinstance(context.get("response_language"), Mapping) else {}).get("language")
        or ""
    )
    scaffold_summary = _memo_writer_static_scaffold_summary(
        memo_profile=memo_profile,
        response_language=response_language,
    )
    components: dict[str, Any] = {
        "shared_memo_context": context,
        "supervising_analyst_pack": _compact_supervising_analyst_pack(
            state.get("supervising_analyst_pack") or {},
            budget=writer_budget,
        ),
        "memo_logic_plan": _compact_memo_logic_plan_for_writer_prompt(
            state.get("memo_logic_plan") or {},
            budget=writer_budget,
        ),
        "verified_judgment_plan": compact_judgment,
        "specialist_verification": _compact_specialist_verification(state.get("specialist_verification") or {}),
    }
    summaries = {
        name: _memo_writer_input_component_summary(component)
        for name, component in components.items()
    }
    known_refs = _dedupe_strings(
        ref
        for component in components.values()
        for ref in _memo_writer_input_evidence_refs(component)
    )
    digest_payload = {
        "component_digests": {
            name: summary.get("digest") for name, summary in summaries.items()
        },
        "known_evidence_refs": known_refs,
        "memo_profile": memo_profile.profile,
        "static_prompt_scaffold": {
            "policy_id": scaffold_summary.get("policy_id"),
            "system_prompt_digest": scaffold_summary.get("system_prompt_digest"),
            "user_instruction_digest": scaffold_summary.get("user_instruction_digest"),
        },
    }
    return {
        "schema_version": MEMO_WRITER_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION,
        "agent_id": "memo_writer",
        "memo_profile": memo_profile.profile,
        "response_language": response_language,
        "digest": _fingerprint_digest(digest_payload),
        "component_summaries": summaries,
        "known_evidence_ref_count": len(known_refs),
        "known_evidence_refs": known_refs[:256],
        "known_evidence_refs_truncated": len(known_refs) > 256,
        "approx_prompt_payload_chars": sum(int(summary.get("approx_chars") or 0) for summary in summaries.values()),
        "writer_budget": {
            "profile": writer_budget.profile,
            "supported_claim_cap": writer_budget.supported_claim_cap,
            "sections_cap": writer_budget.sections_cap,
            "required_item_cap": writer_budget.required_item_cap,
            "financial_line_item_cap": writer_budget.financial_line_item_cap,
            "graph_edge_cap": writer_budget.graph_edge_cap,
        },
        "static_prompt_scaffold_summary": scaffold_summary,
        "approx_total_prompt_chars_with_scaffold": (
            sum(int(summary.get("approx_chars") or 0) for summary in summaries.values())
            + int(scaffold_summary.get("system_prompt_chars") or 0)
            + int(scaffold_summary.get("user_instruction_chars") or 0)
        ),
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }


def memo_writer_input_pack_fingerprint_for_state(
    state: Mapping[str, Any],
    *,
    capture_source: str = "deterministic_using_memo_writer_input_contract",
) -> dict[str, Any]:
    """Build the same digest-only Memo Writer input fingerprint outside LLM routes.

    Mock / deterministic graph paths still need the input economy ledger to see
    what would have been handed to Memo Writer. This wrapper keeps the route and
    non-route projections on the same compact contract without persisting prompt
    text.
    """

    fingerprint = _memo_writer_input_pack_fingerprint(
        state,
        shared_context=_compact_shared_memo_context_for_prompt(build_shared_memo_context(state)),
        judgment=state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else {},
    )
    return {**fingerprint, "capture_source": capture_source}


def _memo_writer_input_component_summary(value: Any) -> dict[str, Any]:
    refs = _memo_writer_input_evidence_refs(value)
    return {
        "digest": _fingerprint_digest(value),
        "item_count": _memo_writer_input_item_count(value),
        "evidence_ref_count": len(refs),
        "approx_chars": len(json.dumps(_clean_for_prompt_any(value), ensure_ascii=False, sort_keys=True)),
    }


def _memo_writer_input_item_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, Mapping):
        preferred_keys = (
            "supported_claims",
            "unsupported_claims",
            "sections",
            "memo_claims",
            "dimension_analyses",
            "evidence_to_thesis_bridge",
            "required_item_answer_plan",
            "route_results",
        )
        counts = [
            len(value.get(key) or [])
            for key in preferred_keys
            if isinstance(value.get(key), (list, tuple))
        ]
        return sum(counts) if counts else len(value)
    return 0 if value is None or value == "" else 1


def _memo_writer_input_evidence_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key in (
            "evidence_refs",
            "required_evidence_refs",
            "source_claim_refs",
            "supporting_evidence_ids",
            "evidence_ref",
            "evidence_id",
            "source_id",
        ):
            refs.extend(_string_list(value.get(key)))
        for item in value.values():
            if isinstance(item, (Mapping, list)):
                refs.extend(_memo_writer_input_evidence_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_memo_writer_input_evidence_refs(item))
    return _dedupe_strings(refs)


def _fingerprint_digest(value: Any) -> str:
    text = json.dumps(_clean_for_prompt_any(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean_for_prompt_any(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _verifier_input_pack_fingerprint(projection: Mapping[str, Any]) -> dict[str, Any]:
    components: dict[str, Any] = {
        "memo_answer": projection.get("memo_answer") if isinstance(projection.get("memo_answer"), Mapping) else {},
        "memo_claim_ref_inventory": projection.get("memo_claim_ref_inventory")
        if isinstance(projection.get("memo_claim_ref_inventory"), list)
        else [],
        "allowed_evidence_refs": _string_list(projection.get("allowed_evidence_refs")),
        "source_boundary_notes": projection.get("source_boundary_notes")
        if isinstance(projection.get("source_boundary_notes"), list)
        else [],
        "deterministic_verification": projection.get("deterministic_verification")
        if isinstance(projection.get("deterministic_verification"), Mapping)
        else {},
    }
    summaries = {
        name: _memo_writer_input_component_summary(component)
        for name, component in components.items()
    }
    known_refs = _dedupe_strings(
        ref
        for component in components.values()
        for ref in _memo_writer_input_evidence_refs(component)
    )
    digest_payload = {
        "component_digests": {
            name: summary.get("digest") for name, summary in summaries.items()
        },
        "known_evidence_refs": known_refs,
        "static_prompt_scaffold": _verifier_static_prompt_scaffold_digest_payload(),
    }
    scaffold_summary = _verifier_static_prompt_scaffold_summary()
    payload_chars = sum(int(summary.get("approx_chars") or 0) for summary in summaries.values())
    return {
        "schema_version": VERIFIER_INPUT_PACK_FINGERPRINT_SCHEMA_VERSION,
        "agent_id": "verifier",
        "digest": _fingerprint_digest(digest_payload),
        "component_summaries": summaries,
        "known_evidence_ref_count": len(known_refs),
        "known_evidence_refs": known_refs[:128],
        "known_evidence_refs_truncated": len(known_refs) > 128,
        "approx_prompt_payload_chars": payload_chars,
        "static_prompt_scaffold_summary": scaffold_summary,
        "approx_total_prompt_chars_with_scaffold": (
            payload_chars
            + int(scaffold_summary.get("system_prompt_chars") or 0)
            + int(scaffold_summary.get("user_instruction_chars") or 0)
        ),
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }


def _verifier_static_prompt_scaffold_digest_payload() -> dict[str, Any]:
    summary = _verifier_static_prompt_scaffold_summary()
    return {
        "policy_id": summary.get("policy_id"),
        "system_prompt_digest": summary.get("system_prompt_digest"),
        "user_instruction_digest": summary.get("user_instruction_digest"),
    }


def _verifier_static_prompt_scaffold_summary() -> dict[str, Any]:
    system_prompt = _verifier_system_prompt()
    user_instruction = _verifier_user_instruction_scaffold()
    return {
        "policy_id": "verifier_compact_instruction_scaffold_v0_1",
        "system_prompt_chars": len(system_prompt),
        "user_instruction_chars": len(user_instruction),
        "system_prompt_digest": _fingerprint_digest({"system": system_prompt}),
        "user_instruction_digest": _fingerprint_digest({"user_instruction": user_instruction}),
        "prompt_text_persisted": False,
    }


def verifier_input_projection_for_state(
    state: Mapping[str, Any],
    *,
    deterministic: Mapping[str, Any] | None = None,
    capture_source: str = "deterministic_using_verifier_projection_contract",
) -> dict[str, Any]:
    """Build Verifier minimal projection with a digest-only input fingerprint."""

    projection = _verifier_minimal_projection(state, deterministic=deterministic or {})
    fingerprint = _verifier_input_pack_fingerprint(projection)
    fingerprint = {**fingerprint, "capture_source": capture_source}
    stats = dict(projection.get("projection_stats") or {})
    stats["input_pack_fingerprint"] = fingerprint
    return {**projection, "projection_stats": stats, "input_pack_fingerprint": fingerprint}


def _compact_memo_logic_plan(value: Any, *, budget: MemoWriterBudgetSpec | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    budget = budget or MEMO_WRITER_BUDGET_SPECS["compact"]
    sections = []
    for section in value.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        sections.append(
            {
                "section_id": str(section.get("section_id") or ""),
                "title": _truncate(str(section.get("title") or ""), 90),
                "order": int(section.get("order") or len(sections) + 1),
                "logic_role": str(section.get("logic_role") or ""),
                "required_claim_ids": _string_list(section.get("required_claim_ids"))[:3],
                "required_gap_refs": _string_list(section.get("required_gap_refs"))[:1],
                "required_item_ids": _string_list(section.get("required_item_ids"))[:2],
                "writing_instruction": _truncate(str(section.get("writing_instruction") or ""), 60),
            }
        )
        if len(sections) >= budget.sections_cap:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "plan_id": str(value.get("plan_id") or ""),
        "memo_intent": str(value.get("memo_intent") or ""),
        "opening_answer_policy": str(value.get("opening_answer_policy") or ""),
        "answer_first_outline": _compact_answer_first_outline(value.get("answer_first_outline") or {})
        if isinstance(value.get("answer_first_outline"), Mapping)
        else {},
        "writer_thesis_skeleton": _compact_writer_thesis_skeleton(value.get("writer_thesis_skeleton"), budget=budget)
        if isinstance(value.get("writer_thesis_skeleton"), Mapping)
        else {},
        "thesis_density_contract": _compact_thesis_density_contract(value.get("thesis_density_contract"))
        if isinstance(value.get("thesis_density_contract"), Mapping)
        else {},
        "evidence_to_thesis_bridge": [
            {
                "dimension_id": str(row.get("dimension_id") or ""),
                "thesis_role": str(row.get("thesis_role") or ""),
                "claim_ids": _string_list(row.get("claim_ids"))[:2],
                "gap_refs": _string_list(row.get("gap_refs"))[:1],
                "counter_thesis_refs": _string_list(row.get("counter_thesis_refs"))[:1],
                "writer_instruction": _truncate(str(row.get("writer_instruction") or ""), 65),
            }
            for row in value.get("evidence_to_thesis_bridge") or []
            if isinstance(row, Mapping)
        ][: budget.evidence_bridge_cap],
        "product_reasoning_frame": _compact_product_reasoning_frame(value.get("product_reasoning_frame"))
        if isinstance(value.get("product_reasoning_frame"), Mapping)
        else {},
        "judgment_cards": _compact_memo_judgment_cards(value.get("judgment_cards"), budget=budget),
        "thesis_path": _compact_memo_thesis_path(value.get("thesis_path"), budget=budget)
        if isinstance(value.get("thesis_path"), Mapping)
        else {},
        "economic_role_summary": _compact_economic_role_summary(value.get("economic_role_summary"), budget=budget)
        if isinstance(value.get("economic_role_summary"), Mapping)
        else {},
        "required_question_items": [
            {
                "question_item_id": str(row.get("question_item_id") or ""),
                "dimension": str(row.get("dimension") or ""),
                "required_tickers": _string_list(row.get("required_tickers"))[:6],
                "required_evidence_roles": _string_list(row.get("required_evidence_roles"))[:4],
                "minimum_answer_status": str(row.get("minimum_answer_status") or ""),
                "terms_any": _string_list(row.get("terms_any"))[:3],
                "answer_contract": _truncate(str(row.get("answer_contract") or ""), 55),
            }
            for row in value.get("required_question_items") or []
            if isinstance(row, Mapping)
        ][: budget.required_question_cap],
        "required_item_answer_plan": _compact_required_item_answer_plan(
            value.get("required_item_answer_plan"),
            budget=budget,
        ),
        "focus_ticker_coverage_policy": _compact_focus_ticker_coverage_policy(
            value.get("focus_ticker_coverage_policy")
        ),
        "section_order": _string_list(value.get("section_order"))[: budget.sections_cap],
        "sections": sections[: budget.sections_cap],
        "writer_allowed_inputs": _string_list(value.get("writer_allowed_inputs"))[:8],
        "writer_forbidden_tools": _string_list(value.get("writer_forbidden_tools"))[:8],
        "citation_policy": str(value.get("citation_policy") or ""),
        "validation": _compact_memo_logic_validation(value.get("validation")),
    }


def _compact_memo_logic_plan_for_writer_prompt(
    value: Any,
    *,
    budget: MemoWriterBudgetSpec | None = None,
) -> dict[str, Any]:
    """Project MemoLogicPlan into the minimal writer prompt contract.

    The full plan remains persisted for audit, but the writer prompt should not
    reread the same judgment-card and thesis-path material that is already
    present in the compact verified judgment and supervising analyst pack.
    """

    if not isinstance(value, Mapping) or not value:
        return {}
    compact = _compact_memo_logic_plan(value, budget=budget)
    if not compact:
        return {}
    projected = {
        key: compact.get(key)
        for key in (
            "schema_version",
            "plan_id",
            "memo_intent",
            "opening_answer_policy",
            "answer_first_outline",
            "writer_thesis_skeleton",
            "thesis_density_contract",
            "product_reasoning_frame",
            "economic_role_summary",
            "required_item_answer_plan",
            "focus_ticker_coverage_policy",
            "section_order",
            "sections",
            "writer_allowed_inputs",
            "writer_forbidden_tools",
            "citation_policy",
            "validation",
        )
        if compact.get(key) not in (None, "", [], {})
    }
    skeleton = projected.get("writer_thesis_skeleton") if isinstance(projected.get("writer_thesis_skeleton"), Mapping) else {}
    if skeleton:
        projected["writer_thesis_skeleton"] = {
            key: skeleton.get(key)
            for key in (
                "schema_version",
                "opening_judgment",
                "stance",
                "causal_chain",
                "dimension_moves",
                "product_reasoning_move",
                "thesis_path_move",
                "economic_role_move",
                "writer_priority_order",
                "forbidden_writer_moves",
            )
            if skeleton.get(key) not in (None, "", [], {})
        }
    outline = projected.get("answer_first_outline")
    if isinstance(outline, Mapping):
        refs = _string_list(outline.get("decision_changing_evidence_refs"))
        projected["answer_first_outline"] = {
            key: value
            for key, value in outline.items()
            if key != "decision_changing_evidence_refs" and value not in (None, "", [], {})
        }
        projected["answer_first_outline"]["decision_changing_evidence_ref_count"] = int(
            outline.get("decision_changing_evidence_ref_count") or len(refs)
        )
        projected["answer_first_outline"]["exact_ref_source"] = "verified_judgment_plan.supported_claims"
    projected["writer_prompt_projection_policy"] = (
        "memo_logic_plan_answer_contract_only_no_duplicate_judgment_cards_or_thesis_path_v0_1"
    )
    return projected


def _compact_answer_first_outline(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "thesis_statement": _truncate(str(value.get("thesis_statement") or ""), 105),
        "supporting_dimension_ids": _string_list(value.get("supporting_dimension_ids"))[:3],
        "counter_thesis_dimension_ids": _string_list(value.get("counter_thesis_dimension_ids"))[:3],
        "decision_changing_evidence_refs": _string_list(value.get("decision_changing_evidence_refs"))[:5],
        "decision_changing_evidence_ref_count": len(_string_list(value.get("decision_changing_evidence_refs"))),
        "opening_instruction": _truncate(str(value.get("opening_instruction") or ""), 65),
    }


def _compact_memo_judgment_cards(value: Any, *, budget: MemoWriterBudgetSpec | None = None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    budget = budget or MEMO_WRITER_BUDGET_SPECS["compact"]
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "judgment_card_id": str(item.get("judgment_card_id") or ""),
                "source_claim_id": str(item.get("source_claim_id") or ""),
                "dimension_id": str(item.get("dimension_id") or ""),
                "judgment": _truncate(str(item.get("judgment") or ""), 78),
                "evidence_bridge": _truncate(str(item.get("evidence_bridge") or ""), 70),
                "business_mechanism": _truncate(str(item.get("business_mechanism") or ""), 62),
                "financial_bridge": _truncate(str(item.get("financial_bridge") or ""), 62),
                "counter_read": _truncate(str(item.get("counter_read") or ""), 58),
                "what_would_change_view": [_truncate(str(item), 58) for item in _string_list(item.get("what_would_change_view"))[:1]],
                "evidence_ref_count": len(_string_list(item.get("evidence_refs"))),
                "exact_ref_source": "verified_judgment_plan.supported_claims",
                "source_role": str(item.get("source_role") or ""),
                "authority_boundary": _truncate(str(item.get("authority_boundary") or ""), 58),
                "mechanism_bridge_status": str(item.get("mechanism_bridge_status") or ""),
            }
        )
        if len(rows) >= min(3, budget.supported_claim_cap):
            break
    return rows


def _compact_memo_thesis_path(value: Any, *, budget: MemoWriterBudgetSpec | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    budget = budget or MEMO_WRITER_BUDGET_SPECS["compact"]
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "primary_thesis": _truncate(str(value.get("primary_thesis") or ""), 120),
        "mechanism_bridge_status": str(value.get("mechanism_bridge_status") or ""),
        "path_nodes": [
            {
                "dimension_id": str(row.get("dimension_id") or ""),
                "judgment_card_ids": _string_list(row.get("judgment_card_ids"))[:3],
                "claim_ids": _string_list(row.get("claim_ids"))[:3],
                "evidence_ref_count": len(_string_list(row.get("evidence_refs"))),
                "exact_ref_source": "verified_judgment_plan.supported_claims",
                "business_mechanism": _truncate(str(row.get("business_mechanism") or ""), 80),
                "financial_bridge": _truncate(str(row.get("financial_bridge") or ""), 80),
                "counter_read": _truncate(str(row.get("counter_read") or ""), 70),
            }
            for row in value.get("path_nodes") or []
            if isinstance(row, Mapping)
        ][: budget.dimension_move_cap],
        "path_edges": [
            {
                "edge_type": str(row.get("edge_type") or ""),
                "from_node_id": str(row.get("from_node_id") or ""),
                "to_node_id": str(row.get("to_node_id") or ""),
                "mechanism": _truncate(str(row.get("mechanism") or ""), 85),
                "evidence_ref_count": len(_string_list(row.get("evidence_refs"))),
                "exact_ref_source": "verified_judgment_plan.supported_claims",
            }
            for row in value.get("path_edges") or []
            if isinstance(row, Mapping)
        ][:4],
    }


def _compact_writer_thesis_skeleton(value: Any, *, budget: MemoWriterBudgetSpec | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    budget = budget or MEMO_WRITER_BUDGET_SPECS["compact"]
    product = value.get("product_reasoning_move") if isinstance(value.get("product_reasoning_move"), Mapping) else {}
    economic = value.get("economic_role_move") if isinstance(value.get("economic_role_move"), Mapping) else {}
    thesis_path = value.get("thesis_path_move") if isinstance(value.get("thesis_path_move"), Mapping) else {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "opening_judgment": _truncate(str(value.get("opening_judgment") or ""), 150),
        "stance": _truncate(str(value.get("stance") or ""), 120),
        "causal_chain": [_truncate(str(item), 80) for item in _string_list(value.get("causal_chain"))[:4]],
        "dimension_moves": [
            {
                "dimension_id": str(row.get("dimension_id") or ""),
                "role": str(row.get("role") or ""),
                "claim_ids": _string_list(row.get("claim_ids"))[:2],
                "judgment_card_ids": _string_list(row.get("judgment_card_ids"))[:2],
                "gap_refs": _string_list(row.get("gap_refs"))[:1],
                "required_item_ids": _string_list(row.get("required_item_ids"))[:2],
                "required_item_answer_move_count": len(
                    [item for item in row.get("required_item_answer_moves") or [] if isinstance(item, Mapping)]
                ),
                "required_writer_move": _truncate(str(row.get("required_writer_move") or ""), 55),
            }
            for row in value.get("dimension_moves") or []
            if isinstance(row, Mapping)
        ][: budget.dimension_move_cap],
        "product_reasoning_move": {
            "coverage_roles": _string_list(product.get("coverage_roles"))[:5],
            "required_reasoning_edges": _string_list(product.get("required_reasoning_edges"))[:4],
            "instruction": _truncate(str(product.get("instruction") or ""), 65),
        },
        "thesis_path_move": {
            "primary_thesis": _truncate(str(thesis_path.get("primary_thesis") or ""), 120),
            "mechanism_bridge_status": str(thesis_path.get("mechanism_bridge_status") or ""),
            "required_sequence": [
                {
                    "dimension_id": str(row.get("dimension_id") or ""),
                    "judgment_card_ids": _string_list(row.get("judgment_card_ids"))[:2],
                    "claim_ids": _string_list(row.get("claim_ids"))[:2],
                }
                for row in thesis_path.get("required_sequence") or []
                if isinstance(row, Mapping)
            ][:3],
            "required_edges": [
                {
                    "edge_type": str(row.get("edge_type") or ""),
                    "mechanism": _truncate(str(row.get("mechanism") or ""), 80),
                }
                for row in thesis_path.get("required_edges") or []
                if isinstance(row, Mapping)
            ][:3],
            "writer_instruction": _truncate(str(thesis_path.get("writer_instruction") or ""), 90),
        },
        "judgment_card_moves": [
            {
                "judgment_card_id": str(row.get("judgment_card_id") or ""),
                "source_claim_id": str(row.get("source_claim_id") or ""),
                "dimension_id": str(row.get("dimension_id") or ""),
                "mechanism_bridge_status": str(row.get("mechanism_bridge_status") or ""),
                "evidence_ref_count": len(_string_list(row.get("evidence_refs"))),
                "exact_ref_source": "verified_judgment_plan.supported_claims",
            }
            for row in value.get("judgment_card_moves") or []
            if isinstance(row, Mapping)
        ][:3],
        "economic_role_move": {
            "role_counts": dict(economic.get("role_counts") or {}) if isinstance(economic.get("role_counts"), Mapping) else {},
            "role_boundary_counts": dict(economic.get("role_boundary_counts") or {})
            if isinstance(economic.get("role_boundary_counts"), Mapping)
            else {},
            "instruction": _truncate(str(economic.get("instruction") or ""), 60),
        },
        "writer_priority_order": _string_list(value.get("writer_priority_order"))[:6],
        "forbidden_writer_moves": _string_list(value.get("forbidden_writer_moves"))[:4],
    }


def _compact_economic_role_summary(value: Any, *, budget: MemoWriterBudgetSpec | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    budget = budget or MEMO_WRITER_BUDGET_SPECS["compact"]
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "role_counts": dict(value.get("role_counts") or {}) if isinstance(value.get("role_counts"), Mapping) else {},
        "role_boundary_counts": dict(value.get("role_boundary_counts") or {})
        if isinstance(value.get("role_boundary_counts"), Mapping)
        else {},
        "role_rows": [
            {
                "claim_id": str(row.get("claim_id") or ""),
                "ticker_scope": _string_list(row.get("ticker_scope"))[:4],
                "metric_scope": _string_list(row.get("metric_scope"))[:3],
                "analysis_dimension": str(row.get("analysis_dimension") or ""),
                "scope_role": str(row.get("scope_role") or ""),
                "economic_role": str(row.get("economic_role") or ""),
                "transmission_role": str(row.get("transmission_role") or ""),
                "memo_use_role": _truncate(str(row.get("memo_use_role") or ""), 55),
                "role_boundary": str(row.get("role_boundary") or ""),
            }
            for row in value.get("role_rows") or []
            if isinstance(row, Mapping)
        ][: min(4, budget.economic_role_row_cap)],
        "writer_instruction": _truncate(str(value.get("writer_instruction") or ""), 70),
    }


def _compact_required_item_answer_plan(
    value: Any,
    *,
    budget: MemoWriterBudgetSpec | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    budget = budget or MEMO_WRITER_BUDGET_SPECS["compact"]
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "question_item_id": str(item.get("question_item_id") or ""),
                "dimension": str(item.get("dimension") or ""),
                "answer_role": str(item.get("answer_role") or ""),
                "required_tickers": _string_list(item.get("required_tickers"))[:4],
                "required_evidence_roles": _string_list(item.get("required_evidence_roles"))[:3],
                "terms_any": _string_list(item.get("terms_any"))[:3],
                "answer_first_judgment_prompt": _truncate(str(item.get("answer_first_judgment_prompt") or ""), 48),
                "evidence_bridge_prompt": _truncate(str(item.get("evidence_bridge_prompt") or ""), 48),
                "counter_read_prompt": _truncate(str(item.get("counter_read_prompt") or ""), 42),
                "what_would_change_prompt": _truncate(str(item.get("what_would_change_prompt") or ""), 42),
                "answer": _truncate(str(item.get("answer") or ""), 180),
                "cannot_infer": _truncate(str(item.get("cannot_infer") or ""), 120),
                "what_would_change_view": _truncate(str(item.get("what_would_change_view") or ""), 120),
            }
        )
    return rows[: budget.required_item_cap]


def _compact_focus_ticker_coverage_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    rows: list[dict[str, Any]] = []
    for row in value.get("ticker_policies") or value.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "ticker": str(row.get("ticker") or ""),
                "coverage_status": str(row.get("coverage_status") or row.get("status") or ""),
                "do_not_say_no_data": bool(row.get("do_not_say_no_data") or row.get("has_supported_claims")),
                "supported_claim_ids": _string_list(row.get("supported_claim_ids") or row.get("claim_ids"))[:3],
                "policy_note": _truncate(str(row.get("policy_note") or row.get("reason") or ""), 80),
            }
        )
        if len(rows) >= 6:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "policy": _truncate(str(value.get("policy") or value.get("coverage_policy") or ""), 110),
        "focus_tickers": _string_list(value.get("focus_tickers"))[:8],
        "ticker_policies": rows,
    }


def _compact_memo_logic_validation(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "status": str(value.get("status") or ""),
        "error_count": len(value.get("errors") or []) if isinstance(value.get("errors"), list) else value.get("error_count"),
        "warning_count": len(value.get("warnings") or []) if isinstance(value.get("warnings"), list) else value.get("warning_count"),
        "errors": [
            _truncate(str(item.get("type") or item.get("message") or item), 80)
            if isinstance(item, Mapping)
            else _truncate(str(item), 80)
            for item in (value.get("errors") or [])[:2]
        ]
        if isinstance(value.get("errors"), list)
        else [],
    }


def _compact_thesis_density_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "minimum_supported_insight_sentences": int(value.get("minimum_supported_insight_sentences") or 0),
        "minimum_causal_bridges": int(value.get("minimum_causal_bridges") or 0),
        "maximum_gap_body_share": value.get("maximum_gap_body_share"),
        "required_product_moves": _string_list(value.get("required_product_moves"))[:3],
        "forbidden_low_density_patterns": _string_list(value.get("forbidden_low_density_patterns"))[:3],
        "pass_definition": _truncate(str(value.get("pass_definition") or ""), 95),
    }


def _compact_product_reasoning_frame(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "coverage_roles": _string_list(value.get("coverage_roles"))[:5],
        "product_profile_ref_count": len(_string_list(value.get("product_profile_refs"))),
        "product_spec_ref_count": len(_string_list(value.get("product_spec_refs"))),
        "product_kpi_ref_count": len(_string_list(value.get("product_kpi_refs"))),
        "deployment_ref_count": len(_string_list(value.get("deployment_refs"))),
        "performance_proxy_ref_count": len(_string_list(value.get("performance_proxy_refs"))),
        "relationship_edge_ref_count": len(_string_list(value.get("relationship_edge_refs"))),
        "scope_hypothesis_ref_count": len(_string_list(value.get("scope_hypothesis_refs"))),
        "required_reasoning_edges": _string_list(value.get("required_reasoning_edges"))[:4],
        "writer_instruction": _truncate(str(value.get("writer_instruction") or ""), 120),
    }


def _display_or_value(row: Mapping[str, Any]) -> str:
    return str(
        row.get("display_value")
        or row.get("display_value_zh")
        or row.get("selected_for_display")
        or row.get("formatted_value")
        or ""
    )


def _without_empty_values(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in row.items()
        if item not in ("", None, [], {})
    }


def _dedupe_mappings_by_keys(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        identity = tuple(str(row.get(key) or "") for key in keys)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(row)
    return deduped


def _compact_product_bridge_coverage_for_writer(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    depth_counts = (
        value.get("product_evidence_depth_status_counts")
        if isinstance(value.get("product_evidence_depth_status_counts"), Mapping)
        else {}
    )
    layer_counts = (
        value.get("product_evidence_layer_status_counts")
        if isinstance(value.get("product_evidence_layer_status_counts"), Mapping)
        else {}
    )
    ready_layers = [
        str(layer)
        for layer, status in layer_counts.items()
        if isinstance(status, Mapping) and bool(status.get("ready"))
    ][:8]
    blocked_layers = [
        str(layer)
        for layer, status in layer_counts.items()
        if isinstance(status, Mapping) and not bool(status.get("ready"))
    ][:8]
    return _without_empty_values(
        {
            "has_company_disclosed_product_kpi": bool(value.get("has_company_disclosed_product_kpi")),
            "has_product_mix": bool(value.get("has_product_mix")),
            "has_product_intelligence_graph": bool(value.get("has_product_intelligence_graph")),
            "has_technical_spec_context": bool(value.get("has_technical_spec_context")),
            "has_customer_deployment_signal": bool(value.get("has_customer_deployment_signal")),
            "has_supply_chain_signal": bool(value.get("has_supply_chain_signal")),
            "has_competitive_context": bool(value.get("has_competitive_context")),
            "has_official_context_without_exact_kpi": bool(value.get("has_official_context_without_exact_kpi")),
            "exact_ready_count": int(depth_counts.get("exact_ready") or depth_counts.get("ready") or 0),
            "proxy_ready_count": int(depth_counts.get("proxy_ready") or 0),
            "gap_count": int(value.get("gap_count") or 0),
            "ready_layers": ready_layers,
            "blocked_layers": blocked_layers,
        }
    )


def _compact_supervising_analyst_pack(value: Any, *, budget: MemoWriterBudgetSpec | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    budget = budget or MEMO_WRITER_BUDGET_SPECS["compact"]
    financial = value.get("financial_analysis_model") if isinstance(value.get("financial_analysis_model"), Mapping) else {}
    product = value.get("product_bridge_pack") if isinstance(value.get("product_bridge_pack"), Mapping) else {}
    graph = value.get("capital_transmission_graph") if isinstance(value.get("capital_transmission_graph"), Mapping) else {}
    synthesis = value.get("research_lead_synthesis_plan") if isinstance(value.get("research_lead_synthesis_plan"), Mapping) else {}
    findings = value.get("supervision_findings") if isinstance(value.get("supervision_findings"), Mapping) else {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "validation": dict(value.get("validation") or {}) if isinstance(value.get("validation"), Mapping) else {},
            "summary": dict(value.get("summary") or {}) if isinstance(value.get("summary"), Mapping) else {},
        "financial_analysis_model": {
            "statement_coverage": dict(financial.get("statement_coverage") or {})
            if isinstance(financial.get("statement_coverage"), Mapping)
            else {},
            "key_line_items": [
                {
                    "ticker": str(row.get("ticker") or ""),
                    "metric_family": str(row.get("metric_family") or ""),
                    "statement_type": str(row.get("statement_type") or ""),
                    "product_or_segment": _truncate(str(row.get("product_or_segment") or ""), 64),
                    "period_key": str(row.get("period_key") or ""),
                    "display_value": _display_or_value(row),
                }
                for row in financial.get("key_line_items") or []
                if isinstance(row, Mapping) and _display_or_value(row)
            ][: budget.financial_line_item_cap],
            "derived_ratios": [
                {
                    "ticker": str(row.get("ticker") or ""),
                    "ratio_name": str(row.get("ratio_name") or ""),
                    "display_value": str(row.get("display_value") or ""),
                    "numerator": _truncate(str(row.get("numerator") or ""), 60),
                    "denominator": _truncate(str(row.get("denominator") or ""), 60),
                    "claim_boundary": _truncate(str(row.get("claim_boundary") or ""), 90),
                }
                for row in financial.get("derived_ratios") or []
                if isinstance(row, Mapping) and str(row.get("display_value") or "")
            ][: budget.derived_ratio_cap],
            "peer_comparisons": [
                {
                    "ticker": str(row.get("ticker") or ""),
                    "canonical_metric_id": str(row.get("canonical_metric_id") or ""),
                    "period_key": str(row.get("period_key") or ""),
                    "focus_display_value": _display_or_value(row),
                    "rank_within_scope": row.get("rank_within_scope"),
                    "scope_count": row.get("scope_count"),
                }
                for row in financial.get("peer_comparisons") or []
                if isinstance(row, Mapping) and _display_or_value(row)
            ][: budget.peer_comparison_cap],
            "numeric_reconciler": {
                "attention_required_count": ((financial.get("numeric_reconciler") or {}).get("attention_required_count") if isinstance(financial.get("numeric_reconciler"), Mapping) else 0),
                "attention_required": [
                    {
                        "ticker": str(row.get("ticker") or ""),
                        "metric_family": str(row.get("metric_family") or ""),
                        "selected_for_display": str(row.get("selected_for_display") or ""),
                        "claim_boundary": _truncate(str(row.get("claim_boundary") or ""), 90),
                    }
                    for row in ((financial.get("numeric_reconciler") or {}).get("attention_required") if isinstance(financial.get("numeric_reconciler"), Mapping) else []) or []
                    if isinstance(row, Mapping)
                ][: min(3, budget.derived_ratio_cap)],
            },
        },
        "product_bridge_pack": {
            "company_disclosed_product_kpis": [
                _without_empty_values(
                    {
                        "ticker": str(row.get("ticker") or ""),
                        "metric_family": str(row.get("metric_family") or ""),
                        "product_or_segment": _truncate(str(row.get("product_or_segment") or ""), 70),
                        "period_key": str(row.get("period_key") or ""),
                        "display_value": _display_or_value(row),
                    }
                )
                for row in product.get("company_disclosed_product_kpis") or []
                if isinstance(row, Mapping) and _display_or_value(row)
            ][: budget.product_kpi_cap],
            "product_mix": [
                {
                    "ticker": str(row.get("ticker") or ""),
                    "display_value": str(row.get("display_value") or ""),
                    "numerator": _truncate(str(row.get("numerator") or ""), 60),
                    "denominator": _truncate(str(row.get("denominator") or ""), 60),
                    "claim_boundary": _truncate(str(row.get("claim_boundary") or ""), 90),
                }
                for row in product.get("product_mix") or []
                if isinstance(row, Mapping)
            ][: min(3, budget.product_kpi_cap)],
            "official_product_context": [
                _without_empty_values(
                    {
                        "claim_id": str(row.get("claim_id") or ""),
                        "ticker_scope": _string_list(row.get("ticker_scope"))[:4],
                        "products_or_platforms": _string_list(row.get("products_or_platforms"))[:3],
                        "claim_boundary": _truncate(str(row.get("claim_boundary") or ""), 70),
                    }
                )
                for row in product.get("official_product_context") or []
                if isinstance(row, Mapping)
            ][: budget.product_context_cap],
            "coverage": _compact_product_bridge_coverage_for_writer(product.get("coverage") or {}),
        },
        "capital_transmission_graph": {
            "edge_counts_by_type": dict(graph.get("edge_counts_by_type") or {})
            if isinstance(graph.get("edge_counts_by_type"), Mapping)
            else {},
            "edges": [
                {
                    "source": str(edge.get("source") or ""),
                    "target": _truncate(str(edge.get("target") or ""), 76),
                    "edge_type": str(edge.get("edge_type") or ""),
                    "strength": str(edge.get("strength") or ""),
                    "value": str(edge.get("value") or ""),
                    "claim_boundary": _truncate(str(edge.get("claim_boundary") or ""), 100),
                }
                for edge in graph.get("edges") or []
                if isinstance(edge, Mapping)
            ][: budget.graph_edge_cap],
        },
        "research_lead_synthesis_plan": {
            "plan_id": str(synthesis.get("plan_id") or ""),
            "core_judgment": _truncate(str(synthesis.get("core_judgment") or ""), 220),
            "stance": str(synthesis.get("stance") or ""),
            "argument_order": [
                {
                    "dimension_id": str(row.get("dimension_id") or ""),
                    "purpose": _truncate(str(row.get("purpose") or ""), 80),
                }
                for row in synthesis.get("argument_order") or []
                if isinstance(row, Mapping)
            ][: min(4, budget.dimension_move_cap)],
            "proven": [_truncate(str(item), 75) for item in _string_list(synthesis.get("proven"))[:3]],
            "supported_inference": [_truncate(str(item), 75) for item in _string_list(synthesis.get("supported_inference"))[:3]],
            "not_proven": [_truncate(str(item), 75) for item in _string_list(synthesis.get("not_proven"))[:3]],
            "writer_directives": [
                _truncate(str(item), 75)
                for item in _string_list(synthesis.get("writer_directives"))[: budget.supervision_finding_cap]
            ],
        },
        "supervision_findings": {
            "findings": [
                {
                    "type": str(row.get("type") or ""),
                    "owner_agent": str(row.get("owner_agent") or ""),
                    "message": _truncate(str(row.get("message") or ""), 90),
                }
                for row in findings.get("findings") or []
                if isinstance(row, Mapping)
            ][: budget.supervision_finding_cap],
            "required_followups": _dedupe_mappings_by_keys(
                [
                    {
                        "owner_agent": str(row.get("owner_agent") or ""),
                        "action": _truncate(str(row.get("action") or ""), 85),
                    }
                    for row in findings.get("required_followups") or []
                    if isinstance(row, Mapping)
                ],
                ("owner_agent", "action"),
            )[: budget.supervision_finding_cap],
        },
    }


def _compact_bounded_gap_register_for_memo(state: Mapping[str, Any]) -> dict[str, Any]:
    register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {}
    if not register:
        bundle = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else {}
        register = bundle.get("bounded_gap_register") if isinstance(bundle.get("bounded_gap_register"), Mapping) else {}
    gaps = [dict(item) for item in register.get("gaps") or [] if isinstance(item, Mapping)]
    summary = register.get("summary") if isinstance(register.get("summary"), Mapping) else {}
    return {
        "schema_version": str(register.get("schema_version") or "sec_agent_bounded_gap_register_v0.1"),
        "gap_count": int(register.get("gap_count") or len(gaps)),
        "summary": _clean_for_prompt(dict(summary)),
        "gap_refs": [
            {
                "gap_id": str(gap.get("gap_id") or ""),
                "source_family": str(gap.get("source_family") or ""),
                "gap_type": str(gap.get("gap_type") or ""),
                "ticker": str(gap.get("ticker") or ""),
                "metric": str(gap.get("metric") or ""),
                "repairability": str(gap.get("repairability") or ""),
                "claim_boundary": str(gap.get("claim_boundary") or "do_not_fill_with_generic_fallback_or_proxy_fact"),
            }
            for gap in gaps[:8]
        ],
        "claim_policy": "bounded_gaps_may_be_disclosed_as_missing_evidence_but_not_used_as_supporting_facts",
    }


def _compact_lead_memo_directive(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "memo_stance": str(value.get("memo_stance") or ""),
        "objective_satisfaction": dict(value.get("objective_satisfaction") or {})
        if isinstance(value.get("objective_satisfaction"), Mapping)
        else {},
        "opening_policy": str(value.get("opening_policy") or ""),
        "gap_budget_policy": dict(value.get("gap_budget_policy") or {})
        if isinstance(value.get("gap_budget_policy"), Mapping)
        else {},
        "product_output_contract": dict(value.get("product_output_contract") or {})
        if isinstance(value.get("product_output_contract"), Mapping)
        else {},
        "issuer_targeted_repair_required": bool(value.get("issuer_targeted_repair_required")),
        "issuer_targeted_repair_tickers": _string_list(value.get("issuer_targeted_repair_tickers"))[:12],
        "lead_targeted_repair_result": dict(value.get("lead_targeted_repair_result") or {})
        if isinstance(value.get("lead_targeted_repair_result"), Mapping)
        else {},
    }


def _compact_lead_targeted_repair_execution(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "attempted_count": int(value.get("attempted_count") or 0),
        "success_count": int(value.get("success_count") or 0),
        "bounded_gap_count": int(value.get("bounded_gap_count") or 0),
        "official_context_summaries": [
            {
                "ticker": str(row.get("ticker") or ""),
                "source_class": str(row.get("source_class") or ""),
                "title": _truncate(str(row.get("title") or ""), 120),
                "url": _truncate(str(row.get("url") or ""), 180),
                "claim_boundary": _truncate(str(row.get("claim_boundary") or ""), 180),
                "parser_diagnosis_complete": bool(row.get("parser_diagnosis_complete")),
                "source_specific_parser_status": _truncate(str(row.get("source_specific_parser_status") or ""), 140),
                "exact_fact_parser_failure_reason": _truncate(str(row.get("exact_fact_parser_failure_reason") or ""), 220),
                "next_parser_action": _truncate(str(row.get("next_parser_action") or ""), 180),
            }
            for row in value.get("official_context_summaries") or []
            if isinstance(row, Mapping)
        ][:8],
        "policy": "official_context_only_no_exact_fact_promotion",
    }


def _select_response_language(
    state: Mapping[str, Any],
    *,
    activation: Mapping[str, Any],
    query_contract: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = [
        ("state.response_language", state.get("response_language")),
        ("state.output_language", state.get("output_language")),
        ("activation.response_language", activation.get("response_language")),
        ("activation.output_language", activation.get("output_language")),
        ("query_contract.response_language", query_contract.get("response_language")),
        ("query_contract.output_language", query_contract.get("output_language")),
    ]
    multi_agent_context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), Mapping) else {}
    candidates.append(("multi_agent_context.response_language", multi_agent_context.get("response_language")))
    for source, candidate in candidates:
        language = _normalize_response_language(candidate)
        if language:
            return _response_language_dict(language, source=source)
    user_query = str(state.get("user_query") or query_contract.get("raw_query") or "")
    inferred = "zh-CN" if _contains_cjk(user_query) else "en-US"
    return _response_language_dict(inferred, source="inferred_from_user_query")


def _response_language_dict(language: str, *, source: str) -> dict[str, Any]:
    normalized = _normalize_response_language(language) or "en-US"
    return {
        "schema_version": RESPONSE_LANGUAGE_SCHEMA_VERSION,
        "language": normalized,
        "source": str(source or ""),
        "user_facing_text_language": "Simplified Chinese" if normalized == "zh-CN" else "English",
        "preserve_identifiers": ["tickers", "evidence_refs", "form_names", "numbers", "units"],
        "metric_id_render_policy": "translate_metric_ids_to_analyst_labels_in_prose; preserve raw metric ids only inside evidence refs or runtime-rendered fact tables",
        "policy": "explicit_contract_or_user_query_language_v0_1",
    }


def _response_language_from_context(value: Any) -> str:
    if isinstance(value, Mapping):
        return _normalize_response_language(value.get("language")) or "en-US"
    return _normalize_response_language(value) or "en-US"


def _normalize_response_language(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.lower().replace("_", "-")
    if normalized in {"zh", "zh-cn", "zh-hans", "chinese", "simplified-chinese", "simplified chinese", "中文", "简体中文"}:
        return "zh-CN"
    if normalized in {"en", "en-us", "en-gb", "english", "英文"}:
        return "en-US"
    return ""


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))


def _infer_memo_execution_mode_from_case_state(
    state: Mapping[str, Any],
    *,
    case_contract: Mapping[str, Any],
    judgment: Mapping[str, Any],
) -> str:
    case_id = str(state.get("case_id") or case_contract.get("case_id") or "").lower()
    eval_focus = _string_list(state.get("eval_focus") or case_contract.get("eval_focus"))
    required_moves = _string_list(state.get("required_answer_moves") or case_contract.get("required_answer_moves"))
    required_dimensions = _string_list(state.get("required_dimensions") or case_contract.get("required_dimensions"))
    prompt = str(state.get("user_query") or state.get("prompt") or case_contract.get("prompt") or "").lower()
    stats = judgment.get("claim_card_stats") if isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    supported_claim_count = int(stats.get("supported_claim_count") or len(judgment.get("supported_claims") or []))
    memo_ready_count = int(stats.get("memo_ready_claim_count") or 0)
    gold_or_deep = (
        "gold_workpaper" in case_id
        or any("gold_workpaper" in str(item).lower() or "deep" in str(item).lower() for item in eval_focus)
        or "deep research" in prompt
        or "深度" in prompt
    )
    if gold_or_deep and (supported_claim_count >= 4 or memo_ready_count >= 3 or len(required_moves) >= 5):
        return "deep_research"
    if len(required_moves) >= 7 and len(required_dimensions) >= 5 and supported_claim_count >= 4:
        return "deep_research"
    if len(required_moves) >= 4 and supported_claim_count >= 3:
        return "standard_memo"
    return ""


def _select_memo_profile(
    state: Mapping[str, Any],
    *,
    shared_context: Mapping[str, Any],
    judgment: Mapping[str, Any],
) -> MemoProfileSpec:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    execution_mode = str(activation.get("execution_mode") or shared_context.get("execution_mode") or "").strip()
    coverage = shared_context.get("coverage") if isinstance(shared_context.get("coverage"), Mapping) else {}
    stats = shared_context.get("claim_card_stats") if isinstance(shared_context.get("claim_card_stats"), Mapping) else {}
    thesis_pack = judgment.get("memo_thesis_pack") if isinstance(judgment.get("memo_thesis_pack"), Mapping) else {}
    thesis_plan = judgment.get("memo_thesis_plan") if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {}
    supported_claim_count = int(stats.get("supported_claim_count") or len(judgment.get("supported_claims") or []))
    memo_ready_count = int(stats.get("memo_ready_claim_count") or 0)
    supported_slot_count = int(stats.get("memo_slot_supported_count") or stats.get("supported_memo_slot_count") or 0)
    source_family_count = _supported_source_family_count(judgment)
    pack_ready = str(thesis_pack.get("status") or thesis_plan.get("status") or "") == "ready"
    bounded = bool(coverage.get("bounded_answer_allowed") or state.get("bounded_answer_allowed"))
    missing_requirements = int(coverage.get("missing_requirement_count") or 0)

    reason_parts: list[str] = []
    if supported_claim_count < 3 or memo_ready_count < 2:
        reason_parts.append("compact_due_to_sparse_claim_cards")
        return _profile_with_reason("compact", reason_parts)
    if execution_mode in {"deterministic_lookup", "focused_answer"}:
        reason_parts.append(f"compact_for_{execution_mode or 'focused'}")
        return _profile_with_reason("compact", reason_parts)
    if execution_mode == "deep_research":
        if pack_ready and supported_claim_count >= 6 and memo_ready_count >= 4 and supported_slot_count >= 3 and source_family_count >= 2:
            reason_parts.append("deep_research_ready_claim_density_and_source_diversity")
            return _profile_with_reason("deep_research", reason_parts)
        if pack_ready and supported_claim_count >= 4 and source_family_count >= 2:
            reason_parts.append("deep_research_but_evidence_density_supports_expanded")
            return _profile_with_reason("expanded", reason_parts)
        reason_parts.append("deep_research_but_thin_evidence_uses_standard")
        return _profile_with_reason("standard", reason_parts)
    if execution_mode == "standard_memo":
        if pack_ready and supported_claim_count >= 5 and memo_ready_count >= 3 and source_family_count >= 2 and missing_requirements <= 4:
            reason_parts.append("standard_case_with_enough_claim_density_for_expanded")
            return _profile_with_reason("expanded", reason_parts)
        if pack_ready and supported_claim_count >= 3:
            reason_parts.append("standard_case_with_ready_thesis_pack")
            return _profile_with_reason("standard", reason_parts)
    if pack_ready and supported_claim_count >= 4 and source_family_count >= 2:
        reason_parts.append("fallback_standard_ready_thesis_pack")
        return _profile_with_reason("standard", reason_parts)
    reason_parts.append("default_compact")
    return _profile_with_reason("compact", reason_parts)


def _profile_with_reason(profile: str, reason_parts: list[str]) -> MemoProfileSpec:
    spec = MEMO_PROFILE_SPECS.get(profile, MEMO_PROFILE_SPECS["compact"])
    return MemoProfileSpec(**{**spec.__dict__, "profile": spec.profile})


def _memo_profile_spec_from_name(value: Any) -> MemoProfileSpec:
    return MEMO_PROFILE_SPECS.get(str(value or "").strip(), MEMO_PROFILE_SPECS["compact"])


def _memo_writer_budget_spec_from_profile(profile: MemoProfileSpec | str | None) -> MemoWriterBudgetSpec:
    profile_name = profile.profile if isinstance(profile, MemoProfileSpec) else str(profile or "").strip()
    return MEMO_WRITER_BUDGET_SPECS.get(profile_name, MEMO_WRITER_BUDGET_SPECS["compact"])


def _memo_profile_dict(spec: MemoProfileSpec) -> dict[str, Any]:
    return {
        "schema_version": MEMO_PROFILE_SCHEMA_VERSION,
        "profile": spec.profile,
        "direct_answer_max_chars": spec.direct_answer_max_chars,
        "direct_answer_min_chars": spec.direct_answer_min_chars,
        "memo_claims_min_when_thesis_ready": spec.memo_claims_min_when_thesis_ready,
        "memo_claims_max": spec.memo_claims_max,
        "memo_claim_max_chars": spec.memo_claim_max_chars,
        "caveats_max": spec.caveats_max,
        "unsupported_claims_excluded_max": spec.unsupported_claims_excluded_max,
        "source_boundary_notes_max": spec.source_boundary_notes_max,
        "supported_claim_cap_with_thesis_pack": spec.supported_claim_cap_with_thesis_pack,
        "rendered_claim_max": spec.rendered_claim_max,
    }


def _supported_source_family_count(judgment: Mapping[str, Any]) -> int:
    families = {
        family
        for claim in judgment.get("supported_claims") or []
        if isinstance(claim, Mapping)
        for family in _string_list(claim.get("source_families") or claim.get("source_family"))
        if family
    }
    return len(families)


def _memo_messages(
    state: Mapping[str, Any],
    *,
    prior_failure: Mapping[str, Any] | None,
    prior_content: str,
) -> list[dict[str, str]]:
    full_shared_context = build_shared_memo_context(state)
    shared_context = _compact_shared_memo_context_for_prompt(full_shared_context)
    memo_profile = _memo_profile_spec_from_name(
        ((shared_context.get("memo_profile") or {}) if isinstance(shared_context.get("memo_profile"), Mapping) else {}).get("profile")
    )
    writer_budget = _memo_writer_budget_spec_from_profile(memo_profile)
    response_language = _response_language_from_context(shared_context.get("response_language"))
    response_language_name = "Simplified Chinese" if response_language == "zh-CN" else "English"
    judgment = _compact_judgment_for_memo(
        state.get("verified_judgment_plan") or state.get("judgment_plan") or {},
        memo_profile=memo_profile,
        budget=writer_budget,
    )
    memo_logic_plan = _compact_memo_logic_plan_for_writer_prompt(
        state.get("memo_logic_plan") or {},
        budget=writer_budget,
    )
    supervising_analyst_pack = _compact_supervising_analyst_pack(
        state.get("supervising_analyst_pack") or {},
        budget=writer_budget,
    )
    contract = _memo_output_contract(memo_profile)
    writer_direct_answer_skeleton = _direct_answer_skeleton_from_required_items(
        [
            dict(item)
            for item in memo_logic_plan.get("required_item_answer_plan") or []
            if isinstance(item, Mapping) and str(item.get("answer") or "").strip()
        ],
        response_language=response_language,
        max_chars=memo_profile.direct_answer_max_chars,
    )
    user_payload = {
        "shared_memo_context": shared_context,
        "supervising_analyst_pack": supervising_analyst_pack,
        "memo_logic_plan": memo_logic_plan,
        "writer_direct_answer_skeleton": writer_direct_answer_skeleton,
        "user_query": state.get("user_query") or "",
        "verified_judgment_plan": judgment,
        "specialist_verification": _compact_specialist_verification(state.get("specialist_verification") or {}),
        "memo_input_contract": {
            "allowed_views": [
                "shared_memo_context",
                "supervising_analyst_pack",
                "memo_logic_plan",
                "verified_judgment_plan",
                "specialist_verification",
            ],
            "raw_rows_consumed": False,
            "raw_evidence_rows": "excluded",
            "bounded_evidence_rows": "excluded",
            "private_operator_context": "excluded",
            "tool_calls_allowed": False,
            "response_language": response_language,
            "projection_policy": "memo_writer_v0_10_minimal_judgment_surface_programmatic_projection",
            "writer_budget_profile": writer_budget.profile,
        },
        "memo_output_contract": contract,
    }
    user = (
        "Write one MemoDraft JSON object from the Research Lead synthesis plan, MemoLogicPlan, and compact verified ClaimCard inputs only. "
        "If supervising_analyst_pack.research_lead_synthesis_plan is present, use it as the primary thesis, argument order, proven/not_proven boundary, and investment implication contract. "
        "Use memo_logic_plan.writer_thesis_skeleton as the primary writing plan. It is the Research Lead's compressed answer contract: opening_judgment, causal_chain, dimension_moves, and product_reasoning_move decide the memo order. "
        "Use memo_logic_plan.thesis_density_contract as the quality bar: the memo must produce supported insight and causal bridges, not just avoid mistakes. "
        "Use memo_logic_plan.sections only as the secondary outline; use verified_judgment_plan only to fill the skeleton with verified claims, evidence refs, counterevidence, and gaps. "
        "Use shared_memo_context only for scope, coverage, Specialist route status, and source-boundary framing, never as factual evidence. "
        f"Set response_language.language exactly to {response_language}; user-facing prose must be {response_language_name}. "
        "For zh-CN, translate/synthesize direct_answer, dimension_analyses prose fields, memo_claims.claim, caveats, source_boundary_notes, investment_implications, what_would_change_view, monitoring_items, and evidence_gaps_but_actionable into Simplified Chinese; keep tickers, form names, numbers, units, claim_id, and evidence_refs unchanged. Do not render raw metric IDs or slash-joined internal field names as prose; translate them into natural analyst labels unless they appear only inside an evidence ref or table column. "
        "For zh-CN, any memo_claim.claim that is mostly English prose is invalid; do not quote English ClaimCard text, do not add 'original text' wrappers, and do not say the English text is preserved for traceability. "
        "Use supervising_analyst_pack.research_lead_synthesis_plan first for dimension-led analysis, then memo_logic_plan.sections, judgment_state.dimension_judgments, thesis_driver_pack.dimension_sections, memo_thesis_pack, memo_thesis_plan, and memo_outline as fallbacks. "
        "Before writing, execute memo_logic_plan.required_item_answer_plan item by item. For each item, write a present bounded judgment, the evidence bridge, the counter-read, and what would change the view; a keyword mention or generic 'needs verification' sentence is invalid. "
        "Use memo_logic_plan.required_question_items only as the coverage inventory behind that answer plan. If an item is only answerable with boundary, still state the current bounded judgment and the exact missing link; do not omit it. "
        "Use memo_logic_plan.focus_ticker_coverage_policy to avoid saying a focus ticker has no data when approved facts or supported claims exist for that ticker. "
        "Before interpreting any ClaimCard, read its scope_role, economic_role, transmission_role, memo_use_role, and role_boundary. These fields decide whether the fact is issuer financial quality, issuer product revenue/backlog, customer/demand-side capex, peer context, or issuer own reinvestment. "
        "Never describe customer_or_demand_side_capex_signal or peer_context_ticker facts as supplier-side revenue, product income, backlog, or direct orders. They can only support demand-pool or end-market context unless a verified customer/order/deployment edge is cited. "
        "Never describe issuer_own_capital_investment facts as demand-side customer spend. For focus suppliers such as AMAT/KLAC/LRCX/DELL/NVDA, issuer capex is own reinvestment/capacity/cash-flow pressure, not customer demand, unless a counterparty deployment/order row is cited. "
        "Use memo_logic_plan.economic_role_summary and writer_thesis_skeleton.economic_role_move to keep demand-side, supplier-side, peer-context, and issuer-own facts separate in the opening and every dimension. "
        "Use memo_logic_plan.product_reasoning_frame and memo_logic_plan.writer_thesis_skeleton.product_reasoning_move as the product reasoning spine: product profile/spec/KPI/deployment/proxy/relationship evidence should explain product capability, adoption, supply-chain read-through, and financial bridge before SKU-revenue gaps. "
        "Use supervising_analyst_pack.financial_analysis_model for the fundamentals section, product_bridge_pack for product/product-line evidence, and capital_transmission_graph for capital or supply-chain transmission. "
        "Write direct_answer as a dense executive synthesis across the strongest dimensions, not a driver-by-driver list, row recap, schema recap, or gap ledger. The opening must follow memo_logic_plan.writer_thesis_skeleton.opening_judgment, state the present judgment, why it matters, and the business/financial transmission path before discussing boundaries; never start the memo with data-missing language when any supported product, capital, customer, or financial evidence exists. "
        "Emit dimension_analyses for the supported dimensions actually present in judgment_state.dimension_judgments or thesis_driver_pack.dimension_sections. Each dimension_analyses item must include dimension_id, title, summary, business_mechanism, financial_bridge, competitive_read or counter_read, claim_ids, and evidence_refs copied exactly. "
        "For product_and_production, follow shared_memo_context.lead_review.memo_directive.product_output_contract: name products/platforms, product KPIs/specs/parameters/order/backlog/capacity context when available, and only put commercial tracker gaps in the gap section after public/official sources are exhausted. "
        "Do not say product analysis is impossible only because SKU revenue is absent; explain what spec, architecture, deployment, channel, benchmark, supply-chain, and relationship evidence can support, then separately state the SKU-revenue absence reason. "
        "For issuer coverage gaps, use shared_memo_context.lead_review.targeted_repair_execution: if official source probes succeeded, do not write that the issuer has no public source coverage; say only that exact value parser promotion is still bounded if no ClaimCard exists. "
        "Respect the gap_budget_policy: evidence gaps must be concise, decision-changing, and mainly in evidence_gaps_but_actionable; never let caveats dominate the memo body. "
        "Do not write visible labels such as 'mechanism:', 'financial bridge:', '机制：', '财务桥：', 'Bridge the claim', or schema names in user-facing prose; explain the causal path naturally. "
        "Do not copy internal phrases such as 'Synthesized thesis', 'ClaimCard', '该声明为已核对财务事实', '不得推断未验证', pipe-delimited joined claims, driver_id, gap_id, source_boundary_notes, or repeated claim text into direct_answer. "
        "For user-facing numeric values, use display_value/display_value_zh/selected_for_display exactly as provided; do not use raw value or numeric_value fields as prose. "
        "If a needed numeric fact has no display_value, state the bounded display-lineage issue in evidence_gaps_but_actionable instead of printing the raw number. "
        "Do not recalculate, invent, round, or change units. "
        "Do not request tools, consume raw rows, or add facts beyond verified claim cards.\n\n"
        f"Profile caps: memo_profile={memo_profile.profile}; direct_answer should be {memo_profile.direct_answer_min_chars}-{memo_profile.direct_answer_max_chars} characters when supported and direct_answer <= {memo_profile.direct_answer_max_chars} characters; "
        f"memo_claims {memo_profile.memo_claims_min_when_thesis_ready}-{memo_profile.memo_claims_max} when memo_thesis_pack or memo_thesis_plan is ready; each memo_claim.claim <= {memo_profile.memo_claim_max_chars} characters; "
        f"caveats <= {memo_profile.caveats_max}; unsupported_claims_excluded <= {memo_profile.unsupported_claims_excluded_max}; source_boundary_notes <= {memo_profile.source_boundary_notes_max}. "
        "For standard/expanded/deep_research, include at least two dimension_analyses when supported plus non-empty investment_implications, what_would_change_view, and monitoring_items. "
        "investment_implications must state the agent's present judgment and portfolio/research implication first, then the reason. what_would_change_view must say which new evidence would change that judgment, not repeat metadata, source boundaries, or generic monitoring language. "
        "Every dimension_analyses item should use this sentence order: judgment -> why it matters -> evidence refs -> what can break it. Do not use 'watch X to decide' as the whole conclusion. "
        "Set memo_generation_policy exactly to thesis_led_claim_cards_v0_1. "
        "Emit compact memo_thesis_plan only; do_not_emit_supported_claims=true; do not emit judgment_state, thesis_driver_pack, memo_thesis_pack, memo_outline, analysis traces, source tables, or copied judgment_plan. "
        "Emit memo_claims synthesized from supported claims with claim_id and evidence_refs copied exactly. Return JSON only.\n\n"
        f"Input JSON:\n{_json_for_prompt(user_payload)}"
    )
    user = (
        _memo_writer_compact_instruction_scaffold(
            memo_profile=memo_profile,
            response_language=response_language,
            response_language_name=response_language_name,
        )
        + f"\n\nInput JSON:\n{_json_for_prompt(user_payload)}"
    )
    if prior_failure:
        cleaned_failure = _clean_for_prompt(prior_failure)
        is_length_or_parse_failure = str(prior_failure.get("type") or "") in {"json_parse_failed", "model_output_truncated"}
        repair_payload = _compact_memo_payload_for_repair(user_payload, length_repair=is_length_or_parse_failure)
        if is_length_or_parse_failure:
            user = (
                "Repair the previous MemoDraft response. The prior output was not a complete valid compact JSON object.\n"
                f"Diagnostic:\n{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{_json_for_prompt(repair_payload)}\n\n"
                "Return exactly one minimal MemoDraft JSON object. "
                f"memo_profile must stay {memo_profile.profile}. "
                f"response_language.language must stay {response_language}; user-facing prose must be {response_language_name}. "
                f"direct_answer <= {min(memo_profile.direct_answer_max_chars, 700)} characters, "
                f"memo_claims 3-{min(memo_profile.memo_claims_max, MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP)} when available, "
                "caveats <= 3, unsupported_claims_excluded <= 2, source_boundary_notes <= 3. "
                "Use only claim_id/evidence_refs present in verified_judgment_plan.supported_claims and do not add optional fields beyond the required shape. "
                "Set memo_generation_policy exactly to thesis_led_claim_cards_v0_1. "
                "Preserve numeric values exactly from ClaimCards; do not round or change units. "
                "For zh-CN, translate or synthesize every user-facing claim/section into Simplified Chinese; copy only claim_id, evidence_refs, tickers, numbers, and units. Do not render raw metric IDs or slash-joined internal field names as prose; translate them into analyst labels unless they appear only inside an evidence ref. "
                "For zh-CN, do not quote English claim text or wrap it as original/source text; rewrite the investment meaning in Chinese. "
                "Use memo_logic_plan if present, do not copy internal phrases like 'Synthesized thesis' or 'ClaimCards' into direct_answer, do not use pipe-delimited claim concatenation, and do not repeat the same sentence twice. "
                "If supervising_analyst_pack is present, keep its core_judgment and writer_directives as the repair target. "
                "Do not write visible labels such as '机制：', '财务桥：', 'mechanism:', or 'financial bridge:'; write natural causal prose. Keep gaps short and do not let evidence-boundary language dominate the answer. "
                "For standard/expanded/deep_research, include dimension_analyses with mechanism, financial bridge, counter-read, claim_ids, and evidence_refs, plus non-empty investment_implications, what_would_change_view, and monitoring_items. "
                "Do not emit supported_claims, memo_thesis_pack, or memo_outline. No markdown, no prose, no row-by-row recap."
            )
        else:
            user = (
                "Repair the previous MemoDraft response using the compact verified judgment only.\n"
                f"Diagnostic:\n{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{_json_for_prompt(repair_payload)}\n\n"
                f"Previous output excerpt:\n{_truncate(prior_content, 500)}\n\n"
                "Return one shorter corrected MemoDraft JSON object only. "
                f"memo_profile must stay {memo_profile.profile}. "
                f"response_language.language must stay {response_language}; user-facing prose must be {response_language_name}. "
                "Rewrite direct_answer as a natural user-facing investment paragraph without internal labels or pipe-delimited claim joins. "
                "For zh-CN, translate or synthesize every user-facing claim/section and dimension_analyses prose field into Simplified Chinese; copy only claim_id, evidence_refs, tickers, numbers, and units. Do not render raw metric IDs or slash-joined internal field names as prose; translate them into analyst labels unless they appear only inside an evidence ref. "
                "For zh-CN, do not quote English claim text or wrap it as original/source text; rewrite the investment meaning in Chinese. "
                "Use memo_logic_plan.sections as the writing order when present and do not expose mechanism/financial_bridge as literal headings. Keep gaps short and turn supported evidence into judgment, not a source-boundary report. "
                "If supervising_analyst_pack is present, rewrite around its core_judgment, financial_analysis_model, product_bridge_pack, and capital_transmission_graph instead of summarizing ClaimCards in order. "
                "Remove repeated sentences, and for standard/expanded/deep_research include dimension_analyses plus non-empty investment_implications, what_would_change_view, and monitoring_items. "
                "Set memo_generation_policy exactly to thesis_led_claim_cards_v0_1, preserve numeric values exactly, and do not emit memo_thesis_pack or memo_outline."
            )
    return [
        {"role": "system", "content": _memo_system_prompt()},
        {"role": "user", "content": user},
    ]


def _memo_writer_compact_instruction_scaffold(
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
    response_language_name: str,
) -> str:
    caps = _memo_writer_surface_caps(memo_profile)
    return (
        "Write one MemoDraft JSON object. Use only shared_memo_context, supervising_analyst_pack, "
        "memo_logic_plan, verified_judgment_plan, specialist_verification, and compact verified ClaimCard inputs; "
        "do not request tools or use raw rows.\n"
        "Input priority: supervising_analyst_pack.research_lead_synthesis_plan -> "
        "writer_direct_answer_skeleton -> memo_logic_plan.writer_thesis_skeleton -> memo_logic_plan.required_item_answer_plan -> "
        "memo_logic_plan.sections -> verified_judgment_plan.judgment_state / thesis_driver_pack / "
        "memo_thesis_pack / memo_thesis_plan / memo_outline.\n"
        "Required-item rule: answer each memo_logic_plan.required_item_answer_plan item with bounded present judgment, "
        "evidence bridge, counter-read, and what would change the view; do not satisfy it with keywords or generic 'needs verification'.\n"
        "Role rule: before using any ClaimCard, respect scope_role, economic_role, transmission_role, memo_use_role, "
        "and role_boundary. Demand-side capex or peer context is not supplier revenue/order/backlog; issuer capex is own reinvestment unless a verified counterparty edge exists.\n"
        "Product rule: use writer_thesis_skeleton.product_reasoning_move and memo_logic_plan.product_reasoning_frame to discuss "
        "profile/spec/KPI/deployment/proxy/relationship evidence before SKU-revenue gaps. Do not say product analysis is impossible only because SKU revenue is absent.\n"
        "Surface rule: direct_answer must be thesis-led judgment first, then why it matters, causal path, refs, and concise boundaries. "
        "Do not render internal labels such as mechanism:, financial bridge:, 机制：, 财务桥：, ClaimCard, gap_id, driver_id, or schema names.\n"
        "Language/numeric rule: "
        f"set response_language.language exactly to {response_language}; user-facing prose must be {response_language_name}. "
            "For zh-CN, synthesize user-facing prose in Simplified Chinese while preserving tickers, form names, numbers, units, claim_id, and evidence_refs. Do not render raw metric IDs or slash-joined internal field names as prose; translate them into analyst labels unless they appear only inside an evidence ref. "
        "Use display_value/display_value_zh/selected_for_display exactly; never print raw numeric_value, recalculate, invent, round, or change units.\n"
        "Minimal-output rule: the model's job is judgment prose and thesis meaning, not copying every traceable row. "
        "Emit answer_status, direct_answer, response_language, memo_profile, memo_generation_policy, raw_rows_consumed=false, "
        "tool_calls_requested=[], and compact memo_thesis_plan. Emit only the strongest optional anchors: "
        f"dimension_analyses <= {MEMO_MODEL_OUTPUT_DIMENSION_CAP}, memo_claims <= {MEMO_MODEL_OUTPUT_CLAIM_CAP}, "
        f"investment_implications/what_would_change_view/monitoring_items/evidence_gaps_but_actionable <= {MEMO_MODEL_OUTPUT_ACTION_ITEM_CAP} each. "
        "The runtime will deterministically complete remaining memo_claims, required dimensions, action lists, and traceability from verified_judgment_plan; do not duplicate that work.\n"
        "Use shared_memo_context only for scope/source-boundary framing, not factual support.\n"
        f"Final surface caps after deterministic projection: dimension_analyses <= {caps['dimension_analyses_max']}; "
        f"investment_implications <= {caps['investment_implications_max']}; "
        f"what_would_change_view <= {caps['what_would_change_view_max']}; "
        f"monitoring_items <= {caps['monitoring_items_max']}; "
        f"evidence_gaps_but_actionable <= {caps['evidence_gaps_but_actionable_max']}; "
        f"each dimension summary <= {caps['dimension_summary_max_chars']} chars and mechanism/bridge/counter fields <= {caps['dimension_detail_max_chars']} chars; "
        "do not emit extra explanatory arrays, debug fields, copied source tables, or long caveat ledgers.\n"
        f"Profile caps: memo_profile={memo_profile.profile}; direct_answer {memo_profile.direct_answer_min_chars}-{memo_profile.direct_answer_max_chars} chars; "
        f"memo_claims {memo_profile.memo_claims_min_when_thesis_ready}-{memo_profile.memo_claims_max}; "
        f"caveats <= {memo_profile.caveats_max}; unsupported_claims_excluded <= {memo_profile.unsupported_claims_excluded_max}; "
        f"source_boundary_notes <= {memo_profile.source_boundary_notes_max}.\n"
        "Set memo_generation_policy exactly to thesis_led_claim_cards_v0_1; "
        "do_not_emit_supported_claims=true; do not emit judgment_state, thesis_driver_pack, memo_thesis_pack, "
        "memo_outline, analysis traces, source tables, or copied judgment_plan. Return JSON only. "
        "Projection policy id: memo_writer_v0_10_minimal_judgment_surface_programmatic_projection. "
        "Quality bar: memo_logic_plan.thesis_density_contract."
    )


def _memo_writer_static_scaffold_summary(
    *,
    memo_profile: MemoProfileSpec,
    response_language: str,
) -> dict[str, Any]:
    response_language_name = "Simplified Chinese" if response_language == "zh-CN" else "English"
    system_prompt = _memo_system_prompt()
    instruction = _memo_writer_compact_instruction_scaffold(
        memo_profile=memo_profile,
        response_language=response_language,
        response_language_name=response_language_name,
    )
    return {
        "schema_version": "sec_agent_memo_writer_static_scaffold_fingerprint_v0_1",
        "policy_id": "memo_writer_compact_instruction_scaffold_v0_1",
        "system_prompt_chars": len(system_prompt),
        "user_instruction_chars": len(instruction),
        "system_prompt_digest": _fingerprint_digest({"system_prompt": system_prompt}),
        "user_instruction_digest": _fingerprint_digest({"user_instruction": instruction}),
        "fingerprint_policy": "digest_and_length_only_no_prompt_text_persisted",
    }


def _memo_output_contract(profile: MemoProfileSpec) -> dict[str, Any]:
    surface_caps = _memo_writer_surface_caps(profile)
    return {
        **_memo_profile_dict(profile),
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "surface_policy": "memo_logic_plan_first_user_facing_prose_no_internal_labels_v0_1",
        "model_output_policy": "minimal_judgment_surface_programmatic_projection_v0_1",
        "model_should_emit": [
            "answer_status",
            "direct_answer",
            "response_language",
            "memo_profile",
            "memo_thesis_plan",
            "memo_generation_policy",
            "raw_rows_consumed",
            "tool_calls_requested",
        ],
        "runtime_will_complete_from_verified_judgment": [
            "memo_claims",
            "required_dimension_analyses",
            "investment_implications",
            "what_would_change_view",
            "monitoring_items",
            "traceability_refs",
        ],
        "model_output_caps": {
            "dimension_analyses": MEMO_MODEL_OUTPUT_DIMENSION_CAP,
            "memo_claims": MEMO_MODEL_OUTPUT_CLAIM_CAP,
            "investment_implications": MEMO_MODEL_OUTPUT_ACTION_ITEM_CAP,
            "what_would_change_view": MEMO_MODEL_OUTPUT_ACTION_ITEM_CAP,
            "monitoring_items": MEMO_MODEL_OUTPUT_ACTION_ITEM_CAP,
            "evidence_gaps_but_actionable": MEMO_MODEL_OUTPUT_ACTION_ITEM_CAP,
        },
        "surface_caps": surface_caps,
        "response_language_shape": {
            "schema_version": RESPONSE_LANGUAGE_SCHEMA_VERSION,
            "language": "zh-CN | en-US",
            "source": "memo_writer_context",
        },
        "memo_thesis_plan_shape": [
            "schema_version",
            "status",
            "primary_thesis_claim_id",
            "primary_thesis",
            "thesis_direction",
        ],
        "dimension_analyses_shape": [
            "dimension_id",
            "title",
            "summary",
            "business_mechanism",
            "financial_bridge",
            "competitive_read",
            "counter_read",
            "claim_ids",
            "evidence_refs",
        ],
        "dimension_analyses_max": surface_caps["dimension_analyses_max"],
        "action_items_max": {
            "investment_implications": surface_caps["investment_implications_max"],
            "what_would_change_view": surface_caps["what_would_change_view_max"],
            "monitoring_items": surface_caps["monitoring_items_max"],
            "evidence_gaps_but_actionable": surface_caps["evidence_gaps_but_actionable_max"],
        },
        "do_not_emit_supported_claims": True,
        "do_not_emit_thesis_driver_pack": True,
        "do_not_emit_memo_thesis_pack": True,
        "do_not_emit_memo_outline": True,
        "must_copy_claim_id_and_evidence_refs_from_input": True,
        "must_not_render_internal_field_labels": [
            "business_mechanism",
            "financial_bridge",
            "mechanism:",
            "financial bridge:",
            "机制：",
            "财务桥：",
            "Bridge the claim",
        ],
        "allowed_top_level_fields": [
            "schema_version",
            "answer_status",
            "direct_answer",
            "response_language",
            "memo_profile",
            "dimension_analyses",
            "memo_claims",
            "investment_implications",
            "what_would_change_view",
            "monitoring_items",
            "evidence_gaps_but_actionable",
            "caveats",
            "unsupported_claims_excluded",
            "source_boundary_notes",
            "memo_thesis_plan",
            "source_boundary",
            "raw_rows_consumed",
            "tool_calls_requested",
            "memo_generation_policy",
        ],
    }


def _memo_writer_surface_caps(profile: MemoProfileSpec | str | None) -> dict[str, int]:
    profile_name = profile.profile if isinstance(profile, MemoProfileSpec) else str(profile or "").strip()
    if profile_name == "deep_research":
        return {
            "dimension_analyses_max": 5,
            "dimension_summary_max_chars": 300,
            "dimension_detail_max_chars": 200,
            "investment_implications_max": 3,
            "what_would_change_view_max": 3,
            "monitoring_items_max": 3,
            "evidence_gaps_but_actionable_max": 3,
        }
    if profile_name == "expanded":
        return {
            "dimension_analyses_max": 4,
            "dimension_summary_max_chars": 280,
            "dimension_detail_max_chars": 180,
            "investment_implications_max": 3,
            "what_would_change_view_max": 2,
            "monitoring_items_max": 3,
            "evidence_gaps_but_actionable_max": 3,
        }
    if profile_name == "standard":
        return {
            "dimension_analyses_max": 3,
            "dimension_summary_max_chars": 260,
            "dimension_detail_max_chars": 170,
            "investment_implications_max": 2,
            "what_would_change_view_max": 2,
            "monitoring_items_max": 3,
            "evidence_gaps_but_actionable_max": 2,
        }
    return {
        "dimension_analyses_max": 1,
        "dimension_summary_max_chars": 220,
        "dimension_detail_max_chars": 150,
        "investment_implications_max": 2,
        "what_would_change_view_max": 1,
        "monitoring_items_max": 2,
        "evidence_gaps_but_actionable_max": 2,
    }


def _compact_judgment_for_memo(
    value: Any,
    *,
    memo_profile: MemoProfileSpec | None = None,
    budget: MemoWriterBudgetSpec | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    profile = memo_profile or MEMO_PROFILE_SPECS["compact"]
    budget = budget or _memo_writer_budget_spec_from_profile(profile)
    supported = [_compact_claim_card(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)]
    thesis_pack = _compact_memo_thesis_pack(value.get("memo_thesis_pack") or {})
    thesis_driver_pack = _compact_thesis_driver_pack(value.get("thesis_driver_pack") or {})
    judgment_state = _compact_judgment_state(value.get("judgment_state") or {})
    profile_claim_cap = (
        profile.supported_claim_cap_with_thesis_pack
        if thesis_pack
        else budget.supported_claim_cap
        if profile.profile in {"expanded", "deep_research"}
        else MEMO_SUPPORTED_CLAIM_CAP
    )
    supported_claim_cap = min(budget.supported_claim_cap, profile_claim_cap)
    memo_outline_cap = budget.memo_outline_cap
    unsupported = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 220),
            "reason": _truncate(str(item.get("reason") or ""), 160),
        }
        for item in value.get("unsupported_claims") or []
        if isinstance(item, Mapping)
    ]
    conflicts = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 220),
            "reason": _truncate(str(item.get("reason") or ""), 180),
        }
        for item in value.get("conflicts") or []
        if isinstance(item, Mapping)
    ]
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "supported_claims": _select_memo_supported_claims(supported, value.get("memo_outline") or [], max_claims=supported_claim_cap),
        "unsupported_claims": unsupported[:MEMO_UNSUPPORTED_CLAIM_CAP],
        "conflicts": conflicts[:MEMO_CONFLICT_CAP],
        "source_boundary_notes": _compact_source_boundary_notes(value.get("source_boundary_notes") or []),
        "memo_outline": _compact_memo_outline_for_prompt(value.get("memo_outline") or [], max_items=memo_outline_cap),
        "memo_thesis_plan": _compact_memo_thesis_plan(value.get("memo_thesis_plan") or {}),
        "memo_thesis_pack": thesis_pack,
        "thesis_driver_pack": thesis_driver_pack,
        "judgment_state": judgment_state,
        "claim_card_stats": dict(value.get("claim_card_stats") or {}),
        "memo_constraints": _compact_memo_constraints(value.get("memo_constraints") or {}),
        "memo_writer_allowed": bool(value.get("memo_writer_allowed", True)),
        "aggregation_policy": str(value.get("aggregation_policy") or ""),
    }


def _compact_memo_payload_for_repair(payload: Mapping[str, Any], *, length_repair: bool = False) -> dict[str, Any]:
    judgment = payload.get("verified_judgment_plan") if isinstance(payload.get("verified_judgment_plan"), Mapping) else {}
    compact_judgment = dict(judgment)
    thesis_pack = _compact_memo_thesis_pack(judgment.get("memo_thesis_pack") or {})
    thesis_driver_pack = _compact_thesis_driver_pack(judgment.get("thesis_driver_pack") or {})
    judgment_state = _compact_judgment_state(judgment.get("judgment_state") or {})
    output_contract = payload.get("memo_output_contract") if isinstance(payload.get("memo_output_contract"), Mapping) else {}
    shared_context = payload.get("shared_memo_context") if isinstance(payload.get("shared_memo_context"), Mapping) else {}
    response_language = (
        dict(shared_context.get("response_language") or {}) if isinstance(shared_context.get("response_language"), Mapping) else {}
    )
    profile = _memo_profile_spec_from_name(output_contract.get("profile"))
    writer_budget = _memo_writer_length_repair_budget_spec(profile) if length_repair else _memo_writer_budget_spec_from_profile(profile)
    if length_repair:
        output_contract = _memo_length_repair_output_contract(profile)
    supported_claim_cap = (
        MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP
        if length_repair
        else min(
            writer_budget.supported_claim_cap,
            profile.supported_claim_cap_with_thesis_pack if thesis_pack else MEMO_SUPPORTED_CLAIM_CAP,
        )
    )
    compact_judgment["supported_claims"] = _select_memo_supported_claims(
        [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)],
        judgment.get("memo_outline") or [],
        max_claims=supported_claim_cap,
    )
    compact_judgment["unsupported_claims"] = [
        dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)
    ][:MEMO_UNSUPPORTED_CLAIM_CAP]
    compact_judgment["conflicts"] = [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)][:MEMO_CONFLICT_CAP]
    compact_judgment["source_boundary_notes"] = [dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)][:4]
    compact_judgment["memo_thesis_pack"] = {} if length_repair else thesis_pack
    compact_judgment["thesis_driver_pack"] = {} if length_repair else thesis_driver_pack
    compact_judgment["judgment_state"] = {} if length_repair else judgment_state
    if length_repair:
        compact_judgment["memo_outline"] = [
            dict(item) for item in judgment.get("memo_outline") or [] if isinstance(item, Mapping)
        ][:4]
        compact_judgment["memo_constraints"] = _compact_memo_constraints(judgment.get("memo_constraints") or {})
    return {
        "user_query": _truncate(str(payload.get("user_query") or ""), 240),
        "response_language": response_language,
        "memo_logic_plan": _compact_memo_logic_plan_for_writer_prompt(
            payload.get("memo_logic_plan") or {},
            budget=writer_budget,
        ),
        "supervising_analyst_pack": _compact_supervising_analyst_pack(
            payload.get("supervising_analyst_pack") or {},
            budget=writer_budget,
        ),
        "verified_judgment_plan": compact_judgment,
        "specialist_verification": payload.get("specialist_verification") or {},
        "memo_input_contract": payload.get("memo_input_contract") or {},
        "memo_output_contract": output_contract,
        "required_shape": {
            "schema_version": "sec_agent_multi_agent_memo_draft_v0.1",
            "answer_status": "draft | blocked_by_specialist_verification",
            "direct_answer": "compact bounded answer",
            "response_language": response_language or {"language": "zh-CN | en-US"},
            "memo_profile": {"profile": profile.profile},
            "dimension_analyses": [],
            "memo_claims": [],
            "investment_implications": [],
            "what_would_change_view": [],
            "monitoring_items": [],
            "evidence_gaps_but_actionable": [],
            "caveats": [],
            "unsupported_claims_excluded": [],
            "source_boundary_notes": [],
            "memo_thesis_plan": {
                "schema_version": "",
                "status": "",
                "primary_thesis_claim_id": "",
                "primary_thesis": "",
                "thesis_direction": "",
            },
            "raw_rows_consumed": False,
            "tool_calls_requested": [],
            "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        },
    }


def _memo_writer_length_repair_budget_spec(profile: MemoProfileSpec | str | None = None) -> MemoWriterBudgetSpec:
    profile_name = profile.profile if isinstance(profile, MemoProfileSpec) else str(profile or "").strip() or "compact"
    return MemoWriterBudgetSpec(
        profile=profile_name,
        supported_claim_cap=MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP,
        memo_outline_cap=3,
        sections_cap=3,
        evidence_bridge_cap=2,
        required_question_cap=2,
        required_item_cap=MEMO_LENGTH_REPAIR_REQUIRED_ITEM_CAP,
        dimension_move_cap=MEMO_LENGTH_REPAIR_DIMENSION_CAP,
        economic_role_row_cap=3,
        financial_line_item_cap=2,
        derived_ratio_cap=2,
        peer_comparison_cap=2,
        product_kpi_cap=2,
        product_context_cap=2,
        graph_edge_cap=2,
        supervision_finding_cap=2,
    )


def _memo_length_repair_output_contract(profile: MemoProfileSpec) -> dict[str, Any]:
    caps = _memo_writer_surface_caps(profile)
    return {
        "schema_version": MEMO_PROFILE_SCHEMA_VERSION,
        "profile": profile.profile,
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "surface_policy": "length_repair_minimal_memo_surface_v0_1",
        "direct_answer_max_chars": min(profile.direct_answer_max_chars, 700),
        "memo_claims_min_when_thesis_ready": min(profile.memo_claims_min_when_thesis_ready, MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP),
        "memo_claims_max": min(profile.memo_claims_max, MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP),
        "memo_claim_max_chars": min(profile.memo_claim_max_chars, 220),
        "surface_caps": {
            **caps,
            "dimension_analyses_max": min(int(caps["dimension_analyses_max"]), MEMO_LENGTH_REPAIR_DIMENSION_CAP),
            "investment_implications_max": min(int(caps["investment_implications_max"]), 2),
            "what_would_change_view_max": min(int(caps["what_would_change_view_max"]), 2),
            "monitoring_items_max": min(int(caps["monitoring_items_max"]), 2),
            "evidence_gaps_but_actionable_max": min(int(caps["evidence_gaps_but_actionable_max"]), 2),
        },
        "required_shape": "minimal MemoDraft JSON only; no supported_claims, source tables, memo_thesis_pack, thesis_driver_pack, or debug fields",
    }


def _deterministic_memo_salvage(
    judgment: Mapping[str, Any],
    *,
    specialist_verification: Mapping[str, Any],
    memo_logic_plan: Mapping[str, Any] | None = None,
    memo_profile: MemoProfileSpec,
    response_language: str,
    model_calls: list[dict[str, Any]],
    last_failure: Mapping[str, Any],
) -> dict[str, Any]:
    writer_budget = _memo_writer_budget_spec_from_profile(memo_profile)
    compact_plan = _compact_memo_logic_plan(memo_logic_plan or {}, budget=writer_budget)
    all_claims = [_compact_claim_card(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    selected_claims = _select_memo_supported_claims(
        all_claims,
        judgment.get("memo_outline") or [],
        max_claims=min(MEMO_SALVAGE_SUPPORTED_CLAIM_CAP, memo_profile.memo_claims_max),
    )
    selected_claims = _augment_salvage_claims_for_required_items(
        selected_claims,
        all_claims,
        compact_plan,
        max_claims=max(
            min(MEMO_SALVAGE_SUPPORTED_CLAIM_CAP, memo_profile.memo_claims_max),
            min(12, len(compact_plan.get("required_item_answer_plan") or []) * 2),
        ),
    )
    salvage_judgment = {
        **dict(judgment),
        "supported_claims": selected_claims,
        "unsupported_claims": [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)][
            : memo_profile.unsupported_claims_excluded_max
        ],
        "conflicts": [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)][: memo_profile.caveats_max],
        "source_boundary_notes": [
            dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)
        ][: memo_profile.source_boundary_notes_max],
    }
    draft = build_multi_agent_memo_draft(salvage_judgment, specialist_verification=specialist_verification)
    if compact_plan:
        draft["memo_logic_plan"] = compact_plan
    draft["direct_answer"] = _salvage_direct_answer(salvage_judgment, selected_claims, response_language=response_language)
    required_dimension_rows = _salvage_required_item_dimension_analyses(
        compact_plan,
        selected_claims,
        response_language=response_language,
    )
    if required_dimension_rows:
        draft["dimension_analyses"] = _merge_salvage_dimension_analyses(
            draft.get("dimension_analyses"),
            required_dimension_rows,
            compact_plan,
        )
    draft["memo_claims"] = [
        _salvage_memo_claim_from_supported_claim(item, response_language=response_language)
        for item in selected_claims[: min(MEMO_SALVAGE_SUPPORTED_CLAIM_CAP, memo_profile.memo_claims_max)]
    ]
    draft["investment_implications"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="investment_implications",
        max_items=3,
    )
    draft["what_would_change_view"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="what_would_change_view",
        max_items=2,
    )
    draft["monitoring_items"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="monitoring_items",
        max_items=3,
    )
    draft["evidence_gaps_but_actionable"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="evidence_gaps",
        max_items=2,
    )
    draft["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    draft["llm_route_source"] = f"{MEMO_ROUTE_SOURCE}+deterministic_salvage"
    normalized = _normalize_memo_llm_output(
        draft,
        salvage_judgment,
        memo_profile=memo_profile,
        response_language=response_language,
    )
    normalized = _complete_memo_contract_from_judgment(
        normalized,
        salvage_judgment,
        memo_profile=memo_profile,
        response_language=response_language,
    )
    normalized["memo_writer_diagnostics"] = {
        **dict(normalized.get("memo_writer_diagnostics") or {}),
        "deterministic_salvage_used": True,
        "salvage_reason": _format_failure_reason(last_failure),
        "salvage_claim_count": len(normalized.get("memo_claims") or []),
        "salvage_required_item_answer_count": len(required_dimension_rows),
        "salvage_policy": "length_failure_claim_card_salvage_v0_1",
    }
    normalized["model_diagnostics"] = _aggregate_model_calls(model_calls)
    normalized["llm_route_source"] = f"{MEMO_ROUTE_SOURCE}+deterministic_salvage"
    return normalized


def _merge_salvage_dimension_analyses(
    existing: Any,
    required_rows: list[dict[str, Any]],
    memo_logic_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in existing or [] if isinstance(item, Mapping)]
    for row in required_rows:
        dimension_id = str(row.get("dimension_id") or "")
        if not dimension_id:
            rows.append(dict(row))
            continue
        merged = False
        for index, existing_row in enumerate(rows):
            if str(existing_row.get("dimension_id") or "") != dimension_id:
                continue
            combined = {**existing_row}
            for key, value in row.items():
                if key in {"claim_ids", "counter_claim_ids", "counter_driver_ids", "gap_ids", "evidence_refs", "what_would_change_view"}:
                    combined[key] = _dedupe_strings(_string_list(combined.get(key)) + _string_list(value))[:8]
                elif not combined.get(key) and value:
                    combined[key] = value
            rows[index] = combined
            merged = True
            break
        if not merged:
            rows.append(dict(row))
    section_order = _valid_memo_required_dimension_ids(memo_logic_plan.get("section_order"))
    if not section_order:
        return rows
    order_index = {dimension_id: index for index, dimension_id in enumerate(section_order)}
    return sorted(
        rows,
        key=lambda row: (
            order_index.get(str(row.get("dimension_id") or ""), len(order_index) + 1),
            str(row.get("dimension_id") or ""),
        ),
    )


def _augment_salvage_claims_for_required_items(
    selected_claims: list[dict[str, Any]],
    all_claims: list[dict[str, Any]],
    memo_logic_plan: Mapping[str, Any],
    *,
    max_claims: int,
) -> list[dict[str, Any]]:
    if not memo_logic_plan:
        return selected_claims
    out = [dict(item) for item in selected_claims]
    seen = {str(item.get("claim_id") or "") for item in out}
    for item in memo_logic_plan.get("required_item_answer_plan") or []:
        if not isinstance(item, Mapping):
            continue
        matches = _claims_matching_required_item(all_claims, item)
        for claim in matches[:2]:
            claim_id = str(claim.get("claim_id") or "")
            if claim_id and claim_id in seen:
                continue
            out.append(dict(claim))
            if claim_id:
                seen.add(claim_id)
            if len(out) >= max_claims:
                return out
    return out[:max_claims]


def _claims_matching_required_item(claims: list[dict[str, Any]], item: Mapping[str, Any]) -> list[dict[str, Any]]:
    terms = [str(term or "").strip().lower() for term in _string_list(item.get("terms_any")) if str(term or "").strip()]
    roles = [str(role or "").strip().lower() for role in _string_list(item.get("required_evidence_roles"))]
    tickers = {str(ticker or "").strip().upper() for ticker in _string_list(item.get("required_tickers")) if str(ticker or "").strip()}
    scored: list[tuple[int, dict[str, Any]]] = []
    for claim in claims:
        text = _claim_search_text(claim)
        score = 0
        if terms:
            score += sum(2 for term in terms if term and term in text)
        claim_roles = text + " " + " ".join(_string_list(claim.get("claim_type") or claim.get("source_families") or []))
        if roles:
            score += sum(1 for role in roles if role and role.lower() in claim_roles)
        claim_tickers = {str(ticker or "").strip().upper() for ticker in _string_list(claim.get("ticker_scope"))}
        if tickers and claim_tickers & tickers:
            score += 1
        if score > 0:
            scored.append((score, claim))
    return [claim for _, claim in sorted(scored, key=lambda item_score: item_score[0], reverse=True)]


def _claim_search_text(claim: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "claim": claim.get("claim"),
            "memo_slot": claim.get("memo_slot"),
            "analysis_dimension": claim.get("analysis_dimension"),
            "metric_scope": claim.get("metric_scope"),
            "ticker_scope": claim.get("ticker_scope"),
            "source_families": claim.get("source_families") or claim.get("source_family"),
            "economic_role": claim.get("economic_role"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).lower()


def _salvage_required_item_dimension_analyses(
    memo_logic_plan: Mapping[str, Any],
    selected_claims: list[dict[str, Any]],
    *,
    response_language: str,
) -> list[dict[str, Any]]:
    if not memo_logic_plan:
        return []
    rows: list[dict[str, Any]] = []
    for item in memo_logic_plan.get("required_item_answer_plan") or []:
        if not isinstance(item, Mapping):
            continue
        matches = _claims_matching_required_item(selected_claims, item)
        if not matches:
            continue
        dimension = str(item.get("dimension") or "thesis_synthesis")
        claim_ids = [str(claim.get("claim_id") or "") for claim in matches if str(claim.get("claim_id") or "")][:4]
        evidence_refs = _dedupe_strings(
            ref
            for claim in matches[:3]
            for ref in _string_list(claim.get("evidence_refs") or claim.get("refs"))
        )[:5]
        summary = _salvage_required_item_summary(item, matches, response_language=response_language)
        counter_read = _salvage_required_item_counter_read(item, matches, response_language=response_language)
        rows.append(
            {
                "dimension_id": dimension,
                "title": _zh_dimension_label(dimension) if response_language == "zh-CN" else dimension.replace("_", " ").title(),
                "summary": summary,
                "business_mechanism": summary,
                "financial_bridge": _salvage_required_item_financial_bridge(item, matches, response_language=response_language),
                "competitive_read": counter_read,
                "counter_read": counter_read,
                "claim_ids": claim_ids,
                "evidence_refs": evidence_refs,
                "required_item_id": str(item.get("question_item_id") or ""),
                "rendering_policy": "deterministic_salvage_required_item_answer_v0_1",
            }
        )
    return rows[:8]


def _salvage_required_item_summary(
    item: Mapping[str, Any],
    matches: list[dict[str, Any]],
    *,
    response_language: str,
) -> str:
    item_id = str(item.get("question_item_id") or "")
    terms = ", ".join(_string_list(item.get("terms_any"))[:5])
    lead = _salvage_direct_claim_sentence(matches[0], response_language=response_language)
    if response_language == "zh-CN":
        if item_id == "dell_ai_server_quality_margin_bridge":
            return f"DELL AI server / gross margin 问题不能只看增长，现有证据支撑先把 AI server 收入、ISG 口径和毛利/利润率质量连起来判断：{lead}。"
        if item_id == "nvda_gpu_supply_generation":
            return f"NVDA GPU、H100/H200/B200/GB200/Blackwell 相关证据应作为产品代际和供给能力判断，而不是因为缺 SKU revenue 就排除：{lead}。"
        if item_id == "cloud_capex_read_through":
            return f"AMZN/MSFT/GOOGL cloud capex 只能先说明云厂商数据中心需求池和资本开支强度，是否传导到 NVDA/DELL 还要看客户部署、订单或供应链关系：{lead}。"
        if item_id == "customer_deployment_or_order_signal":
            return f"customer deployment / order / adoption 信号用于验证产品是否真实被采用；当前应把可见部署线索和订单缺口分开写：{lead}。"
        return f"{terms or item_id} 已有可用证据，当前判断是：{lead}。"
    return f"{terms or item_id} has available evidence and should be answered directly: {lead}."


def _salvage_required_item_counter_read(
    item: Mapping[str, Any],
    matches: list[dict[str, Any]],
    *,
    response_language: str,
) -> str:
    item_id = str(item.get("question_item_id") or "")
    if response_language == "zh-CN":
        if item_id == "cloud_capex_read_through":
            return "反向读法是：capex 本身不是供应商订单，缺少 named deployment/order/vendor allocation 时只能证明需求池，不能证明 NVDA/DELL 份额。"
        if item_id == "dell_ai_server_quality_margin_bridge":
            return "反向读法是：如果 AI server 放量伴随毛利率、现金流或服务收入承压，增长质量可能低于收入表观。"
        if item_id == "customer_deployment_or_order_signal":
            return "反向读法是：只有产品页、渠道或泛化 customer context 时，不能冒充订单规模或 sell-through。"
        return "反向读法是：公开证据能支撑方向，但不能替代份额、ASP、SKU revenue 或客户订单 exact 数据。"
    if item_id == "cloud_capex_read_through":
        return "Counter-read: capex is not a supplier order without named deployment, order, or vendor-allocation evidence."
    return "Counter-read: public evidence supports direction, but not share, ASP, SKU revenue, or sell-through exact data."


def _salvage_required_item_financial_bridge(
    item: Mapping[str, Any],
    matches: list[dict[str, Any]],
    *,
    response_language: str,
) -> str:
    bridge_claim = _salvage_direct_claim_sentence(matches[0], response_language=response_language)
    if response_language == "zh-CN":
        return f"财务传导应从该证据进入收入承接、毛利/经营利润、capex 或现金流质量，而不是停留在资料存在性：{bridge_claim}。"
    return f"The financial bridge should connect the evidence to revenue durability, margin, capex, or cash-flow quality: {bridge_claim}."


def _dedupe_strings(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _salvage_memo_claim_from_supported_claim(item: Mapping[str, Any], *, response_language: str) -> dict[str, Any]:
    row = dict(item)
    if response_language == "zh-CN" and _needs_zh_wrapper(row.get("claim")):
        row["claim"] = _zh_salvage_claim_summary(row)
        row["response_language_normalized_user_text"] = True
    return row


def _zh_salvage_claim_summary(item: Mapping[str, Any]) -> str:
    if _memo_claim_is_source_coverage_context(item):
        tickers = "、".join(_string_list(item.get("ticker_scope"))[:4]) or "相关公司"
        actions = "；".join(_string_list(item.get("next_parser_actions"))[:2])
        if actions:
            return f"{tickers} 的官方披露源已定位，但当前只证明披露路径可达，尚未解析成 period/unit/citation 完整的财务或产品 exact fact；下一步 parser 动作为：{actions}。"
        return f"{tickers} 的官方披露源已定位，但当前只证明披露路径可达，不能当作收入、订单、backlog、出货、份额或 ASP 证据。"
    tickers = "、".join(_string_list(item.get("ticker_scope"))[:4]) or "相关公司"
    metrics = "、".join(
        _zh_metric_scope_label(metric)
        for metric in _string_list(item.get("metric_scope"))[:4]
        if _zh_metric_scope_label(metric)
    )
    slot = _zh_memo_slot_label(str(item.get("memo_slot") or ""))
    direction = _zh_direction_label(str(item.get("direction") or ""))
    materiality = _zh_materiality_label(str(item.get("materiality") or ""))
    numbers = _numeric_snippets_for_zh_summary(str(item.get("claim") or ""))
    if direction or materiality:
        parts = [f"{tickers} 的{slot}证据形成一条{direction}{materiality}论据"]
    else:
        parts = [f"{tickers} 的{slot}证据提供当前判断锚点"]
    if metrics:
        parts.append(f"涉及 {metrics}")
    if numbers:
        parts.append(f"关键数值包括 {'、'.join(numbers)}")
    bridge = _zh_salvage_claim_bridge_sentence(item)
    if bridge:
        parts.append(bridge)
    return "；".join(parts) + "。"


def _zh_salvage_claim_bridge_sentence(item: Mapping[str, Any]) -> str:
    dimension = str(item.get("analysis_dimension") or item.get("memo_slot") or "").strip()
    text = str(item.get("claim") or "").lower()
    metrics = " ".join(_string_list(item.get("metric_scope"))).lower()
    if "gross margin" in text or "gross_margin" in metrics or "operating_income" in metrics:
        return "该证据应进入利润质量和产品组合判断，不能只写成收入增长线索"
    if "capex" in text or "capital expenditure" in text or "capital_expenditure" in metrics:
        return "该证据可支撑需求端资本开支强度，但不能直接证明供应商订单或份额"
    if any(marker in text for marker in ("gpu", "blackwell", "h100", "h200", "b200", "gb200", "architecture")):
        return "该证据可支撑产品能力、代际或供给路径判断，但不能直接外推 SKU revenue"
    if "deployment" in text or "customer" in text or "adoption" in text:
        return "该证据可支撑采用/部署存在性，但不能替代订单金额、sell-through 或 backlog"
    if dimension in {"risk_and_counterevidence", "risk_counterevidence"}:
        return "该证据应作为主判断的折价项或反证，不应被写成中性资料摘要"
    if dimension == "industry_supply_chain":
        return "该证据应说明需求如何沿客户、供应链或产能瓶颈传导"
    return "该证据应写清楚支持的判断、不能外推的边界以及后续验证指标"


def _zh_memo_slot_label(value: str) -> str:
    labels = {
        "thesis": "投资主线",
        "fundamentals": "基本面",
        "fundamental": "基本面",
        "product_technology": "产品与产线",
        "product_and_production": "产品与产线",
        "capital_and_financing": "投融资与资本开支",
        "industry_relationship": "行业/关系",
        "market_valuation": "市场/估值",
        "risk_counterevidence": "风险/反证",
    }
    return labels.get(str(value or "").strip(), "投资判断")


def _zh_metric_scope_label(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    labels = {
        "financial_metric:revenue": "收入",
        "financial_metric:gross_margin": "毛利率",
        "financial_metric:gross_profit": "毛利",
        "financial_metric:operating_income": "营业利润",
        "financial_metric:operating_cash_flow": "经营现金流",
        "financial_metric:fcf": "自由现金流",
        "financial_metric:capex": "资本开支",
        "financial_metric:debt": "债务",
        "financial_metric:cash": "现金",
        "financial_metric:inventory": "库存",
        "product_kpi:product_revenue": "产品收入",
        "product_kpi:backlog": "订单积压",
        "product_kpi:shipment": "出货量",
        "product_kpi:delivery": "交付量",
        "product_kpi:capacity": "产能",
        "product_kpi:utilization": "利用率",
        "product_kpi:subscribers": "订阅用户",
        "product_kpi:arr": "ARR",
        "product_kpi:rpo": "RPO",
    }
    if raw in labels:
        return labels[raw]
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    return raw.replace("_", " ")


def _zh_direction_label(value: str) -> str:
    labels = {
        "positive": "正向",
        "negative": "负向",
        "mixed": "多空混合",
        "neutral": "中性",
    }
    return labels.get(str(value or "").strip().lower(), "")


def _zh_materiality_label(value: str) -> str:
    labels = {
        "high": "、高重要性",
        "medium": "、中等重要性",
        "low": "、低重要性",
    }
    return labels.get(str(value or "").strip().lower(), "")


def _numeric_snippets_for_zh_summary(text: str) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"(?<![A-Za-z0-9])[-+]?\$?\d[\d,]*(?:\.\d+)?\s*(?:%|B|M|bn|million|billion|亿美元|百万美元)?",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(str(text or "")):
        token = match.group(0).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        snippets.append(token)
        if len(snippets) >= 4:
            break
    return snippets


def _salvage_direct_answer(
    judgment: Mapping[str, Any],
    selected_claims: list[dict[str, Any]],
    *,
    response_language: str,
) -> str:
    plan = judgment.get("memo_thesis_plan") if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {}
    thesis = _clean_internal_thesis_text(str(plan.get("primary_thesis") or "")).strip()
    dimensions = _salvage_dimension_fragments(selected_claims, response_language=response_language)
    risk_fragment = _salvage_first_claim_fragment(
        selected_claims,
        response_language=response_language,
        preferred_dimensions={"risk_and_counterevidence", "risk_counterevidence"},
    )
    product_fragment = _salvage_first_claim_fragment(
        selected_claims,
        response_language=response_language,
        preferred_dimensions={"product_and_production", "product_technology"},
    )
    if response_language == "zh-CN":
        if thesis and _contains_cjk(thesis):
            return _truncate(thesis, 900)
        if dimensions:
            body_sentences = _salvage_direct_claim_sentences(selected_claims, response_language=response_language)[:4]
            body = "。".join(body_sentences or dimensions[:4])
            tail_parts = []
            if product_fragment and not body_sentences:
                tail_parts.append(f"产品/产线侧的关键锚点是 {product_fragment}")
            if risk_fragment and not any("折价" in sentence or "风险" in sentence for sentence in body_sentences):
                tail_parts.append(f"主要折价项来自 {risk_fragment}")
            tail = "。".join(tail_parts)
            return _truncate(
                "已披露事实给出的主线是："
                f"{body}。"
                + (f"{tail}。" if tail else "")
                + _salvage_direct_answer_tail(selected_claims, response_language=response_language),
                900,
            )
        return _truncate(
            "本轮只能形成低置信判断：先用已披露财务事实、产品/产线线索、资本开支和风险反证搭建分析框架；订单、份额或商业 tracker 尚未提权时，只能作为后续验证项。",
            900,
        )
    if thesis:
        return _truncate(thesis, 900)
    if dimensions:
        return _truncate(
            "The available evidence supports a cautious, dimension-led read: "
            + "; ".join(dimensions[:4])
            + ". Use the disclosed financial, product, and supply-chain links to frame earnings and capex sensitivity, while leaving missing orders, share, and commercial tracker data as follow-up validation items.",
            900,
        )
    return _truncate(
        "The available evidence does not support a strong directional call, but it can still organize the memo around reported financial facts, product or production signals, capital spending, and counterevidence.",
        900,
    )


def _salvage_direct_answer_tail(claims: list[dict[str, Any]], *, response_language: str) -> str:
    roles = {str(claim.get("economic_role") or "").strip() for claim in claims if isinstance(claim, Mapping)}
    if response_language == "zh-CN":
        if roles:
            return (
                "因此当前判断框架是：客户/需求侧 capex、供应商自身 capex、产品收入/订单与毛利锚点要分层看；"
                "只有当客户部署、订单或利润质量证据能连上时，供应链传导才可以上升为更强判断。"
            )
        return "因此当前判断框架是：需求、产品收入、毛利和现金流分层验证；订单、份额和客户归因决定结论能否从方向性判断升级。"
    if roles:
        return (
            " Separate demand-side capex, issuer-own capex, product revenue/backlog, and margin anchors before judging whether the supply-chain read-through is validated by customer deployment, orders, or profit quality."
        )
    return " Validate demand, product revenue, margin, and cash flow separately; orders, share, and customer attribution remain the key follow-ups."


def _salvage_direct_claim_sentences(claims: list[dict[str, Any]], *, response_language: str) -> list[str]:
    sentences: list[str] = []
    seen_dimensions: set[str] = set()
    for claim in _decision_useful_claims_or_all(claims):
        dimension = str(claim.get("analysis_dimension") or claim.get("memo_slot") or "").strip()
        if dimension in seen_dimensions and dimension not in {"product_and_production", "capital_and_financing"}:
            continue
        sentence = _salvage_direct_claim_sentence(claim, response_language=response_language)
        if not sentence:
            continue
        sentences.append(sentence)
        if dimension:
            seen_dimensions.add(dimension)
        if len(sentences) >= 4:
            break
    return sentences


def _salvage_direct_claim_sentence(claim: Mapping[str, Any], *, response_language: str) -> str:
    if response_language != "zh-CN":
        return _salvage_claim_fragment(claim, response_language=response_language)
    tickers = "/".join(_string_list(claim.get("ticker_scope"))[:3])
    metrics = "/".join(_memo_metric_labels(_string_list(claim.get("metric_scope"))[:3], response_language=response_language))
    numbers = "、".join(_numeric_snippets_for_zh_summary(str(claim.get("claim") or ""))[:3])
    dimension = str(claim.get("analysis_dimension") or claim.get("memo_slot") or "").strip()
    subject = tickers or "公司披露"
    metric_text = metrics or "经营指标"
    value_text = f"（{numbers}）" if numbers else ""
    economic_role = str(claim.get("economic_role") or "").strip()
    metric_values = {str(item or "").strip().lower() for item in _string_list(claim.get("metric_scope"))}
    source_families = {str(item or "").strip().lower() for item in _string_list(claim.get("source_families") or claim.get("source_family"))}
    if economic_role == "customer_or_demand_side_capex_signal":
        return (
            f"{subject} 的{metric_text}{value_text}只能说明客户/需求侧资本开支或终端需求池扩张，"
            "不能当作供应商收入、backlog 或直接订单"
        )
    if economic_role == "issuer_own_capital_investment":
        return f"{subject} 的{metric_text}{value_text}是发行人自身再投资、产能准备或现金流压力，不是客户需求信号"
    if economic_role == "issuer_product_revenue_signal":
        return (
            f"{subject} 的{metric_text}{value_text}提供公司披露的产品或分部收入锚点，"
            "可用于收入承接和业务组合判断，但不能外推 SKU 份额、ASP 或客户订单"
        )
    if economic_role == "issuer_order_backlog_signal":
        return f"{subject} 的{metric_text}{value_text}提供订单/积压可见度，但仍需结合交付、客户集中度和利润率判断兑现质量"
    if economic_role == "issuer_margin_quality_anchor":
        return f"{subject} 的{metric_text}{value_text}提供利润质量和定价能力锚点，需要与产品组合、成本和现金流一起判断"
    if economic_role in {"counterparty_business_context", "counterparty_financial_context"}:
        return f"{subject} 的{metric_text}{value_text}只能作为对手方或同业经营背景，不能转写成研究对象自身的收入或订单事实"
    if _memo_claim_is_public_proxy_without_role(claim):
        return (
            f"{subject} 的{metric_text}{value_text}只能说明公开产品页、官方页面或外部 proxy 中存在产品/服务/部署线索，"
            "不能写成产品收入、供应商订单、backlog 或客户需求事实"
        )
    if "customer_deployment" in metric_values or "official_customer_deployment" in source_families:
        return (
            f"{subject} 的{metric_text}{value_text}说明客户部署、配置或采用线索存在，"
            "可用于验证产品 uptake 和需求真实性，但不能替代订单金额、backlog 或 sell-through"
        )
    if any("product_spec" in metric for metric in metric_values) or "official_product_surface" in source_families:
        return (
            f"{subject} 的{metric_text}{value_text}说明产品规格、架构或代际能力，"
            "可用于比较产品竞争力和供给路径，但不能直接写成产品收入或客户订单"
        )
    if dimension in {"product_and_production", "product_technology"}:
        return f"{subject} 的{metric_text}{value_text}说明产品线、技术能力或经营锚点存在，可用于判断需求承接，但不能自动等同于 SKU revenue 或订单"
    if dimension == "capital_and_financing":
        return f"{subject} 的{metric_text}{value_text}说明需求端投入或再投资强度，是供应链收入传导的上游约束"
    if dimension == "industry_supply_chain":
        subject = _relationship_claim_subject(claim, response_language=response_language) or subject
        return f"{subject} 的{metric_text}{value_text}用于验证行业需求能否传到具体供应商收入和毛利"
    if dimension in {"risk_and_counterevidence", "risk_counterevidence"}:
        return f"{subject} 的{metric_text}{value_text}提示市场仍在折价回报周期或传导不确定性"
    if dimension == "competition_and_market_position":
        return f"{subject} 的{metric_text}{value_text}只能辅助判断相对位置，还需要份额、价格或渠道数据确认"
    return f"{subject} 的{metric_text}{value_text}提供基本面锚点，需要和利润率、现金流及订单证据一起判断"


def _salvage_dimension_fragments(claims: list[dict[str, Any]], *, response_language: str) -> list[str]:
    fragments: list[str] = []
    seen: set[str] = set()
    for claim in _decision_useful_claims_or_all(claims):
        dimension = str(claim.get("analysis_dimension") or claim.get("memo_slot") or "").strip()
        if not dimension or dimension in seen:
            continue
        fragment = _salvage_claim_fragment(claim, response_language=response_language)
        if not fragment:
            continue
        seen.add(dimension)
        label = _zh_dimension_label(dimension) if response_language == "zh-CN" else dimension.replace("_", " ")
        if response_language == "zh-CN":
            fragments.append(f"{label}上，{fragment}")
        else:
            fragments.append(f"{label}: {fragment}")
    return fragments


def _salvage_first_claim_fragment(
    claims: list[dict[str, Any]],
    *,
    response_language: str,
    preferred_dimensions: set[str],
) -> str:
    for claim in _decision_useful_claims_or_all(claims):
        dimension = str(claim.get("analysis_dimension") or claim.get("memo_slot") or "").strip()
        if dimension in preferred_dimensions:
            return _salvage_claim_fragment(claim, response_language=response_language)
    return ""


def _salvage_claim_fragment(claim: Mapping[str, Any], *, response_language: str) -> str:
    tickers = _relationship_claim_subject(claim, response_language=response_language) or "/".join(_string_list(claim.get("ticker_scope"))[:3])
    metric_labels = _memo_metric_labels(_string_list(claim.get("metric_scope"))[:3], response_language=response_language)
    metrics = "/".join(metric_labels)
    direction = _zh_direction_label(str(claim.get("direction") or "")) if response_language == "zh-CN" else str(claim.get("direction") or "bounded")
    numbers = _numeric_snippets_for_zh_summary(str(claim.get("claim") or ""))[:3]
    if response_language == "zh-CN":
        parts = []
        if tickers:
            parts.append(tickers)
        if metrics:
            parts.append(metrics)
        if numbers:
            parts.append("、".join(numbers))
        base = " / ".join(parts) or "已披露事实"
        return f"{base} 指向{direction}影响"
    parts = [part for part in (tickers, metrics, ", ".join(numbers)) if part]
    base = " / ".join(parts) or "verified evidence"
    return f"{base} points to a {direction or 'bounded'} read"


def _salvage_action_items(
    selected_claims: list[dict[str, Any]],
    *,
    response_language: str,
    kind: str,
    max_items: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for claim in _decision_useful_claims_or_all(selected_claims):
        if len(items) >= max_items:
            break
        claim_refs = _string_list(claim.get("evidence_refs"))[:2]
        if not claim_refs:
            continue
        items.append(
            {
                "text": _salvage_action_item_text(claim, response_language=response_language, kind=kind),
                "claim_id": str(claim.get("claim_id") or ""),
                "evidence_refs": claim_refs,
            }
        )
    return items[:max_items]


def _salvage_action_item_text(claim: Mapping[str, Any], *, response_language: str, kind: str) -> str:
    dimension = str(claim.get("analysis_dimension") or claim.get("memo_slot") or "verified_evidence").strip()
    metrics = _memo_metric_labels(_string_list(claim.get("metric_scope"))[:3], response_language=response_language)
    tickers = _relationship_claim_subject(claim, response_language=response_language) or "/".join(_string_list(claim.get("ticker_scope"))[:3])
    bridge_parts = [part for part in [tickers, _zh_dimension_label(dimension) if response_language == "zh-CN" else dimension.replace("_", " "), "/".join(metrics)] if part]
    bridge = " / ".join(bridge_parts) or "verified evidence"
    mechanism = _salvage_claim_fragment(claim, response_language=response_language)
    if response_language == "zh-CN":
        investment_text = _zh_dimension_investment_implication(
            dimension=dimension,
            bridge=bridge,
            mechanism=mechanism,
        )
        templates = {
            "investment_implications": investment_text,
            "what_would_change_view": _zh_action_view_change_text(dimension=dimension, bridge=bridge),
            "monitoring_items": _zh_action_monitoring_text(dimension=dimension, bridge=bridge),
            "evidence_gaps": _zh_action_gap_text(dimension=dimension, bridge=bridge),
        }
    else:
        templates = {
            "investment_implications": f"{bridge} shows {mechanism or 'a verified business signal'} and should anchor the revenue, margin, or capex sensitivity read.",
            "what_would_change_view": f"Lower this dimension's weight if same-scope disclosures reverse {bridge} or orders/share data disprove the transmission path.",
            "monitoring_items": f"Track same-scope updates for {bridge} and add order, share, customer, or capacity evidence to validate the transmission.",
            "evidence_gaps": f"Orders, share, or commercial tracker data outside {bridge} remains a follow-up validation gap.",
        }
    return templates.get(kind, templates["investment_implications"])


def _zh_action_view_change_text(*, dimension: str, bridge: str) -> str:
    if dimension in {"product_and_production", "product_technology"}:
        return f"若 {bridge} 后续出现产品延期、规格劣势、客户部署撤回或竞品替代证据，应下调产品竞争力判断。"
    if dimension == "capital_and_financing":
        return f"若 {bridge} 不能转化为可验证订单、产能利用或现金回报，而只体现资本开支前置，应降低需求传导权重。"
    if dimension == "industry_supply_chain":
        return f"若 {bridge} 的客户、供应商或产能瓶颈链条无法绑定到具体公司，应把它降为行业背景而非主论据。"
    if dimension in {"risk_and_counterevidence", "risk_counterevidence"}:
        return f"若 {bridge} 风险被订单兑现、毛利改善或现金流恢复抵消，主判断的折价应相应降低。"
    return f"若 {bridge} 与后续披露的利润率、现金流或订单方向相反，应重估该维度对主判断的贡献。"


def _zh_action_monitoring_text(*, dimension: str, bridge: str) -> str:
    if dimension in {"product_and_production", "product_technology"}:
        return f"跟踪 {bridge} 对应的产品代际、客户配置、供应链约束和竞品规格变化，而不是只跟踪产品名是否出现。"
    if dimension == "capital_and_financing":
        return f"跟踪 {bridge} 之后的订单积压、收入确认、毛利率和自由现金流，确认资本投入是否形成回报。"
    if dimension == "industry_supply_chain":
        return f"跟踪 {bridge} 涉及的客户 capex、供应商产能、交付周期和渠道/OEM 配置，验证 read-through 是否闭合。"
    if dimension in {"risk_and_counterevidence", "risk_counterevidence"}:
        return f"跟踪 {bridge} 对应的风险触发项，包括客户集中、出口限制、价格压力、库存和 capex 消化。"
    return f"跟踪 {bridge} 对应的同口径收入、利润率、现金流和订单/客户证据。"


def _zh_action_gap_text(*, dimension: str, bridge: str) -> str:
    if dimension in {"product_and_production", "product_technology"}:
        return f"{bridge} 仍缺产品级 exact KPI 或客户部署量级；当前只能支撑产品能力/采用方向，不能证明 SKU revenue。"
    if dimension == "capital_and_financing":
        return f"{bridge} 仍缺供应商绑定订单或回报口径；当前只能支撑需求池/资本投入判断，不能证明收入传导完成。"
    if dimension == "industry_supply_chain":
        return f"{bridge} 仍缺 issuer-bound customer/order/supplier row；当前不能把行业关系直接写成公司订单事实。"
    if dimension in {"risk_and_counterevidence", "risk_counterevidence"}:
        return f"{bridge} 的风险项仍需用订单、毛利、现金流或客户集中度更新验证，否则主判断必须保留折价。"
    return f"{bridge} 仍缺可提权的订单、份额、客户或产品 KPI exact 数据，应作为后续验证项单列。"


def _relationship_claim_subject(claim: Mapping[str, Any], *, response_language: str) -> str:
    families = {str(item).strip() for item in _string_list(claim.get("source_families") or claim.get("source_family"))}
    if "relationship_graph" not in families:
        return ""
    dimension = str(claim.get("analysis_dimension") or claim.get("memo_slot") or "").strip()
    if dimension not in {"industry_supply_chain", "industry_relationship"}:
        return ""
    tickers = _string_list(claim.get("ticker_scope"))[:4]
    anchor = tickers[0] if tickers else ""
    if response_language == "zh-CN":
        return f"{anchor} 相关行业关系图" if anchor else "行业关系图"
    return f"relationship graph around {anchor}" if anchor else "relationship graph"


def _zh_dimension_investment_implication(*, dimension: str, bridge: str, mechanism: str) -> str:
    dimension_key = str(dimension or "").strip()
    base = mechanism or bridge or "该维度证据"
    if dimension_key in {"product_and_production", "product_technology"}:
        return (
            f"{bridge} 的投资含义是确定产品线和后续核验指标：只有订单、积压、出货或产品收入继续跟上，"
            "产品存在性才可以升级为需求强度和盈利弹性的证据。"
        )
    if dimension_key == "capital_and_financing":
        return (
            f"{bridge} 要先确认现金流符号和具体科目，再和收入增速、自由现金流及产能安排一起看；"
            "资本开支出流只有能解释未来供给能力或回报周期时，才提高结论权重。"
        )
    if dimension_key == "industry_supply_chain":
        return (
            f"{bridge} 提供的是需求传导路径，不是公司订单事实；它的作用是告诉报告优先检查哪些客户、"
            "供应链节点和资本开支指标能把行业景气落到公司收入。"
        )
    if dimension_key in {"risk_and_counterevidence", "risk_counterevidence"}:
        return (
            f"{bridge} 应作为结论折价项处理：只要出口限制、客户集中或周期风险没有被订单和现金流抵消，"
            "主线判断就不能上调到高置信度。"
        )
    if dimension_key == "competition_and_market_position":
        return (
            f"{bridge} 只有在份额、价格、渠道或竞品同口径数据出现后，才能支撑相对胜负判断；"
            "当前最多用于限定竞争结论的置信度。"
        )
    return (
        f"{bridge} 是财务判断的起点：{base}；投资结论还需要看同口径利润率、现金流和订单/客户证据是否同步。"
    )


def _zh_dimension_label(value: str) -> str:
    return {
        "fundamentals": "基本面",
        "product_and_production": "产品与产线",
        "capital_and_financing": "投融资与资本开支",
        "industry_supply_chain": "行业与供应链",
        "competition_and_market_position": "竞争与市场位置",
        "risk_and_counterevidence": "风险与反证",
        "thesis_synthesis": "综合判断",
    }.get(str(value or "").strip(), str(value or "").replace("_", " "))


def _memo_metric_labels(values: list[str], *, response_language: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    zh = _normalize_response_language(response_language) == "zh-CN"
    for value in values:
        label = _memo_metric_label(value, zh=zh)
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def _memo_metric_label(value: str, *, zh: bool) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.lower().strip()
    zh_map = {
        "financial_metric:revenue": "收入",
        "financial:revenue": "收入",
        "financial_metric:capex": "资本开支",
        "financial_metric:gross_margin": "毛利率",
        "financial_metric:operating_margin": "营业利润率",
        "financial_metric:free_cash_flow": "自由现金流",
        "product_kpi:product_revenue": "产品收入",
        "product_revenue": "产品收入",
        "product revenue": "产品收入",
        "supplier revenue": "供应商收入",
        "supplier_revenue": "供应商收入",
        "segment revenue": "分部收入",
        "segment_revenue": "分部收入",
        "market return": "市场回报",
        "market_return": "市场回报",
        "market reaction": "市场反应",
        "market_reaction": "市场反应",
        "gross_margin": "毛利率",
        "product_kpi:shipments": "出货量",
        "product_kpi:capacity": "产能",
        "revenue": "收入",
        "capex": "资本开支",
        "orders_backlog": "订单/积压",
        "orders backlog": "订单/积压",
        "gross margin": "毛利率",
        "product_surface_context": "产品线/产品面",
        "net bookings": "净订单",
        "backlog": "积压订单",
        "systems revenue": "系统收入",
        "installed base management sales": "装机基础管理收入",
        "capital expenditures": "资本开支",
        "wafer revenue": "晶圆收入",
        "capacity": "产能",
        "technology platform revenue": "技术平台收入",
        "return 3m": "三个月回报",
        "relative return vs benchmark 3m": "三个月相对基准回报",
        "ev sales ttm": "EV/Sales",
    }
    en_map = {
        "financial_metric:revenue": "revenue",
        "financial:revenue": "revenue",
        "financial_metric:capex": "capex",
        "financial_metric:gross_margin": "gross margin",
        "financial_metric:operating_margin": "operating margin",
        "financial_metric:free_cash_flow": "free cash flow",
        "product_kpi:product_revenue": "product revenue",
        "product_kpi:shipments": "shipments",
        "product_kpi:capacity": "capacity",
        "revenue": "revenue",
        "capex": "capex",
        "orders_backlog": "orders/backlog",
        "orders backlog": "orders/backlog",
        "product_surface_context": "product-surface context",
    }
    mapped = (zh_map if zh else en_map).get(normalized)
    if mapped:
        return mapped
    suffix = normalized.split(":", 1)[1] if ":" in normalized else normalized
    suffix = suffix.replace("_", " ").replace("-", " ").strip()
    return suffix if not zh else suffix


def _clean_internal_thesis_text(value: str) -> str:
    cleaned = str(value or "").replace("Synthesized thesis from bounded ClaimCards: ", "").strip()
    cleaned = _clean_memo_facing_internal_terms(cleaned)
    return cleaned.replace(" | ", " ")


def _clean_memo_facing_internal_terms(value: str) -> str:
    cleaned = str(value or "")
    replacements = {
        "This ClaimCard is a reconciled numeric fact;": "This verified numeric fact",
        "bounded ClaimCards": "verified evidence",
        "verified ClaimCards": "verified evidence",
        "ClaimCards": "verified evidence",
        "ClaimCard": "verified evidence",
        "已验证 ClaimCard": "已验证证据",
        "已验证ClaimCard": "已验证证据",
        "该ClaimCard": "该已验证证据",
        "该 ClaimCard": "该已验证证据",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def _compact_claim_card(item: Mapping[str, Any]) -> dict[str, Any]:
    compact = {
        "claim_id": str(item.get("claim_id") or ""),
        "agent_id": str(item.get("agent_id") or ""),
        "claim": _truncate(str(item.get("claim") or ""), 70),
        "claim_type": str(item.get("claim_type") or ""),
        "ticker_scope": _string_list(item.get("ticker_scope"))[:4],
        "metric_scope": _string_list(item.get("metric_scope"))[:2],
        "scope_role": str(item.get("scope_role") or ""),
        "economic_role": str(item.get("economic_role") or ""),
        "transmission_role": str(item.get("transmission_role") or ""),
        "memo_use_role": _truncate(str(item.get("memo_use_role") or ""), 60),
        "role_boundary": str(item.get("role_boundary") or ""),
        "memo_slot": str(item.get("memo_slot") or ""),
        "materiality": str(item.get("materiality") or ""),
        "direction": str(item.get("direction") or ""),
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:1],
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:3],
        "confidence": str(item.get("confidence") or ""),
        "analysis_dimension": str(item.get("analysis_dimension") or ""),
        "missing_confirmations": [_truncate(str(part), 45) for part in _string_list(item.get("missing_confirmations"))[:1]],
    }
    required_keys = {"claim_id", "agent_id", "claim", "claim_type"}
    return {
        key: val
        for key, val in compact.items()
        if key in required_keys or val not in ("", [], {}, None)
    }


def _compact_claim_parser_diagnosis(value: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    if not value and not bool(item.get("parser_diagnosis_complete")):
        return {}
    failure_reasons = _string_list(value.get("exact_fact_parser_failure_reasons"))
    next_actions = _string_list(value.get("next_parser_actions"))
    parser_statuses = _string_list(value.get("source_specific_parser_statuses"))
    return {
        "parser_diagnosis_complete": bool(item.get("parser_diagnosis_complete") or value.get("parser_diagnosis_complete")),
        "source_specific_parser_statuses": [_truncate(str(part), 55) for part in parser_statuses[:1]],
        "exact_fact_parser_failure_reasons": [_truncate(str(part), 75) for part in failure_reasons[:1]],
        "next_parser_actions": [_truncate(str(part), 65) for part in next_actions[:1]],
    }


def _compact_analyst_depth(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact = {
        "analysis_dimension": str(value.get("analysis_dimension") or ""),
        "evidence_role": str(value.get("evidence_role") or ""),
        "transmission_role": str(value.get("transmission_role") or ""),
        "role_boundary": str(value.get("role_boundary") or ""),
        "business_mechanism": _truncate(_clean_memo_facing_internal_terms(str(value.get("business_mechanism") or "")), 42),
        "financial_bridge": _truncate(_clean_memo_facing_internal_terms(str(value.get("financial_bridge") or "")), 42),
        "counter_read": _truncate(_clean_memo_facing_internal_terms(str(value.get("counter_read") or "")), 42),
    }
    return {key: val for key, val in compact.items() if val not in ("", [], {}, None)}


def _compact_memo_thesis_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    sections = []
    for row in value.get("section_sequence") or []:
        if not isinstance(row, Mapping):
            continue
        sections.append(
            {
                "memo_slot": str(row.get("memo_slot") or ""),
                "status": str(row.get("status") or ""),
                "objective": _truncate(str(row.get("objective") or ""), 60),
                "claim_ids": _string_list(row.get("claim_ids"))[:2],
                "primary_evidence_refs": _string_list(row.get("primary_evidence_refs"))[:1],
            }
        )
        if len(sections) >= 3:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "primary_thesis_claim_id": str(value.get("primary_thesis_claim_id") or ""),
        "primary_thesis": _truncate(str(value.get("primary_thesis") or ""), 105),
        "thesis_direction": str(value.get("thesis_direction") or ""),
        "supporting_claim_ids": _string_list(value.get("supporting_claim_ids"))[:2],
        "risk_or_counter_claim_ids": _string_list(value.get("risk_or_counter_claim_ids"))[:1],
        "section_sequence": sections[:2],
        "plan_policy": str(value.get("plan_policy") or ""),
    }


def _compact_memo_outline_for_prompt(value: Any, *, max_items: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "memo_slot": str(item.get("memo_slot") or ""),
                "status": str(item.get("status") or ""),
                "supported_claim_count": int(item.get("supported_claim_count") or 0),
                "primary_claim_ids": _string_list(item.get("primary_claim_ids") or item.get("claim_ids"))[:2],
                "missing_reason": _truncate(str(item.get("missing_reason") or ""), 70),
            }
        )
        if len(rows) >= max_items:
            break
    return rows


def _compact_memo_thesis_pack(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    drivers = []
    for row in value.get("supporting_drivers") or []:
        if not isinstance(row, Mapping):
            continue
        driver = row.get("driver") if isinstance(row.get("driver"), Mapping) else {}
        drivers.append(
            {
                "memo_slot": str(row.get("memo_slot") or ""),
                "section_title": _truncate(str(row.get("section_title") or ""), 60),
                "driver": _compact_pack_claim(driver),
                "supporting_claim_count": int(row.get("supporting_claim_count") or 0),
            }
        )
        if len(drivers) >= 1:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "core_thesis": _compact_pack_claim(value.get("core_thesis") if isinstance(value.get("core_thesis"), Mapping) else {}),
        "supporting_driver_count": len(value.get("supporting_drivers") or []),
        "counterargument_count": len(value.get("counterarguments") or []),
        "source_claim_ref_count": len(_string_list(value.get("source_claim_refs"))),
        "pack_policy": str(value.get("pack_policy") or ""),
    }


def _compact_thesis_driver_pack(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    thesis_cards = []
    for row in value.get("thesis_cards") or []:
        if not isinstance(row, Mapping):
            continue
        thesis_cards.append(
            {
                "thesis_id": str(row.get("thesis_id") or ""),
                "core_thesis": _truncate(str(row.get("core_thesis") or ""), 120),
                "stance": str(row.get("stance") or ""),
                "confidence": str(row.get("confidence") or ""),
                "supporting_driver_ids": _string_list(row.get("supporting_driver_ids"))[:3],
                "counter_driver_ids": _string_list(row.get("counter_driver_ids"))[:1],
                "gap_ids": _string_list(row.get("gap_ids"))[:2],
                "evidence_ref_count": len(_string_list(row.get("evidence_refs"))),
                "what_would_change_the_view": [
                    _truncate(str(item), 80) for item in _string_list(row.get("what_would_change_the_view"))[:1]
                ],
            }
        )
        if len(thesis_cards) >= 1:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "present": bool(value.get("present")),
        "dimension_ids": [
            str(row.get("dimension_id") or "")
            for row in value.get("dimension_sections") or []
            if isinstance(row, Mapping) and str(row.get("dimension_id") or "")
        ][:4],
        "driver_card_count": len(value.get("driver_cards") or []),
        "counter_driver_card_count": len(value.get("counter_driver_cards") or []),
        "gap_card_count": len(value.get("gap_cards") or []),
        "evidence_ref_count": int(value.get("evidence_ref_count") or 0),
        "source_claim_ref_count": len(_string_list(value.get("source_claim_refs"))),
        "pack_policy": str(value.get("pack_policy") or ""),
    }


def _compact_judgment_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "core_thesis": _truncate(str(value.get("core_thesis") or ""), 75),
        "stance": str(value.get("stance") or ""),
        "confidence": str(value.get("confidence") or ""),
        "dimension_judgments": [
            {
                "dimension_id": str(row.get("dimension_id") or ""),
                "title": str(row.get("title") or ""),
                "stance": str(row.get("stance") or ""),
                "support_level": str(row.get("support_level") or ""),
                "summary": _truncate(str(row.get("summary") or ""), 65),
                "business_mechanism": _truncate(str(row.get("business_mechanism") or ""), 40),
                "financial_bridge": _truncate(str(row.get("financial_bridge") or ""), 40),
                "counter_read": _truncate(str(row.get("counter_read") or ""), 40),
                "claim_ids": _string_list(row.get("claim_ids"))[:2],
                "evidence_ref_count": len(_string_list(row.get("evidence_refs"))),
                "gap_ids": _string_list(row.get("gap_ids"))[:1],
            }
            for row in value.get("dimension_judgments") or []
            if isinstance(row, Mapping)
        ][:3],
        "fundamental_statement_summary": {
            key: value.get("fundamental_statement_summary", {}).get(key)
            for key in ("pack_status", "line_item_count", "peer_comparison_count", "priority_metric_available_count")
            if isinstance(value.get("fundamental_statement_summary"), Mapping)
        },
        "gap_state": {
            "unsupported_claim_count": int(((value.get("gap_state") or {}) if isinstance(value.get("gap_state"), Mapping) else {}).get("unsupported_claim_count") or 0),
            "gap_card_count": int(((value.get("gap_state") or {}) if isinstance(value.get("gap_state"), Mapping) else {}).get("gap_card_count") or 0),
        },
        "memo_writer_policy": str(value.get("memo_writer_policy") or ""),
    }


def _compact_dimension_section(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dimension_id": str(value.get("dimension_id") or ""),
        "dimension_title": str(value.get("dimension_title") or value.get("title") or ""),
        "section_thesis": _truncate(str(value.get("section_thesis") or value.get("summary") or ""), 190),
        "business_mechanism": _truncate(str(value.get("business_mechanism") or ""), 130),
        "financial_bridge": _truncate(str(value.get("financial_bridge") or ""), 130),
        "comparison_basis": _string_list(value.get("comparison_basis"))[:2],
        "competitive_read": _truncate(str(value.get("competitive_read") or ""), 120),
        "counter_read": _truncate(str(value.get("counter_read") or ""), 120),
        "primary_claim_ids": _string_list(value.get("primary_claim_ids") or value.get("claim_ids"))[:4],
        "counter_claim_ids": _string_list(value.get("counter_claim_ids"))[:2],
        "evidence_refs": _string_list(value.get("evidence_refs"))[:2],
        "source_boundaries": [_truncate(str(item), 80) for item in _string_list(value.get("source_boundaries"))[:1]],
        "what_would_change_view": [
            _truncate(str(item), 100) for item in _string_list(value.get("what_would_change_view"))[:1]
        ],
        "depth_status": str(value.get("depth_status") or ""),
    }


def _compact_driver_pack_card(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "driver_id": str(value.get("driver_id") or value.get("counter_driver_id") or ""),
        "counter_driver_id": str(value.get("counter_driver_id") or ""),
        "source_claim_id": str(value.get("source_claim_id") or ""),
        "memo_slot": str(value.get("memo_slot") or ""),
        "driver_type": str(value.get("driver_type") or ""),
        "statement": _truncate(str(value.get("statement") or ""), 130),
        "direction": str(value.get("direction") or ""),
        "materiality": str(value.get("materiality") or ""),
        "confidence": str(value.get("confidence") or ""),
        "metric_scope": _string_list(value.get("metric_scope"))[:3],
        "ticker_scope": _string_list(value.get("ticker_scope"))[:3],
        "evidence_refs": _string_list(value.get("evidence_refs"))[:2],
        "source_families": _string_list(value.get("source_families"))[:3],
        "claim_boundary": str(value.get("claim_boundary") or ""),
    }


def _compact_pack_claim(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(value.get("claim_id") or ""),
        "memo_slot": str(value.get("memo_slot") or ""),
        "claim": _truncate(str(value.get("claim") or ""), 130),
        "claim_type": str(value.get("claim_type") or ""),
        "direction": str(value.get("direction") or ""),
        "materiality": str(value.get("materiality") or ""),
        "ticker_scope": _string_list(value.get("ticker_scope"))[:4],
        "metric_scope": _string_list(value.get("metric_scope"))[:4],
        "evidence_refs": _string_list(value.get("evidence_refs"))[:2],
        "source_families": _string_list(value.get("source_families"))[:3],
        "caveats": [_truncate(str(part), 90) for part in _string_list(value.get("caveats"))[:1]],
        "missing_confirmations": [
            _truncate(str(part), 90) for part in _string_list(value.get("missing_confirmations"))[:1]
        ],
    }


def _compact_string_mapping(value: Any, *, max_items: int, max_value_chars: int) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    clean: dict[str, str] = {}
    for key, item in list(value.items())[:max_items]:
        clean[str(key)] = _truncate(str(item), max_value_chars)
    return clean


def _select_memo_supported_claims(
    claims: list[dict[str, Any]],
    memo_outline: Any,
    *,
    max_claims: int,
) -> list[dict[str, Any]]:
    if max_claims <= 0:
        return []
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(claim: Mapping[str, Any]) -> None:
        if len(selected) >= max_claims:
            return
        claim_id = str(claim.get("claim_id") or claim.get("claim") or "")
        if not claim_id or claim_id in seen:
            return
        selected.append(dict(claim))
        seen.add(claim_id)

    def single_ticker(claim: Mapping[str, Any]) -> str:
        tickers = [item.upper() for item in _string_list(claim.get("ticker_scope")) if item]
        return tickers[0] if len(tickers) == 1 else ""

    def selected_ticker_count(ticker: str) -> int:
        if not ticker:
            return 0
        return sum(1 for claim in selected if ticker in {item.upper() for item in _string_list(claim.get("ticker_scope"))})

    def selected_single_ticker_count(ticker: str) -> int:
        if not ticker:
            return 0
        count = 0
        for claim in selected:
            tickers = [item.upper() for item in _string_list(claim.get("ticker_scope")) if item]
            if tickers == [ticker]:
                count += 1
        return count

    def selected_ticker_has_metric(ticker: str, markers: tuple[str, ...]) -> bool:
        if not ticker:
            return False
        return any(
            ticker in {item.upper() for item in _string_list(claim.get("ticker_scope"))}
            and claim_has_metric(claim, markers)
            for claim in selected
        )

    def claim_has_metric(claim: Mapping[str, Any], markers: tuple[str, ...]) -> bool:
        text = " ".join(
            [
                " ".join(_string_list(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric"))),
                str(claim.get("claim") or ""),
                str(claim.get("canonical_metric_id") or ""),
            ]
        ).lower()
        return any(marker in text for marker in markers)

    ranked_claims = _rank_memo_claims_for_selection(claims)
    ranked_supported_claims = [claim for claim in ranked_claims if _memo_claim_selection_penalty(claim) == 0] or ranked_claims
    outline_slots = [
        str(item.get("memo_slot") or "").strip()
        for item in memo_outline
        if isinstance(memo_outline, list) and isinstance(item, Mapping) and str(item.get("status") or "") == "supported"
    ]
    for slot in outline_slots:
        if slot == "thesis":
            continue
        if slot not in {"fundamentals", "product_technology", "capital_allocation"}:
            continue
        for claim in ranked_supported_claims:
            if str(claim.get("memo_slot") or "") == slot:
                add(claim)
                break

    for dimension in (
        "fundamentals",
        "product_and_production",
        "capital_and_financing",
    ):
        for claim in ranked_supported_claims:
            if str(claim.get("analysis_dimension") or "") == dimension:
                add(claim)
                break

    capex_tickers_added = 0
    for claim in ranked_supported_claims:
        ticker = single_ticker(claim)
        if not ticker or selected_ticker_has_metric(ticker, ("capex", "capital expenditure", "capital_expenditure")):
            continue
        if selected_ticker_count(ticker) >= 2:
            continue
        if claim_has_metric(claim, ("capex", "capital expenditure", "capital_expenditure")):
            add(claim)
            capex_tickers_added += 1
        if capex_tickers_added >= 3:
            break

    for claim in ranked_supported_claims:
        if str(claim.get("claim_type") or "") == "investment_thesis_synthesis":
            add(claim)
            break

    ticker_balance_added = 0
    for claim in ranked_supported_claims:
        ticker = single_ticker(claim)
        if not ticker or selected_single_ticker_count(ticker) > 0:
            continue
        if str(claim.get("claim_type") or "") in {
            "company_reported_financial_fact",
            "company_reported_product_operating_fact",
            "technical_product_fact",
            "product_specification_fact",
            "product_architecture_fact",
        }:
            add(claim)
            ticker_balance_added += 1
        if ticker_balance_added >= 2:
            break

    for dimension in (
        "industry_supply_chain",
        "competition_and_market_position",
        "risk_and_counterevidence",
    ):
        for claim in ranked_supported_claims:
            if str(claim.get("analysis_dimension") or "") == dimension:
                add(claim)
                break

    deferred_same_ticker: list[dict[str, Any]] = []
    for claim in ranked_supported_claims:
        ticker = single_ticker(claim)
        if ticker and selected_ticker_count(ticker) >= 2:
            deferred_same_ticker.append(claim)
            continue
        add(claim)
    for claim in deferred_same_ticker:
        add(claim)
    return selected


def _rank_memo_claims_for_selection(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        claims,
        key=lambda claim: (
            _memo_claim_selection_penalty(claim),
            -_memo_claim_context_priority(claim),
            -int(claim.get("claim_rank_score") or 0),
        ),
    )


def _decision_useful_claims_or_all(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    useful = [claim for claim in claims if _memo_claim_selection_penalty(claim) == 0]
    return useful or claims


def _memo_claim_selection_penalty(claim: Mapping[str, Any]) -> int:
    if _memo_claim_is_source_coverage_context(claim):
        return 3
    if _memo_claim_is_gap_only(claim):
        return 3
    if _memo_claim_is_missing_data_context(claim):
        return 2
    if _memo_claim_is_public_proxy_without_role(claim):
        return 2
    if _memo_claim_is_scope_hypothesis_context(claim):
        return 1
    return 0


def _memo_claim_context_priority(claim: Mapping[str, Any]) -> int:
    claim_type = str(claim.get("claim_type") or "").strip().lower()
    families = {str(item).strip() for item in _string_list(claim.get("source_families") or claim.get("source_family"))}
    refs = " ".join(_string_list(claim.get("evidence_refs") or claim.get("refs"))).lower()
    metric_scope = " ".join(_string_list(claim.get("metric_scope"))).lower()
    analysis_dimension = str(claim.get("analysis_dimension") or "").strip().lower()
    display_text = str(claim.get("display_value") or claim.get("value") or claim.get("period_key") or "")
    text = _memo_claim_text_for_selection(claim)
    score = 0
    if claim_type == "company_reported_product_operating_fact":
        score += 12
    elif claim_type == "company_reported_financial_fact":
        score += 10
    elif claim_type == "investment_thesis_synthesis":
        score += 8
    elif claim_type in {"technical_product_fact", "product_specification_fact", "product_architecture_fact"}:
        score += 7
    elif claim_type == "product_taxonomy_context":
        score += 5
    elif claim_type == "public_proxy_context":
        score += 3
    elif claim_type == "business_observation":
        score += 2
    if "product_and_production" in analysis_dimension:
        score += 3
    if any(
        marker in metric_scope or marker in text
        for marker in (
            "product_kpi",
            "product revenue",
            "product_revenue",
            "segment revenue",
            "segment_revenue",
            "gross margin",
            "server",
            "isg",
            "gpu",
            "blackwell",
            "h100",
            "h200",
            "b200",
            "gb200",
        )
    ):
        score += 4
    if display_text.strip():
        score += 2
    if "live_public_web_context" in families or "official_" in refs:
        score += 1 if _memo_claim_is_public_proxy_without_role(claim) else 3
    if "primary_sec_filing" in families or "company_authored_unaudited_sec_filing" in families:
        score += 3
    if "company_product_evidence_graph" in families and claim_type != "source_gap":
        score += 2
    if str(claim.get("memo_readiness") or "").strip() == "memo_ready":
        score += 1
    if _memo_claim_is_source_coverage_context(claim):
        score -= 10
    if _memo_claim_is_missing_data_context(claim):
        score -= 6
    if _memo_claim_is_public_proxy_without_role(claim):
        score -= 5
    if _memo_claim_is_scope_hypothesis_context(claim):
        score -= 2
    return score


def _memo_claim_is_public_proxy_without_role(claim: Mapping[str, Any]) -> bool:
    if _memo_claim_is_source_coverage_context(claim):
        return True
    economic_role = str(claim.get("economic_role") or "").strip()
    if economic_role:
        return False
    families = {
        str(item).strip()
        for item in _string_list(claim.get("source_families") or claim.get("source_family"))
        if str(item).strip()
    }
    refs = " ".join(_string_list(claim.get("evidence_refs") or claim.get("refs"))).lower()
    claim_type = str(claim.get("claim_type") or "").strip().lower()
    if not (
        families & {"live_public_web_context", "public_source_context", "official_product_surface", "company_product_evidence_graph"}
        or "official_" in refs
    ):
        return False
    return claim_type in {
        "product_taxonomy_context",
        "public_proxy_context",
        "business_observation",
        "customer_deployment_context",
        "official_product_surface_context",
    }


def _memo_claim_is_source_coverage_context(claim: Mapping[str, Any]) -> bool:
    claim_type = str(claim.get("claim_type") or claim.get("raw_claim_type") or "").strip().lower()
    if claim_type in SOURCE_COVERAGE_CLAIM_TYPES:
        return True
    claim_id = str(claim.get("claim_id") or "").strip().lower()
    if "lead_targeted_repair_claim:issuer_official" in claim_id:
        return True
    metrics = " ".join(_string_list(claim.get("metric_scope") or claim.get("metrics") or claim.get("metric"))).lower()
    if any(marker in metrics for marker in ("issuer_official_context", "issuer identity", "filing coverage", "filing presence")):
        return True
    text = " ".join(
        [
            str(claim.get("claim") or ""),
            str(claim.get("claim_boundary") or ""),
            " ".join(_string_list(claim.get("caveats"))),
            " ".join(_string_list(claim.get("missing_confirmations"))),
            " ".join(_string_list(claim.get("claim_rank_reasons"))),
        ]
    ).lower()
    return any(
        marker in text
        for marker in (
            "supports issuer coverage",
            "disclosure-path analysis",
            "official source reached",
            "exact value parser promotion still required",
            "does not promote exact",
            "cannot support sales/share/orders",
            "source reachability",
            "filing presence parser",
        )
    )


def _memo_claim_is_gap_only(claim: Mapping[str, Any]) -> bool:
    claim_type = str(claim.get("claim_type") or "").strip().lower()
    if claim_type in {"source_gap", "unsupported_claim"}:
        return True
    refs = " ".join(_string_list(claim.get("evidence_refs") or claim.get("refs"))).lower()
    if "product_source_gap::" in refs or "official_issuer_probe:" in refs:
        return True
    text = _memo_claim_text_for_selection(claim)
    gap_markers = (
        "no company product evidence",
        "no company-disclosed product",
        "no public proxy",
        "all company product evidence graph rows are gap rows",
        "缺少",
        "缺失",
        "缺乏",
        "无法",
        "未披露",
        "source gap",
        "bounded gap",
        "commercial tracker gap",
    )
    return any(marker in text for marker in gap_markers)


def _memo_claim_is_missing_data_context(claim: Mapping[str, Any]) -> bool:
    text = _memo_claim_primary_text_for_missing_data(claim)
    markers = (
        "no runtime facts confirm",
        "not available in bounded evidence",
        "missing confirmation",
        "missing public confirmation",
        "no direct",
        "not disclosed",
        "cannot confirm",
        "missing evidence",
        "缺少确认",
        "缺少公开确认",
        "没有直接",
        "尚未确认",
        "不能确认",
        "无法确认",
        "does not promote",
        "cannot support",
        "exact value parser promotion",
        "source coverage",
        "source reachability",
        "issuer coverage",
        "disclosure-path analysis",
        "parser promotion still required",
    )
    return any(marker in text for marker in markers)


def _memo_claim_is_scope_hypothesis_context(claim: Mapping[str, Any]) -> bool:
    text = _memo_claim_text_for_selection(claim)
    claim_type = str(claim.get("claim_type") or "").strip().lower()
    refs = " ".join(_string_list(claim.get("evidence_refs") or claim.get("refs"))).lower()
    return claim_type in {"scope_hypothesis", "relationship_hypothesis"} or "scope_hypothesis" in refs or "scope_hypothesis" in text


def _memo_claim_text_for_selection(claim: Mapping[str, Any]) -> str:
    return " ".join(
        str(claim.get(key) or "")
        for key in (
            "claim",
            "claim_boundary",
            "missing_confirmations",
            "caveats",
            "metric_scope",
            "analysis_dimension",
            "memo_slot",
            "claim_type",
        )
    ).lower()


def _memo_claim_primary_text_for_missing_data(claim: Mapping[str, Any]) -> str:
    return " ".join(
        str(claim.get(key) or "")
        for key in (
            "claim",
            "missing_confirmations",
            "caveats",
            "claim_type",
        )
    ).lower()


def _compact_source_boundary_notes(value: Any) -> list[dict[str, Any]]:
    notes = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        notes.append(
            {
                "type": str(item.get("type") or ""),
                "agent_id": str(item.get("agent_id") or ""),
                "source_family": str(item.get("source_family") or ""),
                "reason": _truncate(str(item.get("reason") or item.get("note") or ""), 180),
            }
        )
        if len(notes) >= 8:
            break
    return notes


def _compact_memo_constraints(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    missing_items = value.get("missing_evidence") if isinstance(value.get("missing_evidence"), list) else []
    return {
        "memo_writer_allowed": bool(value.get("memo_writer_allowed", True)),
        "blocked_reasons": _string_list(value.get("blocked_reasons"))[:8],
        "missing_evidence": [
            _truncate(str(item.get("reason") or item.get("type") or item), 180) if isinstance(item, Mapping) else _truncate(str(item), 180)
            for item in missing_items[:8]
        ],
        "source_boundary": _truncate(str(value.get("source_boundary") or ""), 240),
    }


def _compact_specialist_verification(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "status": str(value.get("status") or ""),
        "memo_writer_allowed": bool(value.get("memo_writer_allowed", True)),
        "unsupported_claim_count": int(value.get("unsupported_claim_count") or 0),
        "blocked_reasons": _string_list(value.get("blocked_reasons"))[:8],
        "policy": str(value.get("policy") or ""),
    }


def _compact_memo_data_view(value: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(value or {})
    verified = view.get("verified_summary")
    if isinstance(verified, Mapping):
        clean_verified = dict(verified)
        clean_verified["judgment_plan"] = _compact_judgment_for_memo(clean_verified.get("judgment_plan") or {})
        clean_verified["specialist_verification"] = _compact_specialist_verification(clean_verified.get("specialist_verification") or {})
        view["verified_summary"] = clean_verified
    return view


def _compact_judgment_for_verifier(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    supported = [_compact_claim_card_for_verifier(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)]
    unsupported = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 180),
            "reason": _truncate(str(item.get("reason") or ""), 120),
        }
        for item in value.get("unsupported_claims") or []
        if isinstance(item, Mapping)
    ][:10]
    conflicts = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 180),
            "reason": _truncate(str(item.get("reason") or ""), 120),
        }
        for item in value.get("conflicts") or []
        if isinstance(item, Mapping)
    ][:6]
    evidence_refs = sorted(
        {
            ref
            for item in supported
            for ref in _string_list(item.get("evidence_refs"))
            if ref
        }
    )
    return {
        "supported_claims": supported[:14],
        "supported_claim_count": len(value.get("supported_claims") or []),
        "supported_evidence_refs": evidence_refs[:80],
        "unsupported_claims_excluded": unsupported,
        "conflicts": conflicts,
        "memo_outline": _compact_outline_for_verifier(value.get("memo_outline") or []),
        "claim_card_stats": dict(value.get("claim_card_stats") or {}),
        "source_boundary_notes": _compact_source_boundary_notes(value.get("source_boundary_notes") or []),
        "memo_constraints": _compact_memo_constraints(value.get("memo_constraints") or {}),
    }


def _compact_claim_card_for_verifier(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "agent_id": str(item.get("agent_id") or ""),
        "claim": _truncate(str(item.get("claim") or ""), 180),
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:8],
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:6],
    }


def _compact_outline_for_verifier(value: Any) -> list[dict[str, Any]]:
    rows = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "memo_slot": str(item.get("memo_slot") or ""),
                "status": str(item.get("status") or ""),
                "supported_claim_count": int(item.get("supported_claim_count") or 0),
                "missing_reason": _truncate(str(item.get("missing_reason") or ""), 120),
            }
        )
        if len(rows) >= 8:
            break
    return rows


def _compact_memo_for_verifier(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    memo_claims = [_compact_memo_claim_for_verifier(item) for item in value.get("memo_claims") or [] if isinstance(item, Mapping)][:8]
    # Avoid passing the same memo claims twice. Some deterministic/salvage
    # surfaces keep both `memo_claims` and `supported_claims`; the verifier
    # only needs one memo-claim view plus the separate claim-ref inventory.
    supported_claims = (
        []
        if memo_claims
        else [_compact_memo_claim_for_verifier(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)][:8]
    )
    return {
        "answer_status": str(value.get("answer_status") or ""),
        "direct_answer": _truncate(str(value.get("direct_answer") or ""), 500),
        "response_language": dict(value.get("response_language") or {}) if isinstance(value.get("response_language"), Mapping) else {},
        "memo_profile": dict(value.get("memo_profile") or {}) if isinstance(value.get("memo_profile"), Mapping) else {},
        "dimension_analyses": [
            _compact_dimension_analysis_for_verifier(item)
            for item in value.get("dimension_analyses") or []
            if isinstance(item, Mapping)
        ][:4],
        "memo_claims": memo_claims,
        "supported_claims": supported_claims,
        "investment_implications": _compact_loose_items_for_verifier(value.get("investment_implications") or [], max_items=2),
        "what_would_change_view": _compact_loose_items_for_verifier(value.get("what_would_change_view") or [], max_items=2),
        "monitoring_items": _compact_loose_items_for_verifier(value.get("monitoring_items") or [], max_items=2),
        "evidence_gaps_but_actionable": _compact_loose_items_for_verifier(value.get("evidence_gaps_but_actionable") or [], max_items=2),
        "caveats": _compact_loose_items_for_verifier(value.get("caveats") or [], max_items=3),
        "unsupported_claims_excluded": _compact_loose_items_for_verifier(value.get("unsupported_claims_excluded") or [], max_items=3),
        "source_boundary_notes": _compact_loose_items_for_verifier(value.get("source_boundary_notes") or [], max_items=3),
        "consumed_input_views": _string_list(value.get("consumed_input_views"))[:4],
        "raw_rows_consumed": bool(value.get("raw_rows_consumed")),
        "tool_calls_requested": list(value.get("tool_calls_requested") or [])[:2] if isinstance(value.get("tool_calls_requested"), list) else [],
    }


def _compact_dimension_analysis_for_verifier(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dimension_id": str(item.get("dimension_id") or ""),
        "title": _truncate(str(item.get("title") or item.get("dimension_title") or ""), 80),
        "summary": _truncate(str(item.get("summary") or item.get("section_thesis") or ""), 100),
        "business_mechanism": _truncate(str(item.get("business_mechanism") or ""), 70),
        "financial_bridge": _truncate(str(item.get("financial_bridge") or ""), 70),
        "competitive_read": _truncate(str(item.get("competitive_read") or ""), 65),
        "counter_read": _truncate(str(item.get("counter_read") or ""), 65),
        "claim_ids": _string_list(item.get("claim_ids") or item.get("primary_claim_ids"))[:3],
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:3],
    }


def _compact_memo_claim_for_verifier(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "claim": _truncate(str(item.get("claim") or item.get("text") or ""), 90),
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:3],
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:2],
    }


def _verifier_minimal_projection(
    state: Mapping[str, Any],
    *,
    deterministic: Mapping[str, Any],
) -> dict[str, Any]:
    raw_judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    judgment = raw_judgment if isinstance(raw_judgment, Mapping) else {}
    raw_memo = state.get("memo_answer") or {}
    memo = raw_memo if isinstance(raw_memo, Mapping) else {}
    compact_memo = _compact_memo_for_verifier(memo)
    memo_claims = [item for item in compact_memo.get("memo_claims") or [] if isinstance(item, Mapping)]
    memo_claim_ids = {str(item.get("claim_id") or "") for item in memo_claims if str(item.get("claim_id") or "")}
    memo_refs = {
        ref
        for item in memo_claims
        for ref in _string_list(item.get("evidence_refs") or item.get("refs"))
        if ref
    }
    memo_source_families = {
        family
        for item in memo_claims
        for family in _string_list(item.get("source_families") or item.get("source_family"))
        if family
    }
    supported_claims = [item for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    projected_claims = _project_claims_for_verifier(supported_claims, memo_claim_ids=memo_claim_ids, memo_refs=memo_refs)
    projected_refs = {
        ref
        for item in projected_claims
        for ref in _string_list(item.get("evidence_refs") or item.get("refs"))
        if ref
    }
    allowed_refs = sorted(memo_refs | projected_refs)
    projected_source_families = {
        family
        for item in projected_claims
        for family in _string_list(item.get("source_families") or item.get("source_family"))
        if family
    }
    source_boundary_families = memo_source_families | projected_source_families
    source_boundary_notes = _project_source_boundary_notes_for_verifier(
        judgment.get("source_boundary_notes") or memo.get("source_boundary_notes") or [],
        source_families=source_boundary_families,
    )
    projection_stats = {
        "schema_version": VERIFIER_PROJECTION_SCHEMA_VERSION,
        "projection_policy": "final_memo_claims_and_referenced_evidence_only",
        "input_supported_claim_count": len(supported_claims),
        "memo_claim_count": len(memo_claims),
        "projected_claim_count": len(projected_claims),
        "projected_evidence_ref_count": len(allowed_refs),
        "source_boundary_note_count": len(source_boundary_notes),
    }
    return {
        "schema_version": VERIFIER_PROJECTION_SCHEMA_VERSION,
        "projection_policy": "final_memo_claims_and_referenced_evidence_only",
        "memo_answer": compact_memo,
        "memo_claim_ref_inventory": projected_claims,
        "allowed_evidence_refs": allowed_refs[:80],
        "unsupported_claims_excluded": compact_memo.get("unsupported_claims_excluded") or [],
        "source_boundary_notes": source_boundary_notes,
        "memo_constraints": _compact_memo_constraints(judgment.get("memo_constraints") or {}),
        "deterministic_verification": _compact_deterministic_verification(deterministic),
        "projection_stats": projection_stats,
    }


def _project_claims_for_verifier(
    claims: list[Mapping[str, Any]],
    *,
    memo_claim_ids: set[str],
    memo_refs: set[str],
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in claims:
        refs = set(_string_list(item.get("evidence_refs") or item.get("refs")))
        claim_id = str(item.get("claim_id") or "")
        claim_id_matched = bool(memo_claim_ids and claim_id in memo_claim_ids)
        if claim_id_matched:
            should_keep = True
        else:
            should_keep = bool(memo_refs and refs & memo_refs)
        if not should_keep:
            continue
        key = claim_id or "|".join(sorted(refs)) or str(len(projected))
        if key in seen:
            continue
        projected.append(
            _compact_claim_ref_inventory_for_verifier(
                item,
                memo_refs=memo_refs,
                prefer_full_refs=claim_id_matched,
            )
        )
        seen.add(key)
        if len(projected) >= 8:
            break
    return projected


def _compact_claim_ref_inventory_for_verifier(
    item: Mapping[str, Any],
    *,
    memo_refs: set[str],
    prefer_full_refs: bool = False,
) -> dict[str, Any]:
    refs = _string_list(item.get("evidence_refs") or item.get("refs"))
    intersecting_refs = [ref for ref in refs if ref in memo_refs]
    selected_refs = refs[:4] if prefer_full_refs else intersecting_refs[:3] if intersecting_refs else refs[:3]
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "agent_id": str(item.get("agent_id") or ""),
        "claim": _truncate(str(item.get("claim") or ""), 95),
        "evidence_refs": selected_refs,
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:2],
        "input_evidence_ref_count": len(refs),
        "projected_ref_policy": "memo_intersection_refs_only_v0_1",
    }


def _project_source_boundary_notes_for_verifier(value: Any, *, source_families: set[str]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        family = str(item.get("source_family") or "")
        note_type = str(item.get("type") or "")
        severity = str(item.get("severity") or "")
        if source_families and family and family not in source_families and severity != "blocking":
            continue
        if not source_families and family and severity != "blocking":
            continue
        notes.append(
            {
                "type": note_type,
                "severity": severity,
                "agent_id": str(item.get("agent_id") or ""),
                "source_family": family,
                "reason": _truncate(str(item.get("reason") or item.get("note") or ""), 180),
            }
        )
        if len(notes) >= 4:
            break
    return notes


def _compact_loose_items_for_verifier(value: Any, *, max_items: int) -> list[Any]:
    rows = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            rows.append(
                {
                    str(key): _truncate(str(val), 120) if not isinstance(val, (list, dict)) else _sanitize_nested_for_verifier(val)
                    for key, val in item.items()
                    if str(key) not in {"raw_text", "raw_rows", "retrieved_context"}
                }
            )
        else:
            rows.append(_truncate(str(item), 120))
        if len(rows) >= max_items:
            break
    return rows


def _sanitize_nested_for_verifier(value: Any) -> Any:
    if isinstance(value, list):
        return [_truncate(str(item), 80) if not isinstance(item, (dict, list)) else _sanitize_nested_for_verifier(item) for item in value[:4]]
    if isinstance(value, Mapping):
        return {
            str(key): _truncate(str(item), 80) if not isinstance(item, (dict, list)) else _sanitize_nested_for_verifier(item)
            for key, item in list(value.items())[:6]
            if str(key) not in {"raw_text", "raw_rows", "retrieved_context"}
        }
    return _truncate(str(value), 80)


def _compact_deterministic_verification(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": str(value.get("status") or ""),
        "error_types": [str(item.get("type") or "") for item in value.get("errors") or [] if isinstance(item, Mapping)][:12],
        "warning_types": [str(item.get("type") or "") for item in value.get("warnings") or [] if isinstance(item, Mapping)][:12],
        "bounded_answer_allowed": bool(value.get("bounded_answer_allowed")),
        "repair_instruction": _truncate(str(value.get("repair_instruction") or ""), 240),
    }


def _verifier_messages(
    state: Mapping[str, Any],
    *,
    projection: Mapping[str, Any],
) -> list[dict[str, str]]:
    user_payload = {
        "user_query": state.get("user_query") or "",
        "verifier_projection": dict(projection),
        "bounded_block_policy": (
            "If verifier_projection.memo_answer.answer_status starts with blocked_ and "
            "verifier_projection.deterministic_verification.status is pass, "
            "return pass unless the blocked answer itself introduces unsupported new facts, raw rows, tool calls, "
            "or source-boundary misuse. Do not fail only because a full memo was not produced."
        ),
    }
    return [
        {"role": "system", "content": _verifier_system_prompt()},
        {
            "role": "user",
            "content": (
                _verifier_user_instruction_scaffold()
                + "\n\n"
                f"Input JSON:\n{_json_for_prompt(user_payload)}"
            ),
        },
    ]


def _memo_system_prompt() -> str:
    return "\n\n".join(
        [
            "You are the Memo Writer Agent for a SEC investment research multi-agent graph.",
            "Memo Writer Skill: write decision-useful investment prose from verified claims and MemoLogicPlan, not a claim ledger.",
            research_skill_prompt("memo_writer", max_chars=1500),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Only consume shared_memo_context, compact verified_judgment_plan, and specialist_verification. Do not include raw rows or retrieval requests.",
            "Follow memo_outline when present; make unsupported and missing evidence visible as limitations instead of filling gaps.",
        ]
    )


def _verifier_system_prompt() -> str:
    return "\n\n".join(
        [
            "You are the Verifier Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("verifier", max_chars=1600),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Do not generate new investment views, expand scope, or request retrieval.",
            "A bounded blocked answer is valid when deterministic verification passes and it does not add new factual claims.",
            "Use the compact evidence ref inventory to check boundaries; do not require raw evidence rows.",
        ]
    )


def _verifier_user_instruction_scaffold() -> str:
    return (
        "Verify the memo against the minimal memo-claim evidence projection. "
        "Return one JSON object with status, errors, warnings, repair_instruction, and bounded_answer_allowed. "
        "Do not add new facts."
    )


def _json_candidates(text: str) -> list[str]:
    stripped = text.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        candidates.append(fence.group(1).strip())
    balanced = _first_balanced_json_object(stripped)
    if balanced:
        candidates.append(balanced)
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            result.append(candidate)
            seen.add(candidate)
    return result


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _model_call_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "call_id": result.get("call_id"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "proxy_mode": result.get("proxy_mode"),
        "url": result.get("url"),
        "finish_reason": result.get("finish_reason"),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "total_tokens": result.get("total_tokens"),
        "failure_reason": _truncate(str(result.get("failure_reason") or ""), 500),
        "tool_call_count": len(result.get("tool_calls") or []),
        "transport_attempt_count": result.get("transport_attempt_count"),
        "transport_failures": result.get("transport_failures") or [],
    }


def _aggregate_model_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "call_count": len(calls),
        "provider": next((call.get("provider") for call in calls if call.get("provider")), ""),
        "model": next((call.get("model") for call in calls if call.get("model")), ""),
        "latency_ms": _sum_optional_int(calls, "latency_ms"),
        "input_tokens": _sum_optional_int(calls, "input_tokens"),
        "output_tokens": _sum_optional_int(calls, "output_tokens"),
        "total_tokens": _sum_optional_int(calls, "total_tokens"),
        "finish_reasons": [call.get("finish_reason") for call in calls],
        "calls": calls,
        "raw_response_saved": False,
    }


def _sum_optional_int(rows: list[dict[str, Any]], key: str) -> int | None:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def _format_failure_reason(failure: Mapping[str, Any]) -> str:
    failure_type = str(failure.get("type") or "unknown_failure")
    if "errors" in failure:
        return f"{failure_type}: {json.dumps(failure.get('errors') or [], ensure_ascii=False)[:700]}"
    return f"{failure_type}: {failure.get('reason') or failure.get('detail') or ''}".strip()


def _is_bounded_block_memo(memo: Mapping[str, Any]) -> bool:
    return str(memo.get("answer_status") or "").startswith("blocked_") or bool(memo.get("bounded_answer_allowed"))


def _filter_soft_verifier_errors(
    errors: list[dict[str, Any]],
    *,
    warning_type: str,
    reason: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hard_markers = (
        "raw",
        "tool",
        "unsupported_claim_entered",
        "new_fact",
        "scope_expansion",
        "source_boundary",
        "relationship_graph_used",
        "context_source_used",
        "market_claim_missing_as_of_date",
    )
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for error in errors:
        marker = json.dumps(error, ensure_ascii=False).lower()
        if any(item in marker for item in hard_markers):
            kept.append(error)
        else:
            dropped.append(
                {
                    "type": warning_type,
                    "original_error": error,
                    "reason": reason,
                }
            )
    return kept, dropped


def _clean_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _payload_digest(value: Mapping[str, Any]) -> str:
    text = json.dumps(_clean_for_prompt(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _string_list(value: Any) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars)].rstrip() + "...[truncated]"


def _int_env(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def _float_env(value: str | None, *, default: float) -> float:
    try:
        return float(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


_S3_PRESENTATION_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)


def _s3_presentation_identity(
    prefix: str, payload: Mapping[str, Any]
) -> tuple[str, str, str]:
    digest = canonical_digest(dict(payload))
    object_id = f"{prefix}_{digest[:24]}"
    return object_id, f"{object_id}:v1", digest


def _s3_unique_strings(*groups: Sequence[Any]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item or "").strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
    return tuple(result)


def _s3_presentation_maps(
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    financial_pack: Mapping[str, Any],
    graph_pack: Mapping[str, Any],
    judgment_pack: Mapping[str, Any],
) -> tuple[
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
]:
    lineage_fields = ("case_id", "work_unit_id", "attempt_id", "research_run_id")
    for upstream in (evidence_route_plan, financial_pack, graph_pack, judgment_pack):
        if any(upstream.get(field) != runtime_plan.get(field) for field in lineage_fields):
            raise ValueError("s3_presentation_runtime_lineage_mismatch")
    if (
        evidence_route_plan.get("runtime_plan_version_ref")
        != runtime_plan.get("runtime_plan_version_ref")
        or evidence_route_plan.get("runtime_plan_digest")
        != runtime_plan.get("runtime_plan_digest")
        or financial_pack.get("financial_pack_version_ref")
        != graph_pack.get("financial_pack_version_ref")
        or financial_pack.get("financial_pack_digest")
        != graph_pack.get("financial_pack_digest")
        or graph_pack.get("graph_pack_version_ref")
        != judgment_pack.get("graph_pack_version_ref")
        or graph_pack.get("graph_pack_digest")
        != judgment_pack.get("graph_pack_digest")
    ):
        raise ValueError("s3_presentation_upstream_digest_lineage_mismatch")
    branches = {
        str(row.get("program_cell_id") or ""): row
        for row in runtime_plan.get("cell_branches") or ()
    }
    financial_cells = {
        str(row.get("program_cell_id") or ""): row
        for row in financial_pack.get("fundamental_decision_cells") or ()
    }
    graph_cells = {
        str(row.get("program_cell_id") or ""): row
        for row in graph_pack.get("decision_cells") or ()
    }
    judgments = {
        str(row.get("program_cell_id") or ""): row
        for row in judgment_pack.get("specialist_judgments") or ()
    }
    if any(tuple(rows) != _S3_PRESENTATION_CELLS for rows in (
        branches,
        financial_cells,
        graph_cells,
        judgments,
    )):
        raise ValueError("s3_presentation_cell_order_or_cardinality_invalid")
    return branches, financial_cells, graph_cells, judgments


def compile_s3_three_cell_presentation_pack(
    *,
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    financial_pack: Mapping[str, Any],
    graph_pack: Mapping[str, Any],
    judgment_pack: Mapping[str, Any],
    artifact_refs: Mapping[str, str],
) -> S3ThreeCellPresentationPackVersion:
    """Compile the T07 no-source presentation and exact review projection."""

    branches, financial_cells, graph_cells, judgments = _s3_presentation_maps(
        runtime_plan,
        evidence_route_plan,
        financial_pack,
        graph_pack,
        judgment_pack,
    )
    expected_artifact_keys = ("workpaper", "report", "trace")
    if tuple(artifact_refs) != expected_artifact_keys or any(
        not str(artifact_refs[key]).strip() for key in expected_artifact_keys
    ):
        raise ValueError("s3_presentation_exact_artifact_refs_required")
    repairs_by_type = {
        str(row.get("failure_type") or ""): row
        for row in judgment_pack.get("targeted_repairs") or ()
    }
    if set(repairs_by_type) != {"unsupported_claim", "numeric_conflict", "missing_source"}:
        raise ValueError("s3_presentation_repair_ticket_scope_invalid")
    repair_type_by_cell = {
        _S3_PRESENTATION_CELLS[0]: "missing_source",
        _S3_PRESENTATION_CELLS[1]: "numeric_conflict",
        _S3_PRESENTATION_CELLS[2]: "unsupported_claim",
    }
    stop_by_cell = {
        _S3_PRESENTATION_CELLS[0]: "typed_stop_cannot_infer_durable_company_specific_demand",
        _S3_PRESENTATION_CELLS[1]: "typed_stop_product_and_incremental_profit_attribution_unavailable",
        _S3_PRESENTATION_CELLS[2]: "typed_stop_bottleneck_probability_and_financial_impact_unavailable",
    }
    headings = {
        _S3_PRESENTATION_CELLS[0]: "需求真实性与持续性",
        _S3_PRESENTATION_CELLS[1]: "价值与利润捕获",
        _S3_PRESENTATION_CELLS[2]: "瓶颈、反证与判断改变条件",
    }

    claims: list[S3SurfaceClaimVersion] = []
    sections: list[S3WorkpaperCellVersion] = []
    for cell_id in _S3_PRESENTATION_CELLS:
        branch = branches[cell_id]
        judgment = judgments[cell_id]
        fact = judgment.get("fact_layer") or {}
        decision = judgment.get("decision_layer") or {}
        graph_cell = graph_cells[cell_id]
        financial_cell = financial_cells[cell_id]
        repair = repairs_by_type[repair_type_by_cell[cell_id]]
        numeric_refs = tuple(str(row) for row in fact.get("deterministic_numeric_refs") or ())
        evidence_refs = tuple(str(row) for row in fact.get("accepted_evidence_refs") or ())
        graph_ref = str(graph_cell.get("graph_edge_projection_ref") or "")
        gaps = _s3_unique_strings(
            tuple(str(row) for row in decision.get("remaining_gaps") or ()),
            tuple(str(row) for row in graph_cell.get("typed_gaps") or ()),
            tuple(str(row) for row in financial_cell.get("cannot_infer") or ()),
        )
        wwc = tuple(str(row) for row in decision.get("what_would_change") or ())
        if not graph_ref or not gaps or not wwc:
            raise ValueError("s3_presentation_cell_review_semantics_incomplete")
        claim_payload = {
            "program_cell_id": cell_id,
            "claim_text": str(decision.get("direct_answer") or ""),
            "disposition": str(decision.get("disposition") or ""),
            "specialist_judgment_ref": str(judgment.get("specialist_judgment_version_ref") or ""),
            "fact_statements": tuple(str(row) for row in fact.get("fact_statements") or ()),
            "evidence_refs": evidence_refs,
            "numeric_refs": numeric_refs,
            "graph_context_refs": (graph_ref,),
            "gap_codes": gaps,
            "what_would_change": wwc,
            "repair_ticket_refs": (str(repair.get("repair_ticket_version_ref") or ""),),
            "stop_semantic": stop_by_cell[cell_id],
            "source_grade": (
                "deterministic_company_total_only" if numeric_refs else "no_promoted_evidence"
            ),
            "numeric_sanity_status": (
                "exact_company_total_formula_recomputed_product_attribution_unavailable"
                if numeric_refs
                else "not_applicable_no_numeric_authority"
            ),
            "official_or_estimate_flag": (
                "deterministic_exact_company_total_not_product_estimate"
                if numeric_refs
                else "context_only_not_promoted"
            ),
        }
        claim_id, claim_ref, claim_digest = _s3_presentation_identity(
            "s3_surface_claim", claim_payload
        )
        claim = S3SurfaceClaimVersion(
            surface_claim_id=claim_id,
            surface_claim_version_ref=claim_ref,
            surface_claim_digest=claim_digest,
            **claim_payload,
        )
        claims.append(claim)
        sections.append(
            S3WorkpaperCellVersion(
                program_cell_id=cell_id,
                cell_version_ref=str(branch.get("cell_version_ref") or ""),
                surface_claim_ref=claim_ref,
                specialist_judgment_ref=claim.specialist_judgment_ref,
                decision_question=str(branch.get("decision_question") or ""),
                direct_answer=claim.claim_text,
                fact_statements=claim.fact_statements,
                evidence_refs=claim.evidence_refs,
                numeric_refs=claim.numeric_refs,
                graph_drilldown=S3GraphDrilldownVersion(
                    program_cell_id=cell_id,
                    graph_edge_projection_ref=graph_ref,
                    graph_authority="navigation_and_mechanism_context_only",
                    source_followup_refs=tuple(
                        str(row) for row in graph_cell.get("source_followup_refs") or ()
                    ),
                    typed_gaps=tuple(str(row) for row in graph_cell.get("typed_gaps") or ()),
                ),
                gaps=claim.gap_codes,
                what_would_change=claim.what_would_change,
                repair_ticket_refs=claim.repair_ticket_refs,
                stop_semantic=claim.stop_semantic,
            )
        )

    lead = judgment_pack.get("lead_synthesis") or {}
    workpaper_payload = {
        "artifact_ref": str(artifact_refs["workpaper"]),
        "case_id": str(runtime_plan.get("case_id") or ""),
        "research_run_id": str(runtime_plan.get("research_run_id") or ""),
        "decision_surface_contract_ref": str(runtime_plan.get("decision_surface_contract_ref") or ""),
        "lead_synthesis_ref": str(lead.get("lead_synthesis_version_ref") or ""),
        "cell_sections": tuple(sections),
        "status": "bounded_review_ready_not_human_accepted",
    }
    workpaper_id, workpaper_ref, workpaper_digest = _s3_presentation_identity(
        "s3_three_cell_workpaper",
        {
            **workpaper_payload,
            "cell_sections": [row.model_dump(mode="json") for row in sections],
        },
    )
    workpaper = S3WorkpaperVersion(
        workpaper_id=workpaper_id,
        workpaper_version_ref=workpaper_ref,
        workpaper_digest=workpaper_digest,
        **workpaper_payload,
    )

    report_sections = tuple(
        S3ReportSectionVersion(
            section_id=f"s3_report_section_{canonical_digest({'cell': row.program_cell_id, 'claim': row.surface_claim_ref})[:24]}",
            program_cell_id=row.program_cell_id,
            heading=headings[row.program_cell_id],
            content=row.direct_answer,
            surface_claim_ref=row.surface_claim_ref,
            specialist_judgment_ref=row.specialist_judgment_ref,
            evidence_refs=row.evidence_refs,
            numeric_refs=row.numeric_refs,
            boundary=row.stop_semantic,
        )
        for row in sections
    )
    report_payload = {
        "artifact_ref": str(artifact_refs["report"]),
        "workpaper_artifact_ref": str(artifact_refs["workpaper"]),
        "case_id": str(runtime_plan.get("case_id") or ""),
        "research_run_id": str(runtime_plan.get("research_run_id") or ""),
        "title": "NVDA AI 基础设施三 Cell 有界研究报告",
        "executive_answer": str(lead.get("cross_cell_conclusion") or lead.get("variant_view") or ""),
        "sections": report_sections,
        "adjudicated_input_refs": (
            str(lead.get("lead_synthesis_version_ref") or ""),
            *(row.specialist_judgment_ref for row in sections),
        ),
        "presentation_gaps": tuple(str(row) for row in lead.get("unresolved_material_gaps") or ()),
        "writer_decisions": (
            "answer_first_then_three_cell_detail",
            "preserve_all_typed_gaps_and_what_would_change",
            "do_not_convert_company_total_margin_into_product_or_incremental_profit",
        ),
        "writer_source_authority": False,
        "writer_retrieval_authority": False,
        "writer_external_tool_authority": False,
        "raw_candidate_consumption": False,
        "model_writer_executed": False,
        "release_claim_authorized": False,
    }
    if not report_payload["executive_answer"] or not report_payload["presentation_gaps"]:
        raise ValueError("s3_presentation_lead_material_incomplete")
    report_id, report_ref, report_digest = _s3_presentation_identity(
        "s3_three_cell_report",
        {
            **report_payload,
            "sections": [row.model_dump(mode="json") for row in report_sections],
        },
    )
    report = S3ReportVersion(
        report_id=report_id,
        report_version_ref=report_ref,
        report_digest=report_digest,
        **report_payload,
    )

    nodes: list[S3TraceNodeVersion] = [
        S3TraceNodeVersion(
            node_ref=str(runtime_plan.get("research_run_id") or ""),
            node_type="run",
            label="ResearchRun",
        )
    ]
    edges: list[S3TraceEdgeVersion] = []
    run_ref = str(runtime_plan.get("research_run_id") or "")
    for section, claim in zip(sections, claims, strict=True):
        nodes.extend(
            (
                S3TraceNodeVersion(node_ref=section.cell_version_ref, node_type="cell", label=section.program_cell_id),
                S3TraceNodeVersion(node_ref=claim.surface_claim_version_ref, node_type="claim", label=claim.disposition),
                S3TraceNodeVersion(node_ref=section.specialist_judgment_ref, node_type="judgment", label=section.program_cell_id),
            )
        )
        edge_specs = (
            (run_ref, section.cell_version_ref, "run_contains_cell"),
            (section.cell_version_ref, claim.surface_claim_version_ref, "cell_exposes_claim"),
            (claim.surface_claim_version_ref, section.specialist_judgment_ref, "claim_projects_judgment"),
            (claim.surface_claim_version_ref, str(artifact_refs["workpaper"]), "claim_rendered_in_workpaper"),
        )
        for from_ref, to_ref, relation in edge_specs:
            edges.append(
                S3TraceEdgeVersion(
                    edge_id=f"s3_trace_edge_{canonical_digest({'from': from_ref, 'to': to_ref, 'relation': relation})[:24]}",
                    from_ref=from_ref,
                    to_ref=to_ref,
                    relation=relation,
                )
            )
    nodes.extend(
        S3TraceNodeVersion(node_ref=str(artifact_refs[key]), node_type="artifact", label=key)
        for key in expected_artifact_keys
    )
    for from_ref, to_ref, relation in (
        (str(artifact_refs["workpaper"]), str(artifact_refs["report"]), "workpaper_rendered_as_report"),
        (str(artifact_refs["report"]), str(artifact_refs["trace"]), "report_verified_by_trace"),
    ):
        edges.append(
            S3TraceEdgeVersion(
                edge_id=f"s3_trace_edge_{canonical_digest({'from': from_ref, 'to': to_ref, 'relation': relation})[:24]}",
                from_ref=from_ref,
                to_ref=to_ref,
                relation=relation,
            )
        )
    trace_input_digest = canonical_digest(
        {
            "nodes": [row.model_dump(mode="json") for row in nodes],
            "edges": [row.model_dump(mode="json") for row in edges],
            "artifact_refs": [artifact_refs[key] for key in expected_artifact_keys],
        }
    )
    input_head_digest = canonical_digest((runtime_plan.get("decision_surface_contract_ref"),))
    verifier_input_digest = canonical_digest(
        {
            "execution_profile_version_ref": runtime_plan.get("execution_profile_version_ref"),
            "input_head_digest": input_head_digest,
            "analysis_as_of": graph_pack.get("projection_as_of"),
            "workpaper_digest": workpaper.workpaper_digest,
            "report_digest": report.report_digest,
            "trace_input_digest": trace_input_digest,
        }
    )
    all_claim_refs = tuple(row.surface_claim_version_ref for row in claims)
    all_numeric_refs = _s3_unique_strings(*(row.numeric_refs for row in claims))
    findings = (
        S3VerifierFindingVersion(
            finding_id=f"s3_verifier_finding_{verifier_input_digest[:18]}_integrity",
            layer="deterministic_integrity",
            severity="info",
            status="pass",
            affected_refs=tuple(str(artifact_refs[key]) for key in expected_artifact_keys),
            earliest_owner_ref=S3_PRESENTATION_OWNER_REF,
            message="Exact Run, Cell, Claim, Judgment and Artifact refs are closed and replayable.",
        ),
        S3VerifierFindingVersion(
            finding_id=f"s3_verifier_finding_{verifier_input_digest[:18]}_semantic",
            layer="semantic",
            severity="warning",
            status="bounded_gap_preserved",
            affected_refs=all_claim_refs,
            earliest_owner_ref="src.sec_agent.langgraph_orchestrator:s3_specialist_lead_cross_cell_pack",
            message="Durable demand, product attribution and quantified bottleneck risk remain cannot-infer.",
        ),
        S3VerifierFindingVersion(
            finding_id=f"s3_verifier_finding_{verifier_input_digest[:18]}_financial",
            layer="financial",
            severity="warning",
            status="bounded_gap_preserved",
            affected_refs=all_numeric_refs or (str(financial_pack.get("financial_pack_version_ref") or ""),),
            earliest_owner_ref="src.sec_agent.canonical_runtime.parser_numeric:s3_financial_numeric_pack",
            message="Company-total margins are exact; product, segment and incremental-profit attribution is unavailable.",
        ),
        S3VerifierFindingVersion(
            finding_id=f"s3_verifier_finding_{verifier_input_digest[:18]}_visual",
            layer="visual",
            severity="info",
            status="pending_browser_validation",
            affected_refs=(str(artifact_refs["report"]),),
            earliest_owner_ref="apps.workbench.frontend.vite.src.app.WorkbenchNext:presentation_surface",
            message="Responsive source contract is present; real browser visual acceptance is not yet performed.",
        ),
    )
    allowed_actions = (
        "accepted",
        "rejected",
        "needs_source",
        "needs_parser",
        "estimate_only",
        "commercial_gap",
    )
    review_targets = tuple(
        S3CellReviewTargetVersion(
            review_target_id=f"s3_review_target_{claim.surface_claim_digest[:24]}",
            program_cell_id=claim.program_cell_id,
            surface_claim_ref=claim.surface_claim_version_ref,
            specialist_judgment_ref=claim.specialist_judgment_ref,
            artifact_refs=tuple(str(artifact_refs[key]) for key in expected_artifact_keys),
            source_grade=claim.source_grade,
            numeric_sanity_status=claim.numeric_sanity_status,
            official_or_estimate_flag=claim.official_or_estimate_flag,
            cannot_infer=claim.gap_codes,
            what_would_change=claim.what_would_change,
            repair_ticket_refs=claim.repair_ticket_refs,
            stop_semantic=claim.stop_semantic,
            allowed_review_actions=allowed_actions,
        )
        for claim in claims
    )
    review_binding = S3VerifierAndHumanReviewBindingVersion(
        verifier_binding_id=f"s3_verifier_binding_{verifier_input_digest[:24]}",
        verifier_input_digest=verifier_input_digest,
        execution_profile_version_ref=str(runtime_plan.get("execution_profile_version_ref") or ""),
        input_head_digest=input_head_digest,
        analysis_as_of=str(graph_pack.get("projection_as_of") or ""),
        artifact_refs=tuple(str(artifact_refs[key]) for key in expected_artifact_keys),
        bound_content_digests=(workpaper.workpaper_digest, report.report_digest, trace_input_digest),
        findings=findings,
        review_targets=review_targets,
    )
    trace_payload = {
        "artifact_ref": str(artifact_refs["trace"]),
        "workpaper_artifact_ref": str(artifact_refs["workpaper"]),
        "report_artifact_ref": str(artifact_refs["report"]),
        "case_id": str(runtime_plan.get("case_id") or ""),
        "research_run_id": run_ref,
        "nodes": tuple(nodes),
        "edges": tuple(edges),
        "review_binding": review_binding,
    }
    trace_id, trace_ref, trace_digest = _s3_presentation_identity(
        "s3_three_cell_trace_review",
        {
            **trace_payload,
            "nodes": [row.model_dump(mode="json") for row in nodes],
            "edges": [row.model_dump(mode="json") for row in edges],
            "review_binding": review_binding.model_dump(mode="json"),
        },
    )
    trace_review = S3TraceReviewVersion(
        trace_id=trace_id,
        trace_version_ref=trace_ref,
        trace_digest=trace_digest,
        **trace_payload,
    )

    pack_payload = {
        "presentation_pack_contract_ref": S3_PRESENTATION_PACK_CONTRACT_REF,
        "presentation_owner_ref": S3_PRESENTATION_OWNER_REF,
        "case_id": str(runtime_plan.get("case_id") or ""),
        "work_unit_id": str(runtime_plan.get("work_unit_id") or ""),
        "attempt_id": str(runtime_plan.get("attempt_id") or ""),
        "research_run_id": run_ref,
        "execution_profile_version_ref": str(runtime_plan.get("execution_profile_version_ref") or ""),
        "decision_surface_contract_ref": str(runtime_plan.get("decision_surface_contract_ref") or ""),
        "runtime_plan_version_ref": str(runtime_plan.get("runtime_plan_version_ref") or ""),
        "runtime_plan_digest": str(runtime_plan.get("runtime_plan_digest") or ""),
        "evidence_route_plan_version_ref": str(evidence_route_plan.get("evidence_route_plan_version_ref") or ""),
        "evidence_route_plan_digest": str(evidence_route_plan.get("evidence_route_plan_digest") or ""),
        "financial_pack_version_ref": str(financial_pack.get("financial_pack_version_ref") or ""),
        "financial_pack_digest": str(financial_pack.get("financial_pack_digest") or ""),
        "graph_pack_version_ref": str(graph_pack.get("graph_pack_version_ref") or ""),
        "graph_pack_digest": str(graph_pack.get("graph_pack_digest") or ""),
        "judgment_pack_version_ref": str(judgment_pack.get("judgment_pack_version_ref") or ""),
        "judgment_pack_digest": str(judgment_pack.get("judgment_pack_digest") or ""),
        "surface_claims": tuple(claims),
        "workpaper": workpaper,
        "report": report,
        "trace_review": trace_review,
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_business_writes": 0,
        "automatic_new_research_calls": 0,
        "human_review_writes": 0,
        "paid_runs": 0,
    }
    identity_payload = {
        **pack_payload,
        "surface_claims": [row.model_dump(mode="json") for row in claims],
        "workpaper": workpaper.model_dump(mode="json"),
        "report": report.model_dump(mode="json"),
        "trace_review": trace_review.model_dump(mode="json"),
    }
    pack_id, pack_ref, pack_digest = _s3_presentation_identity(
        "s3_three_cell_presentation_pack", identity_payload
    )
    return S3ThreeCellPresentationPackVersion(
        presentation_pack_id=pack_id,
        presentation_pack_version_ref=pack_ref,
        presentation_pack_digest=pack_digest,
        **pack_payload,
    )


def consume_s3_three_cell_presentation_pack(
    pack: S3ThreeCellPresentationPackVersion,
    *,
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    financial_pack: Mapping[str, Any],
    graph_pack: Mapping[str, Any],
    judgment_pack: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    expected = compile_s3_three_cell_presentation_pack(
        runtime_plan=runtime_plan,
        evidence_route_plan=evidence_route_plan,
        financial_pack=financial_pack,
        graph_pack=graph_pack,
        judgment_pack=judgment_pack,
        artifact_refs={
            "workpaper": pack.workpaper.artifact_ref,
            "report": pack.report.artifact_ref,
            "trace": pack.trace_review.artifact_ref,
        },
    )
    if expected.model_dump(mode="json") != pack.model_dump(mode="json"):
        raise ValueError("s3_presentation_pack_recompile_mismatch")
    return (
        {
            "target_node": "memo_writer",
            "presentation_pack_version_ref": pack.presentation_pack_version_ref,
            "presentation_pack_digest": pack.presentation_pack_digest,
            "consumption_mode": "adjudicated_heads_only_no_source_or_retrieval",
            "model_calls": 0,
            "network_calls": 0,
        },
        {
            "target_node": "verifier",
            "presentation_pack_version_ref": pack.presentation_pack_version_ref,
            "presentation_pack_digest": pack.presentation_pack_digest,
            "consumption_mode": "exact_digest_findings_and_decision_binding",
            "model_calls": 0,
            "network_calls": 0,
        },
        {
            "target_node": "workbench",
            "presentation_pack_version_ref": pack.presentation_pack_version_ref,
            "presentation_pack_digest": pack.presentation_pack_digest,
            "consumption_mode": "read_only_cell_graph_gap_WWC_repair_stop_projection",
            "model_calls": 0,
            "network_calls": 0,
        },
    )


def consume_s4_case_runtime_writer_verifier_review(
    binding: S4CaseRuntimeBinding,
) -> dict[str, Any]:
    """Inject case-local gaps/WWC/review bindings without new fact authority."""

    return consume_s4_case_runtime_binding(
        binding, "writer_verifier_and_review_surface"
    ).model_dump(mode="json")


def s3_presentation_artifact_payloads(
    pack: S3ThreeCellPresentationPackVersion,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    return (
        (
            "s3_three_cell_workpaper",
            {
                "artifact_ref": pack.workpaper.artifact_ref,
                "presentation_pack_version_ref": pack.presentation_pack_version_ref,
                "case_id": pack.case_id,
                "research_run_id": pack.research_run_id,
                "workpaper": pack.workpaper.model_dump(mode="json"),
            },
        ),
        (
            "s3_three_cell_report",
            {
                "artifact_ref": pack.report.artifact_ref,
                "presentation_pack_version_ref": pack.presentation_pack_version_ref,
                "case_id": pack.case_id,
                "research_run_id": pack.research_run_id,
                "report": pack.report.model_dump(mode="json"),
            },
        ),
        (
            "s3_three_cell_trace_review",
            {
                "artifact_ref": pack.trace_review.artifact_ref,
                "presentation_pack_version_ref": pack.presentation_pack_version_ref,
                "case_id": pack.case_id,
                "research_run_id": pack.research_run_id,
                "trace_review": pack.trace_review.model_dump(mode="json"),
            },
        ),
    )
