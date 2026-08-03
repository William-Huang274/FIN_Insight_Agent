from __future__ import annotations

from copy import deepcopy
import json
import os
import re
from typing import Any, Callable, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field

from sec_agent.canonical_runtime.failure_observation_policy import (
    registered_failure_observation,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    S4CaseRuntimeBinding,
    S4CaseRuntimeResearchProfileOverlay,
    S4_SOURCE_GROUNDED_INPUT_CONTRACT_REF,
    S4SourceGroundedInputPack,
    S4_RUNTIME_CONSUMER_IDS,
    apply_s4_case_runtime_research_profile_overlay,
    assert_s4_case_runtime_research_profile_overlay,
    assert_s4_consumer_injection,
    consume_s4_case_runtime_binding,
    load_s4_case_runtime_binding,
)

from .bounded_agent_contract_policies import (
    BoundedResearchProfile,
    CaseDeliveryIdentityPolicy,
    CaseNumericAuthorityPolicy,
    CaseNumericAuthorityViolation,
    ClaimFactLinkPolicy,
    ClaimScopeResolver,
    EpistemicStatePolicy,
    FactSupportAuthorityPolicy,
    NarrativeQualityPolicy,
    S3_CLAIM_FACT_LINK_POLICY_REF,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
    S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY,
    S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY,
    S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
    SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REFS,
    SpecialistLocalAssemblyCapacity,
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
    S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
    S4_CASE_DELIVERY_IDENTITY_POLICY_REF,
    S4_CASE_DELIVERY_IDENTITY_POLICY_REFS,
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS,
    S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF,
    S4FinalArtifactSafetyViolation,
    S4_NON_AUTHORITATIVE_NARRATIVE_SHELL_REF,
    S4_OPENAI_STRUCTURED_OUTPUTS_SUBSET_COMPILER_REF,
    S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF,
    S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
    S4_STRICT_TRUTH_KERNEL_POLICY_REF,
    StrictTruthKernelPolicy,
    StrictTruthKernelViolation,
    SpecialistWWCJudgmentAtomPolicy,
    TaskClaimLinkPolicy,
    WhatWouldChangeAuthorityPolicy,
    bounded_research_profile_contract_payload,
    compile_profile_aware_artifact_lineage_contract,
    estimate_provider_input_tokens,
    research_profile_for_ref,
    research_lead_transport_contract,
    research_lead_transport_refs,
    specialist_local_assembly_capacity,
    specialist_transport_contract,
    specialist_transport_refs,
)
from .deterministic_judgment_atom_contract import (
    DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS,
    S3_LOCAL_DETERMINISTIC_FACT_INTERACTION_CONTRACT_REF,
    DeterministicJudgmentAtomCompiledContract,
)
from .fact_candidate_pool_planner import FactCandidatePoolPlannerError
from .fin_0_1_2_runtime_contract_binding import (
    FIN_0_1_2_COMMON_RUNTIME_BINDING_REF,
    FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    Fin012RuntimeContractBindingError,
    load_fin_0_1_2_runtime_contract_binding,
)
from .fin_0_1_2_s3_runtime_contract_binding import (
    FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_REF,
    FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    load_fin_0_1_2_s3_runtime_contract_binding,
)
from .bounded_agent_identity_policies import (
    CellScopedResearchIdentityPolicy,
    CellScopedResearchRef,
    CompactScopedReferenceAliasTable,
    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
    ScopedIdentityViolation,
)
from .case_service import CasePrincipal
from .local_research_service import P36LocalResearchService


BOUNDED_AGENT_PROFILE_REF = "fin01.execution_profile.bounded_agent_internal:v1"
BOUNDED_AGENT_WORKER_REF = "fin01.runtime.bounded_agent_internal.v1"
S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF = (
    "fin01.execution_profile.bounded_agent_internal_three_cell:v1"
)
S3_THREE_CELL_BOUNDED_AGENT_WORKER_REF = (
    "fin01.runtime.bounded_agent_internal_three_cell.v1"
)
S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF = (
    "fin01.s3.bounded_agent_three_cell_input:v1"
)
S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF = (
    "fin01.s3.bounded_agent_three_cell_output:v1"
)
S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF = (
    "fin01.s3.bounded_agent_three_cell_output:v2"
)
S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF = (
    "fin01.s3.bounded_agent_three_cell_output:v3"
)
S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF = (
    "fin01.s3.bounded_agent_three_cell_output:v4"
)
S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF = (
    "fin01.bounded_agent.post_provider_failure_envelope:v1"
)
S3_TYPED_VERIFIER_OUTPUT_CONTRACT_REFS = frozenset(
    {
        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    }
)
S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF = (
    "fin01.s3.owner_grade_verifier_output_state_machine:v2"
)
S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF = (
    "fin01.s3.provider_output_capture.assistant_final_text_only:v1"
)
S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF = (
    "fin01.runtime.provider_interaction_audit_capture:v2"
)
PROVIDER_OUTPUT_CAPTURE_POLICY_REFS = (
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
)
S3_OWNER_GRADE_CLAIM_CARD_CONTRACT_REF = "fin01.s3.owner_grade_claim_card:v1"
S3_ACTIONABLE_WHAT_WOULD_CHANGE_CONTRACT_REF = (
    "fin01.s3.actionable_what_would_change:v1"
)
S3_OWNER_GRADE_CLAIM_STATUSES = (
    "fact_supported",
    "bounded_inference",
    "hypothesis",
    "cannot_infer",
)
S3_OWNER_GRADE_BUSINESS_SCOPE_KINDS = (
    "company_total",
    "segment",
    "product",
    "value_chain",
    "unknown",
)
S3_OWNER_GRADE_ATTRIBUTION_LEVELS = (
    "company_total",
    "segment",
    "product",
    "cross_chain",
    "none",
)
S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF = "fin01.s3.specialist_model_view:v1"
S3_SPECIALIST_V2_MAX_FACTS = 3
S3_SPECIALIST_V2_NARRATIVE_CARDINALITY = {
    "explanation_layer": (1, 3),
    "judgment_layer": (1, 2),
    "remaining_gaps": (1, 4),
    "what_would_change": (1, 3),
}
S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.maximum_narrative_characters
)
S3_SPECIALIST_V2_MAX_SERIALIZED_UTF8_BYTES = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.specialist_segment_max_utf8_bytes
)
# Historical whole-output transports remain bound to 6000 bytes. The v5
# segmented transport has a separate, bounded assembly envelope because three
# independently valid segments do not otherwise close under that old limit.
S3_OWNER_GRADE_SEGMENTED_V5_MAX_ASSEMBLED_UTF8_BYTES = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.specialist_assembly_max_utf8_bytes
)
S3_V2_STAGE_OUTPUT_TOKEN_BUDGETS = {
    "specialist": 2200,
    "lead": 1200,
    "writer": 1400,
    "verifier": 1000,
}
S3_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET = 10200
S3_THREE_CELL_DEEPSEEK_SEGMENTED_TRANSPORT_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_node_json_object:v1"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v1"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v2"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v3"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v4"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v5"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v6"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v7"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v8"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V9_REF = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v9"
)
S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS = (
    specialist_transport_refs()
)
S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS = (
    "facts_explanation_and_terminal",
    "owner_grade_claim_cards",
    "actionable_what_would_change_tasks",
)
S3_OWNER_GRADE_SPECIALIST_SEGMENT_TOKEN_BUDGETS = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.segment_token_budgets
)
S3_OWNER_GRADE_SEGMENTED_STAGE_OUTPUT_TOKEN_BUDGETS = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.stage_token_budgets(
        expanded_lead=False
    )
)
S3_OWNER_GRADE_SEGMENTED_AGGREGATE_OUTPUT_TOKEN_BUDGET = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.aggregate_output_tokens(
        expanded_lead=False
    )
)
S3_PRODUCTION_MODEL_SEGMENT_OUTPUT_TOKEN_BUDGETS = {
    "owner_grade_claim_cards": 900,
    "actionable_what_would_change_tasks": 1100,
}
S3_PRODUCTION_STAGE_OUTPUT_TOKEN_BUDGETS = {
    "specialist": 2000,
    "lead": 1800,
    "writer": 1400,
    "verifier": 800,
}
S3_PRODUCTION_AGGREGATE_OUTPUT_TOKEN_BUDGET = 10000
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V1_REF = (
    "fin01.s3.bounded_agent.research_lead_owner_grade:v1"
)
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF = (
    "fin01.s3.bounded_agent.research_lead_owner_grade:v2"
)
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF = (
    "fin01.s3.bounded_agent.research_lead_owner_grade:v3"
)
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF = (
    "fin01.s3.bounded_agent.research_lead_owner_grade:v4"
)
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF = (
    "fin01.s3.bounded_agent.research_lead_owner_grade:v5"
)
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF = (
    "fin01.s3.bounded_agent.research_lead_owner_grade:v6"
)
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF = (
    "fin01.s3.bounded_agent.research_lead_owner_grade:v7"
)
S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_REFS = (
    research_lead_transport_refs()
)
S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V1_REF = (
    "fin01.s3.bounded_agent.memo_writer_owner_grade:v1"
)
S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF = (
    "fin01.s3.bounded_agent.memo_writer_owner_grade:v2"
)
S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF = (
    "fin01.s3.bounded_agent.memo_writer_owner_grade:v3"
)
S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.stage_token_budgets(
        expanded_lead=True
    )
)
S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.aggregate_output_tokens(
        expanded_lead=True
    )
)
S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_NARRATIVE_CHARS = 320
S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_PROVIDER_UTF8_BYTES = 6000
S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_ASSEMBLED_UTF8_BYTES = 8192
S3_THREE_CELL_PROGRAM_CELL_IDS = (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.program_cell_ids
)
S3_FOUR_LAYER_VERIFIER_LAYERS = (
    "deterministic_integrity",
    "semantic_fidelity",
    "financial_coherence",
    "visual_delivery",
)
BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V1 = (
    "fin01.bounded_agent.specialist_lead_output:v1"
)
BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V2 = (
    "fin01.bounded_agent.specialist_lead_output:v2"
)
BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V3 = (
    "fin01.bounded_agent.specialist_lead_output:v3"
)
BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4 = (
    "fin01.bounded_agent.specialist_lead_output:v4"
)
BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME = "submit_specialist_lead_result"
BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF = (
    "fin01.bounded_agent.deepseek_strict_tool_output:v1"
)
BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF = (
    "fin01.bounded_agent.deepseek_segmented_json_object:v1"
)
BOUNDED_SPECIALIST_LEAD_JSON_OBJECT_TRANSPORT_REF = (
    "fin01.bounded_agent.deepseek_json_object:v1"
)
BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF = (
    "fin01.bounded_agent.native_json_schema_response:v1"
)
BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_NAME = "fin01_specialist_lead_result"
BOUNDED_DEEPSEEK_BETA_BASE_URL = "https://api.deepseek.com/beta"
BOUNDED_OPENAI_BASE_URL = "https://api.openai.com/v1"
CONSUMED_BOUNDED_AGENT_ADMISSION_IDS = frozenset(
    {
        "fin01-s2-t03-bounded-agent-v3-contract-live-validation-r1",
        "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r1",
        "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r2",
        "fin01-s2-t03-bounded-agent-native-json-schema-gpt-5-6-sol-live-validation-r1",
        "fin01-s2-t03-bounded-agent-native-json-schema-gpt-5-6-sol-live-validation-r2",
        "fin01-s2-t03-bounded-agent-deepseek-segmented-v4-live-validation-r1",
    }
)
HISTORICAL_BOUNDED_AGENT_ADMISSION_IDS = frozenset(
    {
        "fin01-s2-t03-bounded-agent-exact-admission-v1.0",
        "fin01-s2-t03-bounded-agent-v2-contract-live-validation-r1",
        "fin01-s2-t03-bounded-agent-v3-contract-live-validation-r1",
        "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r1",
        "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r2",
    }
)
HISTORICAL_JSON_OBJECT_ADMISSION_IDS = frozenset(
    {
        "fin01-s2-t03-bounded-agent-exact-admission-v1.0",
        "fin01-s2-t03-bounded-agent-v2-contract-live-validation-r1",
        "fin01-s2-t03-bounded-agent-v3-contract-live-validation-r1",
    }
)
BOUNDED_AGENT_REASONING_EFFORTS = frozenset(
    {"none", "low", "medium", "high", "xhigh", "max"}
)

BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE = "bounded_agent_manifest"
BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE = "bounded_agent_evidence"
BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE = "bounded_agent_numeric"
BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE = "bounded_agent_judgment"
BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE = "bounded_agent_workpaper"
BOUNDED_AGENT_REPORT_ARTIFACT_TYPE = "bounded_agent_report"
BOUNDED_AGENT_TRACE_ARTIFACT_TYPE = "bounded_agent_trace"
BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE = "bounded_agent_verification"
BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE = "agent_fallback_comparison"

BOUNDED_AGENT_ARTIFACT_TYPES = (
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE,
    BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_AGENT_TRACE_ARTIFACT_TYPE,
    BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
    BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE,
)


class BoundedAgentAdmission(BaseModel):
    """Exact, immutable admission consumed by the bounded profile.

    T02 uses an execution-disabled, zero-call admission. T03 may enable execution
    only after binding the exact evaluation Case/input and provider budget.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    admission_id: str
    execution_profile_version_ref: str = BOUNDED_AGENT_PROFILE_REF
    specialist_output_contract_ref: str = BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V1
    execution_enabled: bool = False
    execution_mode: str
    company: str = "NVDA"
    program_cell_id: str = "demand_authenticity_and_sustainability"
    evidence_role: str = "demand_signal"
    maximum_cell_count: int = 1
    case_id: str | None = None
    case_version: int | None = None
    as_of: str | None = None
    input_digest: str | None = None
    provider: str | None = None
    model: str | None = None
    model_ref: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    specialist_transport_ref: str | None = None
    reasoning_effort: str | None = None
    max_semantic_model_calls: int = 0
    max_provider_calls: int = 0
    max_network_calls: int = 0
    max_transport_attempts_per_call: int = 1
    max_total_cost_usd: float = 0.0
    specialist_max_output_tokens: int = 0
    lead_max_output_tokens: int = 0
    writer_max_output_tokens: int = 0
    verifier_max_output_tokens: int = 0
    timeout_seconds: int = 120
    input_cache_hit_usd_per_million: float = 0.003625
    input_cache_miss_usd_per_million: float = 0.435
    output_usd_per_million: float = 0.87
    source_network_calls_allowed: bool = False
    external_tool_calls_allowed: bool = False
    live_business_case_head_writes_allowed: bool = False
    retry_budget: int = 0

    def digest_payload(self) -> dict[str, Any]:
        """Return the exact digest payload while preserving historical identities."""

        payload = self.model_dump(mode="json")
        if self.specialist_transport_ref is None:
            payload.pop("specialist_transport_ref")
        if self.reasoning_effort is None:
            payload.pop("reasoning_effort")
        if self.lead_max_output_tokens == 0:
            payload.pop("lead_max_output_tokens")
        return payload

    def resolved_specialist_transport_ref(self) -> str:
        if self.specialist_transport_ref:
            return self.specialist_transport_ref
        if self.admission_id in HISTORICAL_JSON_OBJECT_ADMISSION_IDS:
            return BOUNDED_SPECIALIST_LEAD_JSON_OBJECT_TRANSPORT_REF
        if self.admission_id in HISTORICAL_BOUNDED_AGENT_ADMISSION_IDS:
            return BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF
        raise ValueError("bounded_admission_specialist_transport_binding_required")

    def assert_specialist_transport_binding(self) -> None:
        transport_ref = self.resolved_specialist_transport_ref()
        if transport_ref == BOUNDED_SPECIALIST_LEAD_JSON_OBJECT_TRANSPORT_REF:
            if (
                self.admission_id not in HISTORICAL_JSON_OBJECT_ADMISSION_IDS
                or self.reasoning_effort is not None
                or self.provider != "deepseek"
                or self.model != "deepseek-v4-pro"
                or self.model_ref != "deepseek:deepseek-v4-pro"
                or str(self.base_url or "").rstrip("/") != "https://api.deepseek.com"
            ):
                raise ValueError("bounded_historical_json_object_binding_invalid")
            return
        if transport_ref == BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF:
            if self.reasoning_effort not in (None, "none"):
                raise ValueError("bounded_strict_tool_reasoning_must_be_none")
            if (
                self.provider != "deepseek"
                or self.model != "deepseek-v4-pro"
                or self.model_ref != "deepseek:deepseek-v4-pro"
                or str(self.base_url or "").rstrip("/")
                != BOUNDED_DEEPSEEK_BETA_BASE_URL
            ):
                raise ValueError(
                    "bounded_specialist_strict_tool_provider_binding_required"
                )
            return
        if transport_ref == BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF:
            if (
                self.reasoning_effort != "none"
                or self.provider != "deepseek"
                or self.model != "deepseek-v4-pro"
                or self.model_ref != "deepseek:deepseek-v4-pro"
                or str(self.base_url or "").rstrip("/")
                != BOUNDED_DEEPSEEK_BETA_BASE_URL
                or self.api_key_env != "DEEPSEEK_API_KEY"
            ):
                raise ValueError(
                    "bounded_segmented_json_object_provider_binding_required"
                )
            return
        if transport_ref == BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF:
            model = str(self.model or "")
            if (
                self.provider != "openai"
                or not model
                or self.model_ref != f"openai:{model}"
                or str(self.base_url or "").rstrip("/") != BOUNDED_OPENAI_BASE_URL
                or self.api_key_env != "OPENAI_API_KEY"
                or self.reasoning_effort not in BOUNDED_AGENT_REASONING_EFFORTS
            ):
                raise ValueError(
                    "bounded_native_json_schema_openai_provider_binding_required"
                )
            return
        raise ValueError("bounded_admission_specialist_transport_unsupported")

    def assert_profile_admissible(self) -> None:
        if self.execution_profile_version_ref != BOUNDED_AGENT_PROFILE_REF:
            raise ValueError("bounded_admission_profile_identity_mismatch")
        if self.company != "NVDA" or self.evidence_role != "demand_signal":
            raise ValueError("bounded_admission_case_or_cell_scope_mismatch")
        if self.maximum_cell_count != 1:
            raise ValueError("bounded_admission_single_cell_required")
        if self.max_transport_attempts_per_call != 1 or self.retry_budget != 0:
            raise ValueError("bounded_admission_retry_forbidden")
        if (
            self.source_network_calls_allowed
            or self.external_tool_calls_allowed
            or self.live_business_case_head_writes_allowed
        ):
            raise ValueError("bounded_admission_hard_boundary_violation")
        if self.execution_enabled:
            required = (
                self.case_id,
                self.case_version,
                self.as_of,
                self.input_digest,
                self.provider,
                self.model,
                self.model_ref,
                self.api_key_env,
                self.base_url,
            )
            if any(value is None or value == "" for value in required):
                raise ValueError("bounded_admission_exact_execution_binding_required")
            if min(
                self.max_semantic_model_calls,
                self.max_provider_calls,
                self.max_network_calls,
            ) <= 0 or self.max_total_cost_usd <= 0:
                raise ValueError("bounded_admission_positive_budget_required")
            if min(
                self.specialist_max_output_tokens,
                self.writer_max_output_tokens,
                self.verifier_max_output_tokens,
            ) <= 0:
                raise ValueError("bounded_admission_stage_output_budget_required")
            if (
                self.specialist_transport_ref
                == BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF
                and self.lead_max_output_tokens <= 0
            ):
                raise ValueError("bounded_admission_lead_output_budget_required")
            if self.admission_id not in HISTORICAL_BOUNDED_AGENT_ADMISSION_IDS:
                if not self.specialist_transport_ref or not self.reasoning_effort:
                    raise ValueError(
                        "bounded_admission_transport_and_reasoning_binding_required"
                    )
                if self.specialist_transport_ref not in {
                    BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF,
                    BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF,
                    BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF,
                }:
                    raise ValueError(
                        "bounded_admission_specialist_transport_unsupported"
                    )
            if (
                self.reasoning_effort is not None
                and self.reasoning_effort not in BOUNDED_AGENT_REASONING_EFFORTS
            ):
                raise ValueError("bounded_admission_reasoning_effort_unsupported")
        elif any(
            (
                self.max_semantic_model_calls,
                self.max_provider_calls,
                self.max_network_calls,
            )
        ) or self.max_total_cost_usd != 0:
            raise ValueError("zero_call_admission_budget_must_be_zero")


class BoundedAgentInputPack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    case_version: int
    query: str
    as_of: str
    company: str
    program_cell_id: str
    evidence_role: str
    source_preview_digest: str
    deterministic_analysis_digest: str
    decision_question: str
    candidates: tuple[dict[str, Any], ...]
    deterministic_baseline: dict[str, Any]
    source_boundary: dict[str, Any]
    input_digest: str


class BoundedAgentArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_type: str
    payload: dict[str, Any]


class BoundedAgentExecutionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    terminal_reason: str
    artifacts: tuple[BoundedAgentArtifact, ...]
    trace_events: tuple[dict[str, Any], ...] = ()
    provider_output_captures: tuple[dict[str, Any], ...] = ()
    execution_observation: dict[str, Any] = Field(default_factory=dict)


class BoundedAgentExecutorPort(Protocol):
    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput: ...


class S3ThreeCellBoundedAgentAdmission(BaseModel):
    """Versioned S3 profile binding; separate from every consumed S2 admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    admission_id: str
    execution_profile_version_ref: str = S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
    input_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF
    output_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF
    execution_enabled: bool = False
    execution_mode: str
    research_profile_ref: str | None = None
    company: str = S3_NVDA_THREE_CELL_RESEARCH_PROFILE.company
    program_cell_ids: tuple[str, ...] = S3_THREE_CELL_PROGRAM_CELL_IDS
    maximum_cell_count: int = (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE.maximum_cell_count
    )
    case_id: str | None = None
    case_version: int | None = None
    as_of: str | None = None
    input_digest: str | None = None
    provider: str | None = None
    model: str | None = None
    model_ref: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    transport_ref: str = S3_THREE_CELL_DEEPSEEK_SEGMENTED_TRANSPORT_REF
    research_lead_transport_ref: str = (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V1_REF
    )
    memo_writer_transport_ref: str = S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V1_REF
    scoped_identity_contract_ref: str | None = None
    claim_fact_link_policy_ref: str | None = None
    task_claim_link_policy_ref: str | None = None
    wwc_judgment_atom_policy_ref: str | None = None
    judgment_atom_compiled_contract_ref: str | None = None
    runtime_contract_family_binding_ref: str | None = None
    runtime_contract_family_source_digest: str | None = None
    local_fact_interaction_contract_ref: str | None = None
    case_numeric_authority_policy_ref: str | None = None
    case_delivery_identity_policy_ref: str | None = None
    strict_truth_kernel_policy_ref: str | None = None
    provider_capability_ref: str | None = None
    non_authoritative_narrative_shell_ref: str | None = None
    provider_output_capture_policy_ref: str = S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
    reasoning_effort: str = "none"
    max_semantic_model_calls: int = 0
    max_provider_calls: int = 0
    max_network_calls: int = 0
    max_total_cost_usd: float = 0.0
    specialist_max_output_tokens: int = 0
    lead_max_output_tokens: int = 0
    writer_max_output_tokens: int = 0
    verifier_max_output_tokens: int = 0
    timeout_seconds: int = 120
    input_cache_hit_usd_per_million: float = 0.003625
    input_cache_miss_usd_per_million: float = 0.435
    output_usd_per_million: float = 0.87
    max_transport_attempts_per_call: int = 1
    retry_budget: int = 0
    source_network_calls_allowed: bool = False
    external_tool_calls_allowed: bool = False
    live_business_case_head_writes_allowed: bool = False

    def assert_profile_admissible(self) -> None:
        research_profile = research_profile_for_ref(self.research_profile_ref)
        try:
            lead_contract = research_lead_transport_contract(
                self.research_lead_transport_ref
            )
        except ValueError as exc:
            raise ValueError(
                "s3_bounded_admission_research_lead_transport_unsupported"
            ) from exc
        transport_contract = (
            specialist_transport_contract(self.transport_ref)
            if self.transport_ref in S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS
            else None
        )
        if self.execution_profile_version_ref != S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF:
            raise ValueError("s3_bounded_admission_profile_identity_mismatch")
        if self.output_contract_ref not in {
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        }:
            raise ValueError("s3_bounded_admission_output_contract_unsupported")
        if (
            self.provider_output_capture_policy_ref
            not in PROVIDER_OUTPUT_CAPTURE_POLICY_REFS
        ):
            raise ValueError("s3_bounded_admission_output_capture_policy_unsupported")
        if self.memo_writer_transport_ref not in {
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V1_REF,
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
        }:
            raise ValueError("s3_bounded_admission_memo_writer_transport_unsupported")
        if self.claim_fact_link_policy_ref is not None:
            if self.claim_fact_link_policy_ref != S3_CLAIM_FACT_LINK_POLICY_REF:
                raise ValueError(
                    "s3_bounded_admission_claim_fact_link_policy_unsupported"
                )
            if (
                self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                or transport_contract is None
                or not transport_contract.local_scope_assembly
                or not transport_contract.field_local_fact_support_authority
            ):
                raise ValueError(
                    "s3_bounded_admission_claim_fact_link_policy_capability_binding_required"
                )
        if self.task_claim_link_policy_ref is not None:
            if (
                self.task_claim_link_policy_ref
                != S3_TASK_CLAIM_LINK_POLICY_REF
            ):
                raise ValueError(
                    "s3_bounded_admission_task_claim_link_policy_unsupported"
                )
            if (
                self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                or transport_contract is None
                or not transport_contract.local_scope_assembly
                or not transport_contract.field_local_fact_support_authority
            ):
                raise ValueError(
                    "s3_bounded_admission_task_claim_link_policy_"
                    "capability_binding_required"
                )
        if self.wwc_judgment_atom_policy_ref is not None:
            if (
                self.wwc_judgment_atom_policy_ref
                not in SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REFS
            ):
                raise ValueError(
                    "s3_bounded_admission_WWC_judgment_atom_policy_unsupported"
                )
            capacity_binding_valid = (
                (
                    self.wwc_judgment_atom_policy_ref
                    == S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
                    and research_profile.segment_token_budgets.get(
                        "actionable_what_would_change_tasks"
                    )
                    == 1800
                    and research_profile.stage_token_budgets(
                        expanded_lead=True
                    ).get("specialist")
                    == 4600
                    and research_profile.aggregate_output_tokens(
                        expanded_lead=True
                    )
                    == 18000
                )
                or (
                    self.wwc_judgment_atom_policy_ref
                    == S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
                    and research_profile.segment_token_budgets.get(
                        "actionable_what_would_change_tasks", 0
                    )
                    >= 1400
                    and research_profile.stage_token_budgets(
                        expanded_lead=True
                    ).get("specialist", 0)
                    >= 4200
                    and research_profile.aggregate_output_tokens(
                        expanded_lead=True
                    )
                    >= 16800
                )
            )
            if (
                self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                or transport_contract is None
                or not transport_contract.what_would_change_judgment_atom_assembly
                or self.task_claim_link_policy_ref
                != S3_TASK_CLAIM_LINK_POLICY_REF
                or not capacity_binding_valid
            ):
                raise ValueError(
                    "s3_bounded_admission_WWC_judgment_atom_"
                    "capability_binding_required"
                )
        elif (
            transport_contract is not None
            and transport_contract.what_would_change_judgment_atom_assembly
        ):
            raise ValueError(
                "s3_bounded_admission_v8_WWC_judgment_atom_policy_required"
            )
        if self.judgment_atom_compiled_contract_ref is not None:
            if (
                self.judgment_atom_compiled_contract_ref
                not in DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS
                or self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                or transport_contract is None
                or not transport_contract.local_scope_assembly
                or not transport_contract.field_local_fact_support_authority
                or self.claim_fact_link_policy_ref
                != S3_CLAIM_FACT_LINK_POLICY_REF
                or self.task_claim_link_policy_ref
                != S3_TASK_CLAIM_LINK_POLICY_REF
                or self.wwc_judgment_atom_policy_ref
                != S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
                or self.case_numeric_authority_policy_ref
                not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
            ):
                raise ValueError(
                    "s4_bounded_admission_compiled_judgment_atom_"
                    "capability_binding_required"
                )
        if transport_contract is not None and (
            transport_contract.local_deterministic_fact_interaction
        ):
            if (
                self.local_fact_interaction_contract_ref
                != S3_LOCAL_DETERMINISTIC_FACT_INTERACTION_CONTRACT_REF
                or self.judgment_atom_compiled_contract_ref
                != FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF
            ):
                raise ValueError(
                    "s3_bounded_admission_local_fact_production_binding_required"
                )
        elif self.local_fact_interaction_contract_ref is not None:
            raise ValueError(
                "s3_bounded_admission_local_fact_requires_v9_transport"
            )
        fin012_binding_fields = (
            self.runtime_contract_family_binding_ref,
            self.runtime_contract_family_source_digest,
        )
        if (
            self.judgment_atom_compiled_contract_ref
            == FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
        ):
            try:
                load_fin_0_1_2_runtime_contract_binding().assert_admission_binding(
                    binding_ref=self.runtime_contract_family_binding_ref,
                    source_digest=self.runtime_contract_family_source_digest,
                )
            except Fin012RuntimeContractBindingError as exc:
                raise ValueError(exc.code) from exc
            if (
                self.provider_output_capture_policy_ref
                != S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ):
                raise ValueError(
                    "fin012_runtime_contract_capture_v2_binding_required"
                )
        elif (
            self.judgment_atom_compiled_contract_ref
            == FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF
        ):
            try:
                load_fin_0_1_2_s3_runtime_contract_binding().assert_admission_binding(
                    binding_ref=self.runtime_contract_family_binding_ref,
                    source_digest=self.runtime_contract_family_source_digest,
                )
            except Fin012RuntimeContractBindingError as exc:
                raise ValueError(exc.code) from exc
            if (
                self.provider_output_capture_policy_ref
                != S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ):
                raise ValueError(
                    "fin012_runtime_contract_capture_v2_binding_required"
                )
        elif any(value is not None for value in fin012_binding_fields):
            raise ValueError(
                "fin012_runtime_contract_binding_requires_fin012_contract_ref"
            )
        case_policy_refs = (
            self.case_numeric_authority_policy_ref,
            self.case_delivery_identity_policy_ref,
        )
        if any(value is not None for value in case_policy_refs):
            if (
                self.case_numeric_authority_policy_ref
                not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
                or self.case_delivery_identity_policy_ref
                not in S4_CASE_DELIVERY_IDENTITY_POLICY_REFS
            ):
                raise ValueError(
                    "s4_bounded_admission_numeric_and_identity_policy_pair_required"
                )
            if (
                self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                or transport_contract is None
                or not transport_contract.field_local_fact_support_authority
                or not transport_contract.local_scope_assembly
                or self.memo_writer_transport_ref
                != S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
                or not lead_contract.case_material_truth_identity_safety_composable
                or self.scoped_identity_contract_ref
                != S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
            ):
                raise ValueError(
                    "s4_bounded_admission_numeric_and_identity_policy_capability_binding_required"
                )
        strict_truth_refs = (
            self.strict_truth_kernel_policy_ref,
            self.provider_capability_ref,
            self.non_authoritative_narrative_shell_ref,
        )
        if (
            transport_contract is not None
            and transport_contract.local_deterministic_fact_interaction
            and any(value is not None for value in strict_truth_refs)
        ):
            raise ValueError(
                "s3_bounded_admission_local_fact_and_strict_kernel_conflict"
            )
        if any(value is not None for value in strict_truth_refs):
            if strict_truth_refs != (
                S4_STRICT_TRUTH_KERNEL_POLICY_REF,
                S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF,
                S4_NON_AUTHORITATIVE_NARRATIVE_SHELL_REF,
            ):
                raise ValueError(
                    "s4_bounded_admission_strict_truth_kernel_policy_triple_required"
                )
            if (
                self.case_numeric_authority_policy_ref
                not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
                or self.case_delivery_identity_policy_ref
                not in S4_CASE_DELIVERY_IDENTITY_POLICY_REFS
            ):
                raise ValueError(
                    "s4_bounded_admission_strict_truth_kernel_local_owner_required"
                )
        if self.output_contract_ref == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF:
            if (
                transport_contract is None
                or not transport_contract.field_local_fact_support_authority
                or not lead_contract.typed_scoped_identity
                or self.memo_writer_transport_ref
                != S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
                or self.scoped_identity_contract_ref
                != S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
            ):
                raise ValueError(
                    "s3_bounded_admission_output_v4_scoped_identity_binding_required"
                )
        elif (
            lead_contract.typed_scoped_identity
            or self.memo_writer_transport_ref
            == S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
            or self.scoped_identity_contract_ref is not None
        ):
            raise ValueError(
                "s3_bounded_admission_scoped_identity_requires_output_v4"
            )
        if lead_contract.compact_scoped_alias_wire and (
            not lead_contract.local_row_ids
            or not lead_contract.dual_capacity
            or self.research_profile_ref is None
            or research_profile.research_lead_local_capacity_formula_ref
            != (
                "fin01.s3.research_lead_local_capacity."
                "exact_surface_maximum_valid_shape:v1"
            )
        ):
            raise ValueError(
                "s3_bounded_admission_research_lead_compact_alias_profile_required"
            )
        if (
            self.memo_writer_transport_ref
            == S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF
            and (
                transport_contract is None
                or not transport_contract.bounded_assembly
                or self.research_lead_transport_ref
                != S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
                or self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
            )
        ):
            raise ValueError(
                "s3_bounded_admission_memo_writer_v2_requires_specialist_v5_lead_v3_output_v3"
            )
        if (
            self.research_lead_transport_ref
            == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
            and (
                self.transport_ref
                != S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
                or self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
            )
        ):
            raise ValueError(
                "s3_bounded_admission_research_lead_v2_requires_specialist_v5_output_v3"
            )
        if (
            self.research_lead_transport_ref
            == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
            and (
                transport_contract is None
                or not transport_contract.bounded_assembly
                or self.output_contract_ref
                != S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
            )
        ):
            raise ValueError(
                "s3_bounded_admission_research_lead_v3_requires_specialist_v5_output_v3"
            )
        if (
            self.execution_enabled
            and transport_contract is not None
            and transport_contract.explicit_output_capture_binding
            and "provider_output_capture_policy_ref" not in self.model_fields_set
        ):
            transport_version = self.transport_ref.rsplit(":", 1)[-1]
            raise ValueError(
                f"s3_bounded_admission_{transport_version}_"
                "output_capture_policy_explicit_binding_required"
            )
        if (
            transport_contract is not None
            and transport_contract.field_local_fact_support_authority
            and self.research_profile_ref is None
        ):
            raise ValueError(
                "s3_bounded_admission_v7_explicit_research_profile_required"
            )
        try:
            research_profile.assert_scope(
                company=self.company,
                program_cell_ids=self.program_cell_ids,
                maximum_cell_count=self.maximum_cell_count,
            )
        except ValueError as exc:
            if self.research_profile_ref is None:
                raise ValueError(
                    "s3_bounded_admission_exact_three_cell_scope_required"
                ) from exc
            raise
        if self.max_transport_attempts_per_call != 1 or self.retry_budget != 0:
            raise ValueError("s3_bounded_admission_retry_forbidden")
        if (
            self.source_network_calls_allowed
            or self.external_tool_calls_allowed
            or self.live_business_case_head_writes_allowed
        ):
            raise ValueError("s3_bounded_admission_hard_boundary_violation")
        if self.execution_enabled:
            exact = (
                self.case_id,
                self.case_version,
                self.as_of,
                self.input_digest,
                self.provider,
                self.model,
                self.model_ref,
                self.api_key_env,
                self.base_url,
            )
            if any(value is None or value == "" for value in exact):
                raise ValueError("s3_bounded_admission_exact_execution_binding_required")
            if (
                self.strict_truth_kernel_policy_ref
                == S4_STRICT_TRUTH_KERNEL_POLICY_REF
            ):
                if (
                    self.provider != "openai"
                    or not str(self.model or "")
                    or self.model_ref != f"openai:{self.model}"
                    or self.api_key_env != "OPENAI_API_KEY"
                    or str(self.base_url or "").rstrip("/")
                    != BOUNDED_OPENAI_BASE_URL
                    or self.reasoning_effort
                    not in BOUNDED_AGENT_REASONING_EFFORTS
                ):
                    raise ValueError(
                        "s4_strict_truth_kernel_openai_provider_binding_required"
                    )
            elif (
                self.provider != "deepseek"
                or self.model != "deepseek-v4-pro"
                or self.model_ref != "deepseek:deepseek-v4-pro"
                or self.api_key_env != "DEEPSEEK_API_KEY"
                or self.base_url != BOUNDED_DEEPSEEK_BETA_BASE_URL
                or self.transport_ref
                not in (
                    S3_THREE_CELL_DEEPSEEK_SEGMENTED_TRANSPORT_REF,
                    *S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS,
                )
                or self.reasoning_effort != "none"
            ):
                raise ValueError(
                    "s3_bounded_admission_exact_provider_binding_required"
                )
            if self.transport_ref == S3_THREE_CELL_DEEPSEEK_SEGMENTED_TRANSPORT_REF:
                expected_calls = 6
            elif (
                transport_contract is not None
                and transport_contract.local_deterministic_fact_interaction
            ):
                expected_calls = 9
            else:
                expected_calls = 12
                if self.output_contract_ref not in {
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
                }:
                    raise ValueError(
                        "s3_bounded_admission_segmented_specialist_requires_output_v3"
                    )
            if any(
                value != expected_calls
                for value in (
                    self.max_semantic_model_calls,
                    self.max_provider_calls,
                    self.max_network_calls,
                )
            ) or self.max_total_cost_usd <= 0:
                raise ValueError("s3_bounded_admission_exact_call_budget_required")
            if min(
                self.specialist_max_output_tokens,
                self.lead_max_output_tokens,
                self.writer_max_output_tokens,
                self.verifier_max_output_tokens,
            ) <= 0:
                raise ValueError("s3_bounded_admission_stage_output_budget_required")
            if (
                self.transport_ref
                in S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS
            ):
                expanded_lead = lead_contract.closed_semantic_output
                expected_budgets = (
                    research_profile.stage_token_budgets(
                        expanded_lead=expanded_lead
                    )
                )
                expected_aggregate_budget = (
                    research_profile.aggregate_output_tokens(
                        expanded_lead=expanded_lead
                    )
                )
                observed_budgets = {
                    "specialist": self.specialist_max_output_tokens,
                    "lead": self.lead_max_output_tokens,
                    "writer": self.writer_max_output_tokens,
                    "verifier": self.verifier_max_output_tokens,
                }
                aggregate_budget = (
                    3 * self.specialist_max_output_tokens
                    + self.lead_max_output_tokens
                    + self.writer_max_output_tokens
                    + self.verifier_max_output_tokens
                )
                if (
                    transport_contract is not None
                    and transport_contract.local_deterministic_fact_interaction
                ):
                    budget_invalid = (
                        observed_budgets
                        != S3_PRODUCTION_STAGE_OUTPUT_TOKEN_BUDGETS
                        or aggregate_budget
                        != S3_PRODUCTION_AGGREGATE_OUTPUT_TOKEN_BUDGET
                        or self.max_total_cost_usd != 0.06
                    )
                else:
                    budget_invalid = (
                        observed_budgets != expected_budgets
                        or aggregate_budget != expected_aggregate_budget
                        or self.max_total_cost_usd != 0.10
                    )
                if budget_invalid:
                    raise ValueError(
                        "s3_bounded_admission_segmented_specialist_exact_output_budget_required"
                    )
            elif self.output_contract_ref in {
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
            }:
                observed_budgets = {
                    "specialist": self.specialist_max_output_tokens,
                    "lead": self.lead_max_output_tokens,
                    "writer": self.writer_max_output_tokens,
                    "verifier": self.verifier_max_output_tokens,
                }
                aggregate_budget = (
                    3 * self.specialist_max_output_tokens
                    + self.lead_max_output_tokens
                    + self.writer_max_output_tokens
                    + self.verifier_max_output_tokens
                )
                if (
                    observed_budgets != S3_V2_STAGE_OUTPUT_TOKEN_BUDGETS
                    or aggregate_budget != S3_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET
                    or self.max_total_cost_usd != 0.10
                ):
                    version = "v3" if self.output_contract_ref == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF else "v2"
                    raise ValueError(
                        f"s3_bounded_admission_{version}_exact_output_budget_required"
                    )
            if self.timeout_seconds <= 0 or min(
                self.input_cache_hit_usd_per_million,
                self.input_cache_miss_usd_per_million,
                self.output_usd_per_million,
            ) < 0:
                raise ValueError("s3_bounded_admission_transport_budget_invalid")
        elif any(
            (
                self.max_semantic_model_calls,
                self.max_provider_calls,
                self.max_network_calls,
            )
        ) or self.max_total_cost_usd != 0:
            raise ValueError("s3_zero_call_admission_budget_must_be_zero")

    def digest_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        # Preserve the digest of admissions issued before this field existed.
        # Newly issued admissions bind the policy by setting it explicitly.
        if "provider_output_capture_policy_ref" not in self.model_fields_set:
            payload.pop("provider_output_capture_policy_ref", None)
        if "research_lead_transport_ref" not in self.model_fields_set:
            payload.pop("research_lead_transport_ref", None)
        if "memo_writer_transport_ref" not in self.model_fields_set:
            payload.pop("memo_writer_transport_ref", None)
        if "research_profile_ref" not in self.model_fields_set:
            payload.pop("research_profile_ref", None)
        if "scoped_identity_contract_ref" not in self.model_fields_set:
            payload.pop("scoped_identity_contract_ref", None)
        if "claim_fact_link_policy_ref" not in self.model_fields_set:
            payload.pop("claim_fact_link_policy_ref", None)
        if "task_claim_link_policy_ref" not in self.model_fields_set:
            payload.pop("task_claim_link_policy_ref", None)
        if "wwc_judgment_atom_policy_ref" not in self.model_fields_set:
            payload.pop("wwc_judgment_atom_policy_ref", None)
        if "judgment_atom_compiled_contract_ref" not in self.model_fields_set:
            payload.pop("judgment_atom_compiled_contract_ref", None)
        if "runtime_contract_family_binding_ref" not in self.model_fields_set:
            payload.pop("runtime_contract_family_binding_ref", None)
        if "runtime_contract_family_source_digest" not in self.model_fields_set:
            payload.pop("runtime_contract_family_source_digest", None)
        if "local_fact_interaction_contract_ref" not in self.model_fields_set:
            payload.pop("local_fact_interaction_contract_ref", None)
        if "case_numeric_authority_policy_ref" not in self.model_fields_set:
            payload.pop("case_numeric_authority_policy_ref", None)
        if "case_delivery_identity_policy_ref" not in self.model_fields_set:
            payload.pop("case_delivery_identity_policy_ref", None)
        if "strict_truth_kernel_policy_ref" not in self.model_fields_set:
            payload.pop("strict_truth_kernel_policy_ref", None)
        if "provider_capability_ref" not in self.model_fields_set:
            payload.pop("provider_capability_ref", None)
        if (
            "non_authoritative_narrative_shell_ref"
            not in self.model_fields_set
        ):
            payload.pop("non_authoritative_narrative_shell_ref", None)
        return payload


def compile_s4_case_runtime_mandatory_safety_admission(
    source_admission: S3ThreeCellBoundedAgentAdmission,
    *,
    updates: Mapping[str, Any] | None = None,
) -> S3ThreeCellBoundedAgentAdmission:
    """Compile one admission against the current mandatory S4 safety profile."""

    compiled_updates = dict(updates or {})
    compiled_updates.setdefault(
        "case_numeric_authority_policy_ref",
        S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
    )
    compiled_updates.setdefault(
        "case_delivery_identity_policy_ref",
        S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
    )
    compiled = source_admission.model_copy(
        update=compiled_updates
    )
    compiled.assert_profile_admissible()
    return compiled


def compile_fin_0_1_2_common_runtime_admission(
    source_admission: S3ThreeCellBoundedAgentAdmission,
    *,
    updates: Mapping[str, Any] | None = None,
) -> S3ThreeCellBoundedAgentAdmission:
    """Bind a capable historical admission to the FIN 0.1.2 family source."""

    binding = load_fin_0_1_2_runtime_contract_binding()
    compiled_updates = dict(updates or {})
    compiled_updates.setdefault(
        "judgment_atom_compiled_contract_ref",
        FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    )
    compiled_updates.setdefault(
        "runtime_contract_family_binding_ref",
        FIN_0_1_2_COMMON_RUNTIME_BINDING_REF,
    )
    compiled_updates.setdefault(
        "runtime_contract_family_source_digest",
        binding.source_digest,
    )
    compiled_updates.setdefault(
        "provider_output_capture_policy_ref",
        S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
    )
    compiled = source_admission.model_copy(update=compiled_updates)
    compiled.assert_profile_admissible()
    return compiled


def compile_fin_0_1_2_s3_production_admission(
    source_admission: S3ThreeCellBoundedAgentAdmission,
    *,
    updates: Mapping[str, Any] | None = None,
) -> S3ThreeCellBoundedAgentAdmission:
    """Compile the 3-local-Fact/9-Provider S3 production profile."""

    binding = load_fin_0_1_2_s3_runtime_contract_binding()
    compiled_updates: dict[str, Any] = {
        "research_profile_ref": (
            S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
        ),
        "output_contract_ref": (
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ),
        "transport_ref": (
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V9_REF
        ),
        "judgment_atom_compiled_contract_ref": (
            FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF
        ),
        "runtime_contract_family_binding_ref": (
            FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_REF
        ),
        "runtime_contract_family_source_digest": binding.source_digest,
        "local_fact_interaction_contract_ref": (
            S3_LOCAL_DETERMINISTIC_FACT_INTERACTION_CONTRACT_REF
        ),
        "claim_fact_link_policy_ref": S3_CLAIM_FACT_LINK_POLICY_REF,
        "task_claim_link_policy_ref": S3_TASK_CLAIM_LINK_POLICY_REF,
        "wwc_judgment_atom_policy_ref": (
            S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
        ),
        "case_numeric_authority_policy_ref": (
            S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
        ),
        "case_delivery_identity_policy_ref": (
            S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
        ),
        "research_lead_transport_ref": (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
        ),
        "memo_writer_transport_ref": (
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        "scoped_identity_contract_ref": (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        ),
        "provider_output_capture_policy_ref": (
            S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
        ),
        "strict_truth_kernel_policy_ref": None,
        "provider_capability_ref": None,
        "non_authoritative_narrative_shell_ref": None,
    }
    compiled_updates.update(dict(updates or {}))
    execution_enabled = bool(
        compiled_updates.get(
            "execution_enabled", source_admission.execution_enabled
        )
    )
    if execution_enabled:
        compiled_updates.update(
            {
                "max_semantic_model_calls": 9,
                "max_provider_calls": 9,
                "max_network_calls": 9,
                "max_total_cost_usd": 0.06,
                "specialist_max_output_tokens": 2000,
                "lead_max_output_tokens": 1800,
                "writer_max_output_tokens": 1400,
                "verifier_max_output_tokens": 800,
            }
        )
    else:
        compiled_updates.update(
            {
                "max_semantic_model_calls": 0,
                "max_provider_calls": 0,
                "max_network_calls": 0,
                "max_total_cost_usd": 0.0,
                "specialist_max_output_tokens": 0,
                "lead_max_output_tokens": 0,
                "writer_max_output_tokens": 0,
                "verifier_max_output_tokens": 0,
            }
        )
    compiled = source_admission.model_copy(update=compiled_updates)
    compiled.assert_profile_admissible()
    return compiled


def resolve_s4_case_runtime_binding_for_admission(
    repo_root: str | os.PathLike[str],
    admission: S3ThreeCellBoundedAgentAdmission,
) -> tuple[
    S4CaseRuntimeBinding,
    S4CaseRuntimeResearchProfileOverlay | None,
]:
    """Resolve the effective S4 binding from one exact admission, without I/O calls."""

    admission.assert_profile_admissible()
    base_binding = load_s4_case_runtime_binding(repo_root, admission.company)
    profile = research_profile_for_ref(admission.research_profile_ref)
    profile.assert_scope(
        company=base_binding.case_ticker,
        program_cell_ids=base_binding.program_cell_ids,
        maximum_cell_count=len(base_binding.program_cell_ids),
    )
    if profile.profile_ref == base_binding.research_profile_ref:
        return base_binding, None
    effective_binding, overlay = (
        apply_s4_case_runtime_research_profile_overlay(
            base_binding,
            research_profile_ref=profile.profile_ref,
            research_profile_contract_payload=(
                bounded_research_profile_contract_payload(profile)
            ),
        )
    )
    if effective_binding.research_profile_ref != admission.research_profile_ref:
        raise ValueError("s4_admission_research_profile_binding_mismatch")
    return effective_binding, overlay


class S3ThreeCellBoundedAgentInputPack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF
    execution_profile_version_ref: str = S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
    case_id: str
    case_version: int
    query: str
    as_of: str
    company: str = S3_NVDA_THREE_CELL_RESEARCH_PROFILE.company
    decision_surface_contract_ref: str
    input_head_digest: str
    program_cell_ids: tuple[str, ...] = S3_THREE_CELL_PROGRAM_CELL_IDS
    lineage: dict[str, dict[str, str]]
    cell_inputs: tuple[dict[str, Any], ...]
    lead_contract: dict[str, Any]
    writer_contract: dict[str, Any]
    verifier_contract: dict[str, Any]
    paired_baseline_contract: dict[str, Any]
    hard_boundaries: dict[str, Any]
    s4_case_runtime: dict[str, Any] | None = None
    input_digest: str


class S3ThreeCellAgentNodeExecutorPort(Protocol):
    def execute_node(
        self,
        node_id: str,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> Mapping[str, Any]: ...


class S3ThreeCellBoundedAgentExecutorPort(Protocol):
    def execute(
        self,
        input_pack: S3ThreeCellBoundedAgentInputPack,
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput: ...


class S3SegmentedSpecialistShapeError(ValueError):
    """Closed, secret-safe top-level shape failure for one Specialist segment."""

    _ALLOWED_SUBTYPES = {
        "top_level_keys_missing",
        "top_level_keys_unexpected",
        "program_cell_id_mismatch",
    }

    def __init__(
        self,
        *,
        segment_id: str,
        subtype: str,
        missing_key_count: int,
        unexpected_key_count: int,
    ) -> None:
        if (
            segment_id not in S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS
            or subtype not in self._ALLOWED_SUBTYPES
            or missing_key_count < 0
            or unexpected_key_count < 0
        ):
            raise ValueError("s3_segmented_specialist_shape_error_contract_invalid")
        super().__init__("s3_bounded_segmented_specialist_shape_invalid")
        self.telemetry = {
            "parser_contract": "closed_segment_top_level_shape:v1",
            "segment_id": segment_id,
            "shape_subtype": subtype,
            "missing_key_count": missing_key_count,
            "unexpected_key_count": unexpected_key_count,
            "raw_output_persisted": False,
            "arbitrary_key_names_persisted": False,
        }


class S3SegmentedSpecialistTextError(ValueError):
    """Closed, content-free narrative text failure for one Specialist segment."""

    _ALLOWED_FIELDS = {
        "fact_layer.statement_or_boundary",
        "explanation_layer",
        "remaining_gaps",
        "judgment_layer",
        "what_would_change",
    }
    _ALLOWED_SUBTYPES = {
        "item_not_string",
        "item_blank",
        "item_over_max_unicode_characters",
    }

    def __init__(
        self,
        *,
        segment_id: str,
        field_id: str,
        subtype: str,
        failing_item_count: int,
        failure_code: str,
    ) -> None:
        if (
            segment_id not in S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS
            or field_id not in self._ALLOWED_FIELDS
            or subtype not in self._ALLOWED_SUBTYPES
            or type(failing_item_count) is not int
            or failing_item_count <= 0
            or re.fullmatch(r"[a-z0-9_:.-]{1,140}", failure_code) is None
        ):
            raise ValueError("s3_segmented_specialist_text_error_contract_invalid")
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": "closed_segment_narrative_text:v1",
            "segment_id": segment_id,
            "field_id": field_id,
            "text_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_text_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3SegmentedSpecialistAuthorityError(ValueError):
    """Closed, content-free context-authority failure for one claim segment."""

    _ALLOWED_SUBTYPES = {
        "item_not_nonblank_string",
        "evidence_or_numeric_ref_misclassified_as_context",
        "outside_current_cell_context_authority",
    }

    def __init__(self, *, subtype: str, failing_item_count: int) -> None:
        if (
            subtype not in self._ALLOWED_SUBTYPES
            or type(failing_item_count) is not int
            or failing_item_count <= 0
        ):
            raise ValueError("s3_segmented_specialist_authority_error_contract_invalid")
        failure_code = "s3_owner_grade_claim_context_authority_invalid"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": "closed_segment_context_authority:v1",
            "segment_id": "owner_grade_claim_cards",
            "field_id": "judgment_layer.context_refs",
            "authority_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_ref_persisted": False,
            "ref_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3SegmentedSpecialistFactAuthorityError(ValueError):
    """Closed, content-free field-local Fact support authority failure."""

    _ALLOWED_SUBTYPES = {
        "fact_layer_not_array",
        "support_type_invalid",
        "support_refs_not_array",
        "support_refs_empty",
        "item_not_nonblank_string",
        "candidate_or_graph_ref_misclassified_as_fact",
        "evidence_or_numeric_cross_type",
        "outside_current_cell_fact_authority",
        "support_ref_duplicate",
    }

    def __init__(self, *, subtype: str, failing_item_count: int) -> None:
        if (
            subtype not in self._ALLOWED_SUBTYPES
            or type(failing_item_count) is not int
            or failing_item_count <= 0
        ):
            raise ValueError(
                "s3_segmented_specialist_fact_authority_error_contract_invalid"
            )
        failure_code = "s3_owner_grade_fact_support_authority_invalid"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": "closed_fact_support_authority:v1",
            "segment_id": "facts_explanation_and_terminal",
            "field_id": "fact_layer.support_refs",
            "authority_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_ref_persisted": False,
            "ref_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3SegmentedSpecialistClaimFactLinkError(ValueError):
    """Closed, content-free Claim-to-Fact alias/expansion failure."""

    _ALLOWED_SUBTYPES = {
        "support_alias_not_array",
        "support_alias_item_invalid",
        "support_alias_empty_when_required",
        "support_alias_unknown",
        "support_alias_duplicate",
        "support_alias_wrong_cell",
        "raw_fact_or_source_ref_used_in_alias_field",
        "local_expansion_mismatch",
    }

    def __init__(self, *, subtype: str, failing_item_count: int) -> None:
        if (
            subtype not in self._ALLOWED_SUBTYPES
            or type(failing_item_count) is not int
            or failing_item_count <= 0
        ):
            raise ValueError(
                "s3_segmented_specialist_claim_fact_link_error_contract_invalid"
            )
        failure_code = "s3_owner_grade_claim_fact_link_invalid"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": S3_CLAIM_FACT_LINK_POLICY_REF,
            "segment_id": "owner_grade_claim_cards",
            "field_id": "judgment_layer.support_fact_aliases",
            "failure_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_alias_persisted": False,
            "fact_id_persisted": False,
            "source_ref_persisted": False,
            "program_cell_id_persisted": False,
            "item_index_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3SegmentedSpecialistTaskClaimLinkError(ValueError):
    """Closed, content-free WWC Task-to-Claim alias failure."""

    _ALLOWED_SUBTYPES = {
        "task_claim_alias_unknown",
    }

    def __init__(self, *, subtype: str, failing_item_count: int) -> None:
        if (
            subtype not in self._ALLOWED_SUBTYPES
            or type(failing_item_count) is not int
            or failing_item_count <= 0
        ):
            raise ValueError(
                "s3_segmented_specialist_task_claim_link_error_contract_invalid"
            )
        failure_code = "s3_owner_grade_task_claim_link_invalid"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": S3_TASK_CLAIM_LINK_POLICY_REF,
            "segment_id": "actionable_what_would_change_tasks",
            "field_id": "what_would_change.claim_alias",
            "failure_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_alias_persisted": False,
            "claim_id_persisted": False,
            "program_cell_id_persisted": False,
            "item_index_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3SegmentedSpecialistWWCJudgmentAtomError(ValueError):
    """Closed, content-free v8 WWC atom validation/assembly failure."""

    _ALLOWED_SUBTYPES = {
        "provider_output_byte_count_invalid",
        "provider_output_over_max_utf8_bytes",
        "provider_top_level_shape_invalid",
        "atom_cardinality_invalid",
        "atom_shape_invalid",
        "claim_alias_wrong_kind",
        "claim_alias_unknown_or_cross_cell",
        "authority_alias_wrong_kind",
        "authority_alias_unknown_or_cross_cell",
        "authority_alias_array_invalid",
        "atom_narrative_invalid",
        "rule_type_unknown",
        "expected_claim_transition_unknown",
        "start_trigger_code_unknown",
        "review_timing_code_unknown",
        "start_date_alias_binding_invalid",
        "review_date_alias_binding_invalid",
        "temporal_local_rendering_failed",
    }

    def __init__(
        self,
        *,
        subtype: str,
        field_id: str,
        failing_item_count: int,
        validator_contract: str = (
            S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
        ),
    ) -> None:
        if (
            subtype not in self._ALLOWED_SUBTYPES
            or not isinstance(field_id, str)
            or not field_id
            or type(failing_item_count) is not int
            or failing_item_count <= 0
            or validator_contract
            not in SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REFS
        ):
            raise ValueError(
                "s3_segmented_specialist_WWC_judgment_atom_"
                "error_contract_invalid"
            )
        failure_code = "s3_owner_grade_WWC_judgment_atom_invalid"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": validator_contract,
            "segment_id": "actionable_what_would_change_tasks",
            "field_id": field_id,
            "failure_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_atom_persisted": False,
            "raw_alias_persisted": False,
            "canonical_task_persisted": False,
            "program_cell_id_persisted": False,
            "item_index_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3SegmentedSpecialistWhatWouldChangeAuthorityError(ValueError):
    """Closed, content-free WWC task authority membership failure."""

    _ALLOWED_SUBTYPES = {
        "authority_refs_not_nonempty_string_array",
        "authority_ref_outside_current_cell_closed_surface",
    }

    def __init__(self, *, subtype: str, failing_item_count: int) -> None:
        if (
            subtype not in self._ALLOWED_SUBTYPES
            or type(failing_item_count) is not int
            or failing_item_count <= 0
        ):
            raise ValueError(
                "s3_segmented_specialist_what_would_change_authority_"
                "error_contract_invalid"
            )
        failure_code = "s3_owner_grade_WWC_task_authority_invalid"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
            "segment_id": "actionable_what_would_change_tasks",
            "field_id": "what_would_change.authority_refs",
            "authority_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_ref_persisted": False,
            "ref_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3SegmentedSpecialistEpistemicStatusError(ValueError):
    """Closed, content-free cannot-infer state conflict for one claim segment."""

    _ALLOWED_SUBTYPES = {
        "cannot_infer_has_support_fact_ids",
        "cannot_infer_missing_cannot_support",
        "cannot_infer_has_support_and_missing_boundary",
    }

    def __init__(self, *, subtype: str, failing_item_count: int) -> None:
        if (
            subtype not in self._ALLOWED_SUBTYPES
            or type(failing_item_count) is not int
            or failing_item_count <= 0
        ):
            raise ValueError(
                "s3_segmented_specialist_epistemic_status_error_contract_invalid"
            )
        failure_code = "s3_owner_grade_epistemic_status_statement_conflict"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": "closed_claim_card_epistemic_status_state:v1",
            "segment_id": "owner_grade_claim_cards",
            "field_id": (
                "judgment_layer.epistemic_status_support_fact_ids_"
                "qualification_cannot_support"
            ),
            "status_subtype": subtype,
            "failing_item_count": failing_item_count,
            "raw_claim_persisted": False,
            "support_fact_ids_persisted": False,
            "cannot_support_text_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3ResearchLeadContractError(ValueError):
    """Closed, content-free failure for the bounded Research Lead v2 contract."""

    _ALLOWED_FAMILIES = {
        "parse",
        "shape",
        "cardinality",
        "text",
        "authority",
        "capacity",
        "assembly",
    }
    _ALLOWED_SUBTYPES = {
        "native_json_required",
        "json_decode_failed",
        "duplicate_key",
        "non_object",
        "top_level_keys_missing",
        "top_level_keys_unexpected",
        "item_schema_invalid",
        "below_minimum",
        "above_maximum",
        "item_not_string",
        "item_blank",
        "item_over_max_unicode_characters",
        "claim_ref_invalid",
        "task_ref_invalid",
        "provider_length_stop",
        "provider_segment_over_max_utf8_bytes",
        "deterministic_heads_invalid",
        "assembled_output_over_max_utf8_bytes",
        "canonical_validation_failed",
    }
    _ALLOWED_FIELDS = {
        "top_level",
        "cross_cell_dependencies",
        "conflict_adjudications",
        "variant_view",
        "remaining_gaps",
        "cell_heads",
        "assembled_output",
    }

    def __init__(
        self,
        *,
        failure_family: str,
        failure_subtype: str,
        field_id: str,
        failing_item_count: int,
    ) -> None:
        if (
            failure_family not in self._ALLOWED_FAMILIES
            or failure_subtype not in self._ALLOWED_SUBTYPES
            or field_id not in self._ALLOWED_FIELDS
            or type(failing_item_count) is not int
            or failing_item_count < 0
        ):
            raise ValueError("s3_research_lead_contract_error_invalid")
        failure_code = (
            f"s3_bounded_research_lead_v2_{failure_family}_{failure_subtype}"
        )
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": "closed_research_lead_output:v2",
            "failure_family": failure_family,
            "failure_subtype": failure_subtype,
            "field_id": field_id,
            "failing_item_count": failing_item_count,
            "raw_text_persisted": False,
            "ref_or_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3ResearchLeadV3ContractError(ValueError):
    """Closed, content-free failure for the bounded Research Lead v3 contract."""

    _ALLOWED_FAMILIES = S3ResearchLeadContractError._ALLOWED_FAMILIES | {
        "semantic"
    }
    _ALLOWED_SUBTYPES = S3ResearchLeadContractError._ALLOWED_SUBTYPES | {
        "involved_claim_ref_duplicate",
        "fact_presence_summary_invalid",
        "fact_presence_summary_mismatch",
        "explicit_global_fact_presence_statement_conflict",
    }
    _ALLOWED_FIELDS = S3ResearchLeadContractError._ALLOWED_FIELDS | {
        "conflict_adjudications.fact_presence_summary",
        "remaining_gap_atoms",
    }

    def __init__(
        self,
        *,
        failure_family: str,
        failure_subtype: str,
        field_id: str,
        failing_item_count: int,
    ) -> None:
        if (
            failure_family not in self._ALLOWED_FAMILIES
            or failure_subtype not in self._ALLOWED_SUBTYPES
            or field_id not in self._ALLOWED_FIELDS
            or type(failing_item_count) is not int
            or failing_item_count < 0
        ):
            raise ValueError("s3_research_lead_v3_contract_error_invalid")
        failure_code = (
            f"s3_bounded_research_lead_v3_{failure_family}_{failure_subtype}"
        )
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": "closed_research_lead_output:v3",
            "failure_family": failure_family,
            "failure_subtype": failure_subtype,
            "field_id": field_id,
            "failing_item_count": failing_item_count,
            "raw_text_persisted": False,
            "ref_or_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3MemoWriterContractError(ValueError):
    """Closed, content-free failure for the bounded Memo Writer v2 contract."""

    _ALLOWED_FAMILIES = {
        "shape",
        "cardinality",
        "text",
        "authority",
        "assembly",
        "semantic",
    }
    _ALLOWED_SUBTYPES = {
        "top_level_keys_mismatch",
        "claim_rendering_schema_invalid",
        "claim_rendering_cardinality_mismatch",
        "claim_ref_invalid",
        "claim_ref_duplicate",
        "analysis_text_blank",
        "analysis_text_over_max_unicode_characters",
        "graph_terminology_invalid",
        "canonical_validation_failed",
    }
    _ALLOWED_FIELDS = {
        "top_level",
        "claim_renderings",
        "claim_renderings.claim_id",
        "claim_renderings.analysis_text_zh_cn",
        "assembled_output",
    }

    def __init__(
        self,
        *,
        failure_family: str,
        failure_subtype: str,
        field_id: str,
        failing_item_count: int,
    ) -> None:
        if (
            failure_family not in self._ALLOWED_FAMILIES
            or failure_subtype not in self._ALLOWED_SUBTYPES
            or field_id not in self._ALLOWED_FIELDS
            or type(failing_item_count) is not int
            or failing_item_count < 0
        ):
            raise ValueError("s3_memo_writer_contract_error_invalid")
        failure_code = (
            f"s3_bounded_memo_writer_v2_{failure_family}_{failure_subtype}"
        )
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": "closed_memo_writer_output:v2",
            "failure_family": failure_family,
            "failure_subtype": failure_subtype,
            "field_id": field_id,
            "failing_item_count": failing_item_count,
            "raw_text_persisted": False,
            "ref_or_digest_persisted": False,
            "item_index_persisted": False,
            "arbitrary_key_names_persisted": False,
            "private_reasoning_persisted": False,
        }


class S3ScopedIdentityContractError(ValueError):
    """Closed, content-free failure for cross-Cell identity lineage."""

    def __init__(self, violation: ScopedIdentityViolation) -> None:
        failure_code = (
            "s3_bounded_cross_cell_scoped_identity_"
            f"{violation.failure_subtype}"
        )
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "identity_kind": violation.identity_kind,
            "failure_subtype": violation.failure_subtype,
            "failing_item_count": violation.failing_item_count,
        }


class S3VerifierStateMachineError(ValueError):
    """Closed, content-free failure for typed Verifier cross-field state."""

    _ALLOWED_SUBTYPES = {
        "pass_with_nonempty_issue_codes",
        "pass_with_nonempty_refs",
        "pass_with_repair_owner",
        "nonpass_without_issue_codes",
        "nonpass_without_refs",
        "nonpass_without_repair_owner",
        "decision_findings_state_conflict",
    }

    def __init__(
        self,
        *,
        failure_subtype: str,
        failing_layer_count: int,
        nonempty_issue_layer_count: int,
        nonempty_ref_layer_count: int,
    ) -> None:
        counts = (
            failing_layer_count,
            nonempty_issue_layer_count,
            nonempty_ref_layer_count,
        )
        if (
            failure_subtype not in self._ALLOWED_SUBTYPES
            or any(type(value) is not int or value < 0 for value in counts)
            or failing_layer_count <= 0
        ):
            raise ValueError("s3_verifier_state_machine_error_contract_invalid")
        failure_code = "s3_bounded_verifier_state_machine_invalid"
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "validator_contract": S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
            "failure_subtype": failure_subtype,
            "failing_layer_count": failing_layer_count,
            "nonempty_issue_layer_count": nonempty_issue_layer_count,
            "nonempty_ref_layer_count": nonempty_ref_layer_count,
            "raw_issue_codes_persisted": False,
            "raw_refs_persisted": False,
            "repair_owner_persisted": False,
            "raw_output_persisted": False,
            "private_reasoning_persisted": False,
        }


class BoundedAgentExecutionError(RuntimeError):
    def __init__(
        self,
        stage: str,
        *,
        usage_receipts: list[Mapping[str, Any]],
        estimated_cost_usd: float,
        failure_codes: tuple[str, ...] = (),
        output_shape: Mapping[str, Any] | None = None,
        strict_tool_parse_subtype: str | None = None,
        segmented_specialist_shape: Mapping[str, Any] | None = None,
        segmented_specialist_text: Mapping[str, Any] | None = None,
        segmented_specialist_authority: Mapping[str, Any] | None = None,
        segmented_specialist_fact_authority: Mapping[str, Any] | None = None,
        segmented_specialist_claim_fact_link: Mapping[str, Any] | None = None,
        segmented_specialist_task_claim_link: Mapping[str, Any] | None = None,
        segmented_specialist_WWC_judgment_atom: (
            Mapping[str, Any] | None
        ) = None,
        segmented_specialist_what_would_change_authority: (
            Mapping[str, Any] | None
        ) = None,
        segmented_specialist_epistemic_status: Mapping[str, Any] | None = None,
        specialist_local_assembly_capacity: Mapping[str, Any] | None = None,
        research_lead_contract: Mapping[str, Any] | None = None,
        memo_writer_contract: Mapping[str, Any] | None = None,
        scoped_identity_contract: Mapping[str, Any] | None = None,
        verifier_state_machine: Mapping[str, Any] | None = None,
        case_numeric_authority: Mapping[str, Any] | None = None,
        case_delivery_identity: Mapping[str, Any] | None = None,
        final_artifact_safety: Mapping[str, Any] | None = None,
        strict_truth_kernel: Mapping[str, Any] | None = None,
        profile_artifact_lineage: Mapping[str, Any] | None = None,
        fact_candidate_pool: Mapping[str, Any] | None = None,
        provider_output_captures: list[Mapping[str, Any]] | None = None,
        local_fact_receipts: list[Mapping[str, Any]] | None = None,
        observed_counts: Mapping[str, Any] | None = None,
        completed_node_receipts: list[Mapping[str, Any]] | None = None,
        failure_contract_ref: str | None = None,
        lifecycle_phase: str | None = None,
    ) -> None:
        if sum(
            telemetry is not None
            for telemetry in (
                strict_tool_parse_subtype,
                segmented_specialist_shape,
                segmented_specialist_text,
                segmented_specialist_authority,
                segmented_specialist_fact_authority,
                segmented_specialist_claim_fact_link,
                segmented_specialist_task_claim_link,
                segmented_specialist_WWC_judgment_atom,
                segmented_specialist_what_would_change_authority,
                segmented_specialist_epistemic_status,
                specialist_local_assembly_capacity,
                research_lead_contract,
                memo_writer_contract,
                scoped_identity_contract,
                verifier_state_machine,
                case_numeric_authority,
                case_delivery_identity,
                final_artifact_safety,
                strict_truth_kernel,
                profile_artifact_lineage,
                fact_candidate_pool,
            )
        ) > 1:
            raise ValueError("bounded_agent_failure_telemetry_family_ambiguous")
        super().__init__("bounded_agent_execution_failed")
        self.stage = stage
        self.provider_output_captures = [
            dict(row) for row in (provider_output_captures or ())
        ]
        self.failure_observation = {
            "stage": stage,
            "failure_codes": list(failure_codes),
            "observed_counts": (
                {
                    str(key): int(value)
                    for key, value in observed_counts.items()
                }
                if observed_counts is not None
                else {
                    "model_calls": len(usage_receipts),
                    "provider_calls": len(usage_receipts),
                    "network_calls": len(usage_receipts),
                    "source_network_calls": 0,
                    "external_tool_calls": 0,
                }
            ),
            "estimated_cost_usd": round(estimated_cost_usd, 8),
            "usage_receipts": [dict(row) for row in usage_receipts],
            "private_reasoning_persisted": False,
            "raw_provider_response_persisted": False,
        }
        if local_fact_receipts:
            self.failure_observation["local_fact_receipts"] = [
                dict(row) for row in local_fact_receipts
            ]
        if failure_contract_ref is not None:
            self.failure_observation.update(
                {
                    "contract_ref": failure_contract_ref,
                    "lifecycle_phase": str(lifecycle_phase or stage),
                    "failure_code": (
                        failure_codes[0]
                        if failure_codes
                        else "s3_bounded_post_provider_failure"
                    ),
                    "completed_node_receipts": [
                        dict(row)
                        for row in (completed_node_receipts or ())
                    ],
                }
            )
        if output_shape is not None:
            self.failure_observation["output_shape"] = dict(output_shape)
        if strict_tool_parse_subtype in {
            "json_decode_error",
            "duplicate_key",
            "non_object",
        }:
            self.failure_observation["failure_telemetry"] = {
                "strict_tool_arguments": {
                    "parser_contract": (
                        "native_json_object_no_fence_no_duplicate_keys"
                    ),
                    "parse_subtype": strict_tool_parse_subtype,
                    "raw_arguments_persisted": False,
                    "argument_digest_persisted": False,
                    "argument_length_persisted": False,
                }
            }
        if segmented_specialist_shape is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_shape": dict(segmented_specialist_shape)
            }
        if segmented_specialist_text is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_text": dict(segmented_specialist_text)
            }
        if segmented_specialist_authority is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_authority": dict(
                    segmented_specialist_authority
                )
            }
        if segmented_specialist_fact_authority is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_fact_authority": dict(
                    segmented_specialist_fact_authority
                )
            }
        if segmented_specialist_claim_fact_link is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_claim_fact_link": dict(
                    segmented_specialist_claim_fact_link
                )
            }
        if segmented_specialist_task_claim_link is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_task_claim_link": dict(
                    segmented_specialist_task_claim_link
                )
            }
        if segmented_specialist_WWC_judgment_atom is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_WWC_judgment_atom": dict(
                    segmented_specialist_WWC_judgment_atom
                )
            }
        if segmented_specialist_what_would_change_authority is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_what_would_change_authority": dict(
                    segmented_specialist_what_would_change_authority
                )
            }
        if segmented_specialist_epistemic_status is not None:
            self.failure_observation["failure_telemetry"] = {
                "segmented_specialist_epistemic_status": dict(
                    segmented_specialist_epistemic_status
                )
            }
        if specialist_local_assembly_capacity is not None:
            self.failure_observation["failure_telemetry"] = {
                "specialist_local_assembly_capacity": dict(
                    specialist_local_assembly_capacity
                )
            }
        if research_lead_contract is not None:
            self.failure_observation["failure_telemetry"] = {
                "research_lead_contract": dict(research_lead_contract)
            }
        if memo_writer_contract is not None:
            self.failure_observation["failure_telemetry"] = {
                "memo_writer_contract": dict(memo_writer_contract)
            }
        if scoped_identity_contract is not None:
            self.failure_observation["failure_telemetry"] = {
                "scoped_identity_contract": dict(scoped_identity_contract)
            }
        if verifier_state_machine is not None:
            self.failure_observation["failure_telemetry"] = {
                "verifier_state_machine": dict(verifier_state_machine)
            }
        if case_numeric_authority is not None:
            self.failure_observation["failure_telemetry"] = {
                "case_numeric_authority": dict(case_numeric_authority)
            }
        if case_delivery_identity is not None:
            self.failure_observation["failure_telemetry"] = {
                "case_delivery_identity": dict(case_delivery_identity)
            }
        if final_artifact_safety is not None:
            self.failure_observation["failure_telemetry"] = {
                "final_artifact_safety": dict(
                    final_artifact_safety
                )
            }
        if strict_truth_kernel is not None:
            self.failure_observation["failure_telemetry"] = {
                "registered_observation": registered_failure_observation(
                    "strict_truth_kernel",
                    strict_truth_kernel,
                )
            }
        if profile_artifact_lineage is not None:
            self.failure_observation["failure_telemetry"] = {
                "profile_artifact_lineage": dict(
                    profile_artifact_lineage
                )
            }
        if fact_candidate_pool is not None:
            self.failure_observation["failure_telemetry"] = {
                "fact_candidate_pool": dict(fact_candidate_pool)
            }


class S3SpecialistLocalAssemblyCapacityError(ValueError):
    """Typed, content-free Specialist capacity failure."""

    failure_code = "s3_bounded_specialist_output_byte_budget_exceeded"

    def __init__(self, telemetry: Mapping[str, Any]) -> None:
        super().__init__(self.failure_code)
        self.telemetry = dict(telemetry)


def assert_specialist_validated_segment_union_capacity(
    *,
    capacity: SpecialistLocalAssemblyCapacity,
    observed_validated_segment_utf8_bytes: Sequence[int],
    observed_whole_union_utf8_bytes: int,
) -> None:
    """Fail closed while retaining only safe byte counts and capacity limits."""

    observed = tuple(observed_validated_segment_utf8_bytes)
    phase = (
        "post_local_expansion_segment_validation"
        if any(
            value
            > capacity.post_local_expansion_segment_limit_utf8_bytes
            for value in observed
        )
        else "validated_segment_union_assembly"
    )
    if (
        any(
            value
            > capacity.post_local_expansion_segment_limit_utf8_bytes
            for value in observed
        )
        or observed_whole_union_utf8_bytes
        > capacity.whole_union_limit_utf8_bytes
    ):
        raise S3SpecialistLocalAssemblyCapacityError(
            capacity.failure_telemetry(
                observed_validated_segment_utf8_bytes=observed,
                observed_whole_union_utf8_bytes=(
                    observed_whole_union_utf8_bytes
                ),
                failure_phase=phase,
            )
        )


def build_s3_post_provider_failure_error(
    *,
    lifecycle_phase: str,
    failure_code: str,
    execution_observation: Mapping[str, Any],
    provider_output_captures: tuple[Mapping[str, Any], ...]
    | list[Mapping[str, Any]],
    profile_artifact_lineage: Mapping[str, Any] | None = None,
) -> BoundedAgentExecutionError:
    """Materialize one safe typed failure after provider work has completed."""

    receipts = [
        dict(row)
        for row in execution_observation.get("usage_receipts", ())
        if isinstance(row, Mapping)
    ]
    counts = execution_observation.get("observed_counts")
    node_receipts = [
        dict(row)
        for row in execution_observation.get("completed_node_receipts", ())
        if isinstance(row, Mapping)
    ]
    normalized_counts = (
        dict(counts) if isinstance(counts, Mapping) else {}
    )
    for key in ("model_calls", "provider_calls", "network_calls"):
        normalized_counts[key] = len(receipts)
    normalized_counts.setdefault("source_network_calls", 0)
    normalized_counts.setdefault("external_tool_calls", 0)
    return BoundedAgentExecutionError(
        lifecycle_phase,
        usage_receipts=receipts,
        estimated_cost_usd=sum(
            float(row.get("estimated_cost_usd") or 0.0)
            for row in receipts
        ),
        failure_codes=(failure_code,),
        provider_output_captures=[
            dict(row)
            for row in provider_output_captures
            if isinstance(row, Mapping)
        ],
        local_fact_receipts=[
            dict(row)
            for row in execution_observation.get(
                "local_fact_receipts", ()
            )
            if isinstance(row, Mapping)
        ],
        observed_counts=normalized_counts,
        completed_node_receipts=node_receipts,
        failure_contract_ref=S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF,
        lifecycle_phase=lifecycle_phase,
        profile_artifact_lineage=profile_artifact_lineage,
    )


def _upgrade_s3_post_provider_failure_error(
    error: BoundedAgentExecutionError,
    lifecycle: Mapping[str, Any],
) -> None:
    """Add the shared lifecycle ledger without dropping typed telemetry."""

    observation = error.failure_observation
    prior_receipts = [
        dict(row)
        for row in lifecycle.get("usage_receipts", ())
        if isinstance(row, Mapping)
    ]
    error_receipts = [
        dict(row)
        for row in observation.get("usage_receipts", ())
        if isinstance(row, Mapping)
    ]
    receipts_by_call = {
        (
            str(row.get("call_id") or ""),
            str(row.get("stage") or ""),
        ): row
        for row in (*prior_receipts, *error_receipts)
    }
    receipts = list(receipts_by_call.values())
    prior_captures = [
        dict(row)
        for row in lifecycle.get("provider_output_captures", ())
        if isinstance(row, Mapping)
    ]
    error_captures = [
        dict(row)
        for row in error.provider_output_captures
        if isinstance(row, Mapping)
    ]
    captures_by_call = {
        (
            str(row.get("call_id") or ""),
            str(row.get("stage") or ""),
        ): row
        for row in (*prior_captures, *error_captures)
    }
    counts = dict(lifecycle.get("observed_counts") or {})
    for key in ("model_calls", "provider_calls", "network_calls"):
        counts[key] = len(receipts)
    counts.setdefault("source_network_calls", 0)
    counts.setdefault("external_tool_calls", 0)
    failure_codes = list(observation.get("failure_codes") or ())
    phase = str(
        lifecycle.get("lifecycle_phase")
        or observation.get("stage")
        or error.stage
    )
    observation.update(
        {
            "contract_ref": (
                S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF
            ),
            "lifecycle_phase": phase,
            "failure_code": (
                failure_codes[0]
                if failure_codes
                else str(
                    lifecycle.get("failure_code")
                    or "s3_bounded_post_provider_failure"
                )
            ),
            "observed_counts": counts,
            "estimated_cost_usd": round(
                sum(
                    float(row.get("estimated_cost_usd") or 0.0)
                    for row in receipts
                ),
                8,
            ),
            "usage_receipts": receipts,
            "completed_node_receipts": [
                dict(row)
                for row in lifecycle.get(
                    "completed_node_receipts", ()
                )
                if isinstance(row, Mapping)
            ],
        }
    )
    prior_local_fact_receipts = [
        dict(row)
        for row in lifecycle.get("local_fact_receipts", ())
        if isinstance(row, Mapping)
    ]
    error_local_fact_receipts = [
        dict(row)
        for row in observation.get("local_fact_receipts", ())
        if isinstance(row, Mapping)
    ]
    local_fact_receipts_by_digest = {
        str(row.get("receipt_digest") or ""): row
        for row in (
            *prior_local_fact_receipts,
            *error_local_fact_receipts,
        )
    }
    local_fact_receipts = list(
        local_fact_receipts_by_digest.values()
    )
    if local_fact_receipts:
        observation["local_fact_receipts"] = local_fact_receipts
    error.provider_output_captures = list(captures_by_call.values())
    runtime_bindings = {
        json.dumps(
            row["runtime_contract_family_binding"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in error.provider_output_captures
        if isinstance(row.get("runtime_contract_family_binding"), Mapping)
    }
    if len(runtime_bindings) > 1:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_failure_capture_binding_drift"
        )
    if runtime_bindings:
        observed_binding = json.loads(next(iter(runtime_bindings)))
        binding = (
            load_fin_0_1_2_s3_runtime_contract_binding()
            if observed_binding.get("binding_ref")
            == load_fin_0_1_2_s3_runtime_contract_binding().binding_ref
            else load_fin_0_1_2_runtime_contract_binding()
        )
        binding.assert_admission_binding(
            binding_ref=observed_binding.get("binding_ref"),
            source_digest=observed_binding.get("source_digest"),
        )
        observation["runtime_contract_family_binding"] = {
            "binding_ref": binding.binding_ref,
            "source_digest": binding.source_digest,
            "contract_id": binding.contract_id,
            "contract_version": binding.contract_version,
            "consumer_binding": binding.consumer_receipt("typed_failure"),
        }


def build_bounded_agent_input_pack(
    service: P36LocalResearchService,
    case_id: str,
    principal: CasePrincipal,
) -> BoundedAgentInputPack:
    """Compile exact-input parity for the agent run and deterministic baseline."""

    source = service.preview(case_id, principal)
    analysis = service.analysis_preview(case_id, principal)
    if analysis.get("source_preview_digest") != source.get("preview_digest"):
        raise ValueError("bounded_input_source_preview_digest_mismatch")
    cells = [
        row
        for row in source.get("cells", ())
        if isinstance(row, Mapping) and row.get("evidence_role") == "demand_signal"
    ]
    judgments = [
        row
        for row in analysis.get("judgments", ())
        if isinstance(row, Mapping) and row.get("evidence_role") == "demand_signal"
    ]
    sections = [
        row
        for row in (analysis.get("workpaper") or {}).get("sections", ())
        if isinstance(row, Mapping) and row.get("evidence_role") == "demand_signal"
    ]
    if len(cells) != 1 or len(judgments) != 1 or len(sections) != 1:
        raise ValueError("bounded_input_single_cell_baseline_required")
    cell = dict(cells[0])
    candidates = tuple(dict(row) for row in cell.get("candidates", ()))
    if not candidates:
        raise ValueError("bounded_input_local_official_candidate_required")
    if any(
        not str(row.get("citation_url") or "").startswith("https://www.sec.gov/")
        or row.get("promotion_status") != "candidate_not_promoted"
        for row in candidates
    ):
        raise ValueError("bounded_input_candidate_authority_or_promotion_invalid")
    baseline = {
        "run_kind": "deterministic_paired_baseline",
        "analysis_digest": analysis["analysis_digest"],
        "judgment": dict(judgments[0]),
        "workpaper_section": dict(sections[0]),
        "writer_sections": [
            dict(row)
            for row in (analysis.get("writer") or {}).get("sections", ())
            if isinstance(row, Mapping) and row.get("evidence_role") == "demand_signal"
        ],
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "external_tool_calls": 0,
        },
    }
    source_boundary = {
        "retrieval": "repo_local_official_first",
        "source_network_calls_allowed": False,
        "candidate_is_evidence": False,
        "writer_source_or_tool_calls": 0,
    }
    digest_payload = {
        "case_id": source["case_id"],
        "case_version": source["case_version"],
        "query": source["query"],
        "as_of": source["as_of"],
        "company": "NVDA",
        "program_cell_id": "demand_authenticity_and_sustainability",
        "evidence_role": "demand_signal",
        "source_preview_digest": source["preview_digest"],
        "deterministic_analysis_digest": analysis["analysis_digest"],
        "decision_question": cell["decision_question"],
        "candidate_digests": [canonical_digest(row) for row in candidates],
        "deterministic_baseline_digest": canonical_digest(baseline),
        "source_boundary": source_boundary,
    }
    return BoundedAgentInputPack(
        case_id=str(source["case_id"]),
        case_version=int(source["case_version"]),
        query=str(source["query"]),
        as_of=str(source["as_of"]),
        company="NVDA",
        program_cell_id="demand_authenticity_and_sustainability",
        evidence_role="demand_signal",
        source_preview_digest=str(source["preview_digest"]),
        deterministic_analysis_digest=str(analysis["analysis_digest"]),
        decision_question=str(cell["decision_question"]),
        candidates=candidates,
        deterministic_baseline=baseline,
        source_boundary=source_boundary,
        input_digest=canonical_digest(digest_payload),
    )


def _s3_rows_for_cell(payload: Mapping[str, Any], cell_id: str) -> dict[str, Any]:
    scoped: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(value, (list, tuple)):
            continue
        rows = [
            dict(row)
            for row in value
            if isinstance(row, Mapping) and row.get("program_cell_id") == cell_id
        ]
        if rows:
            scoped[str(key)] = rows
    return scoped


def _s3_collect_values_for_keys(value: Any, keys: frozenset[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in keys:
                if isinstance(item, str) and item:
                    found.add(item)
                elif isinstance(item, (list, tuple)):
                    found.update(str(row) for row in item if str(row))
            found.update(_s3_collect_values_for_keys(item, keys))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_s3_collect_values_for_keys(item, keys))
    return found


def build_s3_three_cell_bounded_agent_input_pack(
    service: P36LocalResearchService,
    case_id: str,
    principal: CasePrincipal,
    *,
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    financial_pack: Mapping[str, Any],
    graph_pack: Mapping[str, Any],
    judgment_pack: Mapping[str, Any],
    presentation_pack: Mapping[str, Any],
) -> S3ThreeCellBoundedAgentInputPack:
    """Compile blind, cell-isolated live input while retaining T02-T07 lineage."""

    source = service.preview(case_id, principal)
    identity_fields = ("case_id", "work_unit_id", "attempt_id", "research_run_id")
    packs = {
        "runtime_plan": dict(runtime_plan),
        "evidence_route_plan": dict(evidence_route_plan),
        "financial_pack": dict(financial_pack),
        "graph_pack": dict(graph_pack),
        "judgment_contract": dict(judgment_pack),
        "presentation_contract": dict(presentation_pack),
    }
    for field in identity_fields:
        values = {str(row.get(field) or "") for row in packs.values()}
        if len(values) != 1 or "" in values:
            raise ValueError(f"s3_bounded_input_{field}_lineage_mismatch")
    if str(runtime_plan.get("case_id")) != case_id:
        raise ValueError("s3_bounded_input_case_scope_mismatch")
    decision_surface_ref = str(runtime_plan.get("decision_surface_contract_ref") or "")
    if not decision_surface_ref or any(
        str(row.get("decision_surface_contract_ref") or "") != decision_surface_ref
        for row in packs.values()
    ):
        raise ValueError("s3_bounded_input_decision_surface_lineage_mismatch")
    branch_rows = {
        str(row.get("program_cell_id")): dict(row)
        for row in runtime_plan.get("cell_branches", ())
        if isinstance(row, Mapping)
    }
    route_rows = {
        str(row.get("program_cell_id")): dict(row)
        for row in evidence_route_plan.get("cell_routes", ())
        if isinstance(row, Mapping)
    }
    fundamental_rows = {
        str(row.get("program_cell_id")): dict(row)
        for row in financial_pack.get("fundamental_decision_cells", ())
        if isinstance(row, Mapping)
    }
    graph_rows = {
        str(row.get("program_cell_id")): dict(row)
        for row in graph_pack.get("decision_cells", ())
        if isinstance(row, Mapping)
    }
    if any(
        set(rows) != set(S3_THREE_CELL_PROGRAM_CELL_IDS)
        for rows in (branch_rows, route_rows, fundamental_rows, graph_rows)
    ):
        raise ValueError("s3_bounded_input_exact_three_cell_lineage_required")

    selected_financial_rows = [
        dict(row)
        for row in financial_pack.get("selected_financial_rows", ())
        if isinstance(row, Mapping)
    ]
    derived_metrics = [
        dict(row)
        for row in financial_pack.get("derived_metrics", ())
        if isinstance(row, Mapping)
    ]
    cell_inputs: list[dict[str, Any]] = []
    for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS:
        fundamental = fundamental_rows[cell_id]
        numeric_refs = set(map(str, fundamental.get("selected_financial_row_refs", ())))
        numeric_refs.update(map(str, fundamental.get("derived_metric_refs", ())))
        numeric_payload = {
            "fundamental_decision_cell": fundamental,
            "selected_financial_rows": [
                row for row in selected_financial_rows if row.get("financial_row_id") in numeric_refs
            ],
            "derived_metrics": [
                row for row in derived_metrics if row.get("derived_metric_id") in numeric_refs
            ],
        }
        evidence_input = route_rows[cell_id]
        graph_input = {
            **_s3_rows_for_cell(graph_pack, cell_id),
            "decision_cell": graph_rows[cell_id],
        }
        accepted_evidence_refs = _s3_collect_values_for_keys(
            (evidence_input, graph_input), frozenset({"accepted_evidence_refs"})
        )
        candidate_refs = _s3_collect_values_for_keys(
            evidence_input,
            frozenset({"candidate_id", "source_candidate_id", "candidate_refs"}),
        )
        graph_context_refs = _s3_collect_values_for_keys(
            graph_input,
            frozenset(
                {
                    "graph_edge_projection_ref",
                    "product_industry_projection_input_ref",
                    "market_context_ref",
                    "risk_context_ref",
                    "source_followup_refs",
                }
            ),
        )
        cell_inputs.append(
            {
                "program_cell_id": cell_id,
                "runtime_branch": branch_rows[cell_id],
                "role_contexts": [
                    dict(row)
                    for row in runtime_plan.get("role_context_plans", ())
                    if isinstance(row, Mapping)
                    and row.get("program_cell_id") == cell_id
                    and row.get("target_node") in {"domain_specialist", "evidence_operator"}
                ],
                "evidence_input": evidence_input,
                "numeric_input": numeric_payload,
                "graph_context_input": graph_input,
                "authority_refs": {
                    "accepted_evidence_refs": sorted(accepted_evidence_refs),
                    "numeric_refs": sorted(numeric_refs),
                    "candidate_refs_not_evidence": sorted(candidate_refs),
                    "graph_context_refs_not_evidence": sorted(graph_context_refs),
                },
            }
        )

    lineage = {
        "T02_runtime_plan": {
            "version_ref": str(runtime_plan["runtime_plan_version_ref"]),
            "digest": str(runtime_plan["runtime_plan_digest"]),
        },
        "T03_evidence_route_plan": {
            "version_ref": str(evidence_route_plan["evidence_route_plan_version_ref"]),
            "digest": str(evidence_route_plan["evidence_route_plan_digest"]),
        },
        "T04_financial_pack": {
            "version_ref": str(financial_pack["financial_pack_version_ref"]),
            "digest": str(financial_pack["financial_pack_digest"]),
        },
        "T05_graph_pack": {
            "version_ref": str(graph_pack["graph_pack_version_ref"]),
            "digest": str(graph_pack["graph_pack_digest"]),
        },
        "T06_judgment_contract": {
            "version_ref": str(judgment_pack["judgment_pack_version_ref"]),
            "digest": str(judgment_pack["judgment_pack_digest"]),
        },
        "T07_presentation_contract": {
            "version_ref": str(presentation_pack["presentation_pack_version_ref"]),
            "digest": str(presentation_pack["presentation_pack_digest"]),
        },
    }
    lead_contract = {
        "contract_ref": str(judgment_pack["judgment_pack_contract_ref"]),
        "required_specialist_count": 3,
        "required_program_cell_ids": list(S3_THREE_CELL_PROGRAM_CELL_IDS),
        "requires_cross_cell_dependencies": True,
        "requires_conflict_adjudication": True,
        "deterministic_judgment_body_exposed_to_agent": False,
    }
    writer_contract = {
        "contract_ref": str(presentation_pack["presentation_pack_contract_ref"]),
        "required_section_count": 3,
        "consumes_only_cross_cell_lead_and_specialist_heads": True,
        "source_authority": False,
        "tool_authority": False,
        "deterministic_report_body_exposed_to_agent": False,
    }
    verifier_contract = {
        "contract_ref": str(presentation_pack["presentation_pack_contract_ref"]),
        "required_layers": list(S3_FOUR_LAYER_VERIFIER_LAYERS),
        "binds_exact_input_and_output_digests": True,
        "machine_verifier_is_human_acceptance": False,
    }
    paired_baseline_contract = {
        "contract_ref": "fin01.s3.paired_three_cell_deterministic_baseline:v1",
        "baseline_profile_ref": "fin01.execution_profile.p36_local_deterministic:v1",
        "shared_input_head_digest": canonical_digest((decision_surface_ref,)),
        "runs_and_artifacts_must_be_distinct": True,
        "automatic_fallback_allowed": False,
        "baseline_output_body_exposed_to_agent": False,
    }
    hard_boundaries = {
        "candidate_is_evidence": False,
        "graph_edge_is_evidence": False,
        "numeric_requires_exact_program": True,
        "writer_source_or_tool_calls": 0,
        "source_network_calls_allowed": False,
        "external_tool_calls_allowed": False,
        "live_business_case_head_writes_allowed": False,
    }
    digest_payload = {
        "input_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF,
        "execution_profile_version_ref": S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        "case_id": str(source["case_id"]),
        "case_version": int(source["case_version"]),
        "query": str(source["query"]),
        "as_of": str(source["as_of"]),
        "decision_surface_contract_ref": decision_surface_ref,
        "program_cell_ids": list(S3_THREE_CELL_PROGRAM_CELL_IDS),
        "lineage": lineage,
        "cell_inputs": cell_inputs,
        "lead_contract": lead_contract,
        "writer_contract": writer_contract,
        "verifier_contract": verifier_contract,
        "paired_baseline_contract": paired_baseline_contract,
        "hard_boundaries": hard_boundaries,
    }
    return S3ThreeCellBoundedAgentInputPack(
        case_id=str(source["case_id"]),
        case_version=int(source["case_version"]),
        query=str(source["query"]),
        as_of=str(source["as_of"]),
        decision_surface_contract_ref=decision_surface_ref,
        input_head_digest=canonical_digest((decision_surface_ref,)),
        lineage=lineage,
        cell_inputs=tuple(cell_inputs),
        lead_contract=lead_contract,
        writer_contract=writer_contract,
        verifier_contract=verifier_contract,
        paired_baseline_contract=paired_baseline_contract,
        hard_boundaries=hard_boundaries,
        input_digest=canonical_digest(digest_payload),
    )


def build_s4_case_pack_bounded_agent_input_fixture(
    binding: S4CaseRuntimeBinding,
    *,
    case_id: str,
    case_version: int = 1,
    query: str,
) -> S3ThreeCellBoundedAgentInputPack:
    """Compile one fact-empty S4 Case Pack into the existing three-Cell input."""

    consumer_injections = {
        consumer_id: consume_s4_case_runtime_binding(
            binding, consumer_id
        ).model_dump(mode="json")
        for consumer_id in S4_RUNTIME_CONSUMER_IDS
    }
    cell_contracts = {
        str(row["program_cell_id"]): dict(row)
        for row in binding.program_cell_contracts
    }
    cell_inputs: list[dict[str, Any]] = []
    for cell_id in binding.program_cell_ids:
        contract = cell_contracts[cell_id]
        cell_inputs.append(
            {
                "program_cell_id": cell_id,
                "runtime_branch": {
                    "program_cell_id": cell_id,
                    "owner_role": contract["owner_role"],
                    "evidence_role": contract["required_evidence_roles"][0],
                    "decision_question": contract["decision_question"],
                    "mandatory_judgment_chain": contract[
                        "mandatory_judgment_chain"
                    ],
                    "stop_rule": contract["stop_rule"],
                    "what_would_change": contract[
                        "what_would_change_targets"
                    ],
                    "branch_state": "deterministic_S4_case_fixture",
                    "observation": "fact_empty_contract_fixture",
                },
                "role_contexts": [
                    {
                        "target_node": "domain_specialist",
                        "authority": {
                            "case_ticker": binding.case_ticker,
                            "issuer_identifier": binding.issuer_identifier,
                            "case_identity_namespace": (
                                binding.case_identity_namespace
                            ),
                            "source_or_numeric_rows_admitted": 0,
                        },
                    },
                    {
                        "target_node": "evidence_operator",
                        "authority": {
                            "local_source_routes": list(
                                binding.local_source_routes_by_cell[cell_id]
                            ),
                            "network_execution_authorized": False,
                        },
                    },
                ],
                "evidence_input": {
                    "program_cell_id": cell_id,
                    "route_outcome": (
                        "typed_gap_source_routes_resolved_not_executed"
                    ),
                    "candidate_bundle": {"candidates": []},
                    "promotion_assessment": {
                        "decision": "no_candidate_or_evidence_in_T03_fixture",
                        "candidate_refs": [],
                        "context_refs": [],
                        "rejected_refs": [],
                        "typed_gap_codes": contract[
                            "typed_cannot_infer_codes"
                        ],
                        "accepted_evidence_refs": [],
                    },
                    "sourcehunter_boundary": {
                        "status": "not_executed",
                        "trigger_reason": "T03_zero_paid_call_fixture",
                        "boundary_contract_ref": (
                            binding.source_authority_policy[
                                "source_policy_ref"
                            ]
                        ),
                        "source_followup_request_ref": None,
                        "exact_network_admission_required": True,
                        "network_execution_authorized": False,
                        "external_tool_execution_authorized": False,
                    },
                    "local_source_routes": list(
                        binding.local_source_routes_by_cell[cell_id]
                    ),
                },
                "numeric_input": {
                    "fundamental_decision_cell": {
                        "program_cell_id": cell_id,
                        "availability": "typed_cannot_infer",
                        "typed_cannot_infer": contract[
                            "typed_cannot_infer_codes"
                        ],
                        "support_boundary": contract["stop_rule"],
                        "specialist_input_eligible": True,
                        "narrative_fill_authorized": False,
                    },
                    "selected_financial_rows": [],
                    "derived_metrics": [],
                    "numeric_policy": binding.numeric_policy,
                },
                "graph_context_input": {
                    "decision_cell": {
                        "program_cell_id": cell_id,
                        "typed_gaps": contract[
                            "typed_cannot_infer_codes"
                        ],
                    },
                    "product_industry_inputs": [],
                    "skill_contracts": [],
                    "graph_edges": [],
                    "market_price_in_contexts": [],
                    "risk_contexts": [],
                    "graph_policy": binding.graph_policy,
                },
                "authority_refs": {
                    "accepted_evidence_refs": [],
                    "numeric_refs": [],
                    "candidate_refs_not_evidence": [],
                    "graph_context_refs_not_evidence": [],
                },
                "s4_case_method": {
                    "runtime_binding_digest": (
                        binding.runtime_binding_digest
                    ),
                    "case_ticker": binding.case_ticker,
                    "issuer_identifier": binding.issuer_identifier,
                    "case_identity_namespace": (
                        binding.case_identity_namespace
                    ),
                    "case_profile_ref": binding.case_profile_ref,
                    "method_id": binding.method_id,
                    "program_cell_contract": contract,
                    "judgment_atom_schema": (
                        binding.judgment_atom_contract
                    ),
                },
            }
        )

    fixture_source_payload = {
        "contract_ref": S4_SOURCE_GROUNDED_INPUT_CONTRACT_REF,
        "case_ticker": binding.case_ticker,
        "issuer_identifier": binding.issuer_identifier,
        "as_of": binding.as_of,
        "fixture_only": True,
        "fact_rows_admitted": 0,
        "source_network_calls": 0,
    }
    fixture_source_payload["source_pack_digest"] = canonical_digest(
        fixture_source_payload
    )
    runtime_payload = {
        "binding": binding.model_dump(mode="json"),
        "source_grounded_input": fixture_source_payload,
        "consumer_injections": consumer_injections,
        "node_consumption_required": [
            "domain_specialist",
            "research_lead",
            "memo_writer",
            "verifier",
            "workbench",
        ],
        "paid_execution_authorized": False,
    }
    lineage = {
        "S4_T02_case_pack": {
            "version_ref": binding.case_profile_ref,
            "digest": binding.case_pack_sha256,
        },
        "S4_T02_method_contract": {
            "version_ref": binding.method_contract_ref,
            "digest": binding.method_contract_sha256,
        },
        "S4_T03_runtime_binding": {
            "version_ref": binding.contract_ref,
            "digest": binding.runtime_binding_digest,
        },
        "S4_T04_source_grounded_input": {
            "version_ref": fixture_source_payload["contract_ref"],
            "digest": fixture_source_payload["source_pack_digest"],
        },
    }
    lead_contract = {
        "contract_ref": binding.method_contract_ref,
        "method_id": binding.method_id,
        "required_specialist_count": 3,
        "required_program_cell_ids": list(binding.program_cell_ids),
        "requires_cross_cell_dependencies": True,
        "requires_conflict_adjudication": True,
        "judgment_atom_schema_ref": (
            binding.judgment_atom_contract.get("schema_ref")
            or "fin01.s4.case_local_judgment_atom:v1"
        ),
        "deterministic_judgment_body_exposed_to_agent": False,
    }
    writer_contract = {
        "contract_ref": binding.method_contract_ref,
        "method_id": binding.method_id,
        "required_section_count": 3,
        "required_program_cell_ids": list(binding.program_cell_ids),
        "consumes_only_cross_cell_lead_and_specialist_heads": True,
        "source_authority": False,
        "tool_authority": False,
        "deterministic_report_body_exposed_to_agent": False,
    }
    verifier_contract = {
        "contract_ref": binding.method_contract_ref,
        "method_id": binding.method_id,
        "required_layers": list(S3_FOUR_LAYER_VERIFIER_LAYERS),
        "binds_exact_input_and_output_digests": True,
        "machine_verifier_is_human_acceptance": False,
    }
    paired_baseline_contract = {
        "contract_ref": "fin01.s4.paired_case_local_deterministic_baseline:v1",
        "baseline_profile_ref": (
            "fin01.execution_profile.p36_local_deterministic:v1"
        ),
        "shared_input_head_digest": canonical_digest(
            (
                binding.runtime_binding_digest,
                case_id,
                case_version,
            )
        ),
        "runs_and_artifacts_must_be_distinct": True,
        "automatic_fallback_allowed": False,
        "baseline_output_body_exposed_to_agent": False,
    }
    hard_boundaries = {
        "candidate_is_evidence": False,
        "graph_edge_is_evidence": False,
        "numeric_requires_exact_program": True,
        "writer_source_or_tool_calls": 0,
        "source_network_calls_allowed": False,
        "external_tool_calls_allowed": False,
        "live_business_case_head_writes_allowed": False,
        "cross_case_fact_reuse_allowed": False,
    }
    digest_payload = {
        "input_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF,
        "execution_profile_version_ref": S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        "case_id": case_id,
        "case_version": case_version,
        "query": query,
        "as_of": binding.as_of,
        "company": binding.case_ticker,
        "decision_surface_contract_ref": binding.case_profile_ref,
        "program_cell_ids": list(binding.program_cell_ids),
        "lineage": lineage,
        "cell_inputs": cell_inputs,
        "lead_contract": lead_contract,
        "writer_contract": writer_contract,
        "verifier_contract": verifier_contract,
        "paired_baseline_contract": paired_baseline_contract,
        "hard_boundaries": hard_boundaries,
        "s4_case_runtime": runtime_payload,
    }
    return S3ThreeCellBoundedAgentInputPack(
        case_id=case_id,
        case_version=case_version,
        query=query,
        as_of=binding.as_of,
        company=binding.case_ticker,
        decision_surface_contract_ref=binding.case_profile_ref,
        input_head_digest=paired_baseline_contract[
            "shared_input_head_digest"
        ],
        lineage=lineage,
        cell_inputs=tuple(cell_inputs),
        lead_contract=lead_contract,
        writer_contract=writer_contract,
        verifier_contract=verifier_contract,
        paired_baseline_contract=paired_baseline_contract,
        hard_boundaries=hard_boundaries,
        s4_case_runtime=runtime_payload,
        input_digest=canonical_digest(digest_payload),
    )


def build_s4_source_grounded_bounded_agent_input(
    binding: S4CaseRuntimeBinding,
    source_pack: S4SourceGroundedInputPack,
    *,
    case_id: str,
    decision_surface_contract_ref: str,
    case_version: int = 1,
    query: str,
    research_profile_overlay: (
        S4CaseRuntimeResearchProfileOverlay | None
    ) = None,
) -> S3ThreeCellBoundedAgentInputPack:
    """Compile issuer-bound S4 facts into the shared three-Cell contract."""

    if (
        source_pack.case_ticker != binding.case_ticker
        or source_pack.issuer_identifier != binding.issuer_identifier
        or source_pack.as_of != binding.as_of
        or not decision_surface_contract_ref.strip()
    ):
        raise ValueError("s4_source_grounded_input_identity_mismatch")
    consumer_injections = {
        consumer_id: consume_s4_case_runtime_binding(
            binding, consumer_id
        ).model_dump(mode="json")
        for consumer_id in S4_RUNTIME_CONSUMER_IDS
    }
    cell_contracts = {
        str(row["program_cell_id"]): dict(row)
        for row in binding.program_cell_contracts
    }

    def _rows_for(
        rows: tuple[dict[str, Any], ...], cell_id: str
    ) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in rows
            if cell_id in tuple(row.get("program_cell_ids") or ())
        ]

    cell_inputs: list[dict[str, Any]] = []
    for cell_id in binding.program_cell_ids:
        contract = cell_contracts[cell_id]
        evidence_rows = _rows_for(source_pack.evidence_rows, cell_id)
        numeric_rows = _rows_for(source_pack.numeric_rows, cell_id)
        derived_rows = _rows_for(source_pack.derived_metrics, cell_id)
        graph_rows = _rows_for(source_pack.graph_edges, cell_id)
        typed_gaps = _rows_for(source_pack.typed_gaps, cell_id)
        evidence_refs = [
            str(row["evidence_ref"]) for row in evidence_rows
        ]
        numeric_refs = [str(row["numeric_ref"]) for row in numeric_rows]
        graph_refs = [str(row["graph_edge_ref"]) for row in graph_rows]
        cell_inputs.append(
            {
                "program_cell_id": cell_id,
                "runtime_branch": {
                    "program_cell_id": cell_id,
                    "owner_role": contract["owner_role"],
                    "evidence_role": contract["required_evidence_roles"][0],
                    "decision_question": contract["decision_question"],
                    "mandatory_judgment_chain": contract[
                        "mandatory_judgment_chain"
                    ],
                    "stop_rule": contract["stop_rule"],
                    "what_would_change": contract[
                        "what_would_change_targets"
                    ],
                    "branch_state": "source_grounded_exact_input_ready",
                    "observation": {
                        "accepted_evidence_count": len(evidence_rows),
                        "exact_numeric_count": len(numeric_rows),
                        "context_only_graph_count": len(graph_rows),
                        "typed_gap_count": len(typed_gaps),
                    },
                },
                "role_contexts": [
                    {
                        "target_node": "domain_specialist",
                        "authority": {
                            "case_ticker": binding.case_ticker,
                            "issuer_identifier": binding.issuer_identifier,
                            "case_identity_namespace": (
                                binding.case_identity_namespace
                            ),
                            "source_or_numeric_rows_admitted": (
                                len(evidence_rows) + len(numeric_rows)
                            ),
                            "source_pack_digest": (
                                source_pack.source_pack_digest
                            ),
                        },
                    },
                    {
                        "target_node": "evidence_operator",
                        "authority": {
                            "local_source_routes": list(
                                binding.local_source_routes_by_cell[cell_id]
                            ),
                            "route_execution_receipt_refs": [
                                str(row["route_receipt_ref"])
                                for row in source_pack.route_execution_receipts
                                if cell_id
                                in tuple(row.get("program_cell_ids") or ())
                            ],
                            "network_execution_authorized": False,
                        },
                    },
                ],
                "evidence_input": {
                    "program_cell_id": cell_id,
                    "route_outcome": (
                        "issuer_bound_rows_promoted_with_typed_gaps_retained"
                    ),
                    "candidate_bundle": {
                        "candidates": evidence_rows,
                    },
                    "promotion_assessment": {
                        "decision": "accept_issuer_bound_rows_only",
                        "candidate_refs": evidence_refs,
                        "context_refs": graph_refs,
                        "rejected_refs": [],
                        "typed_gap_codes": [
                            str(row["gap_code"]) for row in typed_gaps
                        ],
                        "accepted_evidence_refs": evidence_refs,
                    },
                    "sourcehunter_boundary": {
                        "status": "executed_before_exact_input_freeze",
                        "trigger_reason": "RC-P36-056_repair",
                        "boundary_contract_ref": (
                            binding.source_authority_policy[
                                "source_policy_ref"
                            ]
                        ),
                        "source_followup_request_ref": next(
                            (
                                str(row.get("followup_ref"))
                                for row in typed_gaps
                                if row.get("followup_ref")
                            ),
                            None,
                        ),
                        "exact_network_admission_required": False,
                        "network_execution_authorized": False,
                        "external_tool_execution_authorized": False,
                    },
                    "local_source_routes": list(
                        binding.local_source_routes_by_cell[cell_id]
                    ),
                },
                "numeric_input": {
                    "fundamental_decision_cell": {
                        "program_cell_id": cell_id,
                        "availability": (
                            "exact_issuer_rows_with_typed_cannot_infer"
                            if numeric_rows
                            else "typed_cannot_infer"
                        ),
                        "typed_cannot_infer": [
                            str(row["gap_code"]) for row in typed_gaps
                        ],
                        "support_boundary": contract["stop_rule"],
                        "specialist_input_eligible": True,
                        "narrative_fill_authorized": False,
                    },
                    "selected_financial_rows": numeric_rows,
                    "derived_metrics": derived_rows,
                    "numeric_policy": binding.numeric_policy,
                },
                "graph_context_input": {
                    "decision_cell": {
                        "program_cell_id": cell_id,
                        "typed_gaps": [
                            str(row["gap_code"]) for row in typed_gaps
                        ],
                    },
                    "product_industry_inputs": graph_rows,
                    "skill_contracts": [],
                    "graph_edges": graph_rows,
                    "market_price_in_contexts": [],
                    "risk_contexts": [
                        dict(row)
                        for row in evidence_rows
                        if row.get("evidence_role")
                        == "issuer_counterevidence"
                    ],
                    "graph_policy": binding.graph_policy,
                },
                "authority_refs": {
                    "accepted_evidence_refs": evidence_refs,
                    "numeric_refs": numeric_refs,
                    "candidate_refs_not_evidence": [],
                    "graph_context_refs_not_evidence": graph_refs,
                },
                "s4_case_method": {
                    "runtime_binding_digest": (
                        binding.runtime_binding_digest
                    ),
                    "source_pack_digest": source_pack.source_pack_digest,
                    "case_ticker": binding.case_ticker,
                    "issuer_identifier": binding.issuer_identifier,
                    "case_identity_namespace": (
                        binding.case_identity_namespace
                    ),
                    "case_profile_ref": binding.case_profile_ref,
                    "method_id": binding.method_id,
                    "program_cell_contract": contract,
                    "judgment_atom_schema": (
                        binding.judgment_atom_contract
                    ),
                },
            }
        )

    input_head_digest = canonical_digest(
        (
            decision_surface_contract_ref,
            source_pack.source_pack_digest,
            binding.runtime_binding_digest,
            case_id,
            case_version,
        )
    )
    runtime_payload = {
        "binding": binding.model_dump(mode="json"),
        "source_grounded_input": source_pack.model_dump(mode="json"),
        "consumer_injections": consumer_injections,
        "node_consumption_required": [
            "domain_specialist",
            "research_lead",
            "memo_writer",
            "verifier",
            "workbench",
        ],
        "paid_execution_authorized": False,
    }
    if research_profile_overlay is not None:
        assert_s4_case_runtime_research_profile_overlay(
            binding,
            research_profile_overlay.model_dump(mode="json"),
        )
        runtime_payload["research_profile_overlay"] = (
            research_profile_overlay.model_dump(mode="json")
        )
    lineage = {
        "S4_T02_case_pack": {
            "version_ref": binding.case_profile_ref,
            "digest": binding.case_pack_sha256,
        },
        "S4_T02_method_contract": {
            "version_ref": binding.method_contract_ref,
            "digest": binding.method_contract_sha256,
        },
        "S4_T03_runtime_binding": {
            "version_ref": binding.contract_ref,
            "digest": binding.runtime_binding_digest,
        },
        "S4_T04_source_grounded_input": {
            "version_ref": source_pack.contract_ref,
            "digest": source_pack.source_pack_digest,
        },
    }
    if research_profile_overlay is not None:
        lineage["S4_research_profile_overlay"] = {
            "version_ref": research_profile_overlay.contract_ref,
            "digest": research_profile_overlay.overlay_digest,
        }
    lead_contract = {
        "contract_ref": binding.method_contract_ref,
        "method_id": binding.method_id,
        "required_specialist_count": 3,
        "required_program_cell_ids": list(binding.program_cell_ids),
        "requires_cross_cell_dependencies": True,
        "requires_conflict_adjudication": True,
        "judgment_atom_schema_ref": (
            binding.judgment_atom_contract.get("schema_ref")
            or "fin01.s4.case_local_judgment_atom:v1"
        ),
        "deterministic_judgment_body_exposed_to_agent": False,
    }
    writer_contract = {
        "contract_ref": binding.method_contract_ref,
        "method_id": binding.method_id,
        "required_section_count": 3,
        "required_program_cell_ids": list(binding.program_cell_ids),
        "consumes_only_cross_cell_lead_and_specialist_heads": True,
        "source_authority": False,
        "tool_authority": False,
        "deterministic_report_body_exposed_to_agent": False,
    }
    verifier_contract = {
        "contract_ref": binding.method_contract_ref,
        "method_id": binding.method_id,
        "required_layers": list(S3_FOUR_LAYER_VERIFIER_LAYERS),
        "binds_exact_input_and_output_digests": True,
        "machine_verifier_is_human_acceptance": False,
    }
    paired_baseline_contract = {
        "contract_ref": "fin01.s4.paired_case_local_deterministic_baseline:v1",
        "baseline_profile_ref": (
            "fin01.execution_profile.p36_local_deterministic:v1"
        ),
        "shared_input_head_digest": input_head_digest,
        "runs_and_artifacts_must_be_distinct": True,
        "automatic_fallback_allowed": False,
        "baseline_output_body_exposed_to_agent": False,
    }
    hard_boundaries = {
        "candidate_is_evidence": False,
        "graph_edge_is_evidence": False,
        "numeric_requires_exact_program": True,
        "writer_source_or_tool_calls": 0,
        "source_network_calls_allowed": False,
        "external_tool_calls_allowed": False,
        "live_business_case_head_writes_allowed": False,
        "cross_case_fact_reuse_allowed": False,
        "source_routes_execute_during_agent_run": False,
    }
    digest_payload = {
        "input_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF,
        "execution_profile_version_ref": S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        "case_id": case_id,
        "case_version": case_version,
        "query": query,
        "as_of": binding.as_of,
        "company": binding.case_ticker,
        "decision_surface_contract_ref": decision_surface_contract_ref,
        "program_cell_ids": list(binding.program_cell_ids),
        "lineage": lineage,
        "cell_inputs": cell_inputs,
        "lead_contract": lead_contract,
        "writer_contract": writer_contract,
        "verifier_contract": verifier_contract,
        "paired_baseline_contract": paired_baseline_contract,
        "hard_boundaries": hard_boundaries,
        "s4_case_runtime": runtime_payload,
    }
    return S3ThreeCellBoundedAgentInputPack(
        case_id=case_id,
        case_version=case_version,
        query=query,
        as_of=binding.as_of,
        company=binding.case_ticker,
        decision_surface_contract_ref=decision_surface_contract_ref,
        input_head_digest=input_head_digest,
        lineage=lineage,
        cell_inputs=tuple(cell_inputs),
        lead_contract=lead_contract,
        writer_contract=writer_contract,
        verifier_contract=verifier_contract,
        paired_baseline_contract=paired_baseline_contract,
        hard_boundaries=hard_boundaries,
        s4_case_runtime=runtime_payload,
        input_digest=canonical_digest(digest_payload),
    )


class NativeJsonSchemaResponseError(ValueError):
    """Typed, provider-text-free native structured response failure."""


class NativeJsonSchemaResponseAdapter:
    """Provider-neutral parser for one strict assistant JSON Schema response."""

    transport_ref = BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF
    schema_name = BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_NAME

    @classmethod
    def text_format(
        cls,
        input_pack: BoundedAgentInputPack,
        *,
        output_contract_ref: str,
    ) -> dict[str, Any]:
        tool = DeepSeekBoundedAgentExecutor._specialist_strict_tool(
            input_pack,
            output_contract_ref=output_contract_ref,
        )
        return {
            "format": {
                "type": "json_schema",
                "name": cls.schema_name,
                "strict": True,
                "schema": tool["function"]["parameters"],
            }
        }

    @staticmethod
    def parse_response(result: Mapping[str, Any]) -> dict[str, Any]:
        response_status = str(result.get("response_status") or "")
        if response_status == "incomplete":
            reason = str(result.get("incomplete_reason") or "")
            suffix = {
                "max_output_tokens": "max_output_tokens",
                "content_filter": "content_filter",
            }.get(reason, "other")
            raise NativeJsonSchemaResponseError(
                f"bounded_agent_native_json_schema_response_incomplete_{suffix}"
            )
        if response_status != "completed":
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_response_status_invalid"
            )

        output = result.get("response_output")
        if not isinstance(output, list):
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_output_not_array"
            )
        messages = [
            item
            for item in output
            if isinstance(item, Mapping) and item.get("type") == "message"
        ]
        if len(messages) != 1:
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_message_cardinality_invalid"
            )
        content = messages[0].get("content")
        if not isinstance(content, list) or len(content) != 1:
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_content_cardinality_invalid"
            )
        item = content[0]
        if not isinstance(item, Mapping):
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_content_item_invalid"
            )
        if item.get("type") == "refusal":
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_response_refusal"
            )
        if item.get("type") != "output_text":
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_content_type_invalid"
            )
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_output_text_empty"
            )

        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, value_item in pairs:
                if key in value:
                    raise NativeJsonSchemaResponseError(
                        "bounded_agent_native_json_schema_duplicate_key"
                    )
                value[key] = value_item
            return value

        try:
            parsed = json.loads(text, object_pairs_hook=reject_duplicate_keys)
        except json.JSONDecodeError as exc:
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_json_decode_failed"
            ) from exc
        except NativeJsonSchemaResponseError:
            raise
        except ValueError as exc:
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_json_decode_failed"
            ) from exc
        if not isinstance(parsed, dict):
            raise NativeJsonSchemaResponseError(
                "bounded_agent_native_json_schema_output_not_object"
            )
        return parsed


class StrictTruthKernelJsonSchemaAdapter:
    """Strict Responses adapter for the S4 alias/enum truth kernel."""

    capability_ref = S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF
    compiler_ref = S4_OPENAI_STRUCTURED_OUTPUTS_SUBSET_COMPILER_REF

    @staticmethod
    def text_format(
        policy: StrictTruthKernelPolicy,
    ) -> dict[str, Any]:
        return {
            "format": {
                "type": "json_schema",
                "name": policy.schema_name,
                "strict": True,
                "schema": policy.server_json_schema(),
            }
        }

    @staticmethod
    def parse_response(result: Mapping[str, Any]) -> dict[str, Any]:
        return NativeJsonSchemaResponseAdapter.parse_response(result)


class DeepSeekBoundedAgentExecutor:
    """Three-call, single-cell executor for an exact T03 admission.

    The executor never persists raw provider responses or reasoning content. It
    returns only validated JSON outputs plus sanitized usage receipts.
    """

    _ROLE_AGENT_IDS = (
        "research_lead",
        "industry_supply_chain_analyst",
        "judgment_plan_aggregator",
        "memo_writer",
        "verifier",
    )

    def __init__(
        self,
        *,
        native_json_schema_adapter: NativeJsonSchemaResponseAdapter | None = None,
        segmented_specialist_lead: bool = False,
    ) -> None:
        self._native_json_schema_adapter = native_json_schema_adapter
        self._segmented_specialist_lead = segmented_specialist_lead

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        admission.assert_profile_admissible()
        if not admission.execution_enabled:
            raise ValueError("real_executor_requires_enabled_admission")
        if admission.admission_id in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS:
            raise ValueError("bounded_agent_admission_consumed")
        if (
            admission.specialist_output_contract_ref
            != BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
        ):
            raise ValueError("bounded_specialist_output_contract_v4_required")
        specialist_transport_ref = admission.resolved_specialist_transport_ref()
        admission.assert_specialist_transport_binding()
        if specialist_transport_ref == BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF:
            if (
                self._native_json_schema_adapter is not None
                or self._segmented_specialist_lead
            ):
                raise ValueError("bounded_specialist_transport_adapter_mismatch")
            specialist_transport_ref = BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF
            specialist_output_tool_name: str | None = (
                BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME
            )
            specialist_output_tool_calls = 1
            specialist_output_segment_count = 1
            specialist_strict_schema_requested = True
        elif (
            specialist_transport_ref
            == BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF
        ):
            if (
                self._native_json_schema_adapter is not None
                or not self._segmented_specialist_lead
            ):
                raise ValueError("bounded_segmented_specialist_adapter_required")
            specialist_output_tool_name = None
            specialist_output_tool_calls = 0
            specialist_output_segment_count = 2
            specialist_strict_schema_requested = False
        elif (
            specialist_transport_ref
            == BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF
        ):
            if (
                self._native_json_schema_adapter is None
                or self._segmented_specialist_lead
            ):
                raise ValueError("bounded_native_json_schema_adapter_required")
            specialist_transport_ref = self._native_json_schema_adapter.transport_ref
            specialist_output_tool_name = None
            specialist_output_tool_calls = 0
            specialist_output_segment_count = 1
            specialist_strict_schema_requested = True
        else:
            raise ValueError("bounded_admission_specialist_transport_unsupported")
        if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
            raise ValueError("llm_gateway_transport_retries_must_equal_zero")
        if not admission.api_key_env or not os.environ.get(admission.api_key_env):
            raise ValueError("bounded_agent_provider_credential_missing")

        from sec_agent.agent_registry import select_agent_definition_versions
        from sec_agent.llm_gateway import chat_completion, responses_completion
        from sec_agent.research_skills import select_skill_pack_version

        agent_versions = select_agent_definition_versions(list(self._ROLE_AGENT_IDS))
        skill_packs = []
        for version in agent_versions:
            contract = dict(version["contract"])
            skill_packs.append(
                select_skill_pack_version(
                    agent_id=str(version["agent_id"]),
                    registered_skill_ids=tuple(contract.get("skill_ids") or ()),
                    execution_profile_version_ref=admission.execution_profile_version_ref,
                    allowed_execution_profile_refs=(admission.execution_profile_version_ref,),
                )
            )

        usage_receipts: list[dict[str, Any]] = []
        spent_usd = 0.0

        def stop(
            stage: str,
            *failure_codes: str,
            output_shape: Mapping[str, Any] | None = None,
            strict_tool_parse_subtype: str | None = None,
        ) -> None:
            raise BoundedAgentExecutionError(
                stage,
                usage_receipts=usage_receipts,
                estimated_cost_usd=spent_usd,
                failure_codes=tuple(failure_codes),
                output_shape=output_shape,
                strict_tool_parse_subtype=strict_tool_parse_subtype,
            )

        def invoke_provider(
            stage: str,
            system: str,
            payload: Mapping[str, Any],
            max_tokens: int,
            *,
            tools: list[dict[str, Any]] | None = None,
            tool_choice: dict[str, Any] | None = None,
            response_format: dict[str, Any] | None = None,
            text: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            nonlocal spent_usd
            if len(usage_receipts) >= admission.max_semantic_model_calls:
                stop(f"{stage}:semantic_call_cap_exhausted")
            user = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            transport_contract = json.dumps(
                {
                    key: value
                    for key, value in {
                        "tools": tools,
                        "tool_choice": tool_choice,
                        "response_format": response_format,
                        "text": text,
                    }.items()
                    if value is not None
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            projected = self._projected_cost(
                estimate_provider_input_tokens(
                    system + user + transport_contract
                ),
                max_tokens,
                admission,
            )
            if spent_usd + projected > admission.max_total_cost_usd:
                stop(f"{stage}:projected_cost_cap_exceeded")
            trace_tags = {
                "admission_id": admission.admission_id,
                "input_digest": input_pack.input_digest,
                "research_run_id": run_identity["research_run_id"],
            }
            if text is not None:
                if any(
                    value is not None
                    for value in (tools, tool_choice, response_format)
                ):
                    raise AssertionError("responses_transport_must_not_mix_tool_contract")
                result = responses_completion(
                    llm_backend=str(admission.provider),
                    base_url=str(admission.base_url),
                    responses_path="/responses",
                    model=str(admission.model),
                    input=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    text=text,
                    reasoning={"effort": str(admission.reasoning_effort)},
                    api_key_env=str(admission.api_key_env),
                    max_output_tokens=max_tokens,
                    timeout_s=admission.timeout_seconds,
                    stream=False,
                    role=stage,
                    profile=admission.execution_profile_version_ref,
                    trace_tags=trace_tags,
                )
            else:
                result = chat_completion(
                    llm_backend=str(admission.provider),
                    base_url=str(admission.base_url),
                    chat_completions_path="/chat/completions",
                    model=str(admission.model),
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    tools=tools,
                    tool_choice=tool_choice,
                    response_format=response_format,
                    api_key_env=str(admission.api_key_env),
                    temperature=0.0,
                    max_tokens=max_tokens,
                    timeout_s=admission.timeout_seconds,
                    stream=False,
                    enable_thinking=bool(
                        admission.reasoning_effort
                        and admission.reasoning_effort != "none"
                    ),
                    reasoning_effort=str(admission.reasoning_effort or ""),
                    role=stage,
                    profile=admission.execution_profile_version_ref,
                    trace_tags=trace_tags,
                )
            receipt = self._usage_receipt(result, admission, stage=stage)
            usage_receipts.append(receipt)
            spent_usd = round(spent_usd + float(receipt["estimated_cost_usd"]), 8)
            if int(receipt["transport_attempt_count"]) != 1:
                stop(f"{stage}:transport_attempt_cardinality_violation")
            if result.get("status") != "ok":
                stop(
                    f"{stage}:provider_failure",
                    "bounded_agent_provider_failure",
                )
            if spent_usd > admission.max_total_cost_usd:
                stop(f"{stage}:actual_cost_cap_exceeded")
            finish_reason = str(result.get("finish_reason") or "")
            if finish_reason == "length":
                stop(
                    f"{stage}:provider_output_truncated",
                    "bounded_agent_provider_output_truncated",
                )
            return result

        def call_native_json_schema_specialist(
            stage: str,
            system: str,
            payload: Mapping[str, Any],
            max_tokens: int,
        ) -> dict[str, Any]:
            adapter = self._native_json_schema_adapter
            if adapter is None:
                raise AssertionError("native_json_schema_adapter_required")
            result = invoke_provider(
                stage,
                system,
                payload,
                max_tokens,
                text=adapter.text_format(
                    input_pack,
                    output_contract_ref=admission.specialist_output_contract_ref,
                ),
            )
            try:
                return adapter.parse_response(result)
            except NativeJsonSchemaResponseError as exc:
                stop(f"{stage}:native_json_schema_response_failed", str(exc))
            raise AssertionError("unreachable")

        def call_json(
            stage: str,
            system: str,
            payload: Mapping[str, Any],
            max_tokens: int,
        ) -> dict[str, Any]:
            result = invoke_provider(
                stage,
                system,
                payload,
                max_tokens,
                response_format={"type": "json_object"},
            )
            if str(result.get("finish_reason") or "") != "stop":
                stop(
                    f"{stage}:provider_finish_reason_not_stop",
                    "bounded_agent_provider_finish_reason_not_stop",
                )
            content = str(result.get("content") or "")
            if not content.strip():
                stop(
                    f"{stage}:provider_output_empty",
                    "bounded_agent_provider_output_empty",
                )
            try:
                return self._parse_json(content, stage=stage)
            except ValueError:
                stop(
                    f"{stage}:json_parse_failed",
                    "bounded_agent_provider_output_invalid_json",
                )
            raise AssertionError("unreachable")

        def call_strict_specialist(
            stage: str,
            system: str,
            payload: Mapping[str, Any],
            max_tokens: int,
        ) -> dict[str, Any]:
            tool = self._specialist_strict_tool(
                input_pack,
                output_contract_ref=admission.specialist_output_contract_ref,
            )
            result = invoke_provider(
                stage,
                system,
                payload,
                max_tokens,
                tools=[tool],
                tool_choice={
                    "type": "function",
                    "function": {"name": BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME},
                },
            )
            if str(result.get("finish_reason") or "") != "tool_calls":
                stop(
                    f"{stage}:strict_tool_finish_reason_invalid",
                    "bounded_agent_strict_tool_finish_reason_invalid",
                )
            if str(result.get("content") or "").strip():
                stop(
                    f"{stage}:strict_tool_unexpected_content",
                    "bounded_agent_strict_tool_unexpected_content",
                )
            tool_calls = result.get("tool_calls")
            if not isinstance(tool_calls, list) or len(tool_calls) != 1:
                stop(
                    f"{stage}:strict_tool_call_cardinality_invalid",
                    "bounded_agent_strict_tool_call_cardinality_invalid",
                )
            tool_call = tool_calls[0]
            function = (
                tool_call.get("function") if isinstance(tool_call, Mapping) else None
            )
            if (
                not isinstance(tool_call, Mapping)
                or tool_call.get("type") != "function"
                or not isinstance(function, Mapping)
            ):
                stop(
                    f"{stage}:strict_tool_call_schema_invalid",
                    "bounded_agent_strict_tool_call_schema_invalid",
                )
            if function.get("name") != BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME:
                stop(
                    f"{stage}:strict_tool_name_invalid",
                    "bounded_agent_strict_tool_name_invalid",
                )
            arguments = function.get("arguments")
            if not isinstance(arguments, str) or not arguments.strip():
                stop(
                    f"{stage}:strict_tool_arguments_empty",
                    "bounded_agent_strict_tool_arguments_empty",
                )
            try:
                return self._parse_strict_tool_arguments(arguments)
            except ValueError as exc:
                parse_subtype = {
                    "bounded_agent_strict_tool_arguments_json_decode_failed": (
                        "json_decode_error"
                    ),
                    "bounded_agent_strict_tool_duplicate_key": "duplicate_key",
                    "bounded_agent_strict_tool_arguments_not_object": "non_object",
                }.get(str(exc))
                stop(
                    f"{stage}:strict_tool_arguments_invalid_json",
                    "bounded_agent_strict_tool_arguments_invalid_json",
                    strict_tool_parse_subtype=parse_subtype,
                )
            raise AssertionError("unreachable")

        candidates = [
            {
                "candidate_id": row["candidate_id"],
                "title": row["title"],
                "excerpt": row["excerpt"],
                "published_at": row["published_at"],
                "citation_span": row["citation_span"],
                "claim_boundary": row["claim_boundary"],
            }
            for row in input_pack.candidates
        ]
        combined_specialist_system = (
            (
                "You are a financial-research specialist and lead adjudicator. Use only the "
                "provided SEC-filing candidate text. Return exactly one assistant response "
                "conforming to the supplied strict JSON Schema. Do not call or simulate any "
                "function or external tool. The request document is input only: never copy "
                "request_contract or analysis_input fields into the response. Do not invent "
                "facts, URLs, numbers, customers, dates, or citations. Distinguish reported "
                "demand conversion from durability inference and preserve every claim boundary. "
                "The example is a shape example only; replace its prose with candidate-grounded "
                "analysis."
            )
            if self._native_json_schema_adapter is not None
            else (
                "You are a financial-research specialist and lead adjudicator. Use only the "
                "provided SEC-filing candidate text. Call submit_specialist_lead_result exactly "
                "once, using its strict schema. Put the single outer key 'result' in the function "
                "arguments, and put no answer in message content. The request document is input "
                "only: never copy request_contract or analysis_input fields into the arguments. "
                "Do not invent facts, URLs, numbers, customers, dates, or citations. Distinguish "
                "reported demand conversion from durability inference and preserve every claim boundary. "
                "The example is a shape example only; replace its prose with candidate-grounded analysis."
            )
        )
        combined_specialist_payload = {
                "request_contract": {
                    "output_contract_ref": admission.specialist_output_contract_ref,
                    "response_outer_keys": ["result"],
                    "result_keys": [
                        "output_contract_ref",
                        "specialist_judgment",
                        "lead_adjudication",
                    ],
                    "additional_properties_allowed": False,
                    "confidence_enum": ["low", "medium", "high"],
                    "decision_enum": ["accept", "repair", "reject"],
                    "candidate_id_rule": "copy an exact candidate_id from analysis_input.candidates",
                    "evidence_findings_min_items": 1,
                    "evidence_refs_min_items": 1,
                },
                "analysis_input": {
                    "task": "Assess NVDA AI-infrastructure demand authenticity and sustainability.",
                    "decision_question": input_pack.decision_question,
                    "as_of": input_pack.as_of,
                    "candidates": candidates,
                },
                "response_shape_example": {
                    "result": {
                        "output_contract_ref": admission.specialist_output_contract_ref,
                        "specialist_judgment": {
                            "thesis": "Candidate text supports a bounded demand-conversion thesis.",
                            "confidence": "medium",
                            "evidence_findings": [
                                {
                                    "candidate_id": candidates[0]["candidate_id"],
                                    "supported_claim": "A claim supported by this candidate text.",
                                    "boundary": "What this candidate does not establish.",
                                }
                            ],
                            "counter_thesis": "A candidate-grounded alternative explanation.",
                            "unresolved_gaps": ["A material unresolved evidence gap"],
                        },
                        "lead_adjudication": {
                            "decision": "accept",
                            "adjudicated_judgment": "A bounded judgment preserving the evidence limit.",
                            "confidence": "medium",
                            "evidence_refs": [candidates[0]["candidate_id"]],
                            "remaining_gaps": ["A material remaining gap"],
                            "what_would_change": ["Specific new evidence that would change the judgment"],
                        },
                    },
                },
            }
        if self._segmented_specialist_lead:
            specialist_segment = call_json(
                "bounded_specialist",
                (
                    "You are a financial-research specialist. Return one JSON object, no "
                    "markdown. Use only the supplied SEC-filing candidates. Produce only the "
                    "five requested specialist fields; do not adjudicate, call tools, invent "
                    "facts, or weaken any candidate claim boundary."
                ),
                {
                    "task": "Assess NVDA AI-infrastructure demand authenticity and sustainability.",
                    "decision_question": input_pack.decision_question,
                    "as_of": input_pack.as_of,
                    "candidates": candidates,
                    "required_schema": {
                        "thesis": "non-empty string",
                        "confidence": "low|medium|high",
                        "evidence_findings": [
                            {
                                "candidate_id": "exact supplied candidate_id",
                                "supported_claim": "non-empty string",
                                "boundary": "non-empty string",
                            }
                        ],
                        "counter_thesis": "non-empty string",
                        "unresolved_gaps": ["non-empty string"],
                    },
                    "additional_properties_allowed": False,
                },
                admission.specialist_max_output_tokens,
            )
            try:
                specialist_segment = self._validate_specialist_segment(
                    specialist_segment,
                    input_pack,
                )
            except ValueError as exc:
                stop("bounded_specialist:contract_validation_failed", str(exc))

            lead_segment = call_json(
                "bounded_lead_adjudication",
                (
                    "You are the research lead adjudicator. Return one JSON object, no "
                    "markdown. Adjudicate only the supplied validated specialist judgment and "
                    "candidate identifiers. Produce only the six requested lead fields; do not "
                    "call tools, add sources, or invent evidence."
                ),
                {
                    "decision_question": input_pack.decision_question,
                    "validated_specialist_judgment": specialist_segment,
                    "allowed_candidate_ids": sorted(
                        str(row["candidate_id"]) for row in input_pack.candidates
                    ),
                    "required_schema": {
                        "decision": "accept|repair|reject",
                        "adjudicated_judgment": "non-empty string",
                        "confidence": "low|medium|high",
                        "evidence_refs": ["exact supplied candidate_id"],
                        "remaining_gaps": ["non-empty string"],
                        "what_would_change": ["non-empty string"],
                    },
                    "additional_properties_allowed": False,
                },
                admission.lead_max_output_tokens,
            )
            try:
                lead_segment = self._validate_lead_segment(
                    lead_segment,
                    input_pack,
                    specialist_segment,
                )
            except ValueError as exc:
                stop("bounded_lead_adjudication:contract_validation_failed", str(exc))
            specialist = {
                "result": {
                    "output_contract_ref": admission.specialist_output_contract_ref,
                    "specialist_judgment": specialist_segment,
                    "lead_adjudication": lead_segment,
                }
            }
        else:
            specialist_call = (
                call_native_json_schema_specialist
                if self._native_json_schema_adapter is not None
                else call_strict_specialist
            )
            specialist = specialist_call(
                "bounded_specialist_and_lead",
                combined_specialist_system,
                combined_specialist_payload,
                admission.specialist_max_output_tokens,
            )
        specialist_envelope = specialist
        specialist_adaptations: tuple[str, ...] = ()
        try:
            specialist = self._validate_specialist(
                specialist_envelope,
                input_pack,
                output_contract_ref=admission.specialist_output_contract_ref,
            )
        except ValueError as exc:
            stop(
                "bounded_specialist_and_lead:contract_validation_failed",
                str(exc),
                output_shape=self._specialist_output_shape(specialist_envelope),
            )

        writer_input = {
            "task": "Compose a concise internal Chinese research note.",
            "as_of": input_pack.as_of,
            "adjudication": specialist["lead_adjudication"],
            "evidence_summaries": specialist["specialist_judgment"]["evidence_findings"],
            "numeric_status": {
                "status": "typed_gap",
                "reason": "single demand-signal cell does not establish an exact sustainability metric",
            },
            "required_schema": {
                "title_zh_cn": "string",
                "executive_summary_zh_cn": "string",
                "sections": [
                    {"heading_zh_cn": "string", "content_zh_cn": "string", "evidence_refs": ["id"]}
                ],
                "limitations_zh_cn": ["string"],
            },
        }
        writer = call_json(
            "bounded_writer_no_source",
            (
                "You are a no-source internal writer. Return one JSON object, no markdown. "
                "Use only the supplied adjudication and evidence summaries. You cannot call "
                "sources or tools. Do not add unsupported numbers or facts; retain limitations."
            ),
            writer_input,
            admission.writer_max_output_tokens,
        )
        try:
            self._validate_writer(writer, input_pack)
        except ValueError:
            stop("bounded_writer_no_source:contract_validation_failed")

        verification = call_json(
            "bounded_semantic_financial_verifier",
            (
                "You are the semantic-fidelity and financial-coherence verifier. Return one "
                "JSON object, no markdown. Check claim-boundary preservation, demand authenticity "
                "versus sustainability, unsupported precision, and consistency between judgment "
                "and report. Acknowledge gaps instead of repairing by invention."
            ),
            {
                "adjudication": specialist["lead_adjudication"],
                "evidence_summaries": specialist["specialist_judgment"]["evidence_findings"],
                "report": writer,
                "deterministic_baseline_judgment": input_pack.deterministic_baseline["judgment"],
                "required_schema": {
                    "semantic_fidelity": {
                        "status": "pass|review_required|fail",
                        "score": "integer 0-100",
                        "issues": ["string"],
                    },
                    "financial_coherence": {
                        "status": "pass|review_required|fail",
                        "score": "integer 0-100",
                        "issues": ["string"],
                    },
                    "recommendation": "accept_for_internal_review|repair|reject",
                    "material_gain_assessment": "string",
                },
            },
            admission.verifier_max_output_tokens,
        )
        try:
            self._validate_verification(verification)
        except ValueError:
            stop("bounded_semantic_financial_verifier:contract_validation_failed")

        allowed_refs = {str(row["candidate_id"]) for row in input_pack.candidates}
        used_refs = set(specialist["lead_adjudication"]["evidence_refs"])
        deterministic_integrity = {
            "status": "pass" if used_refs and used_refs.issubset(allowed_refs) else "fail",
            "exact_input_digest_bound": True,
            "evidence_refs_are_supplied_candidates": used_refs.issubset(allowed_refs),
            "writer_source_calls": 0,
            "writer_tool_calls": 0,
            "specialist_output_tool_calls": specialist_output_tool_calls,
            "external_tool_executions": 0,
            "private_reasoning_persisted": False,
        }
        visual_delivery = {
            "status": "pass"
            if writer.get("title_zh_cn") and writer.get("sections") and writer.get("limitations_zh_cn")
            else "fail",
            "title_present": bool(writer.get("title_zh_cn")),
            "section_count": len(writer.get("sections") or ()),
            "limitations_present": bool(writer.get("limitations_zh_cn")),
        }
        if deterministic_integrity["status"] != "pass" or visual_delivery["status"] != "pass":
            stop("deterministic_or_visual_verifier_failed")

        observed_counts = {
            "model_calls": len(usage_receipts),
            "provider_calls": len(usage_receipts),
            "network_calls": len(usage_receipts),
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "live_case_head_writes": 0,
            "evaluation_evidence_promotions": 1,
        }
        if (
            observed_counts["model_calls"] > admission.max_semantic_model_calls
            or observed_counts["provider_calls"] > admission.max_provider_calls
            or observed_counts["network_calls"] > admission.max_network_calls
        ):
            stop("observed_call_cap_exceeded")
        hard_boundaries = {
            "candidate_is_evidence": 0,
            "graph_edge_is_evidence": 0,
            "writer_source_or_tool_calls": 0,
            "adapter_direct_canonical_writes": 0,
            "live_business_case_head_writes": 0,
            "release_admission": 0,
        }
        versions = {
            "agent_definition_versions": [
                {
                    "agent_id": row["agent_id"],
                    "agent_definition_version_ref": row["agent_definition_version_ref"],
                    "canonical_digest": row["canonical_digest"],
                }
                for row in agent_versions
            ],
            "skill_pack_versions": [
                {
                    "agent_id": row["agent_id"],
                    "skill_pack_version_ref": row["skill_pack_version_ref"],
                    "canonical_digest": row["canonical_digest"],
                }
                for row in skill_packs
            ],
        }
        receipts_by_stage = {str(row["stage"]): row for row in usage_receipts}
        specialist_receipt = receipts_by_stage.get(
            "bounded_specialist",
            receipts_by_stage.get("bounded_specialist_and_lead"),
        )
        writer_receipt = receipts_by_stage.get("bounded_writer_no_source")
        verifier_receipt = receipts_by_stage.get(
            "bounded_semantic_financial_verifier"
        )
        if not specialist_receipt or not writer_receipt or not verifier_receipt:
            stop("bounded_agent_stage_receipt_missing")
        lead_event_payload = {
            "agent_id": "research_lead",
            "decision": specialist["lead_adjudication"]["decision"],
        }
        lead_receipt = receipts_by_stage.get("bounded_lead_adjudication")
        if lead_receipt is not None:
            lead_event_payload["call_ref"] = lead_receipt["call_id"]
        artifact_payloads: dict[str, dict[str, Any]] = {
            BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-manifest",
                "admission_id": admission.admission_id,
                "input_digest": input_pack.input_digest,
                "observed_counts": observed_counts,
                "estimated_cost_usd": spent_usd,
                "usage_receipts": usage_receipts,
                "specialist_output_contract_ref": admission.specialist_output_contract_ref,
                "specialist_output_adaptations": list(specialist_adaptations),
                "specialist_output_transport_ref": specialist_transport_ref,
                "reasoning_effort": admission.reasoning_effort,
                "specialist_output_tool_name": specialist_output_tool_name,
                "specialist_output_segment_count": specialist_output_segment_count,
                "specialist_output_assembly": (
                    "deterministic_local_v4"
                    if self._segmented_specialist_lead
                    else "provider_single_envelope"
                ),
                "specialist_strict_schema_requested": specialist_strict_schema_requested,
                "specialist_external_tool_executed": False,
                "hard_boundaries": hard_boundaries,
                **versions,
            },
            BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-evidence",
                "status": "run_scoped_evaluation_evidence_version",
                "input_digest": input_pack.input_digest,
                "candidate_refs": sorted(used_refs),
                "findings": specialist["specialist_judgment"]["evidence_findings"],
                "live_evidence_head_promoted": False,
            },
            BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-numeric",
                "status": "typed_gap",
                "metric": "demand_sustainability",
                "value": None,
                "reason": "single demand-signal cell does not establish an exact sustainability metric",
            },
            BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-judgment",
                "specialist_judgment": specialist["specialist_judgment"],
                "lead_adjudication": specialist["lead_adjudication"],
            },
            BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-workpaper",
                "decision_question": input_pack.decision_question,
                "evidence_ref": "logical:bounded-agent-evidence",
                "numeric_ref": "logical:bounded-agent-numeric",
                "judgment_ref": "logical:bounded-agent-judgment",
                "remaining_gaps": specialist["lead_adjudication"]["remaining_gaps"],
            },
            BOUNDED_AGENT_REPORT_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-report",
                "mode": "model_no_source_internal_writer",
                "writer_source_calls": 0,
                "writer_tool_calls": 0,
                "report": writer,
            },
            BOUNDED_AGENT_TRACE_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-trace",
                "input_digest": input_pack.input_digest,
                "usage_receipts": usage_receipts,
                "specialist_output_contract_ref": admission.specialist_output_contract_ref,
                "specialist_output_adaptations": list(specialist_adaptations),
                "specialist_output_transport_ref": specialist_transport_ref,
                "reasoning_effort": admission.reasoning_effort,
                "specialist_output_tool_name": specialist_output_tool_name,
                "specialist_output_segment_count": specialist_output_segment_count,
                "specialist_output_assembly": (
                    "deterministic_local_v4"
                    if self._segmented_specialist_lead
                    else "provider_single_envelope"
                ),
                "specialist_strict_schema_requested": specialist_strict_schema_requested,
                "specialist_external_tool_executed": False,
                "private_reasoning_persisted": False,
                "raw_provider_response_persisted": False,
                **versions,
            },
            BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE: {
                "artifact_ref": "logical:bounded-agent-verification",
                "deterministic_integrity": deterministic_integrity,
                "semantic_fidelity": verification["semantic_fidelity"],
                "financial_coherence": verification["financial_coherence"],
                "visual_delivery": visual_delivery,
                "recommendation": verification["recommendation"],
            },
            BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE: {
                "artifact_ref": "logical:agent-fallback-comparison",
                "paired_input_digest": input_pack.input_digest,
                "runs_must_be_distinct": True,
                "comparison_status": "pending_distinct_deterministic_run",
                "agent_research_run_id": run_identity["research_run_id"],
                "deterministic_research_run_id": None,
                "deterministic_baseline": input_pack.deterministic_baseline,
                "agent_result_refs": {
                    "judgment": "logical:bounded-agent-judgment",
                    "report": "logical:bounded-agent-report",
                    "verification": "logical:bounded-agent-verification",
                },
                "material_gain_assessment": verification["material_gain_assessment"],
                "material_gain_accepted": False,
                "owner_review_status": "not_performed_in_t03",
            },
        }
        if admission.local_fact_interaction_contract_ref is not None:
            interaction_topology = {
                "logical_node_count": len(node_receipts),
                "logical_interaction_count": (
                    len(usage_receipts) + len(local_fact_receipts)
                ),
                "local_fact_interaction_count": len(
                    local_fact_receipts
                ),
                "provider_interaction_count": len(usage_receipts),
                "provider_capture_count": len(
                    provider_output_captures
                ),
                "business_artifact_count": len(
                    BOUNDED_AGENT_ARTIFACT_TYPES
                ),
            }
            artifact_payloads[
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
            ]["interaction_topology"] = interaction_topology
            artifact_payloads[
                BOUNDED_AGENT_TRACE_ARTIFACT_TYPE
            ]["interaction_topology"] = interaction_topology
        trace_events = (
            {
                "event_type": "BOUNDED_AGENT_INPUT_BOUND",
                "event_payload": {"input_digest": input_pack.input_digest, "cell_count": 1},
            },
            {
                "event_type": "BOUNDED_AGENT_VERSIONS_SELECTED",
                "event_payload": versions,
            },
            {
                "event_type": "BOUNDED_AGENT_SPECIALIST_COMPLETED",
                "event_payload": {
                    "agent_id": "industry_supply_chain_analyst",
                    "call_ref": specialist_receipt["call_id"],
                    "output_contract_ref": admission.specialist_output_contract_ref,
                    "output_adaptations": list(specialist_adaptations),
                    "output_transport_ref": specialist_transport_ref,
                    "output_tool_name": specialist_output_tool_name,
                    "external_tool_executed": False,
                },
            },
            {
                "event_type": "BOUNDED_AGENT_LEAD_ADJUDICATED",
                "event_payload": lead_event_payload,
            },
            {
                "event_type": "BOUNDED_AGENT_WRITER_COMPLETED",
                "event_payload": {"agent_id": "memo_writer", "call_ref": writer_receipt["call_id"], "source_calls": 0, "tool_calls": 0},
            },
            {
                "event_type": "BOUNDED_AGENT_VERIFIERS_COMPLETED",
                "event_payload": {"agent_id": "verifier", "call_ref": verifier_receipt["call_id"], "deterministic_integrity": "pass", "visual_delivery": "pass"},
            },
            {
                "event_type": "BOUNDED_AGENT_EXECUTION_COMPLETED",
                "event_payload": {"observed_counts": observed_counts, "estimated_cost_usd": spent_usd},
            },
        )
        return BoundedAgentExecutionOutput(
            terminal_reason="bounded_agent_one_cell_first_run_succeeded",
            artifacts=tuple(
                BoundedAgentArtifact(artifact_type=kind, payload=artifact_payloads[kind])
                for kind in BOUNDED_AGENT_ARTIFACT_TYPES
            ),
            trace_events=trace_events,
        )

    @staticmethod
    def _specialist_strict_tool(
        input_pack: BoundedAgentInputPack,
        *,
        output_contract_ref: str,
    ) -> dict[str, Any]:
        """Build the exact DeepSeek strict function used only as an output carrier."""

        candidate_ids = sorted(
            {str(row.get("candidate_id") or "") for row in input_pack.candidates}
            - {""}
        )
        if not candidate_ids:
            raise ValueError("bounded_agent_strict_tool_candidate_enum_required")

        def closed_object(properties: dict[str, Any]) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            }

        text_array = {"type": "array", "items": {"type": "string"}}
        evidence_finding = closed_object(
            {
                "candidate_id": {
                    "type": "string",
                    "enum": candidate_ids,
                },
                "supported_claim": {"type": "string"},
                "boundary": {"type": "string"},
            }
        )
        specialist_judgment = closed_object(
            {
                "thesis": {"type": "string"},
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "evidence_findings": {
                    "type": "array",
                    "items": evidence_finding,
                },
                "counter_thesis": {"type": "string"},
                "unresolved_gaps": text_array,
            }
        )
        lead_adjudication = closed_object(
            {
                "decision": {
                    "type": "string",
                    "enum": ["accept", "repair", "reject"],
                },
                "adjudicated_judgment": {"type": "string"},
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string", "enum": candidate_ids},
                },
                "remaining_gaps": text_array,
                "what_would_change": text_array,
            }
        )
        parameters = closed_object(
            {
                "result": closed_object(
                    {
                        "output_contract_ref": {
                            "type": "string",
                            "enum": [output_contract_ref],
                        },
                        "specialist_judgment": specialist_judgment,
                        "lead_adjudication": lead_adjudication,
                    }
                )
            }
        )
        return {
            "type": "function",
            "function": {
                "name": BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME,
                "description": (
                    "Submit the bounded Specialist judgment and Lead adjudication as "
                    "schema-validated output. The function is not executed."
                ),
                "strict": True,
                "parameters": parameters,
            },
        }

    @staticmethod
    def _parse_strict_tool_arguments(arguments: str) -> dict[str, Any]:
        """Parse native JSON only and reject duplicate object keys."""

        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("bounded_agent_strict_tool_duplicate_key")
                value[key] = item
            return value

        try:
            value = json.loads(arguments, object_pairs_hook=reject_duplicate_keys)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "bounded_agent_strict_tool_arguments_json_decode_failed"
            ) from exc
        except ValueError as exc:
            if str(exc) == "bounded_agent_strict_tool_duplicate_key":
                raise
            raise ValueError(
                "bounded_agent_strict_tool_arguments_json_decode_failed"
            ) from exc
        if not isinstance(value, dict):
            raise ValueError("bounded_agent_strict_tool_arguments_not_object")
        return value

    @staticmethod
    def _parse_json(content: str, *, stage: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I | re.S)
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"bounded_agent_invalid_json:{stage}:{exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"bounded_agent_output_not_object:{stage}")
        return value

    @staticmethod
    def _normalize_specialist_stage_output(
        value: Mapping[str, Any],
    ) -> tuple[dict[str, Any], tuple[str, ...]]:
        """Normalize declared v4 result fields without dropping envelope extensions."""

        normalized = dict(value)
        adaptations: list[str] = []
        result = normalized.get("result")
        if not isinstance(result, Mapping):
            return normalized, ()
        result = dict(result)

        specialist = result.get("specialist_judgment")
        if isinstance(specialist, Mapping):
            specialist = dict(specialist)
            confidence = specialist.get("confidence")
            if isinstance(confidence, str):
                canonical = confidence.strip().lower()
                if canonical != confidence:
                    specialist["confidence"] = canonical
                    adaptations.append("normalized_specialist_confidence_case_whitespace")
            findings = specialist.get("evidence_findings")
            if isinstance(findings, Mapping):
                specialist["evidence_findings"] = [dict(findings)]
                adaptations.append("wrapped_single_evidence_finding")
            gaps = specialist.get("unresolved_gaps")
            if isinstance(gaps, str):
                specialist["unresolved_gaps"] = [gaps]
                adaptations.append("wrapped_single_unresolved_gap")
            result["specialist_judgment"] = specialist

        lead = result.get("lead_adjudication")
        if isinstance(lead, Mapping):
            lead = dict(lead)
            for key in ("decision", "confidence"):
                current = lead.get(key)
                if isinstance(current, str):
                    canonical = current.strip().lower()
                    if canonical != current:
                        lead[key] = canonical
                        adaptations.append(f"normalized_lead_{key}_case_whitespace")
            for key in ("evidence_refs", "remaining_gaps", "what_would_change"):
                current = lead.get(key)
                if isinstance(current, str):
                    lead[key] = [current]
                    adaptations.append(f"wrapped_single_lead_{key}")
            result["lead_adjudication"] = lead

        normalized["result"] = result

        return normalized, tuple(adaptations)

    @staticmethod
    def _specialist_output_shape(value: Mapping[str, Any]) -> dict[str, Any]:
        """Return key-shape telemetry without provider prose or unknown key names."""

        expected = {"result"}
        keys = set(map(str, value))
        unexpected = sorted(keys - expected)
        result_value = value.get("result")
        result_payload = (
            dict(result_value) if isinstance(result_value, Mapping) else {}
        )
        expected_result = {
            "output_contract_ref",
            "specialist_judgment",
            "lead_adjudication",
        }
        result_keys = set(map(str, result_payload))
        unexpected_result = sorted(result_keys - expected_result)
        shape: dict[str, Any] = {
            "outer_key_count": len(keys),
            "expected_outer_keys_present": sorted(keys & expected),
            "missing_outer_keys": sorted(expected - keys),
            "unexpected_outer_key_count": len(unexpected),
            "unexpected_outer_keys_digest": (
                canonical_digest(unexpected) if unexpected else None
            ),
            "recognized_wrapper_keys_present": sorted(keys & {"result"}),
            "expected_outer_value_types": {
                key: type(value[key]).__name__ for key in sorted(keys & expected)
            },
            "result_key_count": len(result_keys),
            "expected_result_keys_present": sorted(result_keys & expected_result),
            "missing_result_keys": sorted(expected_result - result_keys),
            "unexpected_result_key_count": len(unexpected_result),
            "unexpected_result_keys_digest": (
                canonical_digest(unexpected_result) if unexpected_result else None
            ),
            "expected_result_value_types": {
                key: type(result_payload[key]).__name__
                for key in sorted(result_keys & expected_result)
            },
        }
        return shape

    @staticmethod
    def _projected_cost(
        estimated_input_tokens: int,
        max_output_tokens: int,
        admission: BoundedAgentAdmission,
    ) -> float:
        return (
            estimated_input_tokens
            * admission.input_cache_miss_usd_per_million
            + max_output_tokens * admission.output_usd_per_million
        ) / 1_000_000

    @staticmethod
    def _usage_receipt(
        result: Mapping[str, Any], admission: BoundedAgentAdmission, *, stage: str
    ) -> dict[str, Any]:
        raw = result.get("raw_response")
        usage = raw.get("usage") if isinstance(raw, Mapping) else {}
        usage = usage if isinstance(usage, Mapping) else {}
        cache_hit = int(usage.get("prompt_cache_hit_tokens") or 0)
        cache_miss = int(usage.get("prompt_cache_miss_tokens") or result.get("input_tokens") or 0)
        output = int(result.get("output_tokens") or 0)
        cost = (
            cache_hit * admission.input_cache_hit_usd_per_million
            + cache_miss * admission.input_cache_miss_usd_per_million
            + output * admission.output_usd_per_million
        ) / 1_000_000
        return {
            "stage": stage,
            "call_id": str(result.get("call_id") or ""),
            "provider": str(result.get("provider") or admission.provider or ""),
            "model": str(result.get("model") or admission.model or ""),
            "status": str(result.get("status") or "unknown"),
            "finish_reason": result.get("finish_reason"),
            "input_tokens": int(result.get("input_tokens") or 0),
            "input_cache_hit_tokens": cache_hit,
            "input_cache_miss_tokens": cache_miss,
            "output_tokens": output,
            "total_tokens": int(result.get("total_tokens") or 0),
            "estimated_cost_usd": round(cost, 8),
            "latency_ms": int(result.get("latency_ms") or 0),
            "transport_attempt_count": int(result.get("transport_attempt_count") or 0),
        }

    @staticmethod
    def _validate_specialist_segment(
        value: Mapping[str, Any],
        input_pack: BoundedAgentInputPack,
    ) -> dict[str, Any]:
        expected = {
            "thesis",
            "confidence",
            "evidence_findings",
            "counter_thesis",
            "unresolved_gaps",
        }
        if set(value) != expected:
            raise ValueError("bounded_agent_specialist_segment_schema_invalid")
        if value.get("confidence") not in {"low", "medium", "high"}:
            raise ValueError("bounded_agent_specialist_segment_confidence_invalid")
        if not all(
            isinstance(value.get(key), str) and value.get(key).strip()
            for key in ("thesis", "counter_thesis")
        ):
            raise ValueError("bounded_agent_specialist_segment_text_required")
        findings = value.get("evidence_findings")
        allowed = {str(row["candidate_id"]) for row in input_pack.candidates}
        if not isinstance(findings, list) or not findings:
            raise ValueError("bounded_agent_specialist_segment_findings_required")
        if any(
            not isinstance(row, Mapping)
            or set(row) != {"candidate_id", "supported_claim", "boundary"}
            or str(row.get("candidate_id") or "") not in allowed
            or not all(
                isinstance(row.get(key), str) and row.get(key).strip()
                for key in ("candidate_id", "supported_claim", "boundary")
            )
            for row in findings
        ):
            raise ValueError("bounded_agent_specialist_segment_finding_invalid")
        gaps = value.get("unresolved_gaps")
        if not isinstance(gaps, list) or any(
            not isinstance(row, str) or not row.strip() for row in gaps
        ):
            raise ValueError("bounded_agent_specialist_segment_gap_invalid")
        return dict(value)

    @staticmethod
    def _validate_lead_segment(
        value: Mapping[str, Any],
        input_pack: BoundedAgentInputPack,
        specialist: Mapping[str, Any],
    ) -> dict[str, Any]:
        expected = {
            "decision",
            "adjudicated_judgment",
            "confidence",
            "evidence_refs",
            "remaining_gaps",
            "what_would_change",
        }
        if set(value) != expected:
            raise ValueError("bounded_agent_lead_segment_schema_invalid")
        if value.get("decision") not in {"accept", "repair", "reject"}:
            raise ValueError("bounded_agent_lead_segment_decision_invalid")
        if value.get("confidence") not in {"low", "medium", "high"}:
            raise ValueError("bounded_agent_lead_segment_confidence_invalid")
        if not isinstance(value.get("adjudicated_judgment"), str) or not value.get(
            "adjudicated_judgment"
        ).strip():
            raise ValueError("bounded_agent_lead_segment_judgment_required")
        refs = value.get("evidence_refs")
        allowed = {str(row["candidate_id"]) for row in input_pack.candidates}
        finding_refs = {
            str(row.get("candidate_id") or "")
            for row in specialist.get("evidence_findings", ())
            if isinstance(row, Mapping)
        }
        if (
            not isinstance(refs, list)
            or not refs
            or not set(map(str, refs)).issubset(allowed)
            or not set(map(str, refs)).issubset(finding_refs)
        ):
            raise ValueError("bounded_agent_lead_segment_evidence_ref_invalid")
        for key in ("remaining_gaps", "what_would_change"):
            rows = value.get(key)
            if not isinstance(rows, list) or any(
                not isinstance(row, str) or not row.strip() for row in rows
            ):
                raise ValueError("bounded_agent_lead_segment_gap_invalid")
        return dict(value)

    @staticmethod
    def _validate_specialist(
        value: Mapping[str, Any],
        input_pack: BoundedAgentInputPack,
        *,
        output_contract_ref: str,
    ) -> dict[str, Any]:
        expected_outer_keys = {"result"}
        if expected_outer_keys - set(value):
            raise ValueError("bounded_agent_specialist_envelope_keys_missing")
        if set(value) - expected_outer_keys:
            raise ValueError("bounded_agent_specialist_envelope_keys_unexpected")
        result = value.get("result")
        if not isinstance(result, Mapping):
            raise ValueError("bounded_agent_specialist_result_schema_invalid")
        result = dict(result)
        if result.get("output_contract_ref") != output_contract_ref:
            raise ValueError("bounded_agent_specialist_contract_ref_invalid")
        expected_result_keys = {
            "output_contract_ref",
            "specialist_judgment",
            "lead_adjudication",
        }
        if expected_result_keys - set(result):
            raise ValueError("bounded_agent_specialist_result_keys_missing")
        if set(result) - expected_result_keys:
            raise ValueError("bounded_agent_specialist_result_keys_unexpected")
        specialist = result.get("specialist_judgment")
        lead = result.get("lead_adjudication")
        if not isinstance(specialist, Mapping) or not isinstance(lead, Mapping):
            raise ValueError("bounded_agent_specialist_schema_invalid")
        if set(specialist) != {
            "thesis",
            "confidence",
            "evidence_findings",
            "counter_thesis",
            "unresolved_gaps",
        }:
            raise ValueError("bounded_agent_specialist_judgment_schema_invalid")
        if set(lead) != {
            "decision",
            "adjudicated_judgment",
            "confidence",
            "evidence_refs",
            "remaining_gaps",
            "what_would_change",
        }:
            raise ValueError("bounded_agent_lead_schema_invalid")
        if specialist.get("confidence") not in {"low", "medium", "high"}:
            raise ValueError("bounded_agent_specialist_confidence_invalid")
        if not all(
            isinstance(specialist.get(key), str) and specialist.get(key).strip()
            for key in ("thesis", "counter_thesis")
        ):
            raise ValueError("bounded_agent_specialist_judgment_text_required")
        if lead.get("decision") not in {"accept", "repair", "reject"} or lead.get("confidence") not in {"low", "medium", "high"}:
            raise ValueError("bounded_agent_lead_adjudication_invalid")
        findings = specialist.get("evidence_findings")
        refs = lead.get("evidence_refs")
        allowed = {str(row["candidate_id"]) for row in input_pack.candidates}
        if not isinstance(findings, list) or not findings or not isinstance(refs, list) or not refs:
            raise ValueError("bounded_agent_evidence_findings_required")
        if any(
            not isinstance(row, Mapping)
            or set(row) != {"candidate_id", "supported_claim", "boundary"}
            or not all(isinstance(row.get(key), str) and row.get(key).strip() for key in row)
            for row in findings
        ):
            raise ValueError("bounded_agent_evidence_finding_schema_invalid")
        finding_refs = {
            str(row.get("candidate_id") or "") for row in findings if isinstance(row, Mapping)
        }
        if not finding_refs or not finding_refs.issubset(allowed) or not set(map(str, refs)).issubset(allowed):
            raise ValueError("bounded_agent_evidence_ref_not_in_input")
        if not isinstance(lead.get("remaining_gaps"), list) or not isinstance(lead.get("what_would_change"), list):
            raise ValueError("bounded_agent_lead_gap_schema_invalid")
        if not isinstance(specialist.get("unresolved_gaps"), list):
            raise ValueError("bounded_agent_specialist_gap_schema_invalid")
        for rows, code in (
            (specialist["unresolved_gaps"], "bounded_agent_specialist_gap_schema_invalid"),
            (lead["remaining_gaps"], "bounded_agent_lead_gap_schema_invalid"),
            (lead["what_would_change"], "bounded_agent_lead_gap_schema_invalid"),
        ):
            if any(not isinstance(row, str) or not row.strip() for row in rows):
                raise ValueError(code)
        if not isinstance(lead.get("adjudicated_judgment"), str) or not lead.get(
            "adjudicated_judgment"
        ).strip():
            raise ValueError("bounded_agent_adjudicated_judgment_required")
        return result

    @staticmethod
    def _validate_writer(value: Mapping[str, Any], input_pack: BoundedAgentInputPack) -> None:
        if not all(isinstance(value.get(key), expected) for key, expected in (
            ("title_zh_cn", str),
            ("executive_summary_zh_cn", str),
            ("sections", list),
            ("limitations_zh_cn", list),
        )):
            raise ValueError("bounded_agent_writer_schema_invalid")
        allowed = {str(row["candidate_id"]) for row in input_pack.candidates}
        for section in value.get("sections") or ():
            if not isinstance(section, Mapping) or not set(map(str, section.get("evidence_refs") or ())).issubset(allowed):
                raise ValueError("bounded_agent_writer_evidence_ref_invalid")

    @staticmethod
    def _validate_verification(value: Mapping[str, Any]) -> None:
        for key in ("semantic_fidelity", "financial_coherence"):
            row = value.get(key)
            if not isinstance(row, Mapping) or row.get("status") not in {"pass", "review_required", "fail"}:
                raise ValueError(f"bounded_agent_verifier_schema_invalid:{key}")
            try:
                score = int(row.get("score"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"bounded_agent_verifier_score_invalid:{key}") from exc
            if score < 0 or score > 100 or not isinstance(row.get("issues"), list):
                raise ValueError(f"bounded_agent_verifier_score_invalid:{key}")
        if value.get("recommendation") not in {"accept_for_internal_review", "repair", "reject"}:
            raise ValueError("bounded_agent_verifier_recommendation_invalid")
        if not isinstance(value.get("material_gain_assessment"), str):
            raise ValueError("bounded_agent_material_gain_assessment_missing")


class S3ThreeCellBoundedAgentExecutor:
    """Fixed six-node S3 topology over an injected provider-neutral node port."""

    def __init__(self, node_executor: S3ThreeCellAgentNodeExecutorPort) -> None:
        self._node_executor = node_executor

    @staticmethod
    def _case_numeric_authority_cell_input(
        cell_input: Mapping[str, Any],
        *,
        policy_ref: str = S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
    ) -> dict[str, Any]:
        """Adapt S4 flat and legacy numeric rows before any model view."""

        if policy_ref not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS:
            raise ValueError("s4_case_numeric_authority_policy_unsupported")
        adapted = deepcopy(dict(cell_input))
        numeric_input = adapted.get("numeric_input")
        authority = adapted.get("authority_refs")
        if not isinstance(numeric_input, Mapping) or not isinstance(
            authority, Mapping
        ):
            raise ValueError(
                "s4_case_numeric_projection_input_shape_invalid"
            )
        refs: list[str] = []
        for row in numeric_input.get(
            "selected_financial_rows", ()
        ):
            if isinstance(row, Mapping):
                ref = str(
                    row.get("numeric_ref")
                    or row.get("financial_row_id")
                    or ""
                )
                if ref:
                    refs.append(ref)
        for row in numeric_input.get("derived_metrics", ()):
            if isinstance(row, Mapping):
                ref = str(
                    row.get("derived_metric_ref")
                    or row.get("derived_metric_id")
                    or ""
                )
                if ref:
                    refs.append(ref)
        if len(refs) != len(set(refs)):
            raise ValueError(
                "s4_case_numeric_projection_duplicate_ref"
            )
        adapted["authority_refs"] = {
            **dict(authority),
            "numeric_refs": sorted(refs),
        }
        adapted["_case_numeric_authority_policy_ref"] = policy_ref
        return adapted

    @staticmethod
    def _first_s4_final_artifact_safety_violation(
        *,
        artifact_payloads: Mapping[str, Mapping[str, Any]],
        specialists: list[Mapping[str, Any]],
        writer: Mapping[str, Any],
        verifier: Mapping[str, Any],
        case_numeric_policies: Mapping[
            str, CaseNumericAuthorityPolicy
        ],
        case_numeric_contracts: list[Mapping[str, Any]],
        case_delivery_identity_projection: Mapping[
            str, Any
        ]
        | None,
        require_s4_runtime_projection: bool,
        artifact_lineage_projection: Mapping[str, Any] | None = None,
    ) -> S4FinalArtifactSafetyViolation | None:
        """Recompute material truth and identity over the final 9 payloads."""

        def fail(
            subtype: str,
            artifact_type: str,
            field_id: str,
            count: int = 1,
        ) -> S4FinalArtifactSafetyViolation:
            return S4FinalArtifactSafetyViolation(
                subtype=subtype,
                artifact_type=artifact_type,
                field_id=field_id,
                failing_item_count=count,
            )

        missing = [
            kind
            for kind in BOUNDED_AGENT_ARTIFACT_TYPES
            if kind not in artifact_payloads
        ]
        if missing:
            return fail(
                "artifact_set_incomplete",
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                "artifact_types",
                len(missing),
            )
        if (
            not isinstance(
                case_delivery_identity_projection, Mapping
            )
            or not case_numeric_policies
            or not case_numeric_contracts
        ):
            return fail(
                "mandatory_projection_missing",
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                "case_safety_profile",
            )
        try:
            identity = CaseDeliveryIdentityPolicy.from_projection(
                case_delivery_identity_projection
            )
        except ValueError:
            return fail(
                "identity_projection_invalid",
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                "case_delivery_identity_projection",
            )

        expected_contracts = [
            policy.prompt_contract()
            for policy in case_numeric_policies.values()
        ]
        if list(case_numeric_contracts) != expected_contracts:
            return fail(
                "numeric_projection_correspondence_mismatch",
                BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
                "case_numeric_authority_projections",
            )

        manifest = artifact_payloads[
            BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
        ]
        trace_payload = artifact_payloads[
            BOUNDED_AGENT_TRACE_ARTIFACT_TYPE
        ]
        if artifact_lineage_projection is not None:
            expected_manifest_lineage = (
                artifact_lineage_projection.get("manifest")
            )
            expected_trace_lineage = (
                artifact_lineage_projection.get("trace_lineage")
            )
            if (
                not isinstance(expected_manifest_lineage, Mapping)
                or any(
                    manifest.get(key) != value
                    for key, value in expected_manifest_lineage.items()
                )
                or trace_payload.get("lineage")
                != expected_trace_lineage
            ):
                return fail(
                    "artifact_lineage_projection_mismatch",
                    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                    "lineage",
                )
        expected_manifest = {
            "case_runtime_safety_profile_ref": (
                S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF
            ),
            "case_numeric_authority_policy_ref": (
                next(iter(case_numeric_policies.values())).contract_ref
            ),
            "case_delivery_identity_policy_ref": (
                identity.contract_ref
            ),
            "case_ticker": identity.case_ticker,
            "case_numeric_projection_digests": [
                policy.projection_digest
                for policy in case_numeric_policies.values()
            ],
            "case_delivery_identity_projection_digest": (
                identity.projection_digest
            ),
        }
        if any(
            manifest.get(key) != value
            for key, value in expected_manifest.items()
        ):
            return fail(
                "manifest_safety_binding_mismatch",
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                "case_safety_profile",
            )

        numeric_payload = artifact_payloads[
            BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE
        ]
        if numeric_payload.get(
            "case_numeric_authority_projections"
        ) != expected_contracts:
            return fail(
                "numeric_projection_payload_mismatch",
                BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
                "case_numeric_authority_projections",
            )

        expected_numeric_facts: list[dict[str, Any]] = []
        for specialist in specialists:
            cell_id = str(
                specialist.get("program_cell_id") or ""
            )
            policy = case_numeric_policies.get(cell_id)
            if policy is None:
                return fail(
                    "cell_numeric_policy_missing",
                    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
                    "specialist_outputs.program_cell_id",
                )
            fact_layer = specialist.get("fact_layer")
            violation = policy.first_canonical_fact_violation(
                fact_layer
            )
            if violation is not None:
                return fail(
                    "canonical_numeric_fact_mismatch",
                    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
                    violation.field_id,
                    violation.failing_item_count,
                )
            expected_numeric_facts.extend(
                dict(fact)
                for fact in (
                    fact_layer
                    if isinstance(fact_layer, list)
                    else ()
                )
                if isinstance(fact, Mapping)
                and fact.get("support_type") == "Numeric"
            )
        if (
            numeric_payload.get("agent_numeric_fact_rows")
            != expected_numeric_facts
        ):
            return fail(
                "numeric_fact_artifact_mismatch",
                BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
                "agent_numeric_fact_rows",
            )

        judgment_payload = artifact_payloads[
            BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE
        ]
        workpaper_payload = artifact_payloads[
            BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE
        ]
        report_payload = artifact_payloads[
            BOUNDED_AGENT_REPORT_ARTIFACT_TYPE
        ]
        verification_payload = artifact_payloads[
            BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE
        ]
        if judgment_payload.get("specialist_outputs") != specialists:
            return fail(
                "judgment_specialist_projection_mismatch",
                BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
                "specialist_outputs",
            )
        if workpaper_payload.get("cells") != specialists:
            return fail(
                "workpaper_specialist_projection_mismatch",
                BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE,
                "cells",
            )
        if report_payload.get("report") != writer:
            return fail(
                "report_writer_projection_mismatch",
                BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                "report",
            )
        if verification_payload.get("verification") != verifier:
            return fail(
                "verification_projection_mismatch",
                BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
                "verification",
            )

        if (
            writer.get("title_zh_cn") != identity.title_zh_cn
            or workpaper_payload.get("entity_label")
            != identity.case_ticker
            or verification_payload.get("entity_label")
            != identity.case_ticker
            or report_payload.get(
                "case_delivery_identity_projection_digest"
            )
            != identity.projection_digest
        ):
            return fail(
                "delivery_identity_surface_mismatch",
                BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                "case_delivery_identity",
            )

        sections = writer.get("sections")
        if not isinstance(sections, list) or len(sections) != len(
            specialists
        ):
            return fail(
                "report_section_shape_mismatch",
                BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                "report.sections",
            )
        rendered_texts: list[str] = []
        specialists_by_cell = {
            str(row.get("program_cell_id") or ""): row
            for row in specialists
        }
        for section in sections:
            if not isinstance(section, Mapping):
                return fail(
                    "report_section_shape_mismatch",
                    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                    "report.sections",
                )
            cell_id = str(
                section.get("program_cell_id") or ""
            )
            specialist = specialists_by_cell.get(cell_id)
            policy = case_numeric_policies.get(cell_id)
            renderings = section.get("claim_renderings")
            if (
                specialist is None
                or policy is None
                or not isinstance(renderings, list)
            ):
                return fail(
                    "report_cell_projection_mismatch",
                    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                    "report.sections.program_cell_id",
                )
            claims = specialist.get("judgment_layer")
            facts = {
                str(fact.get("fact_id") or ""): fact
                for fact in specialist.get("fact_layer", ())
                if isinstance(fact, Mapping)
            }
            if not isinstance(claims, list) or len(renderings) != len(
                claims
            ):
                return fail(
                    "report_claim_cardinality_mismatch",
                    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                    "report.sections.claim_renderings",
                )
            for claim, rendering in zip(
                claims, renderings, strict=True
            ):
                if not isinstance(claim, Mapping) or not isinstance(
                    rendering, Mapping
                ):
                    return fail(
                        "report_claim_rendering_shape_mismatch",
                        BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                        "report.sections.claim_renderings",
                    )
                numeric_refs = [
                    str(ref)
                    for fact_id in claim.get(
                        "support_fact_ids", ()
                    )
                    for ref in facts.get(
                        str(fact_id), {}
                    ).get("support_refs", ())
                    if facts.get(
                        str(fact_id), {}
                    ).get("support_type")
                    == "Numeric"
                ]
                expected_prefix = "；".join(
                    policy.rendered_clauses_for_refs(numeric_refs)
                )
                rendered_text = str(
                    rendering.get("rendered_text_zh_cn") or ""
                )
                if expected_prefix:
                    prefix = f"{expected_prefix}；"
                    if not rendered_text.startswith(prefix):
                        return fail(
                            "report_numeric_rendering_mismatch",
                            BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                            (
                                "report.sections.claim_renderings."
                                "rendered_text_zh_cn"
                            ),
                        )
                    narrative_suffix = rendered_text[len(prefix):]
                else:
                    narrative_suffix = rendered_text
                narrative_violation = (
                    policy.first_provider_narrative_violation(
                        {
                            "analysis_text_zh_cn": (
                                narrative_suffix
                            )
                        }
                    )
                )
                if narrative_violation is not None:
                    return fail(
                        "report_nonlocal_numeric_token",
                        BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                        narrative_violation.field_id,
                        narrative_violation.failing_item_count,
                    )
                rendered_texts.append(rendered_text)
        if writer.get("executive_summary_zh_cn") != "；".join(
            rendered_texts
        ):
            return fail(
                "report_summary_projection_mismatch",
                BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
                "report.executive_summary_zh_cn",
            )

        first_policy = (
            CaseNumericAuthorityPolicy.combined_narrative_classifier(
                list(case_numeric_policies.values())
            )
        )
        verifier_numeric = (
            first_policy.first_provider_narrative_violation(verifier)
        )
        if verifier_numeric is not None:
            return fail(
                "verification_nonlocal_numeric_token",
                BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
                verifier_numeric.field_id,
                verifier_numeric.failing_item_count,
            )
        if (
            identity.first_provider_narrative_identity_violation(
                verifier
            )
            is not None
        ):
            return fail(
                "verification_nonlocal_identity_token",
                BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
                "verification",
            )

        wrong_runtime_labels = (
            sum(
                1
                for payload in artifact_payloads.values()
                if not isinstance(
                    payload.get("s4_case_runtime"), Mapping
                )
                or payload["s4_case_runtime"].get("case_ticker")
                != identity.case_ticker
            )
            if require_s4_runtime_projection
            else 0
        )
        if wrong_runtime_labels:
            return fail(
                "artifact_runtime_identity_mismatch",
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                "s4_case_runtime.case_ticker",
                wrong_runtime_labels,
            )
        return None

    def execute(
        self,
        input_pack: S3ThreeCellBoundedAgentInputPack,
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        lifecycle: dict[str, Any] = {
            "lifecycle_phase": "node_envelope_accounting",
            "failure_code": "s3_bounded_node_envelope_accounting_failed",
            "completed_node_receipts": [],
            "usage_receipts": [],
            "local_fact_receipts": [],
            "provider_output_captures": [],
            "quality_observations": [],
            "recoverable_protocol_findings": [],
            "observed_counts": {
                "model_calls": 0,
                "provider_calls": 0,
                "network_calls": 0,
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "live_case_head_writes": 0,
                "evaluation_evidence_promotions": 0,
            },
        }
        try:
            return self._execute_with_lifecycle(
                input_pack,
                admission,
                run_identity=run_identity,
                lifecycle=lifecycle,
            )
        except BoundedAgentExecutionError as exc:
            if (
                lifecycle["usage_receipts"]
                or lifecycle["provider_output_captures"]
                or exc.failure_observation.get("usage_receipts")
                or exc.failure_observation.get("local_fact_receipts")
                or exc.provider_output_captures
            ):
                _upgrade_s3_post_provider_failure_error(exc, lifecycle)
            raise
        except Exception as exc:
            if not (
                lifecycle["usage_receipts"]
                or lifecycle["local_fact_receipts"]
                or lifecycle["provider_output_captures"]
            ):
                raise
            raise build_s3_post_provider_failure_error(
                lifecycle_phase=str(lifecycle["lifecycle_phase"]),
                failure_code=str(lifecycle["failure_code"]),
                execution_observation=lifecycle,
                provider_output_captures=(
                    lifecycle["provider_output_captures"]
                ),
            ) from exc

    def _execute_with_lifecycle(
        self,
        input_pack: S3ThreeCellBoundedAgentInputPack,
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
        lifecycle: dict[str, Any],
    ) -> BoundedAgentExecutionOutput:
        admission.assert_profile_admissible()
        if input_pack.execution_profile_version_ref != admission.execution_profile_version_ref:
            raise ValueError("s3_bounded_input_profile_identity_mismatch")
        if admission.execution_enabled and (
            admission.case_id != input_pack.case_id
            or admission.case_version != input_pack.case_version
            or admission.as_of != input_pack.as_of
            or admission.input_digest != input_pack.input_digest
        ):
            raise ValueError("s3_bounded_admission_exact_input_mismatch")

        s4_binding: S4CaseRuntimeBinding | None = None
        s4_consumer_injections: dict[str, dict[str, Any]] = {}
        if input_pack.s4_case_runtime is not None:
            raw_binding = input_pack.s4_case_runtime.get("binding")
            raw_injections = input_pack.s4_case_runtime.get(
                "consumer_injections"
            )
            if not isinstance(raw_binding, Mapping) or not isinstance(
                raw_injections, Mapping
            ):
                raise ValueError("s4_case_runtime_input_shape_invalid")
            s4_binding = S4CaseRuntimeBinding.model_validate(dict(raw_binding))
            raw_overlay = input_pack.s4_case_runtime.get(
                "research_profile_overlay"
            )
            if raw_overlay is not None:
                if not isinstance(raw_overlay, Mapping):
                    raise ValueError(
                        "s4_case_runtime_research_profile_overlay_invalid"
                    )
                assert_s4_case_runtime_research_profile_overlay(
                    s4_binding,
                    raw_overlay,
                )
            elif not s4_binding.research_profile_ref.endswith(":v1"):
                raise ValueError(
                    "s4_case_runtime_research_profile_overlay_required"
                )
            for consumer_id in S4_RUNTIME_CONSUMER_IDS:
                injection = raw_injections.get(consumer_id)
                if not isinstance(injection, Mapping):
                    raise ValueError(
                        "s4_case_runtime_consumer_injection_missing"
                    )
                assert_s4_consumer_injection(
                    s4_binding, injection, consumer_id
                )
                s4_consumer_injections[consumer_id] = dict(injection)
            if (
                input_pack.company != s4_binding.case_ticker
                or input_pack.as_of != s4_binding.as_of
                or input_pack.program_cell_ids
                != s4_binding.program_cell_ids
                or not input_pack.decision_surface_contract_ref.strip()
                or admission.company != s4_binding.case_ticker
                or admission.research_profile_ref
                != s4_binding.research_profile_ref
                or input_pack.s4_case_runtime.get(
                    "paid_execution_authorized"
                )
                is not False
            ):
                raise ValueError("s4_case_runtime_input_identity_mismatch")
            if (
                admission.case_numeric_authority_policy_ref
                not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
                or admission.case_delivery_identity_policy_ref
                not in S4_CASE_DELIVERY_IDENTITY_POLICY_REFS
            ):
                raise ValueError(
                    "s4_case_runtime_mandatory_material_truth_and_"
                    "identity_safety_profile_required"
                )

        case_numeric_policies: dict[
            str, CaseNumericAuthorityPolicy
        ] = {}
        case_numeric_contracts: list[dict[str, Any]] = []
        case_delivery_identity_projection: dict[str, Any] | None = None
        if (
            admission.case_numeric_authority_policy_ref
            in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
        ):
            if (
                admission.case_delivery_identity_policy_ref
                not in S4_CASE_DELIVERY_IDENTITY_POLICY_REFS
            ):
                raise ValueError(
                    "s4_case_numeric_and_identity_policy_pair_required"
                )
            for cell_input in input_pack.cell_inputs:
                adapted_cell_input = (
                    self._case_numeric_authority_cell_input(
                        cell_input,
                        policy_ref=str(
                            admission.case_numeric_authority_policy_ref
                        ),
                    )
                )
                policy = CaseNumericAuthorityPolicy.from_cell_input(
                    adapted_cell_input
                )
                cell_id = str(cell_input.get("program_cell_id") or "")
                case_numeric_policies[cell_id] = policy
                case_numeric_contracts.append(
                    policy.prompt_contract()
                )
            case_delivery_identity_projection = (
                CaseDeliveryIdentityPolicy.compile(
                    company=input_pack.company,
                    s4_case_runtime=input_pack.s4_case_runtime,
                    contract_ref=(
                        admission.case_delivery_identity_policy_ref
                        or S4_CASE_DELIVERY_IDENTITY_POLICY_REF
                    ),
                ).projection()
            )

        node_receipts = lifecycle["completed_node_receipts"]
        usage_receipts = lifecycle["usage_receipts"]
        local_fact_receipts = lifecycle["local_fact_receipts"]
        provider_output_captures = lifecycle["provider_output_captures"]
        quality_observations = lifecycle["quality_observations"]
        recoverable_protocol_findings = lifecycle[
            "recoverable_protocol_findings"
        ]
        observed_counts = lifecycle["observed_counts"]

        def run_node(node_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
            lifecycle["lifecycle_phase"] = "node_envelope_accounting"
            lifecycle["failure_code"] = (
                "s3_bounded_node_envelope_accounting_failed"
            )
            raw = self._node_executor.execute_node(
                node_id,
                payload,
                admission,
                run_identity=run_identity,
            )
            if (
                not isinstance(raw, Mapping)
                or not {
                    "node_id",
                    "output",
                    "observed_counts",
                    "usage_receipts",
                    "version_bindings",
                }.issubset(raw)
                or set(raw)
                - {
                    "node_id",
                    "output",
                    "observed_counts",
                    "usage_receipts",
                    "version_bindings",
                    "provider_output_captures",
                    "local_fact_receipts",
                    "quality_observations",
                    "recoverable_protocol_findings",
                }
            ):
                raise ValueError(f"s3_bounded_node_envelope_invalid:{node_id}")
            if raw.get("node_id") != node_id or not isinstance(raw.get("output"), Mapping):
                raise ValueError(f"s3_bounded_node_identity_or_output_invalid:{node_id}")
            counts = raw.get("observed_counts")
            if not isinstance(counts, Mapping):
                raise ValueError(f"s3_bounded_node_counts_missing:{node_id}")
            for key in observed_counts:
                try:
                    value = int(counts.get(key, 0))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"s3_bounded_node_count_invalid:{node_id}:{key}") from exc
                if value < 0:
                    raise ValueError(f"s3_bounded_node_count_invalid:{node_id}:{key}")
                observed_counts[key] += value
            if any(int(counts.get(key, 0)) != 0 for key in (
                "source_network_calls", "external_tool_calls", "live_case_head_writes"
            )):
                raise ValueError(f"s3_bounded_node_hard_boundary_violation:{node_id}")
            receipts = raw.get("usage_receipts")
            bindings = raw.get("version_bindings")
            if not isinstance(receipts, list) or not isinstance(bindings, Mapping):
                raise ValueError(f"s3_bounded_node_receipt_or_binding_invalid:{node_id}")
            if not all(
                isinstance(bindings.get(key), str) and str(bindings[key]).strip()
                for key in (
                    "agent_definition_version_ref",
                    "skill_pack_version_ref",
                )
            ):
                raise ValueError(f"s3_bounded_node_agent_or_skill_binding_missing:{node_id}")
            if (
                node_id.startswith("domain_specialist:")
                and admission.output_contract_ref in {
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
                }
                and (
                    bindings.get("model_view_contract_ref")
                    != S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF
                    or not re.fullmatch(
                        r"[0-9a-f]{64}", str(bindings.get("model_view_digest") or "")
                    )
                )
            ):
                raise ValueError(
                    f"s3_bounded_node_model_view_binding_missing:{node_id}"
                )
            usage_receipts.extend(dict(row) for row in receipts if isinstance(row, Mapping))
            local_receipts = raw.get("local_fact_receipts") or []
            if not isinstance(local_receipts, list) or any(
                not isinstance(row, Mapping) for row in local_receipts
            ):
                raise ValueError(
                    f"s3_bounded_node_local_fact_receipt_invalid:{node_id}"
                )
            for row in local_receipts:
                receipt = dict(row)
                if (
                    not node_id.startswith("domain_specialist:")
                    or receipt.get("contract_ref")
                    != S3_LOCAL_DETERMINISTIC_FACT_INTERACTION_CONTRACT_REF
                    or receipt.get("program_cell_id")
                    != node_id.split(":", 1)[1]
                    or any(
                        receipt.get(key) != 0
                        for key in (
                            "model_calls",
                            "provider_calls",
                            "network_calls",
                        )
                    )
                    or receipt.get("provider_capture_created") is not False
                    or not re.fullmatch(
                        r"[0-9a-f]{64}",
                        str(receipt.get("receipt_digest") or ""),
                    )
                    or receipt.get("receipt_digest")
                    != canonical_digest(
                        {
                            key: value
                            for key, value in receipt.items()
                            if key != "receipt_digest"
                        }
                    )
                ):
                    raise ValueError(
                        f"s3_bounded_node_local_fact_receipt_not_closed:{node_id}"
                    )
                local_fact_receipts.append(receipt)
            captures = raw.get("provider_output_captures") or []
            if not isinstance(captures, list) or any(
                not isinstance(row, Mapping) for row in captures
            ):
                raise ValueError(f"s3_bounded_node_output_capture_invalid:{node_id}")
            provider_output_captures.extend(dict(row) for row in captures)
            node_quality = raw.get("quality_observations") or []
            if not isinstance(node_quality, list) or any(
                not isinstance(row, Mapping) for row in node_quality
            ):
                raise ValueError(
                    f"s3_bounded_node_quality_observations_invalid:{node_id}"
                )
            for row in node_quality:
                observation = dict(row)
                if (
                    observation.get("quality_contract_ref")
                    not in NarrativeQualityPolicy.contract_refs
                    or observation.get("quality_code")
                    not in NarrativeQualityPolicy.quality_codes
                    or observation.get("terminal") is not False
                    or observation.get("raw_text_persisted") is not False
                    or observation.get("item_index_persisted") is not False
                ):
                    raise ValueError(
                        f"s3_bounded_node_quality_observation_not_closed:{node_id}"
                    )
                quality_observations.append(
                    {"node_id": node_id, **observation}
                )
            node_recoverable = raw.get(
                "recoverable_protocol_findings"
            ) or []
            if not isinstance(node_recoverable, list) or any(
                not isinstance(row, Mapping) for row in node_recoverable
            ):
                raise ValueError(
                    f"s3_bounded_node_recoverable_protocol_findings_invalid:{node_id}"
                )
            policy = S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY
            for row in node_recoverable:
                finding = dict(row)
                if (
                    node_id != "research_lead"
                    or finding.get("finding_code") != policy.finding_code
                    or finding.get("acceptance_layer")
                    != policy.acceptance_layer
                    or finding.get("terminal") is not False
                    or finding.get("projection_policy_ref")
                    != policy.policy_ref
                ):
                    raise ValueError(
                        f"s3_bounded_node_recoverable_protocol_finding_not_closed:{node_id}"
                    )
                recoverable_protocol_findings.append(
                    {"node_id": node_id, **finding}
                )
            output = dict(raw["output"])
            node_receipt = {
                "node_id": node_id,
                "input_digest": canonical_digest(payload),
                "output_digest": canonical_digest(output),
                "observed_counts": {
                    key: int(counts.get(key, 0))
                    for key in observed_counts
                },
                "version_bindings": dict(bindings),
            }
            s4_node_injection = payload.get("s4_case_runtime")
            if isinstance(s4_node_injection, Mapping):
                node_receipt["s4_case_runtime_consumption"] = {
                    "runtime_binding_digest": s4_node_injection.get(
                        "runtime_binding_digest"
                    ),
                    "consumer_id": s4_node_injection.get("consumer_id"),
                    "injection_digest": s4_node_injection.get(
                        "injection_digest"
                    ),
                }
            node_receipts.append(node_receipt)
            return output

        def validate_post_node(
            stage: str,
            validator_family: str,
            validator: Callable[..., None],
            *args: Any,
            **kwargs: Any,
        ) -> None:
            lifecycle["lifecycle_phase"] = "post_node_validation"
            lifecycle["failure_code"] = (
                "s3_bounded_post_node_validation_failed"
            )
            try:
                validator(*args, **kwargs)
            except ValueError as exc:
                estimated_cost_usd = sum(
                    float(row.get("estimated_cost_usd") or 0.0)
                    for row in usage_receipts
                )
                scoped_error = (
                    exc if isinstance(exc, S3ScopedIdentityContractError) else None
                )
                raise BoundedAgentExecutionError(
                    f"{stage}:post_node_validation",
                    usage_receipts=usage_receipts,
                    estimated_cost_usd=estimated_cost_usd,
                    failure_codes=tuple(
                        value
                        for value in (
                            "s3_bounded_post_node_validation_failed:"
                            f"{validator_family}",
                            (
                                scoped_error.failure_code
                                if scoped_error is not None
                                else None
                            ),
                        )
                        if value is not None
                    ),
                    scoped_identity_contract=(
                        scoped_error.telemetry
                        if scoped_error is not None
                        else None
                    ),
                    provider_output_captures=provider_output_captures,
                ) from exc

        research_profile = research_profile_for_ref(
            admission.research_profile_ref
        )
        specialist_output_max_utf8_bytes = (
            specialist_local_assembly_capacity(
                transport_ref=admission.transport_ref,
                research_profile=research_profile,
            ).whole_union_limit_utf8_bytes
            if admission.transport_ref
            in S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS
            else S3_SPECIALIST_V2_MAX_SERIALIZED_UTF8_BYTES
        )
        specialists: list[dict[str, Any]] = []
        for cell_input in input_pack.cell_inputs:
            cell_id = str(cell_input["program_cell_id"])
            execution_cell_input = (
                self._case_numeric_authority_cell_input(
                    cell_input,
                    policy_ref=str(
                        admission.case_numeric_authority_policy_ref
                    ),
                )
                if cell_id in case_numeric_policies
                else cell_input
            )
            output = run_node(
                f"domain_specialist:{cell_id}",
                {
                    "input_contract_ref": input_pack.input_contract_ref,
                    "input_digest": input_pack.input_digest,
                    "cell_input": execution_cell_input,
                    "required_output_layers": [
                        "fact_layer",
                        "explanation_layer",
                        "judgment_layer",
                        "remaining_gaps",
                        "what_would_change",
                    ],
                    **(
                        {
                            "s4_case_runtime": s4_consumer_injections[
                                "specialist_and_research_lead"
                            ]
                        }
                        if s4_binding is not None
                        else {}
                    ),
                    **(
                        {
                            "case_numeric_authority_contract": (
                                case_numeric_policies[
                                    cell_id
                                ].prompt_contract()
                            ),
                            "case_delivery_identity_projection": (
                                case_delivery_identity_projection
                            ),
                        }
                        if cell_id in case_numeric_policies
                        else {}
                    ),
                },
            )
            validate_post_node(
                f"domain_specialist:{cell_id}",
                "specialist_output",
                self._validate_specialist_output,
                output,
                execution_cell_input,
                output_contract_ref=admission.output_contract_ref,
                max_serialized_utf8_bytes=specialist_output_max_utf8_bytes,
            )
            if cell_id in case_numeric_policies:
                violation = case_numeric_policies[
                    cell_id
                ].first_canonical_fact_violation(
                    output.get("fact_layer")
                )
                if violation is not None:
                    raise BoundedAgentExecutionError(
                        f"domain_specialist:{cell_id}:"
                        "post_node_numeric_L1_validation",
                        usage_receipts=usage_receipts,
                        estimated_cost_usd=sum(
                            float(
                                row.get("estimated_cost_usd")
                                or 0.0
                            )
                            for row in usage_receipts
                        ),
                        failure_codes=(
                            "s4_case_numeric_authority_"
                            f"{violation.subtype}",
                        ),
                        case_numeric_authority=(
                            violation.telemetry()
                        ),
                        provider_output_captures=(
                            provider_output_captures
                        ),
                    )
            specialists.append(output)

        specialist_digests = {
            str(row["program_cell_id"]): canonical_digest(row) for row in specialists
        }
        scoped_identity_surface: dict[str, Any] | None = None
        if (
            admission.output_contract_ref
            == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ):
            try:
                scoped_identity_surface = self._derive_scoped_identity_surface(
                    specialists
                )
            except S3ScopedIdentityContractError as exc:
                raise BoundedAgentExecutionError(
                    "scoped_identity_projection",
                    usage_receipts=usage_receipts,
                    estimated_cost_usd=sum(
                        float(row.get("estimated_cost_usd") or 0.0)
                        for row in usage_receipts
                    ),
                    failure_codes=(exc.failure_code,),
                    scoped_identity_contract=exc.telemetry,
                    provider_output_captures=provider_output_captures,
                ) from exc
        lead = run_node(
            "research_lead",
            {
                "input_digest": input_pack.input_digest,
                "lead_contract": input_pack.lead_contract,
                "specialist_outputs": specialists,
                "specialist_output_digests": specialist_digests,
                **(
                    {"scoped_identity_surface": scoped_identity_surface}
                    if scoped_identity_surface is not None
                    else {}
                ),
                **(
                    {
                        "s4_case_runtime": s4_consumer_injections[
                            "specialist_and_research_lead"
                        ]
                    }
                    if s4_binding is not None
                    else {}
                ),
                **(
                    {
                        "case_numeric_authority_contracts": (
                            case_numeric_contracts
                        ),
                        "case_delivery_identity_projection": (
                            case_delivery_identity_projection
                        ),
                    }
                    if case_numeric_contracts
                    and case_delivery_identity_projection is not None
                    else {}
                ),
            },
        )
        validate_post_node(
            "research_lead",
            "lead_output",
            self._validate_lead_output,
            lead,
            specialist_digests,
            specialist_outputs=specialists,
            scoped_identity_surface=scoped_identity_surface,
            output_contract_ref=admission.output_contract_ref,
        )
        lead_digest = canonical_digest(lead)
        writer = run_node(
            "memo_writer",
            {
                "input_digest": input_pack.input_digest,
                "writer_contract": input_pack.writer_contract,
                "specialist_heads": specialists,
                "cross_cell_lead": lead,
                "cross_cell_lead_digest": lead_digest,
                **(
                    {"scoped_identity_surface": scoped_identity_surface}
                    if scoped_identity_surface is not None
                    else {}
                ),
                **(
                    {
                        "s4_case_runtime": s4_consumer_injections[
                            "writer_verifier_and_review_surface"
                        ]
                    }
                    if s4_binding is not None
                    else {}
                ),
                **(
                    {
                        "case_numeric_authority_contracts": (
                            case_numeric_contracts
                        ),
                        "case_delivery_identity_projection": (
                            case_delivery_identity_projection
                        ),
                    }
                    if case_numeric_contracts
                    and case_delivery_identity_projection is not None
                    else {}
                ),
            },
        )
        validate_post_node(
            "memo_writer",
            "writer_output",
            self._validate_writer_output,
            writer,
            lead_digest,
            specialist_outputs=specialists,
            cross_cell_lead=lead,
            scoped_identity_surface=scoped_identity_surface,
            output_contract_ref=admission.output_contract_ref,
            case_numeric_authority_contracts=(
                case_numeric_contracts or None
            ),
            case_delivery_identity_projection=(
                case_delivery_identity_projection
            ),
        )
        writer_digest = canonical_digest(writer)
        verifier_payload: dict[str, Any] = {
            "input_digest": input_pack.input_digest,
            "verifier_contract": input_pack.verifier_contract,
            "lineage": input_pack.lineage,
            "specialist_output_digests": specialist_digests,
            "cross_cell_lead_digest": lead_digest,
            "writer_digest": writer_digest,
            "writer_output": writer,
            **(
                {
                    "case_numeric_authority_contracts": (
                        case_numeric_contracts
                    ),
                    "case_delivery_identity_projection": (
                        case_delivery_identity_projection
                    ),
                }
                if case_numeric_contracts
                and case_delivery_identity_projection is not None
                else {}
            ),
            **(
                {
                    "s4_case_runtime": s4_consumer_injections[
                        "writer_verifier_and_review_surface"
                    ]
                }
                if s4_binding is not None
                else {}
            ),
        }
        local_semantic_issues: list[str] = []
        if (
            admission.output_contract_ref
            in {
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
            }
        ):
            authority_surface_by_cell = {
                str(cell_input["program_cell_id"]): (
                    self._owner_grade_authority_surface(
                        self._case_numeric_authority_cell_input(
                            cell_input,
                            policy_ref=str(
                                admission.case_numeric_authority_policy_ref
                            ),
                        )
                        if str(cell_input["program_cell_id"])
                        in case_numeric_policies
                        else cell_input
                    )
                )
                for cell_input in input_pack.cell_inputs
            }
            specialist_claim_cards = {
                str(row["program_cell_id"]): {
                    "fact_layer": list(row["fact_layer"]),
                    "claim_cards": list(row["judgment_layer"]),
                    "what_would_change": list(row["what_would_change"]),
                }
                for row in specialists
            }
            verifier_payload.update(
                {
                    "verifier_input_contract_ref": (
                        "fin01.s3.owner_grade_verifier_input:v2"
                    ),
                    "authority_surface_by_cell": authority_surface_by_cell,
                    "specialist_claim_cards": specialist_claim_cards,
                    "cross_cell_lead": lead,
                    "local_semantic_issues": local_semantic_issues,
                    **(
                        {
                            "scoped_identity_contract_ref": (
                                admission.scoped_identity_contract_ref
                            ),
                            "scoped_identity_surface": scoped_identity_surface,
                        }
                        if scoped_identity_surface is not None
                        else {}
                    ),
                }
            )
            validate_post_node(
                "verifier",
                "verifier_input",
                self._validate_owner_grade_verifier_input,
                verifier_payload,
            )
        verifier = run_node(
            "verifier",
            verifier_payload,
        )
        validate_post_node(
            "verifier",
            "verifier_output",
            self._validate_verifier_output,
            verifier,
            lead_digest,
            writer_digest,
            output_contract_ref=admission.output_contract_ref,
            local_semantic_issues=local_semantic_issues,
            specialist_outputs=(
                specialists if scoped_identity_surface is not None else None
            ),
            scoped_identity_surface=scoped_identity_surface,
        )

        lifecycle["lifecycle_phase"] = "post_verifier_call_accounting"
        lifecycle["failure_code"] = (
            "s3_bounded_post_verifier_call_accounting_failed"
        )
        if not admission.execution_enabled and any(
            observed_counts[key] != 0
            for key in ("model_calls", "provider_calls", "network_calls")
        ):
            raise ValueError("s3_bounded_zero_call_probe_execution_violation")
        expected_execution_calls = (
            9
            if (
                admission.transport_ref
                in S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS
                and specialist_transport_contract(
                    admission.transport_ref
                ).local_deterministic_fact_interaction
            )
            else (
                12
                if admission.transport_ref
                in S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS
                else 6
            )
        )
        if admission.execution_enabled and any(
            observed_counts[key] != expected_execution_calls
            for key in ("model_calls", "provider_calls", "network_calls")
        ):
            raise ValueError("s3_bounded_exact_call_cardinality_violation")
        if (
            admission.execution_enabled
            and admission.local_fact_interaction_contract_ref is not None
            and (
                len(local_fact_receipts) != 3
                or len(usage_receipts) + len(local_fact_receipts) != 12
                or len(provider_output_captures) != 9
            )
        ):
            raise ValueError(
                "s3_bounded_exact_logical_interaction_cardinality_violation"
            )

        if (
            case_numeric_contracts
            and case_delivery_identity_projection is not None
        ):
            for specialist in specialists:
                cell_id = str(
                    specialist.get("program_cell_id") or ""
                )
                policy = case_numeric_policies.get(cell_id)
                if policy is None:
                    raise ValueError(
                        "s4_case_numeric_precommit_policy_missing"
                    )
                violation = policy.first_canonical_fact_violation(
                    specialist.get("fact_layer")
                )
                if violation is not None:
                    raise BoundedAgentExecutionError(
                        "pre_artifact_commit_numeric_L1_validation",
                        usage_receipts=usage_receipts,
                        estimated_cost_usd=sum(
                            float(
                                row.get("estimated_cost_usd")
                                or 0.0
                            )
                            for row in usage_receipts
                        ),
                        failure_codes=(
                            "s4_case_numeric_authority_"
                            f"{violation.subtype}",
                        ),
                        case_numeric_authority=(
                            violation.telemetry()
                        ),
                        provider_output_captures=(
                            provider_output_captures
                        ),
                    )
            identity_policy = (
                CaseDeliveryIdentityPolicy.from_projection(
                    case_delivery_identity_projection
                )
            )
            if writer.get("title_zh_cn") != (
                identity_policy.title_zh_cn
            ):
                raise BoundedAgentExecutionError(
                    "pre_artifact_commit_delivery_identity_L1_validation",
                    usage_receipts=usage_receipts,
                    estimated_cost_usd=sum(
                        float(
                            row.get("estimated_cost_usd") or 0.0
                        )
                        for row in usage_receipts
                    ),
                    failure_codes=(
                        "s4_case_delivery_identity_title_mismatch",
                    ),
                    case_delivery_identity={
                        "contract_ref": (
                            identity_policy.contract_ref
                        ),
                        "acceptance_layer": "L1_hard_integrity",
                        "failure_subtype": "title_mismatch",
                        "raw_text_persisted": False,
                    },
                    provider_output_captures=(
                        provider_output_captures
                    ),
                )

        lifecycle["lifecycle_phase"] = "execution_artifact_assembly"
        lifecycle["failure_code"] = (
            "s3_bounded_execution_artifact_assembly_failed"
        )
        hard_boundaries = {
            "candidate_is_evidence": 0,
            "graph_edge_is_evidence": 0,
            "writer_source_or_tool_calls": 0,
            "adapter_direct_canonical_writes": 0,
            "live_business_case_head_writes": 0,
            "release_admission": 0,
        }
        lineage_contract = (
            compile_profile_aware_artifact_lineage_contract(
                input_pack.lineage,
                s4_case_runtime=input_pack.s4_case_runtime,
            )
        )
        fact_rows = [
            dict(fact)
            for specialist in specialists
            for fact in specialist.get("fact_layer", ())
            if isinstance(fact, Mapping)
        ]
        artifact_payloads: dict[str, dict[str, Any]] = {
            BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-manifest",
                "admission_id": admission.admission_id,
                "input_contract_ref": input_pack.input_contract_ref,
                "output_contract_ref": admission.output_contract_ref,
                "input_digest": input_pack.input_digest,
                "input_head_digest": input_pack.input_head_digest,
                "lineage_contract_ref": lineage_contract.contract_ref,
                "lineage_family": lineage_contract.lineage_family,
                "lineage_digest": lineage_contract.lineage_digest,
                "program_cell_ids": list(input_pack.program_cell_ids),
                "node_topology": [row["node_id"] for row in node_receipts],
                "node_receipts": node_receipts,
                "usage_receipts": usage_receipts,
                "local_fact_receipts": local_fact_receipts,
                "observed_counts": observed_counts,
                "hard_boundaries": hard_boundaries,
                "quality_observations": quality_observations,
                "recoverable_protocol_findings": (
                    recoverable_protocol_findings
                ),
            },
            BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-evidence",
                "input_digest": input_pack.input_digest,
                "cell_evidence_inputs": [
                    {
                        "program_cell_id": row["program_cell_id"],
                        "evidence_input": row["evidence_input"],
                        "accepted_evidence_refs": row["authority_refs"]["accepted_evidence_refs"],
                    }
                    for row in input_pack.cell_inputs
                ],
                "agent_fact_rows": [row for row in fact_rows if row.get("support_type") == "Evidence"],
                "live_evidence_head_promoted": False,
            },
            BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-numeric",
                "input_digest": input_pack.input_digest,
                "cell_numeric_inputs": [
                    {"program_cell_id": row["program_cell_id"], "numeric_input": row["numeric_input"]}
                    for row in input_pack.cell_inputs
                ],
                "agent_numeric_fact_rows": [row for row in fact_rows if row.get("support_type") == "Numeric"],
            },
            BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-judgment",
                "specialist_outputs": specialists,
                "specialist_output_digests": specialist_digests,
                "cross_cell_lead": lead,
                "cross_cell_lead_digest": lead_digest,
                "quality_observations": quality_observations,
                "recoverable_protocol_findings": (
                    recoverable_protocol_findings
                ),
                **(
                    {"scoped_identity_surface": scoped_identity_surface}
                    if scoped_identity_surface is not None
                    else {}
                ),
            },
            BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-workpaper",
                "input_digest": input_pack.input_digest,
                "cells": specialists,
                "cross_cell_lead_digest": lead_digest,
                **(
                    {"scoped_identity_surface": scoped_identity_surface}
                    if scoped_identity_surface is not None
                    else {}
                ),
            },
            BOUNDED_AGENT_REPORT_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-report",
                "mode": "model_no_source_three_cell_writer",
                "writer_source_calls": 0,
                "writer_tool_calls": 0,
                "writer_digest": writer_digest,
                "report": writer,
            },
            BOUNDED_AGENT_TRACE_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-trace",
                "input_digest": input_pack.input_digest,
                "lineage": input_pack.lineage,
                "node_receipts": node_receipts,
                "local_fact_receipts": local_fact_receipts,
                "private_reasoning_persisted": False,
                "raw_provider_response_persisted": False,
            },
            BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-bounded-agent-verification",
                "input_digest": input_pack.input_digest,
                "cross_cell_lead_digest": lead_digest,
                "writer_digest": writer_digest,
                "verification": verifier,
                "machine_verifier_is_human_acceptance": False,
            },
            BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE: {
                "artifact_ref": "logical:s3-agent-fallback-comparison",
                "paired_input_digest": input_pack.input_digest,
                "paired_baseline_contract": input_pack.paired_baseline_contract,
                "agent_research_run_id": run_identity["research_run_id"],
                "deterministic_research_run_id": None,
                "comparison_status": "pending_distinct_terminal_deterministic_run",
                "baseline_output_body_exposed_to_agent": False,
                "automatic_fallback_performed": False,
                "owner_review_status": "not_performed",
            },
        }
        if admission.local_fact_interaction_contract_ref is not None:
            interaction_topology = {
                "logical_node_count": len(node_receipts),
                "logical_interaction_count": (
                    len(usage_receipts) + len(local_fact_receipts)
                ),
                "local_fact_interaction_count": len(local_fact_receipts),
                "provider_interaction_count": len(usage_receipts),
                "provider_capture_count": len(provider_output_captures),
                "business_artifact_count": len(
                    BOUNDED_AGENT_ARTIFACT_TYPES
                ),
            }
            artifact_payloads[
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
            ]["interaction_topology"] = interaction_topology
            artifact_payloads[
                BOUNDED_AGENT_TRACE_ARTIFACT_TYPE
            ]["interaction_topology"] = interaction_topology
        if (
            case_numeric_contracts
            and case_delivery_identity_projection is not None
        ):
            identity_policy = (
                CaseDeliveryIdentityPolicy.from_projection(
                    case_delivery_identity_projection
                )
            )
            artifact_payloads[
                BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
            ].update(
                {
                    "case_runtime_safety_profile_ref": (
                        S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF
                    ),
                    "case_numeric_authority_policy_ref": (
                        str(admission.case_numeric_authority_policy_ref)
                    ),
                    "case_delivery_identity_policy_ref": (
                        identity_policy.contract_ref
                    ),
                    "case_ticker": identity_policy.case_ticker,
                    "case_numeric_projection_digests": [
                        str(row["projection_digest"])
                        for row in case_numeric_contracts
                    ],
                    "case_delivery_identity_projection_digest": (
                        identity_policy.projection_digest
                    ),
                }
            )
            artifact_payloads[
                BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE
            ]["case_numeric_authority_projections"] = deepcopy(
                case_numeric_contracts
            )
            artifact_payloads[
                BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE
            ]["entity_label"] = identity_policy.case_ticker
            artifact_payloads[
                BOUNDED_AGENT_REPORT_ARTIFACT_TYPE
            ]["case_delivery_identity_projection_digest"] = (
                identity_policy.projection_digest
            )
            artifact_payloads[
                BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE
            ]["entity_label"] = identity_policy.case_ticker
        if s4_binding is not None:
            s4_runtime_payload = input_pack.s4_case_runtime or {}
            s4_source_payload = s4_runtime_payload.get(
                "source_grounded_input"
            )
            s4_overlay_payload = s4_runtime_payload.get(
                "research_profile_overlay"
            )
            if not isinstance(s4_source_payload, Mapping):
                raise ValueError(
                    "s4_case_runtime_source_grounded_input_missing"
                )
            s4_artifact_projection = {
                "runtime_binding_contract_ref": s4_binding.contract_ref,
                "runtime_binding_digest": (
                    s4_binding.runtime_binding_digest
                ),
                "case_ticker": s4_binding.case_ticker,
                "issuer_identifier": s4_binding.issuer_identifier,
                "case_profile_ref": s4_binding.case_profile_ref,
                "case_pack_sha256": s4_binding.case_pack_sha256,
                "method_contract_ref": s4_binding.method_contract_ref,
                "method_contract_sha256": (
                    s4_binding.method_contract_sha256
                ),
                "source_grounded_input_contract_ref": (
                    s4_source_payload.get("contract_ref")
                ),
                "source_grounded_input_digest": (
                    s4_source_payload.get("source_pack_digest")
                ),
                "research_profile_ref": (
                    s4_binding.research_profile_ref
                ),
                "method_id": s4_binding.method_id,
                "case_identity_namespace": (
                    s4_binding.case_identity_namespace
                ),
                "workbench_projection": s4_consumer_injections[
                    "workbench_projection"
                ],
                "paid_artifact_proven": False,
                "human_review_completed": False,
            }
            if isinstance(s4_overlay_payload, Mapping):
                s4_artifact_projection[
                    "research_profile_overlay"
                ] = {
                    key: s4_overlay_payload.get(key)
                    for key in (
                        "contract_ref",
                        "research_profile_ref",
                        "research_profile_contract_digest",
                        "base_runtime_binding_digest",
                        "effective_runtime_binding_digest",
                        "overlay_digest",
                    )
                }
            for artifact_payload in artifact_payloads.values():
                artifact_payload["s4_case_runtime"] = (
                    s4_artifact_projection
                )
        if (
            case_numeric_contracts
            and case_delivery_identity_projection is not None
        ):
            final_violation = (
                self._first_s4_final_artifact_safety_violation(
                    artifact_payloads=artifact_payloads,
                    specialists=specialists,
                    writer=writer,
                    verifier=verifier,
                    case_numeric_policies=case_numeric_policies,
                    case_numeric_contracts=case_numeric_contracts,
                    case_delivery_identity_projection=(
                        case_delivery_identity_projection
                    ),
                    require_s4_runtime_projection=(
                        s4_binding is not None
                    ),
                    artifact_lineage_projection={
                        "manifest": {
                            "lineage_contract_ref": (
                                lineage_contract.contract_ref
                            ),
                            "lineage_family": (
                                lineage_contract.lineage_family
                            ),
                            "lineage_digest": (
                                lineage_contract.lineage_digest
                            ),
                        },
                        "trace_lineage": input_pack.lineage,
                    },
                )
            )
            if final_violation is not None:
                raise BoundedAgentExecutionError(
                    "final_artifact_material_truth_identity_L1_envelope",
                    usage_receipts=usage_receipts,
                    estimated_cost_usd=sum(
                        float(
                            row.get("estimated_cost_usd") or 0.0
                        )
                        for row in usage_receipts
                    ),
                    failure_codes=(
                        "s4_final_artifact_material_truth_identity_"
                        f"{final_violation.subtype}",
                    ),
                    final_artifact_safety=(
                        final_violation.telemetry()
                    ),
                    provider_output_captures=(
                        provider_output_captures
                    ),
                )
        trace_events = tuple(
            {
                "event_type": "S3_BOUNDED_AGENT_NODE_COMPLETED",
                "event_payload": {
                    "node_id": row["node_id"],
                    "input_digest": row["input_digest"],
                    "output_digest": row["output_digest"],
                },
            }
            for row in node_receipts
        ) + (
            {
                "event_type": "S3_BOUNDED_AGENT_EXECUTION_COMPLETED",
                "event_payload": {
                    "cell_count": 3,
                    "node_count": 6,
                    "observed_counts": observed_counts,
                },
            },
        )
        return BoundedAgentExecutionOutput(
            terminal_reason="s3_bounded_agent_three_cell_execution_succeeded",
            artifacts=tuple(
                BoundedAgentArtifact(artifact_type=kind, payload=artifact_payloads[kind])
                for kind in BOUNDED_AGENT_ARTIFACT_TYPES
            ),
            trace_events=trace_events,
            provider_output_captures=tuple(provider_output_captures),
            execution_observation={
                "contract_ref": (
                    S3_POST_PROVIDER_FAILURE_ENVELOPE_CONTRACT_REF
                ),
                "completed_node_receipts": [
                    dict(row) for row in node_receipts
                ],
                "usage_receipts": [
                    dict(row) for row in usage_receipts
                ],
                "local_fact_receipts": [
                    dict(row) for row in local_fact_receipts
                ],
                "observed_counts": dict(observed_counts),
            },
        )

    @staticmethod
    def _validate_specialist_output(
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
        *,
        output_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
        max_serialized_utf8_bytes: int = S3_SPECIALIST_V2_MAX_SERIALIZED_UTF8_BYTES,
    ) -> None:
        cell_id = str(cell_input["program_cell_id"])
        required = {
            "program_cell_id",
            "fact_layer",
            "explanation_layer",
            "judgment_layer",
            "remaining_gaps",
            "what_would_change",
            "terminal_class",
        }
        if set(output) != required or output.get("program_cell_id") != cell_id:
            raise ValueError(f"s3_bounded_specialist_output_schema_invalid:{cell_id}")
        for key in (
            "fact_layer", "explanation_layer", "judgment_layer", "remaining_gaps", "what_would_change"
        ):
            if not isinstance(output.get(key), list):
                raise ValueError(f"s3_bounded_specialist_output_schema_invalid:{cell_id}:{key}")
        authority = cell_input.get("authority_refs")
        if not isinstance(authority, Mapping):
            raise ValueError(f"s3_bounded_specialist_authority_refs_missing:{cell_id}")
        allowed = {
            "Evidence": set(map(str, authority.get("accepted_evidence_refs", ()))),
            "Numeric": set(map(str, authority.get("numeric_refs", ()))),
        }
        forbidden = set(map(str, authority.get("candidate_refs_not_evidence", ())))
        forbidden.update(map(str, authority.get("graph_context_refs_not_evidence", ())))
        observed_fact_ids: set[str] = set()
        for fact in output.get("fact_layer", ()):
            if not isinstance(fact, Mapping) or set(fact) != {
                "fact_id", "statement", "support_type", "support_refs", "boundary"
            }:
                raise ValueError(f"s3_bounded_specialist_fact_schema_invalid:{cell_id}")
            support_type = str(fact.get("support_type") or "")
            raw_refs = fact.get("support_refs")
            refs = set(map(str, raw_refs or ()))
            if support_type not in allowed or not refs or not refs.issubset(allowed[support_type]):
                raise ValueError(f"s3_bounded_specialist_fact_authority_invalid:{cell_id}")
            if refs & forbidden:
                raise ValueError(f"s3_bounded_candidate_or_graph_promoted_to_fact:{cell_id}")
            if output_contract_ref in {
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
            }:
                fact_id = str(fact.get("fact_id") or "")
                if (
                    not fact_id
                    or fact_id in observed_fact_ids
                    or not isinstance(raw_refs, list)
                    or any(not isinstance(ref, str) or not ref for ref in raw_refs)
                    or len(raw_refs) != len(refs)
                ):
                    raise ValueError(
                        f"s3_bounded_specialist_fact_or_ref_duplicate_invalid:{cell_id}"
                    )
                observed_fact_ids.add(fact_id)
        if not str(output.get("terminal_class") or ""):
            raise ValueError(f"s3_bounded_specialist_terminal_class_missing:{cell_id}")
        if output_contract_ref in {
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        }:
            if len(output["fact_layer"]) > S3_SPECIALIST_V2_MAX_FACTS:
                raise ValueError(
                    f"s3_bounded_specialist_output_cardinality_invalid:{cell_id}:fact_layer"
                )
            narrative_keys = (
                S3_SPECIALIST_V2_NARRATIVE_CARDINALITY
                if output_contract_ref
                == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF
                else {
                    "explanation_layer": (1, 3),
                    "remaining_gaps": (1, 4),
                }
            )
            for key, (minimum, maximum) in narrative_keys.items():
                values = output[key]
                if not minimum <= len(values) <= maximum:
                    raise ValueError(
                        f"s3_bounded_specialist_output_cardinality_invalid:{cell_id}:{key}"
                    )
                if any(
                    not isinstance(value, str)
                    or not value.strip()
                    or len(value) > S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS
                    for value in values
                ):
                    raise ValueError(
                        f"s3_bounded_specialist_output_text_length_invalid:{cell_id}:{key}"
                    )
            for fact in output["fact_layer"]:
                if any(
                    not isinstance(fact.get(key), str)
                    or not str(fact[key]).strip()
                    or len(str(fact[key])) > S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS
                    for key in ("statement", "boundary")
                ):
                    raise ValueError(
                        f"s3_bounded_specialist_output_text_length_invalid:{cell_id}:fact_layer"
                    )
            if (
                output_contract_ref
                in {
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
                }
            ):
                S3ThreeCellBoundedAgentExecutor._validate_owner_grade_claims_and_tasks(
                    output, cell_input
                )
            serialized_bytes = len(
                json.dumps(
                    dict(output),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if serialized_bytes > max_serialized_utf8_bytes:
                raise ValueError(
                    f"s3_bounded_specialist_output_byte_budget_exceeded:{cell_id}"
                )

    @staticmethod
    def _owner_grade_authority_surface(
        cell_input: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Project only the structured authority needed for claim-scope validation."""

        authority = cell_input.get("authority_refs")
        if not isinstance(authority, Mapping):
            authority = {}
        numeric_input = cell_input.get("numeric_input")
        if not isinstance(numeric_input, Mapping):
            numeric_input = {}
        fundamental = numeric_input.get("fundamental_decision_cell")
        if not isinstance(fundamental, Mapping):
            fundamental = {}
        inherited_cannot_support = [
            str(value)
            for value in fundamental.get("typed_cannot_infer", ())
            if isinstance(value, str) and value.strip()
        ]
        numeric_fact_scope: dict[str, dict[str, Any]] = {}
        if (
            cell_input.get("_case_numeric_authority_policy_ref")
            in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
        ):
            policy = CaseNumericAuthorityPolicy.from_cell_input(
                cell_input
            )
            for row in policy.rows:
                company_total = (
                    row.business_scope_ref
                    == "__company_total__"
                )
                numeric_fact_scope[row.numeric_ref] = {
                    "entity_ref": row.entity_ref,
                    "business_scope_kind": (
                        "company_total"
                        if company_total
                        else "segment"
                        if row.authority_kind
                        == "financial_row"
                        else "unknown"
                    ),
                    "business_scope_ref": (
                        row.business_scope_ref
                    ),
                    "period": row.period,
                    "metric_or_mechanism": (
                        row.metric_family
                    ),
                    "attribution_level": (
                        "company_total"
                        if company_total
                        else "segment"
                        if row.authority_kind
                        == "financial_row"
                        else "none"
                    ),
                    "cannot_support": sorted(
                        set(inherited_cannot_support)
                        | set(row.cannot_support)
                    ),
                }
            return {
                "accepted_evidence_refs": sorted(
                    set(
                        map(
                            str,
                            authority.get(
                                "accepted_evidence_refs", ()
                            ),
                        )
                    )
                ),
                "numeric_fact_scope_and_cannot_support": (
                    numeric_fact_scope
                ),
                "candidate_refs_not_evidence": sorted(
                    set(
                        map(
                            str,
                            authority.get(
                                "candidate_refs_not_evidence",
                                (),
                            ),
                        )
                    )
                ),
                "graph_context_refs_not_evidence": sorted(
                    set(
                        map(
                            str,
                            authority.get(
                                "graph_context_refs_not_evidence",
                                (),
                            ),
                        )
                    )
                ),
            }
        for row in numeric_input.get("selected_financial_rows", ()):
            if not isinstance(row, Mapping):
                continue
            ref = str(row.get("financial_row_id") or "")
            selector = row.get("selector")
            if not ref or not isinstance(selector, Mapping):
                continue
            segment_ref = str(selector.get("segment_ref") or "unknown")
            numeric_fact_scope[ref] = {
                "entity_ref": str(selector.get("entity_ref") or "unknown"),
                "business_scope_kind": (
                    "company_total"
                    if segment_ref == "__company_total__"
                    else "segment"
                ),
                "business_scope_ref": segment_ref,
                "period": str(selector.get("period") or "unknown"),
                "metric_or_mechanism": str(
                    selector.get("metric_family") or "unknown"
                ),
                "attribution_level": (
                    "company_total"
                    if segment_ref == "__company_total__"
                    else "segment"
                ),
                "cannot_support": list(inherited_cannot_support),
            }
        for row in numeric_input.get("derived_metrics", ()):
            if not isinstance(row, Mapping):
                continue
            ref = str(row.get("derived_metric_id") or "")
            inputs = [
                item
                for item in row.get("inputs", ())
                if isinstance(item, Mapping)
            ]
            if not ref or not inputs:
                continue
            segment_refs = {
                str(item.get("segment_ref") or "unknown") for item in inputs
            }
            entities = {str(item.get("entity_ref") or "unknown") for item in inputs}
            periods = {str(item.get("period") or "unknown") for item in inputs}
            company_total = segment_refs == {"__company_total__"}
            cannot_support = list(inherited_cannot_support)
            cannot_support.extend(
                str(value)
                for value in row.get("cannot_support", ())
                if isinstance(value, str) and value.strip()
            )
            numeric_fact_scope[ref] = {
                "entity_ref": next(iter(entities)) if len(entities) == 1 else "mixed",
                "business_scope_kind": (
                    "company_total" if company_total else "unknown"
                ),
                "business_scope_ref": (
                    "__company_total__" if company_total else "mixed"
                ),
                "period": next(iter(periods)) if len(periods) == 1 else "mixed",
                "metric_or_mechanism": str(
                    row.get("metric_family") or "unknown"
                ),
                "attribution_level": (
                    "company_total" if company_total else "none"
                ),
                "cannot_support": sorted(set(cannot_support)),
            }
        return {
            "accepted_evidence_refs": sorted(
                set(map(str, authority.get("accepted_evidence_refs", ())))
            ),
            "numeric_fact_scope_and_cannot_support": numeric_fact_scope,
            "candidate_refs_not_evidence": sorted(
                set(map(str, authority.get("candidate_refs_not_evidence", ())))
            ),
            "graph_context_refs_not_evidence": sorted(
                set(map(str, authority.get("graph_context_refs_not_evidence", ())))
            ),
        }

    @staticmethod
    def _validate_owner_grade_claims_and_tasks(
        output: Mapping[str, Any], cell_input: Mapping[str, Any]
    ) -> None:
        claim_by_id = S3ThreeCellBoundedAgentExecutor._validate_owner_grade_claims(
            output, cell_input
        )
        S3ThreeCellBoundedAgentExecutor._validate_owner_grade_tasks(
            output.get("what_would_change"), cell_input, claim_by_id
        )

    @staticmethod
    def _validate_owner_grade_claims(
        output: Mapping[str, Any], cell_input: Mapping[str, Any]
    ) -> dict[str, Mapping[str, Any]]:
        cell_id = str(cell_input["program_cell_id"])
        claims = output.get("judgment_layer")
        if not isinstance(claims, list) or not 1 <= len(claims) <= 2:
            raise ValueError(
                f"s3_bounded_specialist_output_cardinality_invalid:{cell_id}:judgment_layer"
            )
        facts = {
            str(row["fact_id"]): row
            for row in output.get("fact_layer", ())
            if isinstance(row, Mapping) and row.get("fact_id")
        }
        surface = S3ThreeCellBoundedAgentExecutor._owner_grade_authority_surface(
            cell_input
        )
        context_authority = set(surface["candidate_refs_not_evidence"])
        context_authority.update(surface["graph_context_refs_not_evidence"])
        numeric_scopes = surface["numeric_fact_scope_and_cannot_support"]
        claim_ids: set[str] = set()
        claim_by_id: dict[str, Mapping[str, Any]] = {}
        required_claim = {
            "claim_id",
            "statement",
            "epistemic_status",
            "support_fact_ids",
            "context_refs",
            "scope",
            "qualification",
            "cannot_support",
        }
        required_scope = {
            "entity_ref",
            "business_scope_kind",
            "business_scope_ref",
            "period",
            "metric_or_mechanism",
            "attribution_level",
        }
        for claim in claims:
            if not isinstance(claim, Mapping) or set(claim) != required_claim:
                raise ValueError("s3_owner_grade_claim_card_schema_invalid")
            claim_id = str(claim.get("claim_id") or "")
            statement = str(claim.get("statement") or "")
            status = str(claim.get("epistemic_status") or "")
            scope = claim.get("scope")
            support_fact_ids = claim.get("support_fact_ids")
            context_refs = claim.get("context_refs")
            cannot_support = claim.get("cannot_support")
            if (
                not claim_id
                or claim_id in claim_ids
                or not statement.strip()
                or len(statement) > S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS
                or status not in S3_OWNER_GRADE_CLAIM_STATUSES
                or not isinstance(scope, Mapping)
                or set(scope) != required_scope
                or not isinstance(support_fact_ids, list)
                or not isinstance(context_refs, list)
                or not isinstance(cannot_support, list)
                or len(support_fact_ids) != len(set(map(str, support_fact_ids)))
                or len(context_refs) != len(set(map(str, context_refs)))
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in (*scope.values(), *cannot_support)
                )
                or str(scope.get("business_scope_kind"))
                not in S3_OWNER_GRADE_BUSINESS_SCOPE_KINDS
                or str(scope.get("attribution_level"))
                not in S3_OWNER_GRADE_ATTRIBUTION_LEVELS
            ):
                raise ValueError("s3_owner_grade_claim_card_schema_invalid")
            raw_qualification = claim.get("qualification")
            if not isinstance(raw_qualification, str):
                raise ValueError("s3_owner_grade_claim_card_schema_invalid")
            support_set = set(map(str, support_fact_ids))
            context_set = set(map(str, context_refs))
            if not context_set.issubset(context_authority):
                raise ValueError("s3_owner_grade_claim_context_authority_invalid")
            if support_set & context_authority or (
                status in {"fact_supported", "bounded_inference"}
                and not support_set
                and bool(context_set)
            ):
                raise ValueError(
                    "s3_owner_grade_context_promoted_to_claim_authority"
                )
            if not support_set.issubset(facts):
                raise ValueError("s3_owner_grade_claim_support_fact_unknown")
            if status in {"fact_supported", "bounded_inference"} and not support_set:
                raise ValueError("s3_owner_grade_claim_support_fact_required")
            if status == "hypothesis" and not raw_qualification.strip():
                raise ValueError("s3_owner_grade_claim_hypothesis_qualification_required")
            if status == "cannot_infer" and (
                support_set or not cannot_support
            ):
                raise ValueError(
                    "s3_owner_grade_epistemic_status_statement_conflict"
                )
            supported_numeric_scopes = [
                numeric_scopes[ref]
                for fact_id in support_set
                for ref in facts[fact_id].get("support_refs", ())
                if ref in numeric_scopes
            ]
            evidence_only_support = bool(support_set) and not supported_numeric_scopes and any(
                facts[fact_id].get("support_type") == "Evidence"
                for fact_id in support_set
            )
            if evidence_only_support and (
                scope["business_scope_kind"] != "unknown"
                or scope["attribution_level"] != "none"
            ):
                raise ValueError(
                    "s3_owner_grade_claim_scope_exceeds_fact_authority"
                )
            if supported_numeric_scopes:
                requested_business = str(scope["business_scope_kind"])
                requested_attribution = str(scope["attribution_level"])
                elevated = requested_business in {"segment", "product", "value_chain"}
                elevated = elevated or requested_attribution in {
                    "segment",
                    "product",
                    "cross_chain",
                }
                structured_mismatch = any(
                    str(row["entity_ref"]) != str(scope["entity_ref"])
                    or str(row["period"]) != str(scope["period"])
                    or (
                        requested_business != "unknown"
                        and str(row["business_scope_kind"]) != requested_business
                    )
                    or (
                        requested_attribution != "none"
                        and str(row["attribution_level"]) != requested_attribution
                    )
                    for row in supported_numeric_scopes
                )
                forbidden_metrics = {
                    value
                    for row in supported_numeric_scopes
                    for value in row.get("cannot_support", ())
                }
                requested_metric = str(scope["metric_or_mechanism"])
                metric_forbidden = requested_metric in forbidden_metrics
                if elevated or structured_mismatch or metric_forbidden:
                    raise ValueError(
                        "s3_owner_grade_claim_scope_exceeds_fact_authority"
                    )
            claim_ids.add(claim_id)
            claim_by_id[claim_id] = claim
        return claim_by_id

    @staticmethod
    def _validate_owner_grade_tasks(
        tasks: Any,
        cell_input: Mapping[str, Any],
        claim_by_id: Mapping[str, Mapping[str, Any]],
    ) -> None:
        cell_id = str(cell_input["program_cell_id"])
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 3:
            raise ValueError(
                f"s3_bounded_specialist_output_cardinality_invalid:{cell_id}:what_would_change"
            )
        authority_policy = WhatWouldChangeAuthorityPolicy.from_cell_input(
            cell_input
        )
        required_task = {
            "task_id",
            "claim_id",
            "source_target",
            "metric_or_observation",
            "decision_rule",
            "time_window",
            "expected_claim_transition",
            "fallback_stop_condition",
            "authority_refs",
        }
        task_ids: set[str] = set()
        all_authority_refs = set(authority_policy.allowed_refs)
        for task in tasks:
            if not isinstance(task, Mapping) or set(task) != required_task:
                raise ValueError("s3_owner_grade_WWC_task_incomplete")
            source_target = task.get("source_target")
            decision_rule = task.get("decision_rule")
            time_window = task.get("time_window")
            authority_refs = task.get("authority_refs")
            task_id = str(task.get("task_id") or "")
            claim_id = str(task.get("claim_id") or "")
            if (
                not task_id
                or task_id in task_ids
                or claim_id not in claim_by_id
                or not isinstance(source_target, Mapping)
                or set(source_target)
                != {"source_type", "entity_or_owner", "document_event_or_dataset"}
                or not isinstance(decision_rule, Mapping)
                or set(decision_rule)
                != {"rule_type", "comparator_or_condition", "threshold_or_observation"}
                or not isinstance(time_window, Mapping)
                or set(time_window)
                != {"as_of", "start_or_trigger", "deadline_or_review_date"}
                or not isinstance(authority_refs, list)
                or not authority_refs
                or not set(map(str, authority_refs)).issubset(all_authority_refs)
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in (
                        task.get("metric_or_observation"),
                        task.get("expected_claim_transition"),
                        task.get("fallback_stop_condition"),
                        *source_target.values(),
                        *decision_rule.values(),
                        *time_window.values(),
                    )
                )
            ):
                raise ValueError("s3_owner_grade_WWC_task_incomplete")
            task_ids.add(task_id)

    @staticmethod
    def _expected_conflict_fact_presence_summary(
        involved_claim_ids: Any,
        claim_by_id: Mapping[str, Mapping[str, Any]],
    ) -> str:
        if (
            not isinstance(involved_claim_ids, list)
            or not involved_claim_ids
            or any(
                not isinstance(claim_id, str) or not claim_id.strip()
                for claim_id in involved_claim_ids
            )
        ):
            raise ValueError("s3_owner_grade_lead_conflict_claim_refs_invalid")
        if len(set(involved_claim_ids)) != len(involved_claim_ids):
            raise ValueError("s3_owner_grade_lead_involved_claim_ref_duplicate")
        if any(claim_id not in claim_by_id for claim_id in involved_claim_ids):
            raise ValueError("s3_owner_grade_lead_conflict_claim_refs_invalid")
        support_presence = [
            bool(claim_by_id[claim_id].get("support_fact_ids"))
            for claim_id in involved_claim_ids
        ]
        return (
            S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
            .expected_summary(support_presence)
        )

    @staticmethod
    def _derive_scoped_identity_surface(
        specialist_outputs: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        surface = CellScopedResearchIdentityPolicy.derive_surface(
            specialist_outputs
        )
        if isinstance(surface, ScopedIdentityViolation):
            raise S3ScopedIdentityContractError(surface)
        return surface

    @staticmethod
    def _scoped_identity_indexes(
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any] | None,
    ) -> dict[str, dict[tuple[str, str, str], CellScopedResearchRef]]:
        if scoped_identity_surface is None:
            raise S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            )
        expected = CellScopedResearchIdentityPolicy.derive_surface(
            specialist_outputs
        )
        if isinstance(expected, ScopedIdentityViolation):
            raise S3ScopedIdentityContractError(expected)
        if canonical_digest(expected) != canonical_digest(scoped_identity_surface):
            raise S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            )
        indexes = CellScopedResearchIdentityPolicy.index_surface(
            scoped_identity_surface
        )
        if isinstance(indexes, ScopedIdentityViolation):
            raise S3ScopedIdentityContractError(indexes)
        return indexes

    @classmethod
    def _compact_scoped_alias_table(
        cls,
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any] | None,
    ) -> CompactScopedReferenceAliasTable:
        cls._scoped_identity_indexes(
            specialist_outputs,
            scoped_identity_surface,
        )
        assert scoped_identity_surface is not None
        alias_table = CompactScopedReferenceAliasTable.from_surface(
            scoped_identity_surface
        )
        if isinstance(alias_table, ScopedIdentityViolation):
            raise S3ScopedIdentityContractError(alias_table)
        return alias_table

    @classmethod
    def _compact_alias_specialist_projection(
        cls,
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any] | None,
    ) -> tuple[
        list[dict[str, Any]],
        CompactScopedReferenceAliasTable,
    ]:
        alias_table = cls._compact_scoped_alias_table(
            specialist_outputs,
            scoped_identity_surface,
        )
        alias_by_key = {
            row.ref.runtime_key: row.alias for row in alias_table.rows
        }
        projected = deepcopy(specialist_outputs)
        for specialist in projected:
            cell_id = str(specialist["program_cell_id"])
            local_claim_aliases: dict[str, str] = {}
            for claim in specialist.get("judgment_layer", ()):
                local_id = str(claim["claim_id"])
                ref = CellScopedResearchIdentityPolicy.ref(
                    "claim", cell_id, local_id
                )
                alias = alias_by_key[ref.runtime_key]
                local_claim_aliases[local_id] = alias
                claim["claim_id"] = alias
            for task in specialist.get("what_would_change", ()):
                local_id = str(task["task_id"])
                ref = CellScopedResearchIdentityPolicy.ref(
                    "what_would_change", cell_id, local_id
                )
                task["task_id"] = alias_by_key[ref.runtime_key]
                task["claim_id"] = local_claim_aliases[str(task["claim_id"])]
        return projected, alias_table

    @classmethod
    def _scoped_alias_projection(
        cls,
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any] | None,
        lead_output: Mapping[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        indexes = cls._scoped_identity_indexes(
            specialist_outputs,
            scoped_identity_surface,
        )
        alias_by_key = {
            key: ref.validation_alias
            for kind_index in indexes.values()
            for key, ref in kind_index.items()
        }

        def alias_ref(value: Any, kind: str) -> str:
            if isinstance(value, str):
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="raw_local_id_cross_cell_ambiguous",
                        failing_item_count=1,
                    )
                )
            parsed = CellScopedResearchIdentityPolicy.parse(
                value,
                expected_kind=kind,
            )
            if isinstance(parsed, ScopedIdentityViolation):
                raise S3ScopedIdentityContractError(parsed)
            alias = alias_by_key.get(parsed.runtime_key)
            if alias is None:
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="unknown_scoped_ref",
                        failing_item_count=1,
                    )
                )
            return alias

        def alias_refs(values: Any, kind: str) -> list[str]:
            if not isinstance(values, list):
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="scoped_ref_mismatch",
                        failing_item_count=1,
                    )
                )
            aliases = [alias_ref(value, kind) for value in values]
            if len(set(aliases)) != len(aliases):
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="scoped_ref_duplicate",
                        failing_item_count=1,
                    )
                )
            return aliases

        projected_specialists = deepcopy(specialist_outputs)
        for specialist in projected_specialists:
            cell_id = str(specialist["program_cell_id"])
            local_claim_aliases: dict[str, str] = {}
            for claim in specialist.get("judgment_layer", ()):
                local_id = str(claim["claim_id"])
                ref = CellScopedResearchIdentityPolicy.ref(
                    "claim", cell_id, local_id
                )
                alias = alias_by_key[ref.runtime_key]
                local_claim_aliases[local_id] = alias
                claim["claim_id"] = alias
            for task in specialist.get("what_would_change", ()):
                local_id = str(task["task_id"])
                ref = CellScopedResearchIdentityPolicy.ref(
                    "what_would_change", cell_id, local_id
                )
                task["task_id"] = alias_by_key[ref.runtime_key]
                task["claim_id"] = local_claim_aliases[str(task["claim_id"])]

        if lead_output is None:
            return projected_specialists, None
        projected_lead = deepcopy(lead_output)
        for dependency in projected_lead.get("cross_cell_dependencies", ()):
            dependency["claim_ids"] = alias_refs(
                dependency.get("claim_ids"), "claim"
            )
        for conflict in projected_lead.get("conflict_adjudications", ()):
            conflict["involved_claim_ids"] = alias_refs(
                conflict.get("involved_claim_ids"), "claim"
            )
        variant = projected_lead.get("variant_view")
        if isinstance(variant, Mapping):
            variant["claim_ids"] = alias_refs(
                variant.get("claim_ids"), "claim"
            )
            variant["what_would_change_task_ids"] = alias_refs(
                variant.get("what_would_change_task_ids"),
                "what_would_change",
            )
        for gap in projected_lead.get("remaining_gaps", ()):
            gap["claim_ids"] = alias_refs(gap.get("claim_ids"), "claim")
            gap["what_would_change_task_ids"] = alias_refs(
                gap.get("what_would_change_task_ids"),
                "what_would_change",
            )
        return projected_specialists, projected_lead

    @staticmethod
    def _validate_lead_output(
        output: Mapping[str, Any],
        specialist_digests: Mapping[str, str],
        *,
        specialist_outputs: list[Mapping[str, Any]] | None = None,
        scoped_identity_surface: Mapping[str, Any] | None = None,
        output_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
    ) -> None:
        if (
            output_contract_ref
            == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ):
            if specialist_outputs is None:
                raise ValueError("s3_owner_grade_lead_specialist_body_missing")
            projected_specialists, projected_output = (
                S3ThreeCellBoundedAgentExecutor._scoped_alias_projection(
                    specialist_outputs,
                    scoped_identity_surface,
                    output,
                )
            )
            assert projected_output is not None
            S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                projected_output,
                specialist_digests,
                specialist_outputs=projected_specialists,
                output_contract_ref=(
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
                ),
            )
            return
        required = {
            "cell_heads",
            "cross_cell_dependencies",
            "conflict_adjudications",
            "variant_view",
            "remaining_gaps",
        }
        if set(output) != required:
            raise ValueError("s3_bounded_lead_output_schema_invalid")
        heads = output.get("cell_heads")
        if not isinstance(heads, list) or len(heads) != 3:
            raise ValueError("s3_bounded_lead_exact_three_heads_required")
        observed = {
            str(row.get("program_cell_id")): str(row.get("specialist_output_digest"))
            for row in heads
            if isinstance(row, Mapping)
        }
        if observed != dict(specialist_digests):
            raise ValueError("s3_bounded_lead_specialist_digest_binding_mismatch")
        if output_contract_ref == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF:
            if specialist_outputs is None:
                raise ValueError("s3_owner_grade_lead_specialist_body_missing")
            by_cell = {
                str(row["program_cell_id"]): row for row in specialist_outputs
            }
            claim_by_id = {
                str(claim["claim_id"]): claim
                for specialist in specialist_outputs
                for claim in specialist.get("judgment_layer", ())
                if isinstance(claim, Mapping)
            }
            all_claim_ids = set(claim_by_id)
            all_task_ids = {
                str(task["task_id"])
                for specialist in specialist_outputs
                for task in specialist.get("what_would_change", ())
                if isinstance(task, Mapping)
            }
            for head in heads:
                if not isinstance(head, Mapping) or set(head) != {
                    "program_cell_id",
                    "specialist_output_digest",
                    "terminal_class",
                    "evidence_fact_count",
                    "numeric_fact_count",
                    "claim_state_counts",
                }:
                    raise ValueError("s3_owner_grade_lead_cell_head_schema_invalid")
                cell_id = str(head["program_cell_id"])
                specialist = by_cell.get(cell_id)
                if specialist is None:
                    raise ValueError("s3_owner_grade_lead_cell_head_schema_invalid")
                expected_evidence = sum(
                    1
                    for fact in specialist["fact_layer"]
                    if fact.get("support_type") == "Evidence"
                )
                expected_numeric = sum(
                    1
                    for fact in specialist["fact_layer"]
                    if fact.get("support_type") == "Numeric"
                )
                expected_states = {
                    status: sum(
                        1
                        for claim in specialist["judgment_layer"]
                        if claim.get("epistemic_status") == status
                    )
                    for status in S3_OWNER_GRADE_CLAIM_STATUSES
                }
                if (
                    head.get("terminal_class") != specialist.get("terminal_class")
                    or head.get("evidence_fact_count") != expected_evidence
                    or head.get("numeric_fact_count") != expected_numeric
                    or head.get("claim_state_counts") != expected_states
                ):
                    raise ValueError(
                        "s3_owner_grade_lead_cell_head_fact_presence_mismatch"
                    )
            total_facts = sum(
                len(row.get("fact_layer", ())) for row in specialist_outputs
            )
            conflicts = output.get("conflict_adjudications")
            if not isinstance(conflicts, list):
                raise ValueError("s3_owner_grade_lead_conflict_schema_invalid")
            derive_fact_presence = (
                S3ThreeCellBoundedAgentExecutor
                ._expected_conflict_fact_presence_summary
            )
            for conflict in conflicts:
                if not isinstance(conflict, Mapping) or set(conflict) != {
                    "adjudication_id",
                    "involved_claim_ids",
                    "terminal_state_summary",
                    "fact_presence_summary",
                    "resolution_status",
                    "statement",
                }:
                    raise ValueError("s3_owner_grade_lead_conflict_schema_invalid")
                involved = conflict.get("involved_claim_ids")
                if (
                    not str(conflict.get("adjudication_id") or "")
                    or conflict.get("fact_presence_summary")
                    not in {"facts_present", "no_facts_present", "mixed_fact_presence"}
                    or any(
                        not isinstance(conflict.get(key), str)
                        or not str(conflict[key]).strip()
                        for key in (
                            "terminal_state_summary",
                            "resolution_status",
                            "statement",
                        )
                    )
                ):
                    raise ValueError("s3_owner_grade_lead_conflict_schema_invalid")
                try:
                    expected_fact_presence = derive_fact_presence(
                        involved, claim_by_id
                    )
                except ValueError as exc:
                    raise ValueError(
                        "s3_owner_grade_lead_conflict_schema_invalid"
                    ) from exc
                if conflict.get("fact_presence_summary") != expected_fact_presence:
                    raise ValueError(
                        "s3_owner_grade_lead_conflict_fact_presence_mismatch"
                    )
                normalized_fact_text = " ".join(
                    str(conflict.get(key) or "").lower()
                    for key in ("terminal_state_summary", "statement")
                )
                if total_facts > 0 and any(
                    phrase in normalized_fact_text
                    for phrase in (
                        "all cells are in non-fact states",
                        "all cells are non-fact",
                    )
                ):
                    raise ValueError(
                        "s3_owner_grade_lead_explicit_global_fact_presence_"
                        "statement_conflict"
                    )
            S3ThreeCellBoundedAgentExecutor._validate_lead_reference_surface(
                output, all_claim_ids, all_task_ids
            )
        if not isinstance(output.get("cross_cell_dependencies"), list) or not output[
            "cross_cell_dependencies"
        ]:
            raise ValueError("s3_bounded_lead_cross_cell_dependency_required")
        if not isinstance(output.get("conflict_adjudications"), list) or not isinstance(
            output.get("remaining_gaps"), list
        ) or not str(output.get("variant_view") or ""):
            raise ValueError("s3_bounded_lead_synthesis_schema_invalid")

    @staticmethod
    def _validate_lead_reference_surface(
        output: Mapping[str, Any], claim_ids: set[str], task_ids: set[str]
    ) -> None:
        variant = output.get("variant_view")
        gaps = output.get("remaining_gaps")
        dependencies = output.get("cross_cell_dependencies")
        if not isinstance(variant, Mapping) or set(variant) != {
            "statement",
            "claim_ids",
            "what_would_change_task_ids",
        }:
            raise ValueError("s3_owner_grade_lead_reference_surface_invalid")
        rows = [variant]
        if not isinstance(gaps, list) or not gaps or not isinstance(dependencies, list) or not dependencies:
            raise ValueError("s3_owner_grade_lead_reference_surface_invalid")
        for row in gaps:
            if not isinstance(row, Mapping) or set(row) != {
                "gap_id",
                "statement",
                "claim_ids",
                "what_would_change_task_ids",
            }:
                raise ValueError("s3_owner_grade_lead_reference_surface_invalid")
            rows.append(row)
        for row in dependencies:
            if not isinstance(row, Mapping) or set(row) != {
                "dependency_id",
                "statement",
                "claim_ids",
            }:
                raise ValueError("s3_owner_grade_lead_reference_surface_invalid")
            rows.append({**row, "what_would_change_task_ids": []})
        for row in rows:
            row_claim_ids = row.get("claim_ids")
            row_task_ids = row.get("what_would_change_task_ids")
            if (
                not str(row.get("statement") or "")
                or not isinstance(row_claim_ids, list)
                or not isinstance(row_task_ids, list)
                or not set(map(str, row_claim_ids)).issubset(claim_ids)
                or not set(map(str, row_task_ids)).issubset(task_ids)
                or not row_claim_ids
            ):
                raise ValueError("s3_owner_grade_lead_reference_surface_invalid")

    @staticmethod
    def _validate_writer_output(
        output: Mapping[str, Any],
        lead_digest: str,
        *,
        specialist_outputs: list[Mapping[str, Any]] | None = None,
        cross_cell_lead: Mapping[str, Any] | None = None,
        scoped_identity_surface: Mapping[str, Any] | None = None,
        output_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
        case_numeric_authority_contracts: list[
            Mapping[str, Any]
        ]
        | None = None,
        case_delivery_identity_projection: Mapping[
            str, Any
        ]
        | None = None,
    ) -> None:
        if (
            output_contract_ref
            == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ):
            S3ThreeCellBoundedAgentExecutor._validate_scoped_writer_output(
                output,
                lead_digest,
                specialist_outputs=specialist_outputs,
                cross_cell_lead=cross_cell_lead,
                scoped_identity_surface=scoped_identity_surface,
                case_numeric_authority_contracts=(
                    case_numeric_authority_contracts
                ),
                case_delivery_identity_projection=(
                    case_delivery_identity_projection
                ),
            )
            return
        if output_contract_ref == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF:
            S3ThreeCellBoundedAgentExecutor._validate_owner_grade_writer_output(
                output,
                lead_digest,
                specialist_outputs=specialist_outputs,
                cross_cell_lead=cross_cell_lead,
            )
            return
        if set(output) != {
            "title_zh_cn",
            "executive_summary_zh_cn",
            "sections",
            "limitations_zh_cn",
            "consumed_lead_digest",
            "source_calls",
            "tool_calls",
        }:
            raise ValueError("s3_bounded_writer_output_schema_invalid")
        sections = output.get("sections")
        if not isinstance(sections, list) or len(sections) != 3 or {
            str(row.get("program_cell_id")) for row in sections if isinstance(row, Mapping)
        } != set(S3_THREE_CELL_PROGRAM_CELL_IDS):
            raise ValueError("s3_bounded_writer_exact_three_sections_required")
        if (
            output.get("consumed_lead_digest") != lead_digest
            or int(output.get("source_calls", -1)) != 0
            or int(output.get("tool_calls", -1)) != 0
        ):
            raise ValueError("s3_bounded_writer_authority_or_lineage_violation")

    @staticmethod
    def _owner_grade_claim_surface(
        specialist_outputs: list[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "program_cell_id": str(row["program_cell_id"]),
                "claim_cards": list(row["judgment_layer"]),
                "what_would_change": list(row["what_would_change"]),
            }
            for row in specialist_outputs
        ]

    @staticmethod
    def _validate_owner_grade_writer_output(
        output: Mapping[str, Any],
        lead_digest: str,
        *,
        specialist_outputs: list[Mapping[str, Any]] | None,
        cross_cell_lead: Mapping[str, Any] | None,
        expected_title_zh_cn: str = (
            "NVDA 三单元内部研究备忘录"
        ),
        case_numeric_authority_contracts: list[
            Mapping[str, Any]
        ]
        | None = None,
    ) -> None:
        if specialist_outputs is None or cross_cell_lead is None:
            raise ValueError("s3_owner_grade_writer_claim_surface_missing")
        required = {
            "title_zh_cn",
            "executive_summary_zh_cn",
            "sections",
            "limitations_zh_cn",
            "consumed_lead_digest",
            "consumed_claim_surface_digest",
            "exact_claim_ids",
            "exact_WWC_task_ids",
            "source_calls",
            "tool_calls",
        }
        if set(output) != required:
            raise ValueError("s3_bounded_writer_output_schema_invalid")
        claim_surface = S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
            specialist_outputs
        )
        claims = {
            str(claim["claim_id"]): (str(row["program_cell_id"]), claim)
            for row in specialist_outputs
            for claim in row.get("judgment_layer", ())
            if isinstance(claim, Mapping)
        }
        tasks = {
            str(task["task_id"]): str(row["program_cell_id"])
            for row in specialist_outputs
            for task in row.get("what_would_change", ())
            if isinstance(task, Mapping)
        }
        if (
            output.get("consumed_lead_digest") != lead_digest
            or output.get("consumed_claim_surface_digest")
            != canonical_digest(claim_surface)
            or set(map(str, output.get("exact_claim_ids") or ())) != set(claims)
            or set(map(str, output.get("exact_WWC_task_ids") or ())) != set(tasks)
            or int(output.get("source_calls", -1)) != 0
            or int(output.get("tool_calls", -1)) != 0
        ):
            raise ValueError("s3_owner_grade_writer_claim_surface_violation")
        sections = output.get("sections")
        if not isinstance(sections, list) or len(sections) != 3:
            raise ValueError("s3_bounded_writer_exact_three_sections_required")
        rendered_claim_ids: set[str] = set()
        referenced_task_ids: set[str] = set()
        rendered_texts: list[str] = []
        numeric_policies = {
            policy.program_cell_id: policy
            for policy in (
                CaseNumericAuthorityPolicy.from_prompt_contract(
                    row
                )
                for row in (
                    case_numeric_authority_contracts or ()
                )
            )
        }
        specialists_by_cell = {
            str(row["program_cell_id"]): row
            for row in specialist_outputs
        }
        for section in sections:
            if not isinstance(section, Mapping) or set(section) != {
                "program_cell_id",
                "claim_renderings",
                "what_would_change_task_refs",
            }:
                raise ValueError("s3_owner_grade_writer_claim_surface_violation")
            cell_id = str(section.get("program_cell_id") or "")
            renderings = section.get("claim_renderings")
            task_refs = section.get("what_would_change_task_refs")
            if not isinstance(renderings, list) or not isinstance(task_refs, list):
                raise ValueError("s3_owner_grade_writer_claim_surface_violation")
            for rendering in renderings:
                if not isinstance(rendering, Mapping) or set(rendering) != {
                    "claim_id",
                    "rendered_text_zh_cn",
                    "epistemic_status",
                    "scope_digest",
                    "qualification_preserved",
                }:
                    raise ValueError("s3_owner_grade_writer_claim_surface_violation")
                claim_id = str(rendering.get("claim_id") or "")
                source = claims.get(claim_id)
                if source is None or source[0] != cell_id or claim_id in rendered_claim_ids:
                    raise ValueError("s3_owner_grade_writer_claim_surface_violation")
                claim = source[1]
                text = str(rendering.get("rendered_text_zh_cn") or "")
                if (
                    rendering.get("epistemic_status") != claim.get("epistemic_status")
                    or rendering.get("scope_digest") != canonical_digest(claim["scope"])
                    or not text.strip()
                ):
                    raise ValueError("s3_owner_grade_writer_claim_surface_violation")
                numeric_policy = numeric_policies.get(cell_id)
                if numeric_policy is not None:
                    specialist = specialists_by_cell[cell_id]
                    facts = {
                        str(fact.get("fact_id") or ""): fact
                        for fact in specialist.get(
                            "fact_layer", ()
                        )
                        if isinstance(fact, Mapping)
                    }
                    numeric_refs = [
                        str(ref)
                        for fact_id in claim.get(
                            "support_fact_ids", ()
                        )
                        for ref in facts.get(
                            str(fact_id), {}
                        ).get("support_refs", ())
                        if facts.get(str(fact_id), {}).get(
                            "support_type"
                        )
                        == "Numeric"
                    ]
                    expected_clauses = (
                        numeric_policy.rendered_clauses_for_refs(
                            numeric_refs
                        )
                    )
                    if expected_clauses and not text.startswith(
                        "；".join(expected_clauses) + "；"
                    ):
                        raise ValueError(
                            "s4_case_numeric_writer_rendering_mismatch"
                        )
                if "图表假设" in text or "图表关系" in text:
                    raise ValueError(
                        "s3_owner_grade_writer_graph_terminology_invalid"
                    )
                if claim.get("epistemic_status") in {"hypothesis", "cannot_infer"} and (
                    rendering.get("qualification_preserved") is not True
                    or str(claim.get("qualification") or "") not in text
                ):
                    raise ValueError("s3_owner_grade_writer_qualification_dropped")
                rendered_claim_ids.add(claim_id)
                rendered_texts.append(text)
            for task_ref in task_refs:
                ref = str(task_ref)
                if tasks.get(ref) != cell_id:
                    raise ValueError("s3_owner_grade_writer_claim_surface_violation")
                referenced_task_ids.add(ref)
        if rendered_claim_ids != set(claims) or referenced_task_ids != set(tasks):
            raise ValueError("s3_owner_grade_writer_claim_surface_violation")
        expected_limitations = sorted(
            {
                str(boundary)
                for _, claim in claims.values()
                for boundary in claim.get("cannot_support", ())
                if isinstance(boundary, str) and boundary.strip()
            }
        )
        if (
            output.get("title_zh_cn") != expected_title_zh_cn
            or output.get("executive_summary_zh_cn") != "；".join(rendered_texts)
            or output.get("limitations_zh_cn") != expected_limitations
        ):
            raise ValueError("s3_owner_grade_writer_claim_surface_violation")

    @staticmethod
    def _validate_scoped_writer_output(
        output: Mapping[str, Any],
        lead_digest: str,
        *,
        specialist_outputs: list[Mapping[str, Any]] | None,
        cross_cell_lead: Mapping[str, Any] | None,
        scoped_identity_surface: Mapping[str, Any] | None,
        case_numeric_authority_contracts: list[
            Mapping[str, Any]
        ]
        | None,
        case_delivery_identity_projection: Mapping[
            str, Any
        ]
        | None,
    ) -> None:
        if specialist_outputs is None or cross_cell_lead is None:
            raise ValueError("s3_owner_grade_writer_claim_surface_missing")
        projected_specialists, _ = (
            S3ThreeCellBoundedAgentExecutor._scoped_alias_projection(
                specialist_outputs,
                scoped_identity_surface,
            )
        )
        indexes = S3ThreeCellBoundedAgentExecutor._scoped_identity_indexes(
            specialist_outputs,
            scoped_identity_surface,
        )

        def alias(value: Any, kind: str) -> str:
            if isinstance(value, str):
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="raw_local_id_cross_cell_ambiguous",
                        failing_item_count=1,
                    )
                )
            parsed = CellScopedResearchIdentityPolicy.parse(
                value, expected_kind=kind
            )
            if isinstance(parsed, ScopedIdentityViolation):
                raise S3ScopedIdentityContractError(parsed)
            known = indexes[kind].get(parsed.runtime_key)
            if known is None:
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="unknown_scoped_ref",
                        failing_item_count=1,
                    )
                )
            return known.validation_alias

        required = {
            "title_zh_cn",
            "executive_summary_zh_cn",
            "sections",
            "limitations_zh_cn",
            "consumed_lead_digest",
            "consumed_claim_surface_digest",
            "consumed_scoped_identity_surface_digest",
            "exact_claim_refs",
            "exact_WWC_task_refs",
            "source_calls",
            "tool_calls",
        }
        if (
            set(output) != required
            or scoped_identity_surface is None
            or output.get("consumed_scoped_identity_surface_digest")
            != canonical_digest(scoped_identity_surface)
        ):
            raise ValueError("s3_owner_grade_writer_claim_surface_violation")
        projected = deepcopy(output)
        projected.pop("consumed_scoped_identity_surface_digest")
        projected["consumed_claim_surface_digest"] = canonical_digest(
            S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
                projected_specialists
            )
        )
        projected["exact_claim_ids"] = [
            alias(value, "claim")
            for value in projected.pop("exact_claim_refs")
        ]
        projected["exact_WWC_task_ids"] = [
            alias(value, "what_would_change")
            for value in projected.pop("exact_WWC_task_refs")
        ]
        for section in projected.get("sections", ()):
            for rendering in section.get("claim_renderings", ()):
                rendering["claim_id"] = alias(
                    rendering.pop("claim_ref"), "claim"
                )
            section["what_would_change_task_refs"] = [
                alias(value, "what_would_change")
                for value in section.get(
                    "what_would_change_task_refs", ()
                )
            ]
        expected_title = "NVDA 三单元内部研究备忘录"
        if case_delivery_identity_projection is not None:
            expected_title = (
                CaseDeliveryIdentityPolicy.from_projection(
                    case_delivery_identity_projection
                ).title_zh_cn
            )
        S3ThreeCellBoundedAgentExecutor._validate_owner_grade_writer_output(
            projected,
            lead_digest,
            specialist_outputs=projected_specialists,
            cross_cell_lead=cross_cell_lead,
            expected_title_zh_cn=expected_title,
            case_numeric_authority_contracts=(
                case_numeric_authority_contracts
            ),
        )

    @staticmethod
    def _validate_owner_grade_verifier_input(payload: Mapping[str, Any]) -> None:
        required = {
            "authority_surface_by_cell",
            "specialist_claim_cards",
            "specialist_output_digests",
            "cross_cell_lead",
            "cross_cell_lead_digest",
            "writer_output",
            "writer_digest",
        }
        if not required.issubset(payload):
            raise ValueError("s3_owner_grade_verifier_authority_surface_missing")
        authority = payload.get("authority_surface_by_cell")
        cards = payload.get("specialist_claim_cards")
        digests = payload.get("specialist_output_digests")
        if (
            not isinstance(authority, Mapping)
            or set(authority) != set(S3_THREE_CELL_PROGRAM_CELL_IDS)
            or not isinstance(cards, Mapping)
            or set(cards) != set(S3_THREE_CELL_PROGRAM_CELL_IDS)
            or not isinstance(digests, Mapping)
            or set(digests) != set(S3_THREE_CELL_PROGRAM_CELL_IDS)
            or any(
                not isinstance(row, Mapping)
                or set(row)
                != {
                    "accepted_evidence_refs",
                    "numeric_fact_scope_and_cannot_support",
                    "candidate_refs_not_evidence",
                    "graph_context_refs_not_evidence",
                }
                for row in authority.values()
            )
            or any(
                not isinstance(row, Mapping)
                or set(row) != {"fact_layer", "claim_cards", "what_would_change"}
                for row in cards.values()
            )
            or canonical_digest(payload.get("cross_cell_lead"))
            != payload.get("cross_cell_lead_digest")
            or canonical_digest(payload.get("writer_output"))
            != payload.get("writer_digest")
        ):
            raise ValueError("s3_owner_grade_verifier_authority_surface_missing")
        scoped_contract_ref = payload.get("scoped_identity_contract_ref")
        scoped_surface = payload.get("scoped_identity_surface")
        if scoped_contract_ref is not None or scoped_surface is not None:
            if (
                scoped_contract_ref
                != S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
                or not isinstance(scoped_surface, Mapping)
            ):
                raise ValueError(
                    "s3_owner_grade_verifier_scoped_identity_surface_invalid"
                )
            specialist_identity_inputs = [
                {
                    "program_cell_id": cell_id,
                    "judgment_layer": list(cards[cell_id]["claim_cards"]),
                    "what_would_change": list(
                        cards[cell_id]["what_would_change"]
                    ),
                }
                for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS
            ]
            S3ThreeCellBoundedAgentExecutor._scoped_identity_indexes(
                specialist_identity_inputs,
                scoped_surface,
            )

    @classmethod
    def _validate_verifier_output(
        cls,
        output: Mapping[str, Any],
        lead_digest: str,
        writer_digest: str,
        *,
        output_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
        local_semantic_issues: list[str] | None = None,
        specialist_outputs: list[Mapping[str, Any]] | None = None,
        scoped_identity_surface: Mapping[str, Any] | None = None,
    ) -> None:
        if set(output) != {"findings", "bound_lead_digest", "bound_writer_digest", "decision"}:
            raise ValueError("s3_bounded_verifier_output_schema_invalid")
        findings = output.get("findings")
        if not isinstance(findings, list) or tuple(
            str(row.get("layer")) for row in findings if isinstance(row, Mapping)
        ) != S3_FOUR_LAYER_VERIFIER_LAYERS:
            raise ValueError("s3_bounded_four_layer_verifier_required")
        if output_contract_ref in S3_TYPED_VERIFIER_OUTPUT_CONTRACT_REFS:
            if any(
                not isinstance(row, Mapping)
                or set(row)
                != {
                    "layer",
                    "status",
                    "issue_codes",
                    "artifact_or_claim_refs",
                    "repair_owner",
                }
                or row.get("status") not in {"pass", "review_required", "fail"}
                or not isinstance(row.get("issue_codes"), list)
                or not isinstance(row.get("artifact_or_claim_refs"), list)
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in row.get("issue_codes", ())
                )
                or (
                    row.get("repair_owner") is not None
                    and (
                        not isinstance(row.get("repair_owner"), str)
                        or not row["repair_owner"].strip()
                    )
                )
                for row in findings
            ):
                raise ValueError("s3_bounded_verifier_finding_schema_invalid")
            cls._validate_verifier_exact_refs(
                findings,
                specialist_outputs=specialist_outputs,
                scoped_identity_surface=scoped_identity_surface,
            )
        elif any(
            not isinstance(row, Mapping)
            or set(row) != {"layer", "status", "issues"}
            or row.get("status") not in {"pass", "review_required", "fail"}
            or not isinstance(row.get("issues"), list)
            for row in findings
        ):
            raise ValueError("s3_bounded_verifier_finding_schema_invalid")
        if output.get("bound_lead_digest") != lead_digest or output.get(
            "bound_writer_digest"
        ) != writer_digest:
            raise ValueError("s3_bounded_verifier_digest_binding_mismatch")
        if output.get("decision") not in {"accept_for_internal_review", "repair", "reject"}:
            raise ValueError("s3_bounded_verifier_decision_invalid")
        if output_contract_ref in S3_TYPED_VERIFIER_OUTPUT_CONTRACT_REFS:
            S3ThreeCellBoundedAgentExecutor._validate_typed_verifier_state_machine(
                findings,
                decision=str(output["decision"]),
                local_semantic_issues=local_semantic_issues or [],
            )

    @classmethod
    def _validate_verifier_exact_refs(
        cls,
        findings: list[Mapping[str, Any]],
        *,
        specialist_outputs: list[Mapping[str, Any]] | None,
        scoped_identity_surface: Mapping[str, Any] | None,
    ) -> None:
        if specialist_outputs is None and scoped_identity_surface is None:
            if any(
                any(
                    not isinstance(value, str) or not value.strip()
                    for value in row.get("artifact_or_claim_refs", ())
                )
                for row in findings
            ):
                raise ValueError("s3_bounded_verifier_finding_schema_invalid")
            return
        if specialist_outputs is None or scoped_identity_surface is None:
            raise ValueError(
                "s3_owner_grade_verifier_scoped_identity_surface_invalid"
            )
        indexes = cls._scoped_identity_indexes(
            specialist_outputs,
            scoped_identity_surface,
        )
        for row in findings:
            observed: set[tuple[str, str, str]] = set()
            for value in row.get("artifact_or_claim_refs", ()):
                if isinstance(value, str):
                    raise S3ScopedIdentityContractError(
                        ScopedIdentityViolation(
                            identity_kind="claim",
                            failure_subtype="raw_local_id_cross_cell_ambiguous",
                            failing_item_count=1,
                        )
                    )
                parsed = CellScopedResearchIdentityPolicy.parse(
                    value,
                    expected_kind="claim",
                )
                if isinstance(parsed, ScopedIdentityViolation):
                    raise S3ScopedIdentityContractError(parsed)
                if parsed.runtime_key not in indexes["claim"]:
                    raise S3ScopedIdentityContractError(
                        ScopedIdentityViolation(
                            identity_kind="claim",
                            failure_subtype="unknown_scoped_ref",
                            failing_item_count=1,
                        )
                    )
                if parsed.runtime_key in observed:
                    raise S3ScopedIdentityContractError(
                        ScopedIdentityViolation(
                            identity_kind="claim",
                            failure_subtype="scoped_ref_duplicate",
                            failing_item_count=1,
                        )
                    )
                observed.add(parsed.runtime_key)

    @staticmethod
    def _validate_typed_verifier_state_machine(
        findings: list[Mapping[str, Any]],
        *,
        decision: str,
        local_semantic_issues: list[str],
    ) -> None:
        nonempty_issue_layer_count = sum(
            bool(row.get("issue_codes")) for row in findings
        )
        nonempty_ref_layer_count = sum(
            bool(row.get("artifact_or_claim_refs")) for row in findings
        )
        ordered_violations = (
            (
                "pass_with_nonempty_issue_codes",
                lambda row: row.get("status") == "pass"
                and bool(row.get("issue_codes")),
            ),
            (
                "pass_with_nonempty_refs",
                lambda row: row.get("status") == "pass"
                and bool(row.get("artifact_or_claim_refs")),
            ),
            (
                "pass_with_repair_owner",
                lambda row: row.get("status") == "pass"
                and row.get("repair_owner") is not None,
            ),
            (
                "nonpass_without_issue_codes",
                lambda row: row.get("status") in {"review_required", "fail"}
                and not bool(row.get("issue_codes")),
            ),
            (
                "nonpass_without_refs",
                lambda row: row.get("status") in {"review_required", "fail"}
                and not bool(row.get("artifact_or_claim_refs")),
            ),
            (
                "nonpass_without_repair_owner",
                lambda row: row.get("status") in {"review_required", "fail"}
                and (
                    not isinstance(row.get("repair_owner"), str)
                    or not row["repair_owner"].strip()
                    or row["repair_owner"].strip().lower() == "none"
                ),
            ),
        )
        for failure_subtype, predicate in ordered_violations:
            failing_layer_count = sum(predicate(row) for row in findings)
            if failing_layer_count:
                raise S3VerifierStateMachineError(
                    failure_subtype=failure_subtype,
                    failing_layer_count=failing_layer_count,
                    nonempty_issue_layer_count=nonempty_issue_layer_count,
                    nonempty_ref_layer_count=nonempty_ref_layer_count,
                )

        statuses = [str(row.get("status") or "") for row in findings]
        expected_decision = (
            "reject"
            if "fail" in statuses
            else (
                "repair"
                if "review_required" in statuses
                else "accept_for_internal_review"
            )
        )
        all_pass_with_local_issues = bool(local_semantic_issues) and all(
            status == "pass" for status in statuses
        )
        if decision != expected_decision or all_pass_with_local_issues:
            conflicting_layer_count = (
                len(findings)
                if all_pass_with_local_issues
                else max(
                    1,
                    sum(
                        status
                        in (
                            {"fail"} if decision != "reject" else {"pass", "review_required"}
                        )
                        for status in statuses
                    ),
                )
            )
            raise S3VerifierStateMachineError(
                failure_subtype="decision_findings_state_conflict",
                failing_layer_count=conflicting_layer_count,
                nonempty_issue_layer_count=nonempty_issue_layer_count,
                nonempty_ref_layer_count=nonempty_ref_layer_count,
            )


class DeepSeekS3ThreeCellNodeExecutor:
    """Exact six-node DeepSeek transport with local, node-specific validation."""

    _NODE_ORDER = (
        *(f"domain_specialist:{cell_id}" for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS),
        "research_lead",
        "memo_writer",
        "verifier",
    )
    _SPECIALIST_AGENT_BY_CELL = {
        "demand_authenticity_and_sustainability": "industry_supply_chain_analyst",
        "value_and_profit_capture": "fundamental_analyst",
        "bottleneck_counterevidence_and_what_would_change": (
            "risk_counterevidence_analyst"
        ),
    }

    def __init__(
        self,
        *,
        chat_completion_fn: Callable[..., Mapping[str, Any]] | None = None,
        responses_completion_fn: Callable[
            ..., Mapping[str, Any]
        ] | None = None,
        strict_truth_kernel_adapter: (
            StrictTruthKernelJsonSchemaAdapter | None
        ) = None,
    ) -> None:
        self._chat_completion_fn = chat_completion_fn
        self._responses_completion_fn = responses_completion_fn
        self._strict_truth_kernel_adapter = (
            strict_truth_kernel_adapter
        )
        self._run_state: dict[str, dict[str, Any]] = {}

    def execute_node(
        self,
        node_id: str,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> Mapping[str, Any]:
        admission.assert_profile_admissible()
        if not admission.execution_enabled:
            raise ValueError("s3_provider_node_requires_enabled_admission")
        if (
            admission.strict_truth_kernel_policy_ref
            == S4_STRICT_TRUTH_KERNEL_POLICY_REF
            and (
                admission.provider_capability_ref
                != S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF
                or self._strict_truth_kernel_adapter is None
                or self._strict_truth_kernel_adapter.capability_ref
                != admission.provider_capability_ref
            )
        ):
            raise ValueError(
                "s4_strict_truth_kernel_capability_unbound_pre_provider"
            )
        if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
            raise ValueError("llm_gateway_transport_retries_must_equal_zero")
        if not admission.api_key_env or not os.environ.get(admission.api_key_env):
            raise ValueError("s3_bounded_agent_provider_credential_missing")
        lead_transport_contract = research_lead_transport_contract(
            admission.research_lead_transport_ref
        )

        input_digest = str(payload.get("input_digest") or "")
        research_run_id = str(run_identity.get("research_run_id") or "")
        if not input_digest or not research_run_id:
            raise ValueError("s3_bounded_node_exact_run_and_input_required")
        state_key = canonical_digest(
            (admission.admission_id, input_digest, research_run_id)
        )
        state = self._run_state.setdefault(
            state_key,
            {
                "next_index": 0,
                "spent_usd": 0.0,
                "usage_receipts": [],
                "local_fact_receipts": [],
                "provider_output_captures": [],
                "failed": False,
            },
        )
        if state["failed"]:
            raise ValueError("s3_bounded_node_run_already_failed")
        next_index = int(state["next_index"])
        if next_index >= len(self._NODE_ORDER) or self._NODE_ORDER[next_index] != node_id:
            raise ValueError("s3_bounded_node_execution_order_violation")

        recoverable_protocol_findings: list[dict[str, Any]] = []
        local_fact_receipts: list[dict[str, Any]] = []
        if (
            node_id.startswith("domain_specialist:")
            and admission.transport_ref
            in S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
                local_fact_receipts,
            ) = self._execute_segmented_specialist(
                node_id=node_id,
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "research_lead"
            and lead_transport_contract.gap_atom_deterministic_projection
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
                recoverable_protocol_findings,
            ) = self._execute_research_lead_v6(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "research_lead"
            and (
                lead_transport_contract
                .conflict_fact_presence_materialization_policy_ref
            )
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
            ) = self._execute_research_lead_v7(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "research_lead"
            and lead_transport_contract.compact_scoped_alias_wire
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
            ) = self._execute_research_lead_v5(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "research_lead"
            and lead_transport_contract.typed_scoped_identity
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
            ) = self._execute_research_lead_v4(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "research_lead"
            and lead_transport_contract.conflict_local_fact_presence
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
            ) = self._execute_research_lead_v3(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "research_lead"
            and lead_transport_contract.closed_semantic_output
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
            ) = self._execute_research_lead_v2(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "memo_writer"
            and admission.memo_writer_transport_ref
            == S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
            ) = self._execute_memo_writer_v2(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        elif (
            node_id == "memo_writer"
            and admission.memo_writer_transport_ref
            == S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ):
            (
                output,
                receipts,
                model_view_binding,
                captures,
            ) = self._execute_memo_writer_v3(
                payload=payload,
                admission=admission,
                state=state,
                input_digest=input_digest,
                research_run_id=research_run_id,
            )
        else:
            max_tokens = self._max_tokens(node_id, admission)
            system, request, model_view_binding = self._node_request(
                node_id, payload, admission
            )
            output, receipt, capture = self._call_json_object(
                state=state,
                logical_node_id=node_id,
                receipt_stage=node_id,
                system=system,
                request=request,
                max_tokens=max_tokens,
                admission=admission,
                input_digest=input_digest,
                research_run_id=research_run_id,
                enforce_specialist_byte_limit=node_id.startswith(
                    "domain_specialist:"
                ),
            )
            try:
                self._validate_node_output(
                    node_id,
                    output,
                    payload,
                    output_contract_ref=admission.output_contract_ref,
                )
            except S3VerifierStateMachineError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    exc.failure_code,
                    verifier_state_machine=exc.telemetry,
                )
            except ValueError as exc:
                state["failed"] = True
                self._stop(state, node_id, str(exc))
            receipts = [receipt]
            captures = [capture]

        agent_version, skill_pack = self._version_bindings(node_id, admission)
        quality_observations: list[dict[str, Any]] = []
        if (
            node_id == "research_lead"
            and lead_transport_contract.compact_scoped_alias_wire
        ):
            research_profile = research_profile_for_ref(
                admission.research_profile_ref
            )
            quality_observations, hard_findings = (
                NarrativeQualityPolicy.assess(
                    [
                        (field_id, value)
                        for field_id, value in (
                            self._research_lead_v5_named_narratives(output)
                        )
                    ],
                    target_characters=(
                        research_profile
                        .research_lead_narrative_target_characters
                    ),
                    hard_max_characters=(
                        research_profile
                        .research_lead_narrative_hard_max_characters
                    ),
                    length_exceedance_is_terminal=(
                        research_profile
                        .research_lead_narrative_character_limits_terminal
                    ),
                    aggregate_target_characters=(
                        research_profile
                        .research_lead_aggregate_narrative_max_characters
                        if not research_profile
                        .research_lead_narrative_character_limits_terminal
                        else None
                    ),
                )
            )
            if hard_findings:
                raise AssertionError(
                    "research_lead_hard_narrative_findings_escaped_assembly"
                )
        policy = S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY
        expected_finding_keys = {
            "finding_code",
            "acceptance_layer",
            "terminal",
            "candidate_count",
            "selected_count",
            "overflow_count",
            "projection_policy_ref",
            "selected_candidate_ordinals",
            "selected_candidate_digests",
            "overflow_candidate_digests",
        }
        for finding in recoverable_protocol_findings:
            if (
                set(finding) != expected_finding_keys
                or finding.get("finding_code") != policy.finding_code
                or finding.get("acceptance_layer")
                != policy.acceptance_layer
                or finding.get("terminal") is not False
                or finding.get("projection_policy_ref")
                != policy.policy_ref
                or type(finding.get("candidate_count")) is not int
                or type(finding.get("selected_count")) is not int
                or type(finding.get("overflow_count")) is not int
                or finding["selected_count"] != policy.canonical_maximum
                or finding["candidate_count"]
                != finding["selected_count"] + finding["overflow_count"]
                or finding["overflow_count"] <= 0
                or not isinstance(
                    finding.get("selected_candidate_ordinals"), list
                )
                or len(finding["selected_candidate_ordinals"])
                != finding["selected_count"]
                or not all(
                    type(value) is int and value > 0
                    for value in finding["selected_candidate_ordinals"]
                )
                or any(
                    not isinstance(values, list)
                    or not all(
                        isinstance(value, str)
                        and re.fullmatch(r"[0-9a-f]{64}", value)
                        for value in values
                    )
                    for values in (
                        finding.get("selected_candidate_digests"),
                        finding.get("overflow_candidate_digests"),
                    )
                )
                or len(finding["selected_candidate_digests"])
                != finding["selected_count"]
                or len(finding["overflow_candidate_digests"])
                != finding["overflow_count"]
            ):
                raise ValueError(
                    "s3_bounded_recoverable_protocol_finding_not_closed"
                )
        state["next_index"] = next_index + 1
        version_bindings = {
            "agent_definition_version_ref": agent_version[
                "agent_definition_version_ref"
            ],
            "skill_pack_version_ref": skill_pack["skill_pack_version_ref"],
        }
        version_bindings.update(model_view_binding)
        envelope = {
            "node_id": node_id,
            "output": output,
            "observed_counts": {
                "model_calls": len(receipts),
                "provider_calls": len(receipts),
                "network_calls": len(receipts),
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "live_case_head_writes": 0,
                "evaluation_evidence_promotions": 0,
            },
            "usage_receipts": receipts,
            "version_bindings": version_bindings,
            "provider_output_captures": captures,
            "local_fact_receipts": local_fact_receipts,
            "quality_observations": quality_observations,
            "recoverable_protocol_findings": (
                recoverable_protocol_findings
            ),
        }
        if int(state["next_index"]) == len(self._NODE_ORDER):
            self._run_state.pop(state_key, None)
        return envelope

    @staticmethod
    def _responses_assistant_output_text(
        result: Mapping[str, Any],
    ) -> str:
        output = result.get("response_output")
        if not isinstance(output, list):
            return ""
        texts: list[str] = []
        for message in output:
            if (
                not isinstance(message, Mapping)
                or message.get("type") != "message"
                or not isinstance(message.get("content"), list)
            ):
                continue
            for item in message["content"]:
                if (
                    isinstance(item, Mapping)
                    and item.get("type") == "output_text"
                    and isinstance(item.get("text"), str)
                ):
                    texts.append(str(item["text"]))
        return "".join(texts)

    @staticmethod
    def _provider_interaction_capture(
        *,
        admission: S3ThreeCellBoundedAgentAdmission,
        capture_sequence: int,
        stage: str,
        receipt: Mapping[str, Any],
        result: Mapping[str, Any],
        assistant_output_text: str,
        model_visible_request: Sequence[Mapping[str, Any]],
        nonsecret_inference_arguments: Mapping[str, Any],
        request_path: str,
    ) -> dict[str, Any]:
        output_present = bool(assistant_output_text)
        if (
            admission.provider_output_capture_policy_ref
            == S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
        ):
            return {
                "capture_policy_ref": S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
                "capture_sequence": capture_sequence,
                "stage": stage,
                "call_id": str(receipt["call_id"]),
                "provider": str(receipt["provider"]),
                "model": str(receipt["model"]),
                "provider_status": str(result.get("status") or ""),
                "finish_reason": str(
                    result.get("finish_reason")
                    or result.get("response_status")
                    or ""
                ),
                "assistant_output_text": assistant_output_text,
                "assistant_output_present": output_present,
                "raw_provider_response_included": False,
                "private_reasoning_included": False,
            }
        if (
            admission.provider_output_capture_policy_ref
            != S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
        ):
            raise ValueError("provider_output_capture_policy_unsupported")
        visible_request = [
            dict(row) for row in model_visible_request
        ]
        inference_arguments = dict(nonsecret_inference_arguments)
        provider_route = {
            "base_url": str(admission.base_url or ""),
            "request_path": request_path,
        }
        capture = {
            "capture_policy_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ),
            "capture_sequence": capture_sequence,
            "stage": stage,
            "call_id": str(receipt["call_id"]),
            "provider": str(receipt["provider"]),
            "model": str(receipt["model"]),
            "provider_status": str(result.get("status") or ""),
            "finish_reason": str(
                result.get("finish_reason")
                or result.get("response_status")
                or ""
            ),
            "assistant_output_text": assistant_output_text,
            "assistant_output_present": output_present,
            "model_visible_request": visible_request,
            "model_visible_request_digest": canonical_digest(
                visible_request
            ),
            "nonsecret_inference_arguments": inference_arguments,
            "nonsecret_inference_arguments_digest": canonical_digest(
                inference_arguments
            ),
            "provider_route": provider_route,
            "provider_route_digest": canonical_digest(provider_route),
            "validator_match_index": [],
            "raw_request_envelope_included": False,
            "raw_provider_response_included": False,
            "private_reasoning_included": False,
            "credentials_included": False,
        }
        if (
            admission.judgment_atom_compiled_contract_ref
            in {
                FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
                FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
            }
        ):
            binding = (
                load_fin_0_1_2_s3_runtime_contract_binding()
                if admission.judgment_atom_compiled_contract_ref
                == FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF
                else load_fin_0_1_2_runtime_contract_binding()
            )
            binding.assert_admission_binding(
                binding_ref=admission.runtime_contract_family_binding_ref,
                source_digest=(
                    admission.runtime_contract_family_source_digest
                ),
            )
            capture["runtime_contract_family_binding"] = {
                "binding_ref": binding.binding_ref,
                "source_digest": binding.source_digest,
                "contract_id": binding.contract_id,
                "contract_version": binding.contract_version,
                "consumer_binding": binding.consumer_receipt(
                    "capture_index"
                ),
            }
        return capture

    def _call_strict_truth_kernel(
        self,
        *,
        state: dict[str, Any],
        logical_node_id: str,
        receipt_stage: str,
        system: str,
        request: Mapping[str, Any],
        max_tokens: int,
        admission: S3ThreeCellBoundedAgentAdmission,
        input_digest: str,
        research_run_id: str,
        policy: StrictTruthKernelPolicy,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        adapter = self._strict_truth_kernel_adapter
        if (
            adapter is None
            or admission.provider_capability_ref
            != adapter.capability_ref
        ):
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s4_strict_truth_kernel_capability_unbound_pre_provider",
                strict_truth_kernel=StrictTruthKernelViolation(
                    "top_level_shape_invalid",
                    "provider_capability_ref",
                    1,
                ).telemetry(),
            )
        user = json.dumps(request, ensure_ascii=False, sort_keys=True)
        transport_contract = json.dumps(
            {"text": adapter.text_format(policy)},
            ensure_ascii=False,
            sort_keys=True,
        )
        projected = self._projected_cost(
            estimate_provider_input_tokens(
                system + user + transport_contract
            ),
            max_tokens,
            admission,
        )
        if float(state["spent_usd"]) + projected > admission.max_total_cost_usd:
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_node_projected_cost_cap_exceeded",
            )

        completion = self._responses_completion_fn
        if completion is None:
            from sec_agent.llm_gateway import responses_completion

            completion = responses_completion
        result = completion(
            llm_backend=str(admission.provider),
            base_url=str(admission.base_url),
            responses_path="/responses",
            model=str(admission.model),
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text=adapter.text_format(policy),
            reasoning={"effort": str(admission.reasoning_effort)},
            api_key_env=str(admission.api_key_env),
            max_output_tokens=max_tokens,
            timeout_s=admission.timeout_seconds,
            stream=False,
            role=receipt_stage,
            profile=admission.execution_profile_version_ref,
            trace_tags={
                "admission_id": admission.admission_id,
                "input_digest": input_digest,
                "research_run_id": research_run_id,
                "node_id": logical_node_id,
                "stage": receipt_stage,
            },
        )
        if not isinstance(result, Mapping):
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_node_provider_envelope_invalid",
            )
        receipt = self._usage_receipt(
            result,
            admission,
            node_id=receipt_stage,
        )
        state["usage_receipts"].append(receipt)
        state["spent_usd"] = round(
            float(state["spent_usd"])
            + float(receipt["estimated_cost_usd"]),
            8,
        )
        response_text = self._responses_assistant_output_text(result)
        capture = self._provider_interaction_capture(
            admission=admission,
            capture_sequence=(
                len(state["provider_output_captures"]) + 1
            ),
            stage=receipt_stage,
            receipt=receipt,
            result=result,
            assistant_output_text=(
                response_text
                if admission.provider_output_capture_policy_ref
                == S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
                else ""
            ),
            model_visible_request=(
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ),
            nonsecret_inference_arguments={
                "api_surface": "responses",
                "text": adapter.text_format(policy),
                "reasoning": {
                    "effort": str(admission.reasoning_effort)
                },
                "max_output_tokens": max_tokens,
                "timeout_seconds": admission.timeout_seconds,
                "stream": False,
            },
            request_path="/responses",
        )
        state["provider_output_captures"].append(capture)
        if int(receipt["output_tokens"]) > max_tokens:
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_node_output_token_cap_exceeded",
            )
        if int(receipt["transport_attempt_count"]) != 1:
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_node_transport_attempt_violation",
            )
        if result.get("status") != "ok":
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_node_provider_failure",
            )
        if float(state["spent_usd"]) > admission.max_total_cost_usd:
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_node_actual_cost_cap_exceeded",
            )
        try:
            provider_atoms = adapter.parse_response(result)
        except NativeJsonSchemaResponseError:
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s4_strict_truth_kernel_provider_response_invalid",
                strict_truth_kernel=StrictTruthKernelViolation(
                    "top_level_shape_invalid",
                    "provider_response",
                    1,
                ).telemetry(),
            )
        if not capture["assistant_output_present"]:
            capture["assistant_output_text"] = json.dumps(
                provider_atoms,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            capture["assistant_output_present"] = True
        rendered, violation = policy.render_provider_output(
            provider_atoms
        )
        if violation is not None or rendered is None:
            state["failed"] = True
            exact_violation = violation or StrictTruthKernelViolation(
                "local_rendering_failed",
                "provider_atoms",
                1,
            )
            self._stop(
                state,
                logical_node_id,
                (
                    "s4_strict_truth_kernel_invalid:"
                    f"{exact_violation.subtype}"
                ),
                strict_truth_kernel=exact_violation.telemetry(),
            )
        return rendered, receipt, capture

    def _call_json_object(
        self,
        *,
        state: dict[str, Any],
        logical_node_id: str,
        receipt_stage: str,
        system: str,
        request: Mapping[str, Any],
        max_tokens: int,
        admission: S3ThreeCellBoundedAgentAdmission,
        input_digest: str,
        research_run_id: str,
        enforce_specialist_byte_limit: bool,
        research_lead_v2_telemetry: bool = False,
        research_lead_v3_telemetry: bool = False,
        output_byte_limit: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        user = json.dumps(request, ensure_ascii=False, sort_keys=True)
        projected = self._projected_cost(
            estimate_provider_input_tokens(system + user),
            max_tokens,
            admission,
        )
        if float(state["spent_usd"]) + projected > admission.max_total_cost_usd:
            state["failed"] = True
            self._stop(
                state, logical_node_id, "s3_bounded_node_projected_cost_cap_exceeded"
            )

        completion = self._chat_completion_fn
        if completion is None:
            from sec_agent.llm_gateway import chat_completion

            completion = chat_completion
        result = completion(
            llm_backend=str(admission.provider),
            base_url=str(admission.base_url),
            chat_completions_path="/chat/completions",
            model=str(admission.model),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=None,
            tool_choice=None,
            response_format={"type": "json_object"},
            api_key_env=str(admission.api_key_env),
            temperature=0.0,
            max_tokens=max_tokens,
            timeout_s=admission.timeout_seconds,
            stream=False,
            enable_thinking=False,
            reasoning_effort="none",
            role=receipt_stage,
            profile=admission.execution_profile_version_ref,
            trace_tags={
                "admission_id": admission.admission_id,
                "input_digest": input_digest,
                "research_run_id": research_run_id,
                "node_id": logical_node_id,
                "stage": receipt_stage,
            },
        )
        if not isinstance(result, Mapping):
            state["failed"] = True
            self._stop(
                state, logical_node_id, "s3_bounded_node_provider_envelope_invalid"
            )
        receipt = self._usage_receipt(
            result, admission, node_id=receipt_stage
        )
        state["usage_receipts"].append(receipt)
        state["spent_usd"] = round(
            float(state["spent_usd"]) + float(receipt["estimated_cost_usd"]), 8
        )
        content = result.get("content")
        capture = self._provider_interaction_capture(
            admission=admission,
            capture_sequence=len(state["provider_output_captures"]) + 1,
            stage=receipt_stage,
            receipt=receipt,
            result=result,
            assistant_output_text=(
                content if isinstance(content, str) else ""
            ),
            model_visible_request=(
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ),
            nonsecret_inference_arguments={
                "api_surface": "chat_completions",
                "tools": None,
                "tool_choice": None,
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
                "max_tokens": max_tokens,
                "timeout_seconds": admission.timeout_seconds,
                "stream": False,
                "enable_thinking": False,
                "reasoning_effort": "none",
            },
            request_path="/chat/completions",
        )
        state["provider_output_captures"].append(capture)
        if int(receipt["output_tokens"]) > max_tokens:
            state["failed"] = True
            self._stop(
                state, logical_node_id, "s3_bounded_node_output_token_cap_exceeded"
            )
        if int(receipt["transport_attempt_count"]) != 1:
            state["failed"] = True
            self._stop(
                state, logical_node_id, "s3_bounded_node_transport_attempt_violation"
            )
        if result.get("status") != "ok":
            state["failed"] = True
            self._stop(state, logical_node_id, "s3_bounded_node_provider_failure")
        finish_reason = str(result.get("finish_reason") or "")
        if finish_reason == "length":
            state["failed"] = True
            if research_lead_v2_telemetry or research_lead_v3_telemetry:
                error_type = (
                    S3ResearchLeadV3ContractError
                    if research_lead_v3_telemetry
                    else S3ResearchLeadContractError
                )
                error = error_type(
                    failure_family="capacity",
                    failure_subtype="provider_length_stop",
                    field_id="assembled_output",
                    failing_item_count=1,
                )
                self._stop(
                    state,
                    logical_node_id,
                    error.failure_code,
                    research_lead_contract=error.telemetry,
                )
            self._stop(state, logical_node_id, "s3_bounded_node_output_truncated")
        if finish_reason != "stop":
            state["failed"] = True
            self._stop(
                state, logical_node_id, "s3_bounded_node_finish_reason_invalid"
            )
        if float(state["spent_usd"]) > admission.max_total_cost_usd:
            state["failed"] = True
            self._stop(
                state, logical_node_id, "s3_bounded_node_actual_cost_cap_exceeded"
            )
        if not isinstance(content, str) or not content.strip():
            state["failed"] = True
            self._stop(state, logical_node_id, "s3_bounded_node_output_empty")
        if (
            enforce_specialist_byte_limit
            and len(content.encode("utf-8"))
            > S3_SPECIALIST_V2_MAX_SERIALIZED_UTF8_BYTES
        ):
            state["failed"] = True
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_specialist_output_byte_budget_exceeded",
            )
        if output_byte_limit is not None and len(content.encode("utf-8")) > output_byte_limit:
            state["failed"] = True
            if research_lead_v2_telemetry or research_lead_v3_telemetry:
                error_type = (
                    S3ResearchLeadV3ContractError
                    if research_lead_v3_telemetry
                    else S3ResearchLeadContractError
                )
                error = error_type(
                    failure_family="capacity",
                    failure_subtype="provider_segment_over_max_utf8_bytes",
                    field_id="assembled_output",
                    failing_item_count=1,
                )
                self._stop(
                    state,
                    logical_node_id,
                    error.failure_code,
                    research_lead_contract=error.telemetry,
                )
            self._stop(
                state,
                logical_node_id,
                "s3_bounded_node_output_byte_budget_exceeded",
            )
        try:
            output = self._parse_native_json_object(content)
        except ValueError as exc:
            state["failed"] = True
            if research_lead_v2_telemetry or research_lead_v3_telemetry:
                subtype_by_code = {
                    "s3_bounded_node_native_json_required": "native_json_required",
                    "s3_bounded_node_json_decode_failed": "json_decode_failed",
                    "s3_bounded_node_duplicate_json_key": "duplicate_key",
                    "s3_bounded_node_output_not_object": "non_object",
                }
                error_type = (
                    S3ResearchLeadV3ContractError
                    if research_lead_v3_telemetry
                    else S3ResearchLeadContractError
                )
                error = error_type(
                    failure_family="parse",
                    failure_subtype=subtype_by_code.get(
                        str(exc), "json_decode_failed"
                    ),
                    field_id="top_level",
                    failing_item_count=1,
                )
                self._stop(
                    state,
                    logical_node_id,
                    error.failure_code,
                    research_lead_contract=error.telemetry,
                )
            self._stop(state, logical_node_id, str(exc))
        if (
            admission.case_numeric_authority_policy_ref
            in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
        ):
            raw_contracts = request.get(
                "case_numeric_authority_contracts"
            )
            if raw_contracts is None:
                single_contract = request.get(
                    "case_numeric_authority_contract"
                )
                raw_contracts = (
                    [single_contract]
                    if isinstance(single_contract, Mapping)
                    else []
                )
            if (
                not isinstance(raw_contracts, list)
                or not raw_contracts
                or any(
                    not isinstance(row, Mapping)
                    for row in raw_contracts
                )
            ):
                state["failed"] = True
                self._stop(
                    state,
                    logical_node_id,
                    "s4_case_numeric_authority_contract_missing",
                )
            try:
                policies = [
                    CaseNumericAuthorityPolicy.from_prompt_contract(
                        row
                    )
                    for row in raw_contracts
                ]
            except ValueError:
                state["failed"] = True
                self._stop(
                    state,
                    logical_node_id,
                    "s4_case_numeric_authority_contract_invalid",
                )
            narrative_policy = (
                CaseNumericAuthorityPolicy.combined_narrative_classifier(
                    policies
                )
            )
            narrative_matches = narrative_policy.provider_narrative_matches(
                output
            )
            if (
                capture.get("capture_policy_ref")
                == S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ):
                capture["validator_match_index"] = [
                    match.safe_index()
                    for match in narrative_matches
                ]
            violation = narrative_policy.first_provider_narrative_violation(
                output
            )
            if violation is not None:
                state["failed"] = True
                self._stop(
                    state,
                    logical_node_id,
                    "s4_case_numeric_authority_provider_narrative_invalid",
                    case_numeric_authority=violation.telemetry(
                        capture_sequence=int(
                            capture["capture_sequence"]
                        ),
                        provider_phase=receipt_stage,
                    ),
                )
            identity_projection = request.get(
                "case_delivery_identity_projection"
            )
            if not isinstance(identity_projection, Mapping):
                state["failed"] = True
                self._stop(
                    state,
                    logical_node_id,
                    "s4_case_delivery_identity_projection_missing",
                )
            try:
                identity_policy = (
                    CaseDeliveryIdentityPolicy.from_projection(
                        identity_projection
                    )
                )
            except ValueError:
                state["failed"] = True
                self._stop(
                    state,
                    logical_node_id,
                    "s4_case_delivery_identity_projection_invalid",
                )
            identity_violation = (
                identity_policy
                .first_provider_narrative_identity_violation(output)
            )
            if identity_violation is not None:
                state["failed"] = True
                identity_telemetry = dict(identity_violation)
                identity_telemetry.update(
                    {
                        "provider_phase": logical_node_id,
                        "segment_id": str(
                            request.get("segment_id")
                            or "unsegmented"
                        ),
                    }
                )
                self._stop(
                    state,
                    logical_node_id,
                    "s4_case_delivery_identity_provider_narrative_invalid",
                    case_delivery_identity=identity_telemetry,
                )
        return output, receipt, capture

    def _execute_research_lead_v2(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        specialists = payload.get("specialist_outputs")
        digests = payload.get("specialist_output_digests")
        if not isinstance(specialists, list) or not isinstance(digests, Mapping):
            state["failed"] = True
            error = S3ResearchLeadContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        try:
            cell_heads = self._derive_research_lead_cell_heads(specialists, digests)
        except ValueError:
            state["failed"] = True
            error = S3ResearchLeadContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        system, request, model_view_binding = self._research_lead_v2_request(
            payload, cell_heads
        )
        segment, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="research_lead",
            receipt_stage="research_lead",
            system=system,
            request=request,
            max_tokens=admission.lead_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
            research_lead_v2_telemetry=True,
            output_byte_limit=S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_PROVIDER_UTF8_BYTES,
        )
        try:
            self._validate_research_lead_v2_segment(segment, specialists)
            output = {"cell_heads": cell_heads, **segment}
            assembled_bytes = len(
                json.dumps(
                    output,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if (
                assembled_bytes
                > S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_ASSEMBLED_UTF8_BYTES
            ):
                raise S3ResearchLeadContractError(
                    failure_family="assembly",
                    failure_subtype="assembled_output_over_max_utf8_bytes",
                    field_id="assembled_output",
                    failing_item_count=1,
                )
            try:
                S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                    output,
                    digests,
                    specialist_outputs=specialists,
                    output_contract_ref=admission.output_contract_ref,
                )
            except ValueError as exc:
                raise S3ResearchLeadContractError(
                    failure_family="assembly",
                    failure_subtype="canonical_validation_failed",
                    field_id="assembled_output",
                    failing_item_count=1,
                ) from exc
        except S3ResearchLeadContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                research_lead_contract=exc.telemetry,
            )
        return output, [receipt], model_view_binding, [capture]

    def _execute_research_lead_v3(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        specialists = payload.get("specialist_outputs")
        digests = payload.get("specialist_output_digests")
        if not isinstance(specialists, list) or not isinstance(digests, Mapping):
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        try:
            cell_heads = self._derive_research_lead_cell_heads(specialists, digests)
        except ValueError:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        system, request, model_view_binding = self._research_lead_v3_request(
            payload, cell_heads
        )
        segment, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="research_lead",
            receipt_stage="research_lead",
            system=system,
            request=request,
            max_tokens=admission.lead_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
            research_lead_v3_telemetry=True,
            output_byte_limit=S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_PROVIDER_UTF8_BYTES,
        )
        try:
            self._validate_research_lead_v3_segment(segment, specialists)
            output = {"cell_heads": cell_heads, **segment}
            assembled_bytes = len(
                json.dumps(
                    output,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if (
                assembled_bytes
                > S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_ASSEMBLED_UTF8_BYTES
            ):
                raise S3ResearchLeadV3ContractError(
                    failure_family="assembly",
                    failure_subtype="assembled_output_over_max_utf8_bytes",
                    field_id="assembled_output",
                    failing_item_count=1,
                )
            try:
                S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                    output,
                    digests,
                    specialist_outputs=specialists,
                    output_contract_ref=admission.output_contract_ref,
                )
            except ValueError as exc:
                raise S3ResearchLeadV3ContractError(
                    failure_family="assembly",
                    failure_subtype="canonical_validation_failed",
                    field_id="assembled_output",
                    failing_item_count=1,
                ) from exc
        except S3ResearchLeadV3ContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                research_lead_contract=exc.telemetry,
            )
        return output, [receipt], model_view_binding, [capture]

    def _execute_research_lead_v4(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        specialists = payload.get("specialist_outputs")
        digests = payload.get("specialist_output_digests")
        scoped_surface = payload.get("scoped_identity_surface")
        if (
            not isinstance(specialists, list)
            or not isinstance(digests, Mapping)
            or not isinstance(scoped_surface, Mapping)
        ):
            state["failed"] = True
            error = S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                scoped_identity_contract=error.telemetry,
            )
        try:
            cell_heads = self._derive_research_lead_cell_heads(
                specialists, digests
            )
        except ValueError:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        system, request, model_view_binding = self._research_lead_v4_request(
            payload, cell_heads
        )
        segment, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="research_lead",
            receipt_stage="research_lead",
            system=system,
            request=request,
            max_tokens=admission.lead_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
            research_lead_v3_telemetry=True,
            output_byte_limit=(
                S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_PROVIDER_UTF8_BYTES
            ),
        )
        try:
            self._validate_research_lead_v4_segment(
                segment,
                specialists,
                scoped_surface,
            )
            output = {"cell_heads": cell_heads, **segment}
            assembled_bytes = len(
                json.dumps(
                    output,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if (
                assembled_bytes
                > S3_OWNER_GRADE_RESEARCH_LEAD_V2_MAX_ASSEMBLED_UTF8_BYTES
            ):
                raise S3ResearchLeadV3ContractError(
                    failure_family="assembly",
                    failure_subtype="assembled_output_over_max_utf8_bytes",
                    field_id="assembled_output",
                    failing_item_count=1,
                )
            S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                output,
                digests,
                specialist_outputs=specialists,
                scoped_identity_surface=scoped_surface,
                output_contract_ref=(
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                ),
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except S3ResearchLeadV3ContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                research_lead_contract=exc.telemetry,
            )
        except ValueError as exc:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="canonical_validation_failed",
                field_id="assembled_output",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
            raise AssertionError("unreachable") from exc
        return output, [receipt], model_view_binding, [capture]

    def _execute_research_lead_v5(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        specialists = payload.get("specialist_outputs")
        digests = payload.get("specialist_output_digests")
        scoped_surface = payload.get("scoped_identity_surface")
        if (
            not isinstance(specialists, list)
            or not isinstance(digests, Mapping)
            or not isinstance(scoped_surface, Mapping)
        ):
            state["failed"] = True
            error = S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                scoped_identity_contract=error.telemetry,
            )
        research_profile = research_profile_for_ref(
            admission.research_profile_ref
        )
        try:
            cell_heads = self._derive_research_lead_cell_heads(
                specialists,
                digests,
                research_profile=research_profile,
            )
            alias_table = (
                S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
                    specialists,
                    scoped_surface,
                )
            )
            capacity = self._research_lead_v5_capacity_envelope(
                alias_table=alias_table,
                cell_heads=cell_heads,
                research_profile=research_profile,
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except ValueError:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        system, request, model_view_binding = self._research_lead_v5_request(
            payload,
            cell_heads,
            research_profile=research_profile,
            capacity=capacity,
        )
        segment, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="research_lead",
            receipt_stage="research_lead",
            system=system,
            request=request,
            max_tokens=admission.lead_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
            research_lead_v3_telemetry=True,
            output_byte_limit=(
                research_profile.research_lead_provider_raw_max_utf8_bytes
            ),
        )
        try:
            output = self._assemble_research_lead_v5_output(
                segment,
                specialists,
                scoped_surface,
                cell_heads=cell_heads,
                research_profile=research_profile,
                capacity=capacity,
            )
            S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                output,
                digests,
                specialist_outputs=specialists,
                scoped_identity_surface=scoped_surface,
                output_contract_ref=(
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                ),
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except S3ResearchLeadV3ContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                research_lead_contract=exc.telemetry,
            )
        except ValueError as exc:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="canonical_validation_failed",
                field_id="assembled_output",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
            raise AssertionError("unreachable") from exc
        return output, [receipt], model_view_binding, [capture]

    def _bind_case_numeric_identity_to_lead_request(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        request: dict[str, Any],
        system: str,
    ) -> str:
        """Compose the shared S4 safety capability with any eligible Lead."""

        if (
            admission.case_numeric_authority_policy_ref
            not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
        ):
            return system
        numeric_contracts = payload.get(
            "case_numeric_authority_contracts"
        )
        if not isinstance(numeric_contracts, list) or not numeric_contracts:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                "s4_case_numeric_authority_contract_missing",
            )
        try:
            numeric_policy = CaseNumericAuthorityPolicy.from_prompt_contract(
                numeric_contracts[0]
            )
        except (TypeError, ValueError):
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                "s4_case_numeric_authority_contract_invalid",
            )
        request["case_numeric_authority_contracts"] = deepcopy(
            numeric_contracts
        )
        identity_projection = payload.get(
            "case_delivery_identity_projection"
        )
        if not isinstance(identity_projection, Mapping):
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                "s4_case_delivery_identity_projection_missing",
            )
        identity_policy = CaseDeliveryIdentityPolicy.from_projection(
            identity_projection
        )
        request["case_delivery_identity_projection"] = deepcopy(
            identity_projection
        )
        return (
            system
            + " "
            + numeric_policy.provider_narrative_instruction()
            + (
                " In dependency, conflict, variant, or gap narrative, refer "
                "to the qualitative mechanism and exact Claim aliases; "
                "numeric rendering remains local."
            )
            + identity_policy.provider_identity_boundary_instruction()
        )

    def _execute_research_lead_v6(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        specialists = payload.get("specialist_outputs")
        digests = payload.get("specialist_output_digests")
        scoped_surface = payload.get("scoped_identity_surface")
        if (
            not isinstance(specialists, list)
            or not isinstance(digests, Mapping)
            or not isinstance(scoped_surface, Mapping)
        ):
            state["failed"] = True
            error = S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                scoped_identity_contract=error.telemetry,
            )
        research_profile = research_profile_for_ref(
            admission.research_profile_ref
        )
        try:
            cell_heads = self._derive_research_lead_cell_heads(
                specialists,
                digests,
                research_profile=research_profile,
            )
            alias_table = (
                S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
                    specialists,
                    scoped_surface,
                )
            )
            capacity = self._research_lead_v5_capacity_envelope(
                alias_table=alias_table,
                cell_heads=cell_heads,
                research_profile=research_profile,
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except ValueError:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        system, request, model_view_binding = self._research_lead_v6_request(
            payload,
            cell_heads,
            research_profile=research_profile,
            capacity=capacity,
        )
        system = self._bind_case_numeric_identity_to_lead_request(
            payload=payload,
            admission=admission,
            state=state,
            request=request,
            system=system,
        )
        segment, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="research_lead",
            receipt_stage="research_lead",
            system=system,
            request=request,
            max_tokens=admission.lead_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
            research_lead_v3_telemetry=True,
            output_byte_limit=(
                research_profile.research_lead_provider_raw_max_utf8_bytes
            ),
        )
        try:
            output, recoverable_protocol_findings = (
                self._assemble_research_lead_v6_output(
                    segment,
                    specialists,
                    scoped_surface,
                    cell_heads=cell_heads,
                    research_profile=research_profile,
                    capacity=capacity,
                )
            )
            S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                output,
                digests,
                specialist_outputs=specialists,
                scoped_identity_surface=scoped_surface,
                output_contract_ref=(
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                ),
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except S3ResearchLeadV3ContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                research_lead_contract=exc.telemetry,
            )
        except ValueError as exc:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="canonical_validation_failed",
                field_id="assembled_output",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
            raise AssertionError("unreachable") from exc
        return (
            output,
            [receipt],
            model_view_binding,
            [capture],
            recoverable_protocol_findings,
        )

    def _execute_research_lead_v7(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        specialists = payload.get("specialist_outputs")
        digests = payload.get("specialist_output_digests")
        scoped_surface = payload.get("scoped_identity_surface")
        if (
            not isinstance(specialists, list)
            or not isinstance(digests, Mapping)
            or not isinstance(scoped_surface, Mapping)
        ):
            state["failed"] = True
            error = S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                scoped_identity_contract=error.telemetry,
            )
        research_profile = research_profile_for_ref(
            admission.research_profile_ref
        )
        try:
            cell_heads = self._derive_research_lead_cell_heads(
                specialists,
                digests,
                research_profile=research_profile,
            )
            alias_table = (
                S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
                    specialists,
                    scoped_surface,
                )
            )
            capacity = self._research_lead_v5_capacity_envelope(
                alias_table=alias_table,
                cell_heads=cell_heads,
                research_profile=research_profile,
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except ValueError:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="deterministic_heads_invalid",
                field_id="cell_heads",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
        system, request, model_view_binding = self._research_lead_v7_request(
            payload,
            cell_heads,
            research_profile=research_profile,
            capacity=capacity,
        )
        system = self._bind_case_numeric_identity_to_lead_request(
            payload=payload,
            admission=admission,
            state=state,
            request=request,
            system=system,
        )
        segment, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="research_lead",
            receipt_stage="research_lead",
            system=system,
            request=request,
            max_tokens=admission.lead_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
            research_lead_v3_telemetry=True,
            output_byte_limit=(
                research_profile.research_lead_provider_raw_max_utf8_bytes
            ),
        )
        try:
            output = self._assemble_research_lead_v7_output(
                segment,
                specialists,
                scoped_surface,
                cell_heads=cell_heads,
                research_profile=research_profile,
                capacity=capacity,
            )
            S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                output,
                digests,
                specialist_outputs=specialists,
                scoped_identity_surface=scoped_surface,
                output_contract_ref=(
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
                ),
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except S3ResearchLeadV3ContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "research_lead",
                exc.failure_code,
                research_lead_contract=exc.telemetry,
            )
        except ValueError as exc:
            state["failed"] = True
            error = S3ResearchLeadV3ContractError(
                failure_family="assembly",
                failure_subtype="canonical_validation_failed",
                field_id="assembled_output",
                failing_item_count=1,
            )
            self._stop(
                state,
                "research_lead",
                error.failure_code,
                research_lead_contract=error.telemetry,
            )
            raise AssertionError("unreachable") from exc
        return output, [receipt], model_view_binding, [capture]

    def _execute_memo_writer_v2(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        system, request, model_view_binding = self._memo_writer_v2_request(payload)
        provider_output, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="memo_writer",
            receipt_stage="memo_writer",
            system=system,
            request=request,
            max_tokens=admission.writer_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
        )
        try:
            output = self._assemble_memo_writer_v2_output(provider_output, payload)
            self._validate_node_output(
                "memo_writer",
                output,
                payload,
                output_contract_ref=admission.output_contract_ref,
            )
        except S3MemoWriterContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "memo_writer",
                exc.failure_code,
                memo_writer_contract=exc.telemetry,
            )
        except ValueError as exc:
            state["failed"] = True
            error = S3MemoWriterContractError(
                failure_family="assembly",
                failure_subtype="canonical_validation_failed",
                field_id="assembled_output",
                failing_item_count=1,
            )
            self._stop(
                state,
                "memo_writer",
                error.failure_code,
                memo_writer_contract=error.telemetry,
            )
            raise AssertionError("unreachable") from exc
        return output, [receipt], model_view_binding, [capture]

    def _execute_memo_writer_v3(
        self,
        *,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        system, request, model_view_binding = self._memo_writer_v3_request(
            payload
        )
        provider_output, receipt, capture = self._call_json_object(
            state=state,
            logical_node_id="memo_writer",
            receipt_stage="memo_writer",
            system=system,
            request=request,
            max_tokens=admission.writer_max_output_tokens,
            admission=admission,
            input_digest=input_digest,
            research_run_id=research_run_id,
            enforce_specialist_byte_limit=False,
        )
        try:
            output = self._assemble_memo_writer_v3_output(
                provider_output, payload
            )
            self._validate_node_output(
                "memo_writer",
                output,
                payload,
                output_contract_ref=admission.output_contract_ref,
            )
        except S3ScopedIdentityContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "memo_writer",
                exc.failure_code,
                scoped_identity_contract=exc.telemetry,
            )
        except S3MemoWriterContractError as exc:
            state["failed"] = True
            self._stop(
                state,
                "memo_writer",
                exc.failure_code,
                memo_writer_contract=exc.telemetry,
            )
        except ValueError as exc:
            state["failed"] = True
            error = S3MemoWriterContractError(
                failure_family="assembly",
                failure_subtype="canonical_validation_failed",
                field_id="assembled_output",
                failing_item_count=1,
            )
            self._stop(
                state,
                "memo_writer",
                error.failure_code,
                memo_writer_contract=error.telemetry,
            )
            raise AssertionError("unreachable") from exc
        return output, [receipt], model_view_binding, [capture]

    def _execute_segmented_specialist(
        self,
        *,
        node_id: str,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        state: dict[str, Any],
        input_digest: str,
        research_run_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        if admission.output_contract_ref not in {
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        }:
            state["failed"] = True
            self._stop(
                state,
                node_id,
                "s3_bounded_segmented_specialist_output_v3_required",
            )
        cell_input = payload.get("cell_input")
        if not isinstance(cell_input, Mapping):
            state["failed"] = True
            self._stop(
                state, node_id, "s3_bounded_node_specialist_input_missing"
            )
        cell_id = str(cell_input.get("program_cell_id") or "")
        research_profile = research_profile_for_ref(admission.research_profile_ref)
        transport_contract = specialist_transport_contract(
            admission.transport_ref
        )
        validated_segments: dict[str, dict[str, Any]] = {}
        receipts: list[dict[str, Any]] = []
        captures: list[dict[str, Any]] = []
        local_fact_receipts: list[dict[str, Any]] = []
        model_view_binding: dict[str, str] = {}
        for segment_id in S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS:
            local_fact_interaction = (
                transport_contract.local_deterministic_fact_interaction
                and segment_id == "facts_explanation_and_terminal"
            )
            if local_fact_interaction:
                local_model_view = {
                    "contract_ref": (
                        S3_LOCAL_DETERMINISTIC_FACT_INTERACTION_CONTRACT_REF
                    ),
                    "program_cell_id": cell_id,
                    "cell_input_digest": canonical_digest(cell_input),
                    "provider_visible": False,
                }
                segment_model_view_binding = {
                    "model_view_contract_ref": (
                        S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF
                    ),
                    "model_view_digest": canonical_digest(
                        local_model_view
                    ),
                }
            else:
                try:
                    system, request, segment_model_view_binding = (
                        self._specialist_segment_request(
                        node_id=node_id,
                        segment_id=segment_id,
                        payload=payload,
                        validated_segments=validated_segments,
                        transport_ref=admission.transport_ref,
                        research_profile=research_profile,
                        claim_fact_link_policy_ref=(
                            admission.claim_fact_link_policy_ref
                        ),
                        task_claim_link_policy_ref=(
                            admission.task_claim_link_policy_ref
                        ),
                        wwc_judgment_atom_policy_ref=(
                            admission.wwc_judgment_atom_policy_ref
                        ),
                        judgment_atom_compiled_contract_ref=(
                            admission.judgment_atom_compiled_contract_ref
                        ),
                        runtime_contract_family_binding_ref=(
                            admission.runtime_contract_family_binding_ref
                        ),
                        runtime_contract_family_source_digest=(
                            admission.runtime_contract_family_source_digest
                        ),
                        case_numeric_authority_policy_ref=(
                            admission.case_numeric_authority_policy_ref
                        ),
                        as_of=str(admission.as_of or ""),
                        )
                    )
                except FactCandidatePoolPlannerError as exc:
                    state["failed"] = True
                    self._stop(
                        state,
                        node_id,
                        exc.failure_code,
                        fact_candidate_pool=exc.telemetry,
                    )
            model_view_binding.update(segment_model_view_binding)
            strict_truth_kernel = (
                admission.strict_truth_kernel_policy_ref
                == S4_STRICT_TRUTH_KERNEL_POLICY_REF
                and segment_id
                == "facts_explanation_and_terminal"
            )
            if local_fact_interaction:
                try:
                    output, local_receipt = (
                        DeterministicJudgmentAtomCompiledContract(
                            cell_input=cell_input,
                            validated_segments=validated_segments,
                            as_of=str(admission.as_of or ""),
                            contract_ref=str(
                                admission.judgment_atom_compiled_contract_ref
                            ),
                            runtime_contract_family_binding_ref=(
                                admission.runtime_contract_family_binding_ref
                            ),
                            runtime_contract_family_source_digest=(
                                admission.runtime_contract_family_source_digest
                            ),
                            research_profile_ref=(
                                research_profile.profile_ref
                            ),
                        ).local_fact_interaction()
                    )
                except FactCandidatePoolPlannerError as exc:
                    state["failed"] = True
                    self._stop(
                        state,
                        node_id,
                        exc.failure_code,
                        fact_candidate_pool=exc.telemetry,
                    )
                local_fact_receipts.append(local_receipt)
                state["local_fact_receipts"].append(local_receipt)
                model_view_binding.update(
                    {
                        "local_fact_interaction_contract_ref": (
                            S3_LOCAL_DETERMINISTIC_FACT_INTERACTION_CONTRACT_REF
                        ),
                        "local_fact_receipt_digest": str(
                            local_receipt["receipt_digest"]
                        ),
                    }
                )
                provider_output_utf8_bytes = 0
            elif strict_truth_kernel:
                truth_policy = StrictTruthKernelPolicy.from_cell_input(
                    cell_input
                )
                system = (
                    "Return only the schema-bound financial judgment atoms. "
                    "Select exact supplied aliases and closed enums. Do not "
                    "return prose, material numbers, periods, entity names, "
                    "canonical IDs, lineage, markdown, or extra fields. "
                    "The local runtime owns canonical rendering."
                )
                request = {
                    "node_id": node_id,
                    "segment_id": segment_id,
                    "analysis_input": request.get("analysis_input"),
                    "truth_kernel_contract": (
                        truth_policy.prompt_contract()
                    ),
                    "required_output_schema": (
                        truth_policy.server_json_schema()
                    ),
                    "additional_properties_allowed": False,
                }
                output, receipt, capture = (
                    self._call_strict_truth_kernel(
                        state=state,
                        logical_node_id=node_id,
                        receipt_stage=f"{node_id}:{segment_id}",
                        system=system,
                        request=request,
                        max_tokens=(
                            research_profile.segment_token_budgets[
                                segment_id
                            ]
                        ),
                        admission=admission,
                        input_digest=input_digest,
                        research_run_id=research_run_id,
                        policy=truth_policy,
                    )
                )
                model_view_binding.update(
                    {
                        "strict_truth_kernel_policy_ref": (
                            S4_STRICT_TRUTH_KERNEL_POLICY_REF
                        ),
                        "provider_capability_ref": (
                            S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF
                        ),
                        "non_authoritative_narrative_shell_ref": (
                            S4_NON_AUTHORITATIVE_NARRATIVE_SHELL_REF
                        ),
                    }
                )
                provider_output_utf8_bytes = len(
                    str(capture["assistant_output_text"]).encode("utf-8")
                )
            else:
                output, receipt, capture = self._call_json_object(
                    state=state,
                    logical_node_id=node_id,
                    receipt_stage=f"{node_id}:{segment_id}",
                    system=system,
                    request=request,
                    max_tokens=(
                        S3_PRODUCTION_MODEL_SEGMENT_OUTPUT_TOKEN_BUDGETS[
                            segment_id
                        ]
                        if transport_contract.local_deterministic_fact_interaction
                        else research_profile.segment_token_budgets[segment_id]
                    ),
                    admission=admission,
                    input_digest=input_digest,
                    research_run_id=research_run_id,
                    enforce_specialist_byte_limit=True,
                )
                provider_output_utf8_bytes = len(
                    str(capture["assistant_output_text"]).encode("utf-8")
                )
            if not local_fact_interaction:
                receipts.append(receipt)
                captures.append(capture)
            try:
                compiled_atom_contract = (
                    admission.judgment_atom_compiled_contract_ref
                    in DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS
                )
                if compiled_atom_contract and not local_fact_interaction:
                    output = DeterministicJudgmentAtomCompiledContract(
                        cell_input=cell_input,
                        validated_segments=validated_segments,
                        as_of=str(admission.as_of or ""),
                        contract_ref=str(
                            admission.judgment_atom_compiled_contract_ref
                        ),
                        runtime_contract_family_binding_ref=(
                            admission.runtime_contract_family_binding_ref
                        ),
                        runtime_contract_family_source_digest=(
                            admission.runtime_contract_family_source_digest
                        ),
                        research_profile_ref=(
                            research_profile.profile_ref
                        ),
                    ).assemble(
                        segment_id,
                        output,
                        provider_output_utf8_bytes=(
                            provider_output_utf8_bytes
                        ),
                    )
                if (
                    admission.case_numeric_authority_policy_ref
                    in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
                    and segment_id
                    == "facts_explanation_and_terminal"
                    and not strict_truth_kernel
                    and not compiled_atom_contract
                ):
                    output = self._expand_specialist_numeric_facts(
                        output=output,
                        cell_input=cell_input,
                        policy_ref=(
                            admission
                            .case_numeric_authority_policy_ref
                        ),
                    )
                if (
                    admission.claim_fact_link_policy_ref is not None
                    and segment_id == "owner_grade_claim_cards"
                ):
                    output = self._expand_specialist_claim_fact_links(
                        output=output,
                        cell_input=cell_input,
                        validated_segments=validated_segments,
                        policy_ref=admission.claim_fact_link_policy_ref,
                    )
                if (
                    admission.wwc_judgment_atom_policy_ref is not None
                    and segment_id
                    == "actionable_what_would_change_tasks"
                    and not compiled_atom_contract
                ):
                    output = self._assemble_specialist_WWC_judgment_atoms(
                        output=output,
                        provider_output_utf8_bytes=len(
                            str(capture["assistant_output_text"]).encode(
                                "utf-8"
                            )
                        ),
                        cell_input=cell_input,
                        validated_segments=validated_segments,
                        policy_ref=(
                            admission.wwc_judgment_atom_policy_ref
                        ),
                        as_of=str(admission.as_of or ""),
                    )
                elif (
                    admission.task_claim_link_policy_ref is not None
                    and segment_id
                    == "actionable_what_would_change_tasks"
                    and not compiled_atom_contract
                ):
                    output = self._expand_specialist_task_claim_links(
                        output=output,
                        cell_input=cell_input,
                        validated_segments=validated_segments,
                        policy_ref=admission.task_claim_link_policy_ref,
                    )
                if (
                    transport_contract.local_scope_assembly
                    and segment_id == "owner_grade_claim_cards"
                ):
                    output = self._assemble_specialist_claim_scopes_v6(
                        output=output,
                        cell_input=cell_input,
                        validated_segments=validated_segments,
                    )
                self._validate_specialist_segment(
                    segment_id=segment_id,
                    output=output,
                    cell_input=cell_input,
                    validated_segments=validated_segments,
                    transport_ref=admission.transport_ref,
                    research_profile=research_profile,
                    judgment_atom_compiled_contract_ref=(
                        admission.judgment_atom_compiled_contract_ref
                    ),
                    runtime_contract_family_binding_ref=(
                        admission.runtime_contract_family_binding_ref
                    ),
                    runtime_contract_family_source_digest=(
                        admission.runtime_contract_family_source_digest
                    ),
                    as_of=str(admission.as_of or ""),
                )
            except S3SegmentedSpecialistShapeError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_shape_invalid:"
                        f"{cell_id}:{segment_id}"
                    ),
                    segmented_specialist_shape=exc.telemetry,
                )
            except S3SegmentedSpecialistTextError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_text=exc.telemetry,
                )
            except S3SegmentedSpecialistAuthorityError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_authority=exc.telemetry,
                )
            except S3SegmentedSpecialistFactAuthorityError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_fact_authority=exc.telemetry,
                )
            except S3SegmentedSpecialistClaimFactLinkError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_claim_fact_link=exc.telemetry,
                )
            except S3SegmentedSpecialistTaskClaimLinkError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_task_claim_link=exc.telemetry,
                )
            except S3SegmentedSpecialistWWCJudgmentAtomError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_WWC_judgment_atom=exc.telemetry,
                )
            except S3SegmentedSpecialistWhatWouldChangeAuthorityError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_what_would_change_authority=(
                        exc.telemetry
                    ),
                )
            except S3SegmentedSpecialistEpistemicStatusError as exc:
                state["failed"] = True
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{exc.failure_code}"
                    ),
                    segmented_specialist_epistemic_status=exc.telemetry,
                )
            except ValueError as exc:
                state["failed"] = True
                detail = str(exc).lower()
                if re.fullmatch(r"[a-z0-9_:.-]{1,140}", detail) is None:
                    detail = "validator_failure"
                self._stop(
                    state,
                    node_id,
                    (
                        "s3_bounded_segmented_specialist_contract_invalid:"
                        f"{cell_id}:{segment_id}:{detail}"
                    ),
                )
            validated_segments[segment_id] = output

        first = validated_segments["facts_explanation_and_terminal"]
        claims = validated_segments["owner_grade_claim_cards"]
        tasks = validated_segments["actionable_what_would_change_tasks"]
        assembled = {
            "program_cell_id": cell_id,
            "fact_layer": list(first["fact_layer"]),
            "explanation_layer": list(first["explanation_layer"]),
            "judgment_layer": list(claims["judgment_layer"]),
            "remaining_gaps": list(first["remaining_gaps"]),
            "what_would_change": list(tasks["what_would_change"]),
            "terminal_class": first["terminal_class"],
        }
        try:
            capacity = specialist_local_assembly_capacity(
                transport_ref=admission.transport_ref,
                research_profile=research_profile,
            )
            observed_segment_bytes = [
                len(
                    json.dumps(
                        dict(validated_segments[segment_id]),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                for segment_id in S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS
            ]
            observed_whole_bytes = len(
                json.dumps(
                    assembled,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            assert_specialist_validated_segment_union_capacity(
                capacity=capacity,
                observed_validated_segment_utf8_bytes=observed_segment_bytes,
                observed_whole_union_utf8_bytes=observed_whole_bytes,
            )
            S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
                assembled,
                cell_input,
                output_contract_ref=admission.output_contract_ref,
                max_serialized_utf8_bytes=(
                    capacity.whole_union_limit_utf8_bytes
                ),
            )
        except S3SpecialistLocalAssemblyCapacityError as exc:
            state["failed"] = True
            self._stop(
                state,
                node_id,
                (
                    "s3_bounded_segmented_specialist_assembly_invalid:"
                    f"{cell_id}:{exc.failure_code}"
                ),
                specialist_local_assembly_capacity=exc.telemetry,
            )
        except ValueError as exc:
            state["failed"] = True
            detail = str(exc).lower()
            if re.fullmatch(r"[a-z0-9_:.-]{1,140}", detail) is None:
                detail = "validator_failure"
            self._stop(
                state,
                node_id,
                (
                    "s3_bounded_segmented_specialist_assembly_invalid:"
                    f"{cell_id}:{detail}"
                ),
            )
        model_view_binding.update(
            {
                "specialist_transport_ref": (
                    admission.transport_ref
                ),
                "specialist_segment_count": "3",
            }
        )
        return (
            assembled,
            receipts,
            model_view_binding,
            captures,
            local_fact_receipts,
        )

    @classmethod
    def _specialist_segment_request(
        cls,
        *,
        node_id: str,
        segment_id: str,
        payload: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        transport_ref: str = S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
        research_profile: BoundedResearchProfile | None = None,
        claim_fact_link_policy_ref: str | None = None,
        task_claim_link_policy_ref: str | None = None,
        wwc_judgment_atom_policy_ref: str | None = None,
        judgment_atom_compiled_contract_ref: str | None = None,
        runtime_contract_family_binding_ref: str | None = None,
        runtime_contract_family_source_digest: str | None = None,
        case_numeric_authority_policy_ref: str | None = None,
        as_of: str = "",
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        if segment_id not in S3_OWNER_GRADE_SPECIALIST_SEGMENT_IDS:
            raise ValueError("s3_segmented_specialist_segment_unknown")
        transport_contract = specialist_transport_contract(transport_ref)
        profile = research_profile or S3_NVDA_THREE_CELL_RESEARCH_PROFILE
        field_local_text_contract = transport_contract.field_local_text
        closed_context_authority_contract = (
            transport_contract.closed_context_authority
        )
        epistemic_status_state_contract = (
            transport_contract.epistemic_status_state
        )
        local_scope_assembly_contract = (
            transport_contract.local_scope_assembly
        )
        field_local_fact_support_contract = (
            transport_contract.field_local_fact_support_authority
        )
        field_local_what_would_change_authority_contract = (
            transport_contract.field_local_what_would_change_authority
        )
        claim_fact_link_policy = None
        if (
            claim_fact_link_policy_ref is not None
            and segment_id == "owner_grade_claim_cards"
        ):
            claim_fact_link_policy = cls._claim_fact_link_policy(
                cell_input=payload["cell_input"],
                validated_segments=validated_segments,
                policy_ref=claim_fact_link_policy_ref,
            )
        task_claim_link_policy = None
        if (
            task_claim_link_policy_ref is not None
            and segment_id == "actionable_what_would_change_tasks"
        ):
            task_claim_link_policy = cls._task_claim_link_policy(
                cell_input=payload["cell_input"],
                validated_segments=validated_segments,
                policy_ref=task_claim_link_policy_ref,
            )
        wwc_judgment_atom_policy = None
        if (
            wwc_judgment_atom_policy_ref is not None
            and segment_id == "actionable_what_would_change_tasks"
        ):
            wwc_judgment_atom_policy = cls._wwc_judgment_atom_policy(
                cell_input=payload["cell_input"],
                validated_segments=validated_segments,
                policy_ref=wwc_judgment_atom_policy_ref,
                as_of=as_of,
                omit_incomplete_authority_refs=(
                    judgment_atom_compiled_contract_ref
                    == FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF
                ),
            )
        nonblank_narrative = (
            "non-empty string, maximum "
            f"{profile.maximum_narrative_characters} Unicode characters"
            if field_local_text_contract
            else "string"
        )
        model_view = cls._specialist_model_view(payload)
        if claim_fact_link_policy is not None:
            model_view = (
                claim_fact_link_policy.redact_claim_selection_model_view(
                    model_view
                )
            )
        if wwc_judgment_atom_policy is not None:
            model_view = dict(model_view)
            model_view.pop("authority_refs", None)
        model_view_digest = canonical_digest(model_view)
        analysis_input = {
            "input_contract_ref": payload.get("input_contract_ref"),
            "input_digest": payload.get("input_digest"),
            "model_view_contract_ref": S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
            "model_view_digest": model_view_digest,
            "cell_input": model_view,
            "required_output_layers": list(
                payload.get("required_output_layers") or ()
            ),
        }
        if segment_id == "facts_explanation_and_terminal":
            schema: dict[str, Any] = {
                "program_cell_id": "exact input program_cell_id",
                "fact_layer": [
                    {
                        "fact_id": "unique string",
                        "statement": nonblank_narrative,
                        "support_type": "Evidence|Numeric",
                        "support_refs": [
                            (
                                "exact value copied from "
                                "fact_support_authority_contract."
                                "allowed_refs_by_support_type[support_type]"
                                if field_local_fact_support_contract
                                else "exact authorized ref"
                            )
                        ],
                        "boundary": nonblank_narrative,
                    }
                ],
                "explanation_layer": [nonblank_narrative],
                "remaining_gaps": [nonblank_narrative],
                "terminal_class": "non-empty string",
            }
            constraints = {
                "fact_layer_cardinality": "0..3",
                "explanation_layer_cardinality": "1..3",
                "remaining_gaps_cardinality": "1..4",
                "maximum_narrative_item_unicode_characters": (
                    profile.maximum_narrative_characters
                ),
                "maximum_serialized_utf8_bytes": (
                    profile.specialist_segment_max_utf8_bytes
                ),
            }
            prior: dict[str, Any] = {}
        elif segment_id == "owner_grade_claim_cards":
            context_authority, _ = cls._segment_context_authority_sets(
                payload["cell_input"]
            )
            allowed_context_refs = sorted(context_authority)
            schema = {
                "program_cell_id": "exact input program_cell_id",
                "judgment_layer": [
                    {
                        "claim_id": "unique string",
                        "statement": nonblank_narrative,
                        "epistemic_status": (
                            "fact_supported|bounded_inference|hypothesis|cannot_infer"
                        ),
                        (
                            "support_fact_aliases"
                            if claim_fact_link_policy is not None
                            else "support_fact_ids"
                        ): [
                            (
                                "exact request-local fact_alias from "
                                "claim_fact_link_contract.allowed_facts"
                                if claim_fact_link_policy is not None
                                else "exact validated fact_id"
                            )
                        ],
                        "context_refs": [
                            (
                                "exact value copied from field_authority_contract."
                                "allowed_context_refs only; use [] when no context "
                                "is used"
                                if closed_context_authority_contract
                                else "exact Candidate or Graph context ref"
                            )
                        ],
                        "scope": (
                            {
                                "metric_or_mechanism": nonblank_narrative,
                            }
                            if local_scope_assembly_contract
                            else {
                                "entity_ref": "string",
                                "business_scope_kind": (
                                    "company_total|segment|product|value_chain|unknown"
                                ),
                                "business_scope_ref": "string",
                                "period": "string",
                                "metric_or_mechanism": nonblank_narrative,
                                "attribution_level": (
                                    "company_total|segment|product|cross_chain|none"
                                ),
                            }
                        ),
                        "qualification": (
                            "string, maximum 320 Unicode characters; non-empty "
                            "for hypothesis"
                            if field_local_text_contract
                            else "string; required for hypothesis"
                        ),
                        "cannot_support": [
                            (
                                "non-empty boundary, maximum 320 Unicode characters, "
                                "required for cannot_infer"
                                if field_local_text_contract
                                else "non-empty boundary for cannot_infer"
                            )
                        ],
                    }
                ],
            }
            constraints = {
                "judgment_layer_cardinality": "1..2",
                "maximum_narrative_item_unicode_characters": (
                    profile.maximum_narrative_characters
                ),
                "maximum_serialized_utf8_bytes": (
                    profile.specialist_segment_max_utf8_bytes
                ),
            }
            first_segment = dict(
                validated_segments["facts_explanation_and_terminal"]
            )
            prior = {
                "facts_explanation_and_terminal": (
                    claim_fact_link_policy.provider_prior_segment(
                        first_segment
                    )
                    if claim_fact_link_policy is not None
                    else first_segment
                )
            }
        else:
            schema = (
                wwc_judgment_atom_policy.required_output_schema()
                if wwc_judgment_atom_policy is not None
                else {
                "program_cell_id": "exact input program_cell_id",
                "what_would_change": [
                    {
                        "task_id": "unique string",
                        (
                            "claim_alias"
                            if task_claim_link_policy is not None
                            else "claim_id"
                        ): (
                            "exact request-local claim_alias from "
                            "task_claim_link_contract.allowed_claims"
                            if task_claim_link_policy is not None
                            else "exact validated claim_id"
                        ),
                        "source_target": {
                            "source_type": nonblank_narrative,
                            "entity_or_owner": nonblank_narrative,
                            "document_event_or_dataset": nonblank_narrative,
                        },
                        "metric_or_observation": nonblank_narrative,
                        "decision_rule": {
                            "rule_type": nonblank_narrative,
                            "comparator_or_condition": nonblank_narrative,
                            "threshold_or_observation": nonblank_narrative,
                        },
                        "time_window": {
                            "as_of": nonblank_narrative,
                            "start_or_trigger": nonblank_narrative,
                            "deadline_or_review_date": nonblank_narrative,
                        },
                        "expected_claim_transition": nonblank_narrative,
                        "fallback_stop_condition": nonblank_narrative,
                        "authority_refs": [
                            (
                                "exact value copied from "
                                "what_would_change_authority_contract."
                                "allowed_refs_by_authority_class"
                                if field_local_what_would_change_authority_contract
                                else "exact routing ref"
                            )
                        ],
                    }
                ],
                }
            )
            constraints = {
                (
                    "what_would_change_judgment_atom_cardinality"
                    if wwc_judgment_atom_policy is not None
                    else "what_would_change_cardinality"
                ): "1..3",
                "maximum_narrative_item_unicode_characters": (
                    (
                        wwc_judgment_atom_policy
                        .provider_atom_max_unicode_characters
                    )
                    if wwc_judgment_atom_policy is not None
                    else profile.maximum_narrative_characters
                ),
                "maximum_serialized_utf8_bytes": (
                    (
                        wwc_judgment_atom_policy
                        .provider_output_max_utf8_bytes
                    )
                    if wwc_judgment_atom_policy is not None
                    else profile.specialist_segment_max_utf8_bytes
                ),
            }
            prior = {
                key: dict(validated_segments[key])
                for key in (
                    "facts_explanation_and_terminal",
                    "owner_grade_claim_cards",
                )
            }
            if wwc_judgment_atom_policy is not None:
                prior["owner_grade_claim_cards"] = (
                    wwc_judgment_atom_policy
                    .provider_prior_claim_segment(
                        validated_segments["owner_grade_claim_cards"]
                    )
                )
            elif task_claim_link_policy is not None:
                prior["owner_grade_claim_cards"] = (
                    task_claim_link_policy.provider_prior_claim_segment(
                        validated_segments["owner_grade_claim_cards"]
                    )
                )
        system = (
            "You are the exact decision-cell financial research specialist. "
            "Return exactly one native JSON object containing only the required "
            "top-level output members for this segment, with no markdown or duplicate "
            "keys. Treat output_constraints as rules, never as output members. Use "
            "only analysis_input and validated_prior_segments. Do not call tools or "
            "sources, add citations, promote Candidate or Graph context to fact "
            "authority, invent numeric precision, or expose private reasoning."
        )
        if field_local_text_contract:
            system += (
                " Before responding, check every narrative field item by item: each "
                "must be a non-blank string no longer than "
                f"{profile.maximum_narrative_characters} Unicode characters, "
                "except qualification may be empty when its epistemic status does not "
                "require it. Prefer a concise typed boundary over repetition. Never "
                "truncate, coerce, drop, join, or split content to satisfy a limit."
            )
        request = {
            "node_id": node_id,
            "segment_id": segment_id,
            "analysis_input": analysis_input,
            "validated_prior_segments": prior,
            "required_output_schema": schema,
            "required_top_level_keys": list(schema),
            "output_constraints": constraints,
            "additional_properties_allowed": False,
        }
        if judgment_atom_compiled_contract_ref is not None:
            if (
                judgment_atom_compiled_contract_ref
                not in DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS
            ):
                raise ValueError(
                    "s4_compiled_judgment_atom_contract_unsupported"
                )
            compiled_policy = DeterministicJudgmentAtomCompiledContract(
                cell_input=payload["cell_input"],
                validated_segments=validated_segments,
                as_of=as_of,
                contract_ref=judgment_atom_compiled_contract_ref,
                research_profile_ref=profile.profile_ref,
                runtime_contract_family_binding_ref=(
                    runtime_contract_family_binding_ref
                ),
                runtime_contract_family_source_digest=(
                    runtime_contract_family_source_digest
                ),
            )
            compiled_surface = compiled_policy.compiled_surface(segment_id)
            identity_projection = payload.get(
                "case_delivery_identity_projection"
            )
            if not isinstance(identity_projection, Mapping):
                raise ValueError(
                    "s4_case_delivery_identity_projection_missing"
                )
            request.update(
                {
                    "required_output_schema": (
                        compiled_surface["wire_schema"]
                    ),
                    "required_top_level_keys": list(
                        compiled_surface["wire_schema"]
                    ),
                    "compiled_judgment_atom_contract": (
                        compiled_surface["model_visible_contract"]
                    ),
                    "case_numeric_authority_contract": (
                        compiled_policy.numeric_policy.prompt_contract()
                    ),
                    "case_delivery_identity_projection": deepcopy(
                        identity_projection
                    ),
                    "output_constraints": {
                        "provider_candidate_maximum": (
                            compiled_policy.provider_candidate_maximum
                        ),
                        "maximum_serialized_utf8_bytes": (
                            compiled_policy.provider_output_max_utf8_bytes
                        ),
                        "arbitrary_narrative_allowed": False,
                        "local_validity_aware_selection": True,
                    },
                }
            )
            system = compiled_policy.provider_system_instruction(segment_id)
            return system, request, {
                "model_view_contract_ref": (
                    S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF
                ),
                "model_view_digest": model_view_digest,
                "judgment_atom_compiled_contract_ref": (
                    judgment_atom_compiled_contract_ref
                ),
                "judgment_atom_family_id": (
                    compiled_surface["family_id"]
                ),
                "judgment_atom_contract_digest": (
                    compiled_surface["model_visible_contract"][
                        "contract_digest"
                    ]
                ),
                **(
                    {
                        "runtime_contract_family_binding_ref": str(
                            compiled_surface[
                                "runtime_contract_family_binding"
                            ]["binding_ref"]
                        ),
                        "runtime_contract_family_source_digest": str(
                            compiled_surface[
                                "runtime_contract_family_binding"
                            ]["source_digest"]
                        ),
                        "runtime_contract_family_version": str(
                            compiled_surface[
                                "runtime_contract_family_binding"
                            ]["contract_version"]
                        ),
                    }
                    if "runtime_contract_family_binding" in compiled_surface
                    else {}
                ),
                **(
                    {
                        "fact_candidate_pool_contract_ref": str(
                            compiled_surface[
                                "fact_candidate_pool_receipt"
                            ]["contract_ref"]
                        ),
                        "fact_candidate_profile_digest": str(
                            compiled_surface[
                                "fact_candidate_pool_receipt"
                            ]["profile_digest"]
                        ),
                        "fact_candidate_pool_digest": str(
                            compiled_surface[
                                "fact_candidate_pool_receipt"
                            ]["candidate_pool_digest"]
                        ),
                    }
                    if "fact_candidate_pool_receipt"
                    in compiled_surface
                    else {}
                ),
            }
        if (
            field_local_fact_support_contract
            and segment_id == "facts_explanation_and_terminal"
        ):
            request["fact_support_authority_contract"] = (
                FactSupportAuthorityPolicy.from_cell_input(
                    payload["cell_input"]
                ).prompt_contract()
            )
            system += (
                " For each fact_layer.support_refs item, first select Evidence "
                "or Numeric as support_type, then copy only exact values from "
                "fact_support_authority_contract.allowed_refs_by_support_type"
                "[support_type]. Candidate and Graph values remain context only. "
                "Use a non-empty subset and never normalize, trim, remap, drop, "
                "or invent a ref."
            )
        if (
            case_numeric_authority_policy_ref
            in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
        ):
            numeric_policy = CaseNumericAuthorityPolicy.from_cell_input(
                payload["cell_input"]
            )
            request["case_numeric_authority_contract"] = (
                numeric_policy.prompt_contract()
            )
            identity_projection = payload.get(
                "case_delivery_identity_projection"
            )
            if not isinstance(identity_projection, Mapping):
                raise ValueError(
                    "s4_case_delivery_identity_projection_missing"
                )
            identity_policy = CaseDeliveryIdentityPolicy.from_projection(
                identity_projection
            )
            request["case_delivery_identity_projection"] = deepcopy(
                identity_projection
            )
            system += (
                identity_policy.provider_identity_boundary_instruction()
            )
            if segment_id == "facts_explanation_and_terminal":
                fact_contract = request.get(
                    "fact_support_authority_contract"
                )
                if isinstance(fact_contract, dict):
                    fact_contract["allowed_refs_by_support_type"][
                        "Numeric"
                    ] = [
                        row.alias for row in numeric_policy.rows
                    ]
                system += (
                    " For Numeric facts, support_refs must contain only exact "
                    "request-local N-prefixed aliases from "
                    "case_numeric_authority_contract.provider_selection_values. "
                    "The runtime expands aliases and renders the exact numeric "
                    "clause locally. Evidence facts continue to use exact "
                    "Evidence refs. "
                ) + numeric_policy.provider_narrative_instruction()
            else:
                system += " " + (
                    numeric_policy.provider_narrative_instruction()
                )
        if (
            field_local_what_would_change_authority_contract
            and segment_id == "actionable_what_would_change_tasks"
            and wwc_judgment_atom_policy is None
        ):
            request["what_would_change_authority_contract"] = (
                WhatWouldChangeAuthorityPolicy.from_cell_input(
                    payload["cell_input"]
                ).prompt_contract()
            )
            system += (
                " For each what_would_change.authority_refs array, copy a "
                "non-empty exact subset from the union of "
                "what_would_change_authority_contract."
                "allowed_refs_by_authority_class. Evidence, Numeric, Candidate, "
                "and Graph may be combined within the current Cell. Never select "
                "a cross-Cell value or normalize, trim, case-fold, fuzzy-match, "
                "remap, drop, relink, or invent a ref."
            )
        if closed_context_authority_contract and segment_id == "owner_grade_claim_cards":
            request["field_authority_contract"] = {
                "field_id": "judgment_layer.context_refs",
                "allowed_context_refs": allowed_context_refs,
                "selection_rule": (
                    "Each item must exactly equal one listed allowed_context_refs value; "
                    "the output array must be a subset of that closed list."
                ),
                "empty_array_rule": "Use [] when the claim uses no context reference.",
                "forbidden_authority_classes": [
                    "Evidence",
                    "Numeric",
                    "fact_id",
                    "routing_ref",
                    "free_text_or_derived_ref",
                ],
            }
            system += (
                " For judgment_layer.context_refs, copy only exact items from "
                "field_authority_contract.allowed_context_refs and use [] when no "
                "context is used. Never place Evidence, Numeric, fact, routing, or "
                "free-text values there. Before responding, verify every item by "
                "exact membership; never normalize, trim, remap, or invent a ref."
            )
        if claim_fact_link_policy is not None:
            request["claim_fact_link_contract"] = (
                claim_fact_link_policy.prompt_contract()
            )
            system += (
                " For judgment_layer support, emit support_fact_aliases and do "
                "not emit support_fact_ids. Select only exact fact_alias values "
                "from claim_fact_link_contract.allowed_facts. The runtime expands "
                "them locally to canonical Fact IDs before scope and epistemic "
                "validation. Evidence, Numeric, Candidate, Graph, object, and "
                "routing refs are never Claim support aliases. Never trim, "
                "normalize, guess a prefix, fuzzy-match, or rewrite an alias."
            )
        if (
            task_claim_link_policy is not None
            and wwc_judgment_atom_policy is None
        ):
            request["task_claim_link_contract"] = (
                task_claim_link_policy.prompt_contract()
            )
            system += (
                " For each what_would_change task, emit claim_alias and do not "
                "emit claim_id. Copy exactly one claim_alias from "
                "task_claim_link_contract.allowed_claims. The runtime expands "
                "the alias locally to the original validated current-Cell "
                "claim_id before existing task validation. Never trim, "
                "case-fold, normalize, guess, fuzzy-match, relink, drop a task, "
                "or rewrite an alias."
            )
        if wwc_judgment_atom_policy is not None:
            request["WWC_judgment_atom_contract"] = (
                wwc_judgment_atom_policy.prompt_contract()
            )
            system += (
                " Emit only what_would_change_judgment_atoms under "
                f"{wwc_judgment_atom_policy.contract_ref}. Select exact "
                "claim and authority aliases from WWC_judgment_atom_contract; "
                "the runtime owns task IDs, canonical Claim and authority refs, "
                "source_target, nested decision_rule and time_window, exact "
                "as_of, ordering, and lineage. Do not emit any locally assembled "
                "field or raw ref. Every atom narrative must be non-blank and at "
                "most 160 Unicode characters; the complete Provider JSON must "
                "be at most 4800 UTF-8 bytes. Never normalize, guess, fuzzy-match, "
                "remap, or silently drop an atom."
            )
            if (
                wwc_judgment_atom_policy.contract_ref
                == S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
            ):
                system += (
                    " For time_window, select only the closed start/review "
                    "codes and exact date aliases in the bound contract. "
                    "Use NONE when the selected code is not bound_date. "
                    "Never write a calendar date, reporting period, duration, "
                    "or free-text time expression; the runtime renders the "
                    "canonical time_window locally."
                )
        if epistemic_status_state_contract and segment_id == "owner_grade_claim_cards":
            support_field_id = (
                "support_fact_aliases"
                if claim_fact_link_policy is not None
                else "support_fact_ids"
            )
            request["epistemic_status_contract"] = (
                EpistemicStatePolicy().prompt_contract(
                    support_field_id=support_field_id
                )
            )
            system += (
                " For each judgment_layer claim, apply exactly one row from "
                "epistemic_status_contract.status_rules and perform its cross-field "
                "check before responding. In particular, cannot_infer requires "
                f"{support_field_id}=[] and one or more non-blank cannot_support "
                "boundaries. Never change a status, delete support, or invent a "
                "boundary merely to make the state valid."
            )
        if local_scope_assembly_contract and segment_id == "owner_grade_claim_cards":
            support_field_id = (
                "support_fact_aliases"
                if claim_fact_link_policy is not None
                else "support_fact_ids"
            )
            request["local_scope_assembly_contract"] = (
                ClaimScopeResolver().prompt_contract(
                    support_field_id=support_field_id
                )
            )
            system += (
                " For judgment_layer.scope, emit only metric_or_mechanism. Do not "
                "emit entity_ref, business_scope_kind, business_scope_ref, period, "
                "or attribution_level; the runtime derives those exact authority "
                f"tokens locally from validated {support_field_id}. Never copy, "
                "normalize, abbreviate, or paraphrase those deterministic tokens."
            )
        binding = {
            "model_view_contract_ref": S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
            "model_view_digest": model_view_digest,
        }
        if claim_fact_link_policy_ref is not None:
            binding["claim_fact_link_policy_ref"] = (
                claim_fact_link_policy_ref
            )
        if task_claim_link_policy_ref is not None:
            binding["task_claim_link_policy_ref"] = (
                task_claim_link_policy_ref
            )
        return system, request, binding

    @classmethod
    def _expand_specialist_numeric_facts(
        cls,
        *,
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
        policy_ref: str,
    ) -> dict[str, Any]:
        if policy_ref not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS:
            raise ValueError(
                "s4_case_numeric_authority_policy_unsupported"
            )
        policy = CaseNumericAuthorityPolicy.from_cell_input(cell_input)
        expanded, violation = policy.expand_provider_fact_output(output)
        if violation is not None:
            raise ValueError(
                f"s4_case_numeric_fact_atom_{violation.subtype}"
            )
        if expanded is None:
            raise ValueError(
                "s4_case_numeric_fact_atom_local_expansion_failed"
            )
        return expanded

    @classmethod
    def _claim_fact_link_policy(
        cls,
        *,
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        policy_ref: str,
    ) -> ClaimFactLinkPolicy:
        if policy_ref != S3_CLAIM_FACT_LINK_POLICY_REF:
            raise ValueError("s3_claim_fact_link_policy_unsupported")
        first = validated_segments.get("facts_explanation_and_terminal")
        if not isinstance(first, Mapping):
            raise ValueError("s3_segmented_specialist_prior_segment_missing")
        surface = S3ThreeCellBoundedAgentExecutor._owner_grade_authority_surface(
            cell_input
        )
        additional_forbidden_refs = [
            *surface["accepted_evidence_refs"],
            *surface["numeric_fact_scope_and_cannot_support"],
            *surface["candidate_refs_not_evidence"],
            *surface["graph_context_refs_not_evidence"],
        ]
        return ClaimFactLinkPolicy.from_validated_facts(
            program_cell_id=str(cell_input.get("program_cell_id") or ""),
            facts=list(first.get("fact_layer") or ()),
            numeric_scopes=surface[
                "numeric_fact_scope_and_cannot_support"
            ],
            additional_forbidden_refs=additional_forbidden_refs,
        )

    @classmethod
    def _expand_specialist_claim_fact_links(
        cls,
        *,
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        policy_ref: str,
    ) -> dict[str, Any]:
        policy = cls._claim_fact_link_policy(
            cell_input=cell_input,
            validated_segments=validated_segments,
            policy_ref=policy_ref,
        )
        expanded, violation = policy.expand_claim_output(output)
        if violation is not None:
            raise S3SegmentedSpecialistClaimFactLinkError(
                subtype=violation.subtype,
                failing_item_count=violation.failing_item_count,
            )
        if expanded is None:
            raise S3SegmentedSpecialistClaimFactLinkError(
                subtype="local_expansion_mismatch",
                failing_item_count=1,
            )
        return expanded

    @classmethod
    def _task_claim_link_policy(
        cls,
        *,
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        policy_ref: str,
    ) -> TaskClaimLinkPolicy:
        if policy_ref != S3_TASK_CLAIM_LINK_POLICY_REF:
            raise ValueError("s3_task_claim_link_policy_unsupported")
        claims = validated_segments.get("owner_grade_claim_cards")
        if not isinstance(claims, Mapping):
            raise ValueError("s3_segmented_specialist_prior_segment_missing")
        return TaskClaimLinkPolicy.from_validated_claims(
            program_cell_id=str(cell_input.get("program_cell_id") or ""),
            claims=list(claims.get("judgment_layer") or ()),
        )

    @classmethod
    def _expand_specialist_task_claim_links(
        cls,
        *,
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        policy_ref: str,
    ) -> dict[str, Any]:
        policy = cls._task_claim_link_policy(
            cell_input=cell_input,
            validated_segments=validated_segments,
            policy_ref=policy_ref,
        )
        expanded, violation = policy.expand_task_output(output)
        if violation is not None:
            raise S3SegmentedSpecialistTaskClaimLinkError(
                subtype=violation.subtype,
                failing_item_count=violation.failing_item_count,
            )
        if expanded is None:
            raise S3SegmentedSpecialistTaskClaimLinkError(
                subtype="task_claim_alias_unknown",
                failing_item_count=1,
            )
        return expanded

    @classmethod
    def _wwc_judgment_atom_policy(
        cls,
        *,
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        policy_ref: str,
        as_of: str,
        omit_incomplete_authority_refs: bool = False,
    ) -> SpecialistWWCJudgmentAtomPolicy:
        if policy_ref not in SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REFS:
            raise ValueError("s3_WWC_judgment_atom_policy_unsupported")
        claims = validated_segments.get("owner_grade_claim_cards")
        if not isinstance(claims, Mapping):
            raise ValueError("s3_segmented_specialist_prior_segment_missing")
        return SpecialistWWCJudgmentAtomPolicy.from_cell_input(
            cell_input=cell_input,
            claims=list(claims.get("judgment_layer") or ()),
            as_of=as_of,
            contract_ref=policy_ref,
            omit_incomplete_authority_refs=(
                omit_incomplete_authority_refs
            ),
        )

    @classmethod
    def _assemble_specialist_WWC_judgment_atoms(
        cls,
        *,
        output: Mapping[str, Any],
        provider_output_utf8_bytes: int,
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        policy_ref: str,
        as_of: str,
    ) -> dict[str, Any]:
        policy = cls._wwc_judgment_atom_policy(
            cell_input=cell_input,
            validated_segments=validated_segments,
            policy_ref=policy_ref,
            as_of=as_of,
        )
        assembled, violation = policy.assemble(
            output,
            provider_output_utf8_bytes=provider_output_utf8_bytes,
        )
        if violation is not None:
            raise S3SegmentedSpecialistWWCJudgmentAtomError(
                subtype=violation.subtype,
                field_id=violation.field_id,
                failing_item_count=violation.failing_item_count,
                validator_contract=policy_ref,
            )
        if assembled is None:
            raise S3SegmentedSpecialistWWCJudgmentAtomError(
                subtype="atom_shape_invalid",
                field_id="what_would_change_judgment_atoms",
                failing_item_count=1,
                validator_contract=policy_ref,
            )
        return assembled

    @classmethod
    def _assemble_specialist_claim_scopes_v6(
        cls,
        *,
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Bind deterministic Claim scope tokens to validated Fact authority."""

        if set(output) != {"program_cell_id", "judgment_layer"}:
            raise ValueError(
                "s3_bounded_specialist_scope_assembly_provider_shape_invalid"
            )
        claims = output.get("judgment_layer")
        first = validated_segments.get("facts_explanation_and_terminal")
        if not isinstance(claims, list) or not isinstance(first, Mapping):
            raise ValueError(
                "s3_bounded_specialist_scope_assembly_provider_shape_invalid"
            )
        facts = {
            str(row["fact_id"]): row
            for row in first.get("fact_layer", ())
            if isinstance(row, Mapping) and row.get("fact_id")
        }
        numeric_scopes = S3ThreeCellBoundedAgentExecutor._owner_grade_authority_surface(cell_input)[
            "numeric_fact_scope_and_cannot_support"
        ]
        return {
            "program_cell_id": output.get("program_cell_id"),
            "judgment_layer": ClaimScopeResolver().assemble(
                claims=claims,
                facts=facts,
                numeric_scopes=numeric_scopes,
            ),
        }

    @classmethod
    def _validate_specialist_segment(
        cls,
        *,
        segment_id: str,
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        transport_ref: str = S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
        research_profile: BoundedResearchProfile | None = None,
        judgment_atom_compiled_contract_ref: str | None = None,
        runtime_contract_family_binding_ref: str | None = None,
        runtime_contract_family_source_digest: str | None = None,
        as_of: str = "",
    ) -> None:
        transport_contract = specialist_transport_contract(transport_ref)
        profile = research_profile or S3_NVDA_THREE_CELL_RESEARCH_PROFILE
        expected_by_segment = {
            "facts_explanation_and_terminal": {
                "program_cell_id",
                "fact_layer",
                "explanation_layer",
                "remaining_gaps",
                "terminal_class",
            },
            "owner_grade_claim_cards": {
                "program_cell_id",
                "judgment_layer",
            },
            "actionable_what_would_change_tasks": {
                "program_cell_id",
                "what_would_change",
            },
        }
        try:
            expected = expected_by_segment[segment_id]
        except KeyError as exc:
            raise ValueError("s3_segmented_specialist_segment_unknown") from exc
        cls._validate_segment_top_level(
            output=output,
            expected_keys=expected,
            expected_cell_id=str(cell_input.get("program_cell_id") or ""),
            segment_id=segment_id,
        )
        serialized_bytes = len(
            json.dumps(
                dict(output),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        capacity = specialist_local_assembly_capacity(
            transport_ref=transport_ref,
            research_profile=profile,
        )
        if serialized_bytes > profile.specialist_segment_max_utf8_bytes:
            if (
                not transport_contract.local_scope_assembly
                or serialized_bytes
                > capacity.post_local_expansion_segment_limit_utf8_bytes
            ):
                raise ValueError("s3_bounded_specialist_output_byte_budget_exceeded")
        if (
            judgment_atom_compiled_contract_ref
            in DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS
        ):
            DeterministicJudgmentAtomCompiledContract(
                cell_input=cell_input,
                validated_segments=validated_segments,
                as_of=as_of,
                contract_ref=str(judgment_atom_compiled_contract_ref),
                research_profile_ref=profile.profile_ref,
                runtime_contract_family_binding_ref=(
                    runtime_contract_family_binding_ref
                ),
                runtime_contract_family_source_digest=(
                    runtime_contract_family_source_digest
                ),
            ).assert_rendered_capacity(
                segment_id,
                output,
                post_local_expansion_limit_utf8_bytes=(
                    capacity.post_local_expansion_segment_limit_utf8_bytes
                ),
            )
            validation_output = deepcopy(dict(output))
            if segment_id == "facts_explanation_and_terminal":
                facts = validation_output.get("fact_layer")
                if isinstance(facts, list):
                    for fact in facts:
                        if not isinstance(fact, dict):
                            continue
                        for key in ("statement", "boundary"):
                            value = fact.get(key)
                            if (
                                isinstance(value, str)
                                and len(value)
                                > profile.maximum_narrative_characters
                            ):
                                fact[key] = (
                                    "locally rendered bound authority text"
                                )
            output = validation_output
        if transport_contract.field_local_text:
            cls._validate_segment_narrative_text(
                segment_id,
                output,
                maximum_characters=profile.maximum_narrative_characters,
            )
        if segment_id == "facts_explanation_and_terminal":
            if transport_contract.field_local_fact_support_authority:
                violation = FactSupportAuthorityPolicy.from_cell_input(
                    cell_input
                ).first_violation(output.get("fact_layer"))
                if violation is not None:
                    raise S3SegmentedSpecialistFactAuthorityError(
                        subtype=violation.subtype,
                        failing_item_count=violation.failing_item_count,
                    )
            cls._validate_facts_explanation_and_terminal_segment(output, cell_input)
            return
        first = validated_segments.get("facts_explanation_and_terminal")
        if not isinstance(first, Mapping):
            raise ValueError("s3_segmented_specialist_prior_segment_missing")
        claim_input = {
            "fact_layer": list(first.get("fact_layer") or ()),
            "judgment_layer": list(output.get("judgment_layer") or ()),
        }
        if segment_id == "owner_grade_claim_cards":
            if transport_contract.closed_context_authority:
                cls._validate_segment_context_authority(output, cell_input)
            if transport_contract.epistemic_status_state:
                cls._validate_segment_epistemic_status_state(output)
            S3ThreeCellBoundedAgentExecutor._validate_owner_grade_claims(
                claim_input, cell_input
            )
            return
        claims = validated_segments.get("owner_grade_claim_cards")
        if not isinstance(claims, Mapping):
            raise ValueError("s3_segmented_specialist_prior_segment_missing")
        claim_input["judgment_layer"] = list(claims.get("judgment_layer") or ())
        claim_by_id = S3ThreeCellBoundedAgentExecutor._validate_owner_grade_claims(
            claim_input, cell_input
        )
        if transport_contract.field_local_what_would_change_authority:
            violation = WhatWouldChangeAuthorityPolicy.from_cell_input(
                cell_input
            ).first_violation(output.get("what_would_change"))
            if violation is not None:
                raise S3SegmentedSpecialistWhatWouldChangeAuthorityError(
                    subtype=violation.subtype,
                    failing_item_count=violation.failing_item_count,
                )
        S3ThreeCellBoundedAgentExecutor._validate_owner_grade_tasks(
            output.get("what_would_change"), cell_input, claim_by_id
        )

    @staticmethod
    def _segment_context_authority_sets(
        cell_input: Mapping[str, Any],
    ) -> tuple[set[str], set[str]]:
        authority = cell_input.get("authority_refs")
        if not isinstance(authority, Mapping):
            authority = {}

        def exact_nonblank_strings(key: str) -> set[str]:
            values = authority.get(key)
            if not isinstance(values, (list, tuple, set, frozenset)):
                return set()
            return {
                value
                for value in values
                if isinstance(value, str) and value.strip()
            }

        context_authority = exact_nonblank_strings("candidate_refs_not_evidence")
        context_authority.update(
            exact_nonblank_strings("graph_context_refs_not_evidence")
        )
        fact_authority = exact_nonblank_strings("accepted_evidence_refs")
        fact_authority.update(exact_nonblank_strings("numeric_refs"))
        return context_authority, fact_authority

    @staticmethod
    def _validate_segment_context_authority(
        output: Mapping[str, Any], cell_input: Mapping[str, Any]
    ) -> None:
        claims = output.get("judgment_layer")
        if not isinstance(claims, list):
            return
        context_values: list[Any] = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                return
            refs = claim.get("context_refs")
            if not isinstance(refs, list):
                return
            context_values.extend(refs)

        invalid_item_count = sum(
            not isinstance(value, str) or not value.strip()
            for value in context_values
        )
        if invalid_item_count:
            raise S3SegmentedSpecialistAuthorityError(
                subtype="item_not_nonblank_string",
                failing_item_count=invalid_item_count,
            )

        allowed_context_refs, fact_authority = (
            DeepSeekS3ThreeCellNodeExecutor._segment_context_authority_sets(
                cell_input
            )
        )
        misclassified_count = sum(
            value in fact_authority for value in context_values
        )
        if misclassified_count:
            raise S3SegmentedSpecialistAuthorityError(
                subtype="evidence_or_numeric_ref_misclassified_as_context",
                failing_item_count=misclassified_count,
            )

        outside_count = sum(
            value not in allowed_context_refs for value in context_values
        )
        if outside_count:
            raise S3SegmentedSpecialistAuthorityError(
                subtype="outside_current_cell_context_authority",
                failing_item_count=outside_count,
            )

    @staticmethod
    def _validate_segment_epistemic_status_state(
        output: Mapping[str, Any],
    ) -> None:
        violation = EpistemicStatePolicy().cannot_infer_violation(
            output.get("judgment_layer")
        )
        if violation is None:
            return
        raise S3SegmentedSpecialistEpistemicStatusError(
            subtype=violation.subtype,
            failing_item_count=violation.failing_item_count,
        )

    @classmethod
    def _validate_segment_narrative_text(
        cls,
        segment_id: str,
        output: Mapping[str, Any],
        *,
        maximum_characters: int = S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS,
    ) -> None:
        if segment_id == "facts_explanation_and_terminal":
            fact_values: list[Any] = []
            facts = output.get("fact_layer")
            if isinstance(facts, list):
                for fact in facts:
                    if isinstance(fact, Mapping):
                        fact_values.extend(
                            fact[key]
                            for key in ("statement", "boundary")
                            if key in fact
                        )
            cls._raise_segment_text_failure_if_any(
                segment_id=segment_id,
                field_id="fact_layer.statement_or_boundary",
                values=fact_values,
                failure_code="s3_bounded_specialist_output_text_length_invalid:fact_layer",
                maximum_characters=maximum_characters,
            )
            for field_id in ("explanation_layer", "remaining_gaps"):
                values = output.get(field_id)
                if isinstance(values, list):
                    cls._raise_segment_text_failure_if_any(
                        segment_id=segment_id,
                        field_id=field_id,
                        values=values,
                        failure_code=(
                            "s3_bounded_specialist_output_text_length_invalid:"
                            f"{field_id}"
                        ),
                        maximum_characters=maximum_characters,
                    )
            return

        if segment_id == "owner_grade_claim_cards":
            values = []
            claims = output.get("judgment_layer")
            if isinstance(claims, list):
                for claim in claims:
                    if not isinstance(claim, Mapping):
                        continue
                    if "statement" in claim:
                        values.append(claim["statement"])
                    if "qualification" in claim:
                        qualification = claim["qualification"]
                        if (
                            not isinstance(qualification, str)
                            or qualification.strip()
                            or claim.get("epistemic_status") == "hypothesis"
                        ):
                            values.append(qualification)
                    cannot_support = claim.get("cannot_support")
                    if isinstance(cannot_support, list):
                        values.extend(cannot_support)
                    scope = claim.get("scope")
                    if isinstance(scope, Mapping) and "metric_or_mechanism" in scope:
                        values.append(scope["metric_or_mechanism"])
            cls._raise_segment_text_failure_if_any(
                segment_id=segment_id,
                field_id="judgment_layer",
                values=values,
                failure_code="s3_bounded_specialist_output_text_length_invalid:judgment_layer",
                maximum_characters=maximum_characters,
            )
            return

        if segment_id == "actionable_what_would_change_tasks":
            values = []
            tasks = output.get("what_would_change")
            if isinstance(tasks, list):
                for task in tasks:
                    if not isinstance(task, Mapping):
                        continue
                    for key in (
                        "metric_or_observation",
                        "expected_claim_transition",
                        "fallback_stop_condition",
                    ):
                        if key in task:
                            values.append(task[key])
                    nested_fields = {
                        "source_target": (
                            "source_type",
                            "entity_or_owner",
                            "document_event_or_dataset",
                        ),
                        "decision_rule": (
                            "rule_type",
                            "comparator_or_condition",
                            "threshold_or_observation",
                        ),
                        "time_window": (
                            "as_of",
                            "start_or_trigger",
                            "deadline_or_review_date",
                        ),
                    }
                    for key, expected_nested_fields in nested_fields.items():
                        nested = task.get(key)
                        if isinstance(nested, Mapping):
                            values.extend(
                                nested[field]
                                for field in expected_nested_fields
                                if field in nested
                            )
            cls._raise_segment_text_failure_if_any(
                segment_id=segment_id,
                field_id="what_would_change",
                values=values,
                failure_code="s3_bounded_specialist_output_text_length_invalid:what_would_change",
                maximum_characters=maximum_characters,
            )
            return
        raise ValueError("s3_segmented_specialist_segment_unknown")

    @staticmethod
    def _raise_segment_text_failure_if_any(
        *,
        segment_id: str,
        field_id: str,
        values: list[Any],
        failure_code: str,
        maximum_characters: int = S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS,
    ) -> None:
        subtype_counts = (
            (
                "item_not_string",
                sum(not isinstance(value, str) for value in values),
            ),
            (
                "item_blank",
                sum(
                    isinstance(value, str) and not value.strip()
                    for value in values
                ),
            ),
            (
                "item_over_max_unicode_characters",
                sum(
                    isinstance(value, str)
                    and bool(value.strip())
                    and len(value) > maximum_characters
                    for value in values
                ),
            ),
        )
        for subtype, failing_item_count in subtype_counts:
            if failing_item_count:
                raise S3SegmentedSpecialistTextError(
                    segment_id=segment_id,
                    field_id=field_id,
                    subtype=subtype,
                    failing_item_count=failing_item_count,
                    failure_code=failure_code,
                )

    @staticmethod
    def _validate_segment_top_level(
        *,
        output: Mapping[str, Any],
        expected_keys: set[str],
        expected_cell_id: str,
        segment_id: str,
    ) -> None:
        observed = set(output)
        missing_count = len(expected_keys - observed)
        unexpected_count = len(observed - expected_keys)
        if unexpected_count:
            raise S3SegmentedSpecialistShapeError(
                segment_id=segment_id,
                subtype="top_level_keys_unexpected",
                missing_key_count=missing_count,
                unexpected_key_count=unexpected_count,
            )
        if missing_count:
            raise S3SegmentedSpecialistShapeError(
                segment_id=segment_id,
                subtype="top_level_keys_missing",
                missing_key_count=missing_count,
                unexpected_key_count=unexpected_count,
            )
        if output.get("program_cell_id") != expected_cell_id:
            raise S3SegmentedSpecialistShapeError(
                segment_id=segment_id,
                subtype="program_cell_id_mismatch",
                missing_key_count=0,
                unexpected_key_count=0,
            )

    @staticmethod
    def _validate_facts_explanation_and_terminal_segment(
        output: Mapping[str, Any], cell_input: Mapping[str, Any]
    ) -> None:
        cell_id = str(cell_input.get("program_cell_id") or "")
        if not all(
            isinstance(output.get(key), list)
            for key in ("fact_layer", "explanation_layer", "remaining_gaps")
        ):
            raise ValueError("s3_bounded_specialist_segment_list_required")
        authority = cell_input.get("authority_refs")
        if not isinstance(authority, Mapping):
            raise ValueError(f"s3_bounded_specialist_authority_refs_missing:{cell_id}")
        allowed = {
            "Evidence": set(map(str, authority.get("accepted_evidence_refs", ()))),
            "Numeric": set(map(str, authority.get("numeric_refs", ()))),
        }
        forbidden = set(map(str, authority.get("candidate_refs_not_evidence", ())))
        forbidden.update(
            map(str, authority.get("graph_context_refs_not_evidence", ()))
        )
        facts = output["fact_layer"]
        if len(facts) > S3_SPECIALIST_V2_MAX_FACTS:
            raise ValueError(
                f"s3_bounded_specialist_output_cardinality_invalid:{cell_id}:fact_layer"
            )
        fact_ids: set[str] = set()
        for fact in facts:
            if not isinstance(fact, Mapping) or set(fact) != {
                "fact_id",
                "statement",
                "support_type",
                "support_refs",
                "boundary",
            }:
                raise ValueError(f"s3_bounded_specialist_fact_schema_invalid:{cell_id}")
            raw_refs = fact.get("support_refs")
            refs = set(map(str, raw_refs or ()))
            support_type = str(fact.get("support_type") or "")
            fact_id = str(fact.get("fact_id") or "")
            if (
                support_type not in allowed
                or not refs
                or not refs.issubset(allowed[support_type])
            ):
                raise ValueError(
                    f"s3_bounded_specialist_fact_authority_invalid:{cell_id}"
                )
            if refs & forbidden:
                raise ValueError(
                    f"s3_bounded_candidate_or_graph_promoted_to_fact:{cell_id}"
                )
            if (
                not fact_id
                or fact_id in fact_ids
                or not isinstance(raw_refs, list)
                or any(not isinstance(ref, str) or not ref for ref in raw_refs)
                or len(raw_refs) != len(refs)
            ):
                raise ValueError(
                    f"s3_bounded_specialist_fact_or_ref_duplicate_invalid:{cell_id}"
                )
            if any(
                not isinstance(fact.get(key), str)
                or not str(fact[key]).strip()
                or len(str(fact[key])) > S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS
                for key in ("statement", "boundary")
            ):
                raise ValueError(
                    f"s3_bounded_specialist_output_text_length_invalid:{cell_id}:fact_layer"
                )
            fact_ids.add(fact_id)
        for key, limits in {
            "explanation_layer": (1, 3),
            "remaining_gaps": (1, 4),
        }.items():
            values = output[key]
            if not limits[0] <= len(values) <= limits[1]:
                raise ValueError(
                    f"s3_bounded_specialist_output_cardinality_invalid:{cell_id}:{key}"
                )
            if any(
                not isinstance(value, str)
                or not value.strip()
                or len(value) > S3_SPECIALIST_V2_MAX_NARRATIVE_CHARS
                for value in values
            ):
                raise ValueError(
                    f"s3_bounded_specialist_output_text_length_invalid:{cell_id}:{key}"
                )
        if not str(output.get("terminal_class") or ""):
            raise ValueError(
                f"s3_bounded_specialist_terminal_class_missing:{cell_id}"
            )

    @staticmethod
    def _projected_cost(
        estimated_input_tokens: int,
        max_output_tokens: int,
        admission: S3ThreeCellBoundedAgentAdmission,
    ) -> float:
        return (
            estimated_input_tokens
            * admission.input_cache_miss_usd_per_million
            + max_output_tokens * admission.output_usd_per_million
        ) / 1_000_000

    @staticmethod
    def _usage_receipt(
        result: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        node_id: str,
    ) -> dict[str, Any]:
        raw = result.get("raw_response")
        usage = raw.get("usage") if isinstance(raw, Mapping) else {}
        usage = usage if isinstance(usage, Mapping) else {}
        cache_hit = int(usage.get("prompt_cache_hit_tokens") or 0)
        cache_miss = int(
            usage.get("prompt_cache_miss_tokens")
            or result.get("input_tokens")
            or 0
        )
        output = int(result.get("output_tokens") or 0)
        cost = (
            cache_hit * admission.input_cache_hit_usd_per_million
            + cache_miss * admission.input_cache_miss_usd_per_million
            + output * admission.output_usd_per_million
        ) / 1_000_000
        return {
            "stage": node_id,
            "call_id": str(result.get("call_id") or ""),
            "provider": str(result.get("provider") or admission.provider or ""),
            "model": str(result.get("model") or admission.model or ""),
            "status": str(result.get("status") or "unknown"),
            "finish_reason": result.get("finish_reason"),
            "input_tokens": int(result.get("input_tokens") or 0),
            "input_cache_hit_tokens": cache_hit,
            "input_cache_miss_tokens": cache_miss,
            "output_tokens": output,
            "total_tokens": int(result.get("total_tokens") or 0),
            "estimated_cost_usd": round(cost, 8),
            "latency_ms": int(result.get("latency_ms") or 0),
            "transport_attempt_count": int(
                result.get("transport_attempt_count") or 0
            ),
        }

    @staticmethod
    def _parse_native_json_object(content: str) -> dict[str, Any]:
        if content != content.strip() or content.lstrip().startswith("```"):
            raise ValueError("s3_bounded_node_native_json_required")

        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("s3_bounded_node_duplicate_json_key")
                value[key] = item
            return value

        try:
            parsed = json.loads(content, object_pairs_hook=reject_duplicates)
        except json.JSONDecodeError as exc:
            raise ValueError("s3_bounded_node_json_decode_failed") from exc
        if not isinstance(parsed, dict):
            raise ValueError("s3_bounded_node_output_not_object")
        return parsed

    @staticmethod
    def _derive_research_lead_cell_heads(
        specialist_outputs: list[Mapping[str, Any]],
        specialist_digests: Mapping[str, str],
        *,
        research_profile: BoundedResearchProfile | None = None,
    ) -> list[dict[str, Any]]:
        expected_profile = (
            research_profile or S3_NVDA_THREE_CELL_RESEARCH_PROFILE
        )
        if len(specialist_outputs) != expected_profile.maximum_cell_count:
            raise ValueError("s3_research_lead_v2_exact_three_specialists_required")
        heads: list[dict[str, Any]] = []
        observed_cells: set[str] = set()
        for specialist in specialist_outputs:
            if not isinstance(specialist, Mapping):
                raise ValueError("s3_research_lead_v2_specialist_body_invalid")
            cell_id = str(specialist.get("program_cell_id") or "")
            digest = specialist_digests.get(cell_id)
            if (
                not cell_id
                or cell_id in observed_cells
                or not isinstance(digest, str)
                or digest != canonical_digest(specialist)
            ):
                raise ValueError("s3_research_lead_v2_specialist_digest_invalid")
            fact_layer = specialist.get("fact_layer")
            claims = specialist.get("judgment_layer")
            if not isinstance(fact_layer, list) or not isinstance(claims, list):
                raise ValueError("s3_research_lead_v2_specialist_body_invalid")
            observed_cells.add(cell_id)
            heads.append(
                {
                    "program_cell_id": cell_id,
                    "specialist_output_digest": digest,
                    "terminal_class": specialist.get("terminal_class"),
                    "evidence_fact_count": sum(
                        1
                        for fact in fact_layer
                        if isinstance(fact, Mapping)
                        and fact.get("support_type") == "Evidence"
                    ),
                    "numeric_fact_count": sum(
                        1
                        for fact in fact_layer
                        if isinstance(fact, Mapping)
                        and fact.get("support_type") == "Numeric"
                    ),
                    "claim_state_counts": {
                        status: sum(
                            1
                            for claim in claims
                            if isinstance(claim, Mapping)
                            and claim.get("epistemic_status") == status
                        )
                        for status in S3_OWNER_GRADE_CLAIM_STATUSES
                    },
                }
            )
        if observed_cells != set(expected_profile.program_cell_ids):
            raise ValueError("s3_research_lead_v2_cell_identity_invalid")
        return heads

    @staticmethod
    def _validate_research_lead_v2_segment(
        output: Mapping[str, Any],
        specialist_outputs: list[Mapping[str, Any]],
        *,
        research_profile: BoundedResearchProfile | None = None,
        remaining_gaps_maximum: int | None = 4,
    ) -> list[dict[str, Any]]:
        required = {
            "cross_cell_dependencies",
            "conflict_adjudications",
            "variant_view",
            "remaining_gaps",
        }
        observed = set(output)
        if required - observed:
            raise S3ResearchLeadContractError(
                failure_family="shape",
                failure_subtype="top_level_keys_missing",
                field_id="top_level",
                failing_item_count=len(required - observed),
            )
        if observed - required:
            raise S3ResearchLeadContractError(
                failure_family="shape",
                failure_subtype="top_level_keys_unexpected",
                field_id="top_level",
                failing_item_count=len(observed - required),
            )
        ranges = {
            "cross_cell_dependencies": (1, 3),
            "conflict_adjudications": (0, 3),
            "remaining_gaps": (1, remaining_gaps_maximum),
        }
        for field_id, (minimum, maximum) in ranges.items():
            value = output.get(field_id)
            if not isinstance(value, list):
                raise S3ResearchLeadContractError(
                    failure_family="shape",
                    failure_subtype="item_schema_invalid",
                    field_id=field_id,
                    failing_item_count=1,
                )
            if len(value) < minimum:
                raise S3ResearchLeadContractError(
                    failure_family="cardinality",
                    failure_subtype="below_minimum",
                    field_id=field_id,
                    failing_item_count=minimum - len(value),
                )
            if maximum is not None and len(value) > maximum:
                raise S3ResearchLeadContractError(
                    failure_family="cardinality",
                    failure_subtype="above_maximum",
                    field_id=field_id,
                    failing_item_count=len(value) - maximum,
                )
        schemas = {
            "cross_cell_dependencies": {
                "dependency_id",
                "statement",
                "claim_ids",
            },
            "conflict_adjudications": {
                "adjudication_id",
                "involved_claim_ids",
                "terminal_state_summary",
                "fact_presence_summary",
                "resolution_status",
                "statement",
            },
            "remaining_gaps": {
                "gap_id",
                "statement",
                "claim_ids",
                "what_would_change_task_ids",
            },
        }
        for field_id, expected_keys in schemas.items():
            invalid_count = sum(
                1
                for row in output[field_id]
                if not isinstance(row, Mapping) or set(row) != expected_keys
            )
            if invalid_count:
                raise S3ResearchLeadContractError(
                    failure_family="shape",
                    failure_subtype="item_schema_invalid",
                    field_id=field_id,
                    failing_item_count=invalid_count,
                )
        variant = output.get("variant_view")
        if not isinstance(variant, Mapping) or set(variant) != {
            "statement",
            "claim_ids",
            "what_would_change_task_ids",
        }:
            raise S3ResearchLeadContractError(
                failure_family="shape",
                failure_subtype="item_schema_invalid",
                field_id="variant_view",
                failing_item_count=1,
            )
        narrative_fields: list[tuple[str, Any]] = [
            *[
                ("cross_cell_dependencies", row.get("statement"))
                for row in output["cross_cell_dependencies"]
            ],
            *[
                ("conflict_adjudications", row.get(key))
                for row in output["conflict_adjudications"]
                for key in (
                    "terminal_state_summary",
                    "resolution_status",
                    "statement",
                )
            ],
            ("variant_view", variant.get("statement")),
            *[
                ("remaining_gaps", row.get("statement"))
                for row in output["remaining_gaps"]
            ],
        ]
        profile = research_profile or S3_NVDA_THREE_CELL_RESEARCH_PROFILE
        quality_observations, hard_findings = NarrativeQualityPolicy.assess(
            narrative_fields,
            target_characters=(
                profile.research_lead_narrative_target_characters
            ),
            hard_max_characters=(
                profile.research_lead_narrative_hard_max_characters
            ),
            length_exceedance_is_terminal=(
                profile.research_lead_narrative_character_limits_terminal
            ),
            aggregate_target_characters=(
                profile.research_lead_aggregate_narrative_max_characters
                if not profile
                .research_lead_narrative_character_limits_terminal
                else None
            ),
        )
        if hard_findings:
            subtype = next(
                candidate
                for candidate in (
                    "item_not_string",
                    "item_blank",
                    "item_over_max_unicode_characters",
                )
                if candidate in hard_findings
            )
            field_counts = hard_findings[subtype]
            failing_item_count = sum(field_counts.values())
            field_id = (
                next(iter(field_counts))
                if len(field_counts) == 1
                else "assembled_output"
            )
            raise S3ResearchLeadContractError(
                failure_family="text",
                failure_subtype=subtype,
                field_id=field_id,
                failing_item_count=failing_item_count,
            )
        claim_ids = {
            str(claim["claim_id"])
            for specialist in specialist_outputs
            for claim in specialist.get("judgment_layer", ())
            if isinstance(claim, Mapping) and claim.get("claim_id")
        }
        task_ids = {
            str(task["task_id"])
            for specialist in specialist_outputs
            for task in specialist.get("what_would_change", ())
            if isinstance(task, Mapping) and task.get("task_id")
        }
        ref_rows = [
            *[
                (
                    "cross_cell_dependencies",
                    row.get("claim_ids"),
                    [],
                )
                for row in output["cross_cell_dependencies"]
            ],
            *[
                (
                    "conflict_adjudications",
                    row.get("involved_claim_ids"),
                    [],
                )
                for row in output["conflict_adjudications"]
            ],
            (
                "variant_view",
                variant.get("claim_ids"),
                variant.get("what_would_change_task_ids"),
            ),
            *[
                (
                    "remaining_gaps",
                    row.get("claim_ids"),
                    row.get("what_would_change_task_ids"),
                )
                for row in output["remaining_gaps"]
            ],
        ]
        for field_id, observed_claims, observed_tasks in ref_rows:
            if (
                not isinstance(observed_claims, list)
                or not observed_claims
                or not set(map(str, observed_claims)).issubset(claim_ids)
            ):
                raise S3ResearchLeadContractError(
                    failure_family="authority",
                    failure_subtype="claim_ref_invalid",
                    field_id=field_id,
                    failing_item_count=1,
                )
            if (
                not isinstance(observed_tasks, list)
                or not set(map(str, observed_tasks)).issubset(task_ids)
            ):
                raise S3ResearchLeadContractError(
                    failure_family="authority",
                    failure_subtype="task_ref_invalid",
                    field_id=field_id,
                    failing_item_count=1,
                )
        return quality_observations

    @staticmethod
    def _validate_research_lead_v3_segment(
        output: Mapping[str, Any],
        specialist_outputs: list[Mapping[str, Any]],
        *,
        research_profile: BoundedResearchProfile | None = None,
        remaining_gaps_maximum: int | None = 4,
    ) -> list[dict[str, Any]]:
        try:
            quality_observations = (
                DeepSeekS3ThreeCellNodeExecutor
                ._validate_research_lead_v2_segment(
                    output,
                    specialist_outputs,
                    research_profile=research_profile,
                    remaining_gaps_maximum=remaining_gaps_maximum,
                )
            )
        except S3ResearchLeadContractError as exc:
            telemetry = exc.telemetry
            raise S3ResearchLeadV3ContractError(
                failure_family=str(telemetry["failure_family"]),
                failure_subtype=str(telemetry["failure_subtype"]),
                field_id=str(telemetry["field_id"]),
                failing_item_count=int(telemetry["failing_item_count"]),
            ) from exc

        claim_by_id = {
            str(claim["claim_id"]): claim
            for specialist in specialist_outputs
            for claim in specialist.get("judgment_layer", ())
            if isinstance(claim, Mapping) and claim.get("claim_id")
        }
        total_facts = sum(
            len(specialist.get("fact_layer", ()))
            for specialist in specialist_outputs
        )
        derive_fact_presence = (
            S3ThreeCellBoundedAgentExecutor
            ._expected_conflict_fact_presence_summary
        )
        for conflict in output["conflict_adjudications"]:
            involved = conflict.get("involved_claim_ids")
            if (
                not isinstance(involved, list)
                or not involved
                or any(
                    not isinstance(claim_id, str) or not claim_id.strip()
                    for claim_id in involved
                )
                or any(claim_id not in claim_by_id for claim_id in involved)
            ):
                raise S3ResearchLeadV3ContractError(
                    failure_family="authority",
                    failure_subtype="claim_ref_invalid",
                    field_id="conflict_adjudications",
                    failing_item_count=1,
                )
            if len(set(involved)) != len(involved):
                raise S3ResearchLeadV3ContractError(
                    failure_family="semantic",
                    failure_subtype="involved_claim_ref_duplicate",
                    field_id="conflict_adjudications.fact_presence_summary",
                    failing_item_count=1,
                )
            observed_summary = conflict.get("fact_presence_summary")
            if observed_summary not in {
                "facts_present",
                "no_facts_present",
                "mixed_fact_presence",
            }:
                raise S3ResearchLeadV3ContractError(
                    failure_family="semantic",
                    failure_subtype="fact_presence_summary_invalid",
                    field_id="conflict_adjudications.fact_presence_summary",
                    failing_item_count=1,
                )
            expected_summary = derive_fact_presence(involved, claim_by_id)
            if observed_summary != expected_summary:
                raise S3ResearchLeadV3ContractError(
                    failure_family="semantic",
                    failure_subtype="fact_presence_summary_mismatch",
                    field_id="conflict_adjudications.fact_presence_summary",
                    failing_item_count=1,
                )
            normalized_fact_text = " ".join(
                str(conflict.get(key) or "").lower()
                for key in ("terminal_state_summary", "statement")
            )
            if total_facts > 0 and any(
                phrase in normalized_fact_text
                for phrase in (
                    "all cells are in non-fact states",
                    "all cells are non-fact",
                )
            ):
                raise S3ResearchLeadV3ContractError(
                    failure_family="semantic",
                    failure_subtype=(
                        "explicit_global_fact_presence_statement_conflict"
                    ),
                    field_id="conflict_adjudications.fact_presence_summary",
                    failing_item_count=1,
                )
        return quality_observations

    @staticmethod
    def _validate_research_lead_v4_segment(
        output: Mapping[str, Any],
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any],
        *,
        research_profile: BoundedResearchProfile | None = None,
    ) -> list[dict[str, Any]]:
        projected_specialists, projected_output = (
            S3ThreeCellBoundedAgentExecutor._scoped_alias_projection(
                specialist_outputs,
                scoped_identity_surface,
                output,
            )
        )
        assert projected_output is not None
        return DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v3_segment(
            projected_output,
            projected_specialists,
            research_profile=research_profile,
        )

    @staticmethod
    def _research_lead_v5_local_row_ids(
        segment: Mapping[str, Any],
    ) -> dict[str, Any]:
        required = {
            "cross_cell_dependencies",
            "conflict_adjudications",
            "variant_view",
            "remaining_gaps",
        }
        if set(segment) != required:
            raise S3ResearchLeadV3ContractError(
                failure_family="shape",
                failure_subtype=(
                    "top_level_keys_missing"
                    if required - set(segment)
                    else "top_level_keys_unexpected"
                ),
                field_id="top_level",
                failing_item_count=len(
                    required - set(segment) or set(segment) - required
                ),
            )
        schemas = {
            "cross_cell_dependencies": {"statement", "claim_ids"},
            "conflict_adjudications": {
                "involved_claim_ids",
                "terminal_state_summary",
                "fact_presence_summary",
                "resolution_status",
                "statement",
            },
            "remaining_gaps": {
                "statement",
                "claim_ids",
                "what_would_change_task_ids",
            },
        }
        output = deepcopy(segment)
        for field_id, expected in schemas.items():
            rows = output.get(field_id)
            if not isinstance(rows, list):
                raise S3ResearchLeadV3ContractError(
                    failure_family="shape",
                    failure_subtype="item_schema_invalid",
                    field_id=field_id,
                    failing_item_count=1,
                )
            invalid = sum(
                1
                for row in rows
                if not isinstance(row, Mapping) or set(row) != expected
            )
            if invalid:
                raise S3ResearchLeadV3ContractError(
                    failure_family="shape",
                    failure_subtype="item_schema_invalid",
                    field_id=field_id,
                    failing_item_count=invalid,
                )
        variant = output.get("variant_view")
        if not isinstance(variant, Mapping) or set(variant) != {
            "statement",
            "claim_ids",
            "what_would_change_task_ids",
        }:
            raise S3ResearchLeadV3ContractError(
                failure_family="shape",
                failure_subtype="item_schema_invalid",
                field_id="variant_view",
                failing_item_count=1,
            )
        for prefix, field_id, id_field in (
            ("dependency", "cross_cell_dependencies", "dependency_id"),
            ("adjudication", "conflict_adjudications", "adjudication_id"),
            ("gap", "remaining_gaps", "gap_id"),
        ):
            for ordinal, row in enumerate(output[field_id], start=1):
                row[id_field] = f"research_lead:{prefix}:{ordinal:03d}"
        return output

    @staticmethod
    def _research_lead_v7_provider_segment(
        segment: Mapping[str, Any],
    ) -> dict[str, Any]:
        required = {
            "cross_cell_dependencies",
            "conflict_adjudications",
            "variant_view",
            "remaining_gaps",
        }
        if set(segment) != required:
            raise S3ResearchLeadV3ContractError(
                failure_family="shape",
                failure_subtype=(
                    "top_level_keys_missing"
                    if required - set(segment)
                    else "top_level_keys_unexpected"
                ),
                field_id="top_level",
                failing_item_count=len(
                    required - set(segment) or set(segment) - required
                ),
            )
        schemas = {
            "cross_cell_dependencies": {"statement", "claim_ids"},
            "conflict_adjudications": {
                "involved_claim_ids",
                "terminal_state_summary",
                "resolution_status",
                "statement",
            },
            "remaining_gaps": {
                "statement",
                "claim_ids",
                "what_would_change_task_ids",
            },
        }
        output = deepcopy(segment)
        for field_id, expected in schemas.items():
            rows = output.get(field_id)
            if not isinstance(rows, list):
                raise S3ResearchLeadV3ContractError(
                    failure_family="shape",
                    failure_subtype="item_schema_invalid",
                    field_id=field_id,
                    failing_item_count=1,
                )
            invalid = sum(
                1
                for row in rows
                if not isinstance(row, Mapping) or set(row) != expected
            )
            if invalid:
                raise S3ResearchLeadV3ContractError(
                    failure_family="shape",
                    failure_subtype="item_schema_invalid",
                    field_id=field_id,
                    failing_item_count=invalid,
                )
        variant = output.get("variant_view")
        if not isinstance(variant, Mapping) or set(variant) != {
            "statement",
            "claim_ids",
            "what_would_change_task_ids",
        }:
            raise S3ResearchLeadV3ContractError(
                failure_family="shape",
                failure_subtype="item_schema_invalid",
                field_id="variant_view",
                failing_item_count=1,
            )
        return output

    @staticmethod
    def _research_lead_v5_narratives(
        segment: Mapping[str, Any],
    ) -> list[Any]:
        return [
            value
            for _, value in (
                DeepSeekS3ThreeCellNodeExecutor
                ._research_lead_v5_named_narratives(segment)
            )
        ]

    @staticmethod
    def _research_lead_v5_named_narratives(
        segment: Mapping[str, Any],
    ) -> list[tuple[str, Any]]:
        variant = segment.get("variant_view")
        return [
            *[
                ("cross_cell_dependencies", row.get("statement"))
                for row in segment.get("cross_cell_dependencies", ())
                if isinstance(row, Mapping)
            ],
            *[
                ("conflict_adjudications", row.get(key))
                for row in segment.get("conflict_adjudications", ())
                if isinstance(row, Mapping)
                for key in (
                    "terminal_state_summary",
                    "resolution_status",
                    "statement",
                )
            ],
            (
                "variant_view",
                (
                    variant.get("statement")
                    if isinstance(variant, Mapping)
                    else None
                ),
            ),
            *[
                ("remaining_gaps", row.get("statement"))
                for row in segment.get("remaining_gaps", ())
                if isinstance(row, Mapping)
            ],
        ]

    @staticmethod
    def _expand_research_lead_v5_alias_segment(
        alias_segment: Mapping[str, Any],
        alias_table: CompactScopedReferenceAliasTable,
    ) -> dict[str, Any]:
        output = deepcopy(alias_segment)

        def expand(
            row: dict[str, Any],
            field_id: str,
            kind: str,
            *,
            allow_empty: bool,
        ) -> None:
            expanded = alias_table.expand_list(
                row.get(field_id),
                expected_kind=kind,
                allow_empty=allow_empty,
            )
            if isinstance(expanded, ScopedIdentityViolation):
                raise S3ScopedIdentityContractError(expanded)
            row[field_id] = expanded

        for row in output["cross_cell_dependencies"]:
            expand(row, "claim_ids", "claim", allow_empty=False)
        for row in output["conflict_adjudications"]:
            expand(
                row,
                "involved_claim_ids",
                "claim",
                allow_empty=False,
            )
        variant = output["variant_view"]
        expand(variant, "claim_ids", "claim", allow_empty=False)
        expand(
            variant,
            "what_would_change_task_ids",
            "what_would_change",
            allow_empty=True,
        )
        for row in output["remaining_gaps"]:
            expand(row, "claim_ids", "claim", allow_empty=False)
            expand(
                row,
                "what_would_change_task_ids",
                "what_would_change",
                allow_empty=True,
            )
        return output

    @classmethod
    def _research_lead_v5_capacity_envelope(
        cls,
        *,
        alias_table: CompactScopedReferenceAliasTable,
        cell_heads: list[Mapping[str, Any]],
        research_profile: BoundedResearchProfile,
    ) -> dict[str, Any]:
        claim_aliases = list(alias_table.aliases_for_kind("claim"))
        task_aliases = list(
            alias_table.aliases_for_kind("what_would_change")
        )
        if not claim_aliases:
            raise ValueError("s3_research_lead_v5_claim_alias_surface_empty")
        narrative_lengths = [1] * 17
        remaining = (
            research_profile
            .research_lead_aggregate_narrative_max_characters
        ) - len(narrative_lengths)
        if remaining < 0:
            raise ValueError(
                "s3_research_lead_v5_narrative_capacity_not_representable"
            )
        for index in range(len(narrative_lengths)):
            additional = min(
                (
                    research_profile
                    .research_lead_narrative_hard_max_characters
                )
                - 1,
                remaining,
            )
            narrative_lengths[index] += additional
            remaining -= additional
        if remaining:
            raise ValueError(
                "s3_research_lead_v5_narrative_capacity_not_representable"
            )
        narratives = iter("x" * length for length in narrative_lengths)
        provider_segment = {
            "cross_cell_dependencies": [
                {
                    "statement": next(narratives),
                    "claim_ids": claim_aliases,
                }
                for _ in range(3)
            ],
            "conflict_adjudications": [
                {
                    "involved_claim_ids": claim_aliases,
                    "terminal_state_summary": next(narratives),
                    "fact_presence_summary": "mixed_fact_presence",
                    "resolution_status": next(narratives),
                    "statement": next(narratives),
                }
                for _ in range(3)
            ],
            "variant_view": {
                "statement": next(narratives),
                "claim_ids": claim_aliases,
                "what_would_change_task_ids": task_aliases,
            },
            "remaining_gaps": [
                {
                    "statement": next(narratives),
                    "claim_ids": claim_aliases,
                    "what_would_change_task_ids": task_aliases,
                }
                for _ in range(4)
            ],
        }
        alias_segment = cls._research_lead_v5_local_row_ids(
            provider_segment
        )
        expanded = cls._expand_research_lead_v5_alias_segment(
            alias_segment,
            alias_table,
        )

        def size(value: Any) -> int:
            return len(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )

        provider_segment_bytes = size(provider_segment)
        canonical_alias_segment_bytes = size(alias_segment)
        expanded_template_bytes = size(
            {"cell_heads": cell_heads, **expanded}
        )
        # Narrative encoding may fill the entire canonical alias envelope.
        # The maximum local output is therefore that closed envelope plus the
        # exact maximum typed-ref/head expansion delta, not merely the ASCII
        # maximum-narrative template size.
        local_expanded_max = (
            research_profile.research_lead_canonical_alias_max_utf8_bytes
            + expanded_template_bytes
            - canonical_alias_segment_bytes
        )
        envelope = {
            "capacity_formula_ref": (
                research_profile.research_lead_local_capacity_formula_ref
            ),
            "exact_claim_alias_count": len(claim_aliases),
            "exact_what_would_change_alias_count": len(task_aliases),
            "maximum_provider_segment_utf8_bytes": provider_segment_bytes,
            "maximum_canonical_alias_segment_utf8_bytes": (
                canonical_alias_segment_bytes
            ),
            "maximum_local_expanded_canonical_utf8_bytes": (
                local_expanded_max
            ),
        }
        if (
            envelope["maximum_provider_segment_utf8_bytes"]
            > research_profile.research_lead_provider_raw_max_utf8_bytes
            or envelope["maximum_canonical_alias_segment_utf8_bytes"]
            > research_profile.research_lead_canonical_alias_max_utf8_bytes
            or envelope["maximum_local_expanded_canonical_utf8_bytes"]
            > (
                research_profile
                .research_lead_local_expanded_hard_max_utf8_bytes
            )
        ):
            raise ValueError(
                "s3_research_lead_v5_profile_capacity_not_closed"
            )
        return envelope

    @classmethod
    def _assemble_research_lead_v5_output(
        cls,
        segment: Mapping[str, Any],
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any],
        *,
        cell_heads: list[Mapping[str, Any]],
        research_profile: BoundedResearchProfile,
        capacity: Mapping[str, Any],
    ) -> dict[str, Any]:
        projected_specialists, alias_table = (
            S3ThreeCellBoundedAgentExecutor
            ._compact_alias_specialist_projection(
                specialist_outputs,
                scoped_identity_surface,
            )
        )
        alias_segment = cls._research_lead_v5_local_row_ids(segment)
        named_narratives = cls._research_lead_v5_named_narratives(
            alias_segment
        )
        narratives = [value for _, value in named_narratives]
        _, hard_findings = NarrativeQualityPolicy.assess(
            named_narratives,
            target_characters=(
                research_profile.research_lead_narrative_target_characters
            ),
            hard_max_characters=(
                research_profile
                .research_lead_narrative_hard_max_characters
            ),
            length_exceedance_is_terminal=(
                research_profile
                .research_lead_narrative_character_limits_terminal
            ),
        )
        if hard_findings:
            subtype = next(
                candidate
                for candidate in (
                    "item_not_string",
                    "item_blank",
                    "item_over_max_unicode_characters",
                )
                if candidate in hard_findings
            )
            field_counts = hard_findings[subtype]
            raise S3ResearchLeadV3ContractError(
                failure_family="text",
                failure_subtype=subtype,
                field_id=(
                    next(iter(field_counts))
                    if len(field_counts) == 1
                    else "assembled_output"
                ),
                failing_item_count=sum(field_counts.values()),
            )
        if (
            research_profile.research_lead_narrative_character_limits_terminal
            and sum(len(value) for value in narratives)
            > (
                research_profile
                .research_lead_aggregate_narrative_max_characters
            )
        ):
            raise S3ResearchLeadV3ContractError(
                failure_family="capacity",
                failure_subtype="assembled_output_over_max_utf8_bytes",
                field_id="assembled_output",
                failing_item_count=1,
            )
        alias_bytes = len(
            json.dumps(
                alias_segment,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if alias_bytes > (
            research_profile.research_lead_canonical_alias_max_utf8_bytes
        ):
            raise S3ResearchLeadV3ContractError(
                failure_family="capacity",
                failure_subtype="provider_segment_over_max_utf8_bytes",
                field_id="assembled_output",
                failing_item_count=1,
            )
        cls._validate_research_lead_v3_segment(
            alias_segment,
            projected_specialists,
            research_profile=research_profile,
        )
        expanded = cls._expand_research_lead_v5_alias_segment(
            alias_segment,
            alias_table,
        )
        output = {"cell_heads": list(cell_heads), **expanded}
        expanded_bytes = len(
            json.dumps(
                output,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if expanded_bytes > int(
            capacity["maximum_local_expanded_canonical_utf8_bytes"]
        ):
            raise S3ResearchLeadV3ContractError(
                failure_family="capacity",
                failure_subtype="assembled_output_over_max_utf8_bytes",
                field_id="assembled_output",
                failing_item_count=1,
            )
        return output

    @classmethod
    def _assemble_research_lead_v7_output(
        cls,
        segment: Mapping[str, Any],
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any],
        *,
        cell_heads: list[Mapping[str, Any]],
        research_profile: BoundedResearchProfile,
        capacity: Mapping[str, Any],
    ) -> dict[str, Any]:
        policy = (
            S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
        )
        projected_specialists, alias_table = (
            S3ThreeCellBoundedAgentExecutor
            ._compact_alias_specialist_projection(
                specialist_outputs,
                scoped_identity_surface,
            )
        )
        provider_segment = cls._research_lead_v7_provider_segment(segment)
        claim_by_id = {
            str(claim["claim_id"]): claim
            for specialist in projected_specialists
            for claim in specialist.get("judgment_layer", ())
            if isinstance(claim, Mapping) and claim.get("claim_id")
        }
        for conflict in provider_segment["conflict_adjudications"]:
            involved_claim_ids = conflict.get("involved_claim_ids")
            expanded = alias_table.expand_list(
                involved_claim_ids,
                expected_kind="claim",
                allow_empty=False,
            )
            if isinstance(expanded, ScopedIdentityViolation):
                raise S3ScopedIdentityContractError(expanded)
            conflict[policy.canonical_field_id] = (
                S3ThreeCellBoundedAgentExecutor
                ._expected_conflict_fact_presence_summary(
                    involved_claim_ids,
                    claim_by_id,
                )
            )
        return cls._assemble_research_lead_v5_output(
            provider_segment,
            specialist_outputs,
            scoped_identity_surface,
            cell_heads=cell_heads,
            research_profile=research_profile,
            capacity=capacity,
        )

    @classmethod
    def _assemble_research_lead_v6_output(
        cls,
        segment: Mapping[str, Any],
        specialist_outputs: list[Mapping[str, Any]],
        scoped_identity_surface: Mapping[str, Any],
        *,
        cell_heads: list[Mapping[str, Any]],
        research_profile: BoundedResearchProfile,
        capacity: Mapping[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        policy = S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY
        required = {
            "cross_cell_dependencies",
            "conflict_adjudications",
            "variant_view",
            policy.provider_field_id,
        }
        observed = set(segment)
        if observed != required:
            raise S3ResearchLeadV3ContractError(
                failure_family="shape",
                failure_subtype=(
                    "top_level_keys_missing"
                    if required - observed
                    else "top_level_keys_unexpected"
                ),
                field_id="top_level",
                failing_item_count=len(
                    required - observed or observed - required
                ),
            )
        atoms = segment.get(policy.provider_field_id)
        if not isinstance(atoms, list):
            raise S3ResearchLeadV3ContractError(
                failure_family="shape",
                failure_subtype="item_schema_invalid",
                field_id=policy.provider_field_id,
                failing_item_count=1,
            )
        if not atoms:
            raise S3ResearchLeadV3ContractError(
                failure_family="cardinality",
                failure_subtype="below_minimum",
                field_id=policy.provider_field_id,
                failing_item_count=1,
            )
        invalid_atom_count = sum(
            1
            for atom in atoms
            if not isinstance(atom, Mapping)
            or set(atom) != set(policy.atom_fields)
        )
        if invalid_atom_count:
            raise S3ResearchLeadV3ContractError(
                failure_family="shape",
                failure_subtype="item_schema_invalid",
                field_id=policy.provider_field_id,
                failing_item_count=invalid_atom_count,
            )
        raw_wire_bytes = len(
            json.dumps(
                segment,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if raw_wire_bytes > (
            research_profile.research_lead_provider_raw_max_utf8_bytes
        ):
            raise S3ResearchLeadV3ContractError(
                failure_family="capacity",
                failure_subtype="provider_segment_over_max_utf8_bytes",
                field_id="assembled_output",
                failing_item_count=1,
            )

        projected_specialists, alias_table = (
            S3ThreeCellBoundedAgentExecutor
            ._compact_alias_specialist_projection(
                specialist_outputs,
                scoped_identity_surface,
            )
        )
        validation_segment = deepcopy(segment)
        validation_segment[policy.canonical_field_id] = (
            validation_segment.pop(policy.provider_field_id)
        )
        validation_segment = cls._research_lead_v5_local_row_ids(
            validation_segment
        )
        cls._validate_research_lead_v3_segment(
            validation_segment,
            projected_specialists,
            research_profile=research_profile,
            remaining_gaps_maximum=None,
        )

        claim_rank_by_alias: dict[str, int] = {}
        claim_cell_by_alias: dict[str, str] = {}
        uncertainty_ranks = policy.uncertainty_rank_by_status
        for specialist in projected_specialists:
            cell_id = str(specialist["program_cell_id"])
            for claim in specialist.get("judgment_layer", ()):
                if not isinstance(claim, Mapping):
                    continue
                alias = str(claim.get("claim_id") or "")
                status = str(claim.get("epistemic_status") or "")
                if alias and status in uncertainty_ranks:
                    claim_rank_by_alias[alias] = uncertainty_ranks[status]
                    claim_cell_by_alias[alias] = cell_id

        ranked: list[tuple[tuple[Any, ...], int, str, dict[str, Any]]] = []
        for provider_ordinal, raw_atom in enumerate(atoms, start=1):
            atom = dict(raw_atom)
            claim_aliases = list(atom["claim_ids"])
            digest = canonical_digest(atom)
            ranking_key = (
                -int(bool(atom["what_would_change_task_ids"])),
                -max(claim_rank_by_alias[alias] for alias in claim_aliases),
                -len({claim_cell_by_alias[alias] for alias in claim_aliases}),
                -len(set(claim_aliases)),
                digest,
                provider_ordinal,
            )
            ranked.append(
                (ranking_key, provider_ordinal, digest, deepcopy(atom))
            )
        ranked.sort(key=lambda row: row[0])
        selected = ranked[: policy.canonical_maximum]
        overflow = ranked[policy.canonical_maximum :]
        canonical_segment = {
            key: deepcopy(value)
            for key, value in segment.items()
            if key != policy.provider_field_id
        }
        canonical_segment[policy.canonical_field_id] = [
            row[3] for row in selected
        ]
        output = cls._assemble_research_lead_v5_output(
            canonical_segment,
            specialist_outputs,
            scoped_identity_surface,
            cell_heads=cell_heads,
            research_profile=research_profile,
            capacity=capacity,
        )
        findings = (
            [
                {
                    "finding_code": policy.finding_code,
                    "acceptance_layer": policy.acceptance_layer,
                    "terminal": False,
                    "candidate_count": len(ranked),
                    "selected_count": len(selected),
                    "overflow_count": len(overflow),
                    "projection_policy_ref": policy.policy_ref,
                    "selected_candidate_ordinals": [
                        row[1] for row in selected
                    ],
                    "selected_candidate_digests": [
                        row[2] for row in selected
                    ],
                    "overflow_candidate_digests": [
                        row[2] for row in overflow
                    ],
                }
            ]
            if overflow
            else []
        )
        return output, findings

    @classmethod
    def _research_lead_v2_request(
        cls,
        payload: Mapping[str, Any],
        cell_heads: list[Mapping[str, Any]],
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        specialists = payload.get("specialist_outputs")
        if not isinstance(specialists, list):
            raise ValueError("s3_research_lead_v2_specialist_body_missing")
        schema: dict[str, Any] = {
            "cross_cell_dependencies": [
                {
                    "dependency_id": "unique string",
                    "statement": "string",
                    "claim_ids": ["exact Specialist claim_id"],
                }
            ],
            "conflict_adjudications": [
                {
                    "adjudication_id": "unique string",
                    "involved_claim_ids": ["exact Specialist claim_id"],
                    "terminal_state_summary": "string",
                    "fact_presence_summary": (
                        "facts_present|no_facts_present|mixed_fact_presence"
                    ),
                    "resolution_status": "string",
                    "statement": "string",
                }
            ],
            "variant_view": {
                "statement": "string",
                "claim_ids": ["exact Specialist claim_id"],
                "what_would_change_task_ids": ["exact Specialist task_id"],
            },
            "remaining_gaps": [
                {
                    "gap_id": "unique string",
                    "statement": "string",
                    "claim_ids": ["exact Specialist claim_id"],
                    "what_would_change_task_ids": ["exact Specialist task_id"],
                }
            ],
        }
        system = (
            "You are the cross-cell Research Lead. Return exactly one native JSON "
            "object with no markdown and no duplicate keys. Use only analysis_input. "
            "Do not emit cell_heads: the runtime derives them deterministically. "
            "Retain the supplied Specialist fact, claim, scope, qualification, gap, "
            "and what-would-change authority. Do not call tools or sources, invent "
            "facts or refs, expose private reasoning, or truncate, trim, coerce, drop, "
            "join, split, or silently repair any item. Check every item against the "
            "cardinality, 320-character, and 6000-byte limits before returning."
        )
        analysis_input = {
            "input_digest": payload.get("input_digest"),
            "lead_contract": payload.get("lead_contract"),
            "specialist_outputs": specialists,
        }
        head_digest = canonical_digest(cell_heads)
        return system, {
            "node_id": "research_lead",
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
            ),
            "analysis_input": analysis_input,
            "required_output_schema": schema,
            "required_top_level_keys": list(schema),
            "output_constraints": {
                "cross_cell_dependencies_cardinality": "1..3",
                "conflict_adjudications_cardinality": "0..3",
                "variant_view_cardinality": "exactly_one_object",
                "remaining_gaps_cardinality": "1..4",
                "maximum_narrative_field_unicode_characters": 320,
                "maximum_provider_segment_serialized_utf8_bytes": 6000,
                "maximum_locally_assembled_lead_utf8_bytes": 8192,
                "cell_heads_emitted_by_provider": False,
            },
            "additional_properties_allowed": False,
        }, {
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
            ),
            "local_cell_heads_digest": head_digest,
        }

    @classmethod
    def _research_lead_v3_request(
        cls,
        payload: Mapping[str, Any],
        cell_heads: list[Mapping[str, Any]],
        *,
        provider_fact_presence_summary: bool = True,
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        system, request, binding = cls._research_lead_v2_request(
            payload, cell_heads
        )
        request = deepcopy(request)
        binding = dict(binding)
        request["research_lead_transport_ref"] = (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
        )
        policy = (
            S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
        )
        conflict_schema = request["required_output_schema"][
            "conflict_adjudications"
        ][0]
        fact_presence_constraints = {
            "conflict_fact_presence_scope": (
                "only involved_claim_ids in the current adjudication"
            ),
            "conflict_fact_presence_source": (
                "each involved Claim Card direct support_fact_ids only"
            ),
            "conflict_fact_presence_truth_table": dict(policy.truth_table),
            "unrelated_facts_affect_summary": False,
            "duplicate_involved_claim_ids_allowed": False,
        }
        if provider_fact_presence_summary:
            conflict_schema[policy.provider_field_id] = (
                "facts_present iff every involved claim has nonempty direct "
                "support_fact_ids; no_facts_present iff none do; "
                "mixed_fact_presence iff some but not all do"
            )
            request["output_constraints"].update(
                fact_presence_constraints
            )
        else:
            conflict_schema.pop(policy.provider_field_id)
            request["output_constraints"].update(
                {
                    **fact_presence_constraints,
                    "provider_emits_fact_presence_summary": False,
                    "conflict_fact_presence_owner": (
                        "local_deterministic_runtime"
                    ),
                    "conflict_fact_presence_materialization_policy_ref": (
                        policy.policy_ref
                    ),
                }
            )
        binding["research_lead_transport_ref"] = (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
        )
        if provider_fact_presence_summary:
            system = (
                system
                + " For each conflict_adjudication, derive "
                "fact_presence_summary only from the direct support_fact_ids "
                "of its involved Claim Cards. Use facts_present when all "
                "involved claims have support, no_facts_present when none "
                "have support, and mixed_fact_presence when some but not all "
                "have support. Ignore global, same-cell, and otherwise "
                "unrelated facts. Reject duplicate involved_claim_ids and "
                "self-check this truth table before returning."
            )
        else:
            system = (
                system
                + " Do not emit fact_presence_summary in any "
                "conflict_adjudication. The runtime validates exact Claim "
                "aliases and materializes that canonical field locally from "
                "each involved Claim Card's direct support_fact_ids. Reject "
                "duplicate involved_claim_ids; never add a placeholder or "
                "guess for the omitted runtime-owned field."
            )
        return system, request, binding

    @classmethod
    def _research_lead_v4_request(
        cls,
        payload: Mapping[str, Any],
        cell_heads: list[Mapping[str, Any]],
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        system, request, binding = cls._research_lead_v3_request(
            payload, cell_heads
        )
        scoped_surface = payload.get("scoped_identity_surface")
        specialists = payload.get("specialist_outputs")
        if not isinstance(scoped_surface, Mapping) or not isinstance(
            specialists, list
        ):
            raise ValueError("s3_research_lead_v4_scoped_identity_missing")
        S3ThreeCellBoundedAgentExecutor._scoped_identity_indexes(
            specialists,
            scoped_surface,
        )
        request = deepcopy(request)
        binding = dict(binding)
        request["research_lead_transport_ref"] = (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF
        )
        request["analysis_input"]["scoped_identity_contract_ref"] = (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        )
        request["analysis_input"]["scoped_identity_surface"] = deepcopy(
            scoped_surface
        )
        scoped_claim = CellScopedResearchIdentityPolicy.wire_schema("claim")
        scoped_task = CellScopedResearchIdentityPolicy.wire_schema(
            "what_would_change"
        )
        schema = request["required_output_schema"]
        schema["cross_cell_dependencies"][0]["claim_ids"] = [scoped_claim]
        schema["conflict_adjudications"][0]["involved_claim_ids"] = [
            scoped_claim
        ]
        schema["variant_view"]["claim_ids"] = [scoped_claim]
        schema["variant_view"]["what_would_change_task_ids"] = [scoped_task]
        schema["remaining_gaps"][0]["claim_ids"] = [scoped_claim]
        schema["remaining_gaps"][0]["what_would_change_task_ids"] = [
            scoped_task
        ]
        request["output_constraints"].update(
            {
                "identity_contract_ref": (
                    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
                ),
                "raw_local_id_only_cross_cell_refs_allowed": False,
                "same_local_id_in_different_cells_allowed": True,
                "same_local_id_in_same_cell_allowed": False,
            }
        )
        binding["research_lead_transport_ref"] = (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF
        )
        binding["scoped_identity_contract_ref"] = (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        )
        system = (
            system
            + " Every Claim and what-would-change reference must be the exact "
            "three-field scoped object from scoped_identity_surface. Never emit a "
            "raw local ID as a cross-cell reference, and never rewrite local_id."
        )
        return system, request, binding

    @classmethod
    def _research_lead_v5_request(
        cls,
        payload: Mapping[str, Any],
        cell_heads: list[Mapping[str, Any]],
        *,
        research_profile: BoundedResearchProfile,
        capacity: Mapping[str, Any],
        provider_fact_presence_summary: bool = True,
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        system, request, binding = cls._research_lead_v3_request(
            payload,
            cell_heads,
            provider_fact_presence_summary=provider_fact_presence_summary,
        )
        specialists = payload.get("specialist_outputs")
        scoped_surface = payload.get("scoped_identity_surface")
        if not isinstance(specialists, list) or not isinstance(
            scoped_surface, Mapping
        ):
            raise ValueError("s3_research_lead_v5_scoped_identity_missing")
        alias_table = (
            S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
                specialists,
                scoped_surface,
            )
        )
        request = deepcopy(request)
        binding = dict(binding)
        request["research_lead_transport_ref"] = (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        )
        request["analysis_input"]["scoped_identity_contract_ref"] = (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        )
        request["analysis_input"]["compact_scoped_reference_alias_table"] = (
            alias_table.to_prompt_payload()
        )
        schema = request["required_output_schema"]
        schema["cross_cell_dependencies"][0].pop("dependency_id")
        schema["cross_cell_dependencies"][0]["claim_ids"] = [
            "exact Cnnn Claim alias"
        ]
        schema["conflict_adjudications"][0].pop("adjudication_id")
        schema["conflict_adjudications"][0]["involved_claim_ids"] = [
            "exact Cnnn Claim alias"
        ]
        schema["variant_view"]["claim_ids"] = [
            "exact Cnnn Claim alias"
        ]
        schema["variant_view"]["what_would_change_task_ids"] = [
            "exact Wnnn what-would-change alias"
        ]
        schema["remaining_gaps"][0].pop("gap_id")
        schema["remaining_gaps"][0]["claim_ids"] = [
            "exact Cnnn Claim alias"
        ]
        schema["remaining_gaps"][0]["what_would_change_task_ids"] = [
            "exact Wnnn what-would-change alias"
        ]
        request["output_constraints"].update(
            {
                "identity_contract_ref": (
                    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
                ),
                "alias_contract_ref": alias_table.contract_ref,
                "provider_emits_row_ids": False,
                "provider_emits_typed_scoped_refs": False,
                "provider_emits_exact_aliases_only": True,
                "duplicate_alias_within_reference_list_allowed": False,
                "claim_alias_list_maximum": len(
                    alias_table.aliases_for_kind("claim")
                ),
                "what_would_change_alias_list_maximum": len(
                    alias_table.aliases_for_kind("what_would_change")
                ),
                "maximum_aggregate_provider_narrative_unicode_characters": (
                    research_profile
                    .research_lead_aggregate_narrative_max_characters
                ),
                "narrative_field_quality_target_unicode_characters": (
                    research_profile
                    .research_lead_narrative_target_characters
                ),
                "maximum_narrative_field_unicode_characters": (
                    research_profile
                    .research_lead_narrative_hard_max_characters
                ),
                "narrative_target_exceedance_is_terminal": False,
                "narrative_hard_maximum_exceedance_is_terminal": (
                    research_profile
                    .research_lead_narrative_character_limits_terminal
                ),
                "aggregate_narrative_maximum_exceedance_is_terminal": (
                    research_profile
                    .research_lead_narrative_character_limits_terminal
                ),
                "ordinary_character_limits_protect_hard_capacity": False,
                "maximum_provider_raw_wire_utf8_bytes": (
                    research_profile
                    .research_lead_provider_raw_max_utf8_bytes
                ),
                "maximum_canonical_alias_segment_utf8_bytes": (
                    research_profile
                    .research_lead_canonical_alias_max_utf8_bytes
                ),
                "maximum_local_expanded_canonical_utf8_bytes": int(
                    capacity[
                        "maximum_local_expanded_canonical_utf8_bytes"
                    ]
                ),
                "local_capacity_formula_ref": (
                    capacity["capacity_formula_ref"]
                ),
                "trim_casefold_fuzzy_remap_or_drop_allowed": False,
            }
        )
        binding.update(
            {
                "research_lead_transport_ref": (
                    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
                ),
                "scoped_identity_contract_ref": (
                    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
                ),
                "compact_alias_table_digest": canonical_digest(
                    alias_table.to_prompt_payload()
                ),
                "lead_capacity_envelope_digest": canonical_digest(
                    dict(capacity)
                ),
                "lead_local_expanded_max_utf8_bytes": str(
                    capacity[
                        "maximum_local_expanded_canonical_utf8_bytes"
                    ]
                ),
            }
        )
        character_limit_label = (
            "hard"
            if research_profile.research_lead_narrative_character_limits_terminal
            else "non-terminal quality-ceiling"
        )
        aggregate_instruction = (
            "Keep aggregate narrative text within the supplied closed capacity. "
            if research_profile.research_lead_narrative_character_limits_terminal
            else (
                "Treat the aggregate character threshold as a non-terminal "
                "quality ceiling. "
            )
        )
        system = (
            system.replace(
                "cardinality, 320-character, and 6000-byte limits",
                (
                    "cardinality, "
                    f"{research_profile.research_lead_narrative_hard_max_characters}"
                    f"-character {character_limit_label}, "
                    f"{research_profile.research_lead_narrative_target_characters}"
                    "-character quality-target, and supplied byte limits"
                ),
            )
            + " Use only exact Cnnn and Wnnn values from the supplied compact "
            "alias table for references. Emit no dependency_id, adjudication_id, "
            "gap_id, typed reference object, or raw local ID; the runtime creates "
            "row IDs and expands aliases locally. Each reference list must be "
            "unique and field-kind correct. Do not trim, case-fold, normalize, "
            "guess, remap, or silently drop an alias. "
            + aggregate_instruction
            + "Aim for the narrative "
            "quality target, but never omit a necessary qualification merely to "
            "meet that target. Character thresholds are non-terminal when the "
            "profile says so; supplied wire, canonical-alias, and local-expanded "
            "byte capacities remain mandatory."
        )
        return system, request, binding

    @classmethod
    def _research_lead_v7_request(
        cls,
        payload: Mapping[str, Any],
        cell_heads: list[Mapping[str, Any]],
        *,
        research_profile: BoundedResearchProfile,
        capacity: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        system, request, binding = cls._research_lead_v5_request(
            payload,
            cell_heads,
            research_profile=research_profile,
            capacity=capacity,
            provider_fact_presence_summary=False,
        )
        policy = (
            S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
        )
        request = deepcopy(request)
        binding = dict(binding)
        request["research_lead_transport_ref"] = (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
        )
        binding.update(
            {
                "research_lead_transport_ref": (
                    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
                ),
                "conflict_fact_presence_materialization_policy_ref": (
                    policy.policy_ref
                ),
            }
        )
        return system, request, binding

    @classmethod
    def _research_lead_v6_request(
        cls,
        payload: Mapping[str, Any],
        cell_heads: list[Mapping[str, Any]],
        *,
        research_profile: BoundedResearchProfile,
        capacity: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        system, request, binding = cls._research_lead_v5_request(
            payload,
            cell_heads,
            research_profile=research_profile,
            capacity=capacity,
        )
        policy = S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY
        request = deepcopy(request)
        binding = dict(binding)
        request["research_lead_transport_ref"] = (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
        )
        schema = request["required_output_schema"]
        canonical_gap_schema = schema.pop(policy.canonical_field_id)[0]
        schema[policy.provider_field_id] = [
            {
                field_id: canonical_gap_schema[field_id]
                for field_id in policy.atom_fields
            }
        ]
        request["required_top_level_keys"] = list(schema)
        constraints = request["output_constraints"]
        constraints.pop("remaining_gaps_cardinality")
        constraints.update(
            {
                "remaining_gap_atoms_minimum_cardinality": 1,
                "remaining_gap_atoms_independent_semantic_maximum": None,
                "canonical_remaining_gaps_maximum": (
                    policy.canonical_maximum
                ),
                "gap_atom_projection_policy_ref": policy.policy_ref,
                "gap_atom_projection_ranking": list(
                    policy.ranking_fields
                ),
                "provider_emits_gap_rank_or_score": False,
                "all_gap_atoms_validated_before_projection": True,
                "invalid_overflow_atom_may_be_dropped": False,
            }
        )
        binding.update(
            {
                "research_lead_transport_ref": (
                    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
                ),
                "gap_atom_projection_policy_ref": policy.policy_ref,
            }
        )
        system = (
            system
            + " Emit remaining_gap_atoms, not remaining_gaps. Every atom must "
            "contain only statement, claim_ids, and "
            "what_would_change_task_ids. Emit no rank, score, gap_id, or "
            "canonical position. The runtime validates every atom before "
            f"deterministically projecting at most {policy.canonical_maximum} "
            "canonical remaining_gaps. Candidate count has no independent "
            "semantic maximum; the supplied raw-wire and token capacities "
            "remain hard. An invalid overflow atom fails the whole response."
        )
        return system, request, binding

    @classmethod
    def _memo_writer_v2_request(
        cls,
        payload: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        specialists = payload.get("specialist_heads")
        lead = payload.get("cross_cell_lead")
        if not isinstance(specialists, list) or not isinstance(lead, Mapping):
            raise ValueError("s3_bounded_memo_writer_v2_input_missing")
        claim_surface = (
            S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
                specialists
            )
        )
        claim_inputs = [
            {
                "program_cell_id": str(row.get("program_cell_id") or ""),
                "claim_id": str(claim.get("claim_id") or ""),
                "statement": str(claim.get("statement") or ""),
                "epistemic_status": str(claim.get("epistemic_status") or ""),
                "qualification": str(claim.get("qualification") or ""),
                "cannot_support": list(claim.get("cannot_support") or ()),
            }
            for row in specialists
            if isinstance(row, Mapping)
            for claim in row.get("judgment_layer", ())
            if isinstance(claim, Mapping)
        ]
        system = (
            "You are the no-source and no-tool internal Memo Writer. Return exactly "
            "one native JSON object with no markdown and no duplicate keys. Emit one "
            "claim_rendering for every supplied claim_id, in the supplied order. Write "
            "only a concise Chinese analysis_text_zh_cn for each claim. The runtime "
            "copies all IDs, digests, scope, epistemic status, qualifications, task "
            "references, title, summary, and limitations deterministically; do not emit "
            "or recompute those fields. Do not call tools or sources, invent facts or "
            "numeric precision, promote Candidate or Graph context to evidence, expose "
            "private reasoning, or translate relationship-graph context as a chart."
        )
        request = {
            "node_id": "memo_writer",
            "memo_writer_transport_ref": S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
            "analysis_input": {
                "input_digest": payload.get("input_digest"),
                "lead_summary": {
                    key: deepcopy(lead.get(key))
                    for key in (
                        "conflict_adjudications",
                        "variant_view",
                        "remaining_gaps",
                    )
                },
                "claims": claim_inputs,
            },
            "required_output_schema": {
                "claim_renderings": [
                    {
                        "claim_id": "exact supplied claim_id",
                        "analysis_text_zh_cn": "non-empty concise Chinese analysis",
                    }
                ]
            },
            "required_top_level_keys": ["claim_renderings"],
            "output_constraints": {
                "claim_rendering_cardinality": len(claim_inputs),
                "maximum_analysis_text_unicode_characters": 320,
                "all_claim_ids_exactly_once": True,
                "upstream_qualification_emitted_by_provider": False,
                "deterministic_lineage_fields_emitted_by_provider": False,
            },
            "additional_properties_allowed": False,
        }
        return system, request, {
            "memo_writer_transport_ref": S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
            "local_claim_surface_digest": canonical_digest(claim_surface),
        }

    @classmethod
    def _memo_writer_v3_request(
        cls,
        payload: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        specialists = payload.get("specialist_heads")
        lead = payload.get("cross_cell_lead")
        scoped_surface = payload.get("scoped_identity_surface")
        if (
            not isinstance(specialists, list)
            or not isinstance(lead, Mapping)
            or not isinstance(scoped_surface, Mapping)
        ):
            raise ValueError("s3_bounded_memo_writer_v3_input_missing")
        S3ThreeCellBoundedAgentExecutor._scoped_identity_indexes(
            specialists,
            scoped_surface,
        )
        claim_inputs = [
            {
                "claim_ref": CellScopedResearchIdentityPolicy.ref(
                    "claim",
                    str(row.get("program_cell_id") or ""),
                    str(claim.get("claim_id") or ""),
                ).to_payload(),
                "statement": str(claim.get("statement") or ""),
                "epistemic_status": str(
                    claim.get("epistemic_status") or ""
                ),
                "qualification": str(claim.get("qualification") or ""),
                "cannot_support": list(
                    claim.get("cannot_support") or ()
                ),
            }
            for row in specialists
            if isinstance(row, Mapping)
            for claim in row.get("judgment_layer", ())
            if isinstance(claim, Mapping)
        ]
        system = (
            "You are the no-source and no-tool internal Memo Writer. Return "
            "exactly one native JSON object with no markdown and no duplicate "
            "keys. Emit one claim_rendering for every supplied claim_ref, in "
            "the supplied order. Copy each exact three-field claim_ref without "
            "rewriting local_id, and write only a concise Chinese "
            "analysis_text_zh_cn. The runtime derives all other lineage and "
            "presentation fields. Do not call tools or sources, invent facts "
            "or numeric precision, promote Candidate or Graph context to "
            "evidence, expose private reasoning, or translate relationship-"
            "graph context as a chart."
        )
        request = {
            "node_id": "memo_writer",
            "memo_writer_transport_ref": (
                S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
            ),
            "analysis_input": {
                "input_digest": payload.get("input_digest"),
                "scoped_identity_contract_ref": (
                    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
                ),
                "lead_summary": {
                    key: deepcopy(lead.get(key))
                    for key in (
                        "conflict_adjudications",
                        "variant_view",
                        "remaining_gaps",
                    )
                },
                "claims": claim_inputs,
            },
            "required_output_schema": {
                "claim_renderings": [
                    {
                        "claim_ref": (
                            CellScopedResearchIdentityPolicy.wire_schema(
                                "claim"
                            )
                        ),
                        "analysis_text_zh_cn": (
                            "non-empty concise Chinese analysis"
                        ),
                    }
                ]
            },
            "required_top_level_keys": ["claim_renderings"],
            "output_constraints": {
                "claim_rendering_cardinality": len(claim_inputs),
                "maximum_analysis_text_unicode_characters": 320,
                "all_scoped_claim_refs_exactly_once": True,
                "raw_local_id_only_refs_allowed": False,
                "deterministic_lineage_fields_emitted_by_provider": False,
            },
            "additional_properties_allowed": False,
        }
        numeric_contracts = payload.get(
            "case_numeric_authority_contracts"
        )
        identity_projection = payload.get(
            "case_delivery_identity_projection"
        )
        if numeric_contracts is not None or identity_projection is not None:
            if (
                not isinstance(numeric_contracts, list)
                or not numeric_contracts
                or not isinstance(identity_projection, Mapping)
            ):
                raise ValueError(
                    "s4_case_writer_numeric_identity_contract_missing"
                )
            identity_policy = CaseDeliveryIdentityPolicy.from_projection(
                identity_projection
            )
            numeric_policy = CaseNumericAuthorityPolicy.from_prompt_contract(
                numeric_contracts[0]
            )
            request["case_numeric_authority_contracts"] = deepcopy(
                numeric_contracts
            )
            request["case_delivery_identity_projection"] = deepcopy(
                identity_projection
            )
            system += (
                " "
                + numeric_policy.provider_narrative_instruction()
                + " This rule applies to analysis_text_zh_cn."
                + identity_policy.provider_identity_boundary_instruction()
            )
        return system, request, {
            "memo_writer_transport_ref": (
                S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
            ),
            "scoped_identity_contract_ref": (
                S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
            ),
            "local_claim_surface_digest": canonical_digest(
                S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
                    specialists
                )
            ),
            "local_scoped_identity_surface_digest": canonical_digest(
                scoped_surface
            ),
        }

    @classmethod
    def _assemble_memo_writer_v2_output(
        cls,
        provider_output: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        if set(provider_output) != {"claim_renderings"}:
            raise S3MemoWriterContractError(
                failure_family="shape",
                failure_subtype="top_level_keys_mismatch",
                field_id="top_level",
                failing_item_count=1,
            )
        specialists = payload.get("specialist_heads")
        lead = payload.get("cross_cell_lead")
        lead_digest = str(payload.get("cross_cell_lead_digest") or "")
        if not isinstance(specialists, list) or not isinstance(lead, Mapping):
            raise S3MemoWriterContractError(
                failure_family="authority",
                failure_subtype="claim_ref_invalid",
                field_id="claim_renderings.claim_id",
                failing_item_count=1,
            )
        claim_surface = (
            S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
                specialists
            )
        )
        claims_in_order = [
            (str(row["program_cell_id"]), claim)
            for row in specialists
            for claim in row.get("judgment_layer", ())
            if isinstance(row, Mapping) and isinstance(claim, Mapping)
        ]
        expected_claim_ids = [str(claim["claim_id"]) for _, claim in claims_in_order]
        renderings = provider_output.get("claim_renderings")
        if not isinstance(renderings, list):
            raise S3MemoWriterContractError(
                failure_family="shape",
                failure_subtype="claim_rendering_schema_invalid",
                field_id="claim_renderings",
                failing_item_count=1,
            )
        if len(renderings) != len(expected_claim_ids):
            raise S3MemoWriterContractError(
                failure_family="cardinality",
                failure_subtype="claim_rendering_cardinality_mismatch",
                field_id="claim_renderings",
                failing_item_count=abs(len(renderings) - len(expected_claim_ids)),
            )
        analysis_by_claim_id: dict[str, str] = {}
        for rendering in renderings:
            if not isinstance(rendering, Mapping) or set(rendering) != {
                "claim_id",
                "analysis_text_zh_cn",
            }:
                raise S3MemoWriterContractError(
                    failure_family="shape",
                    failure_subtype="claim_rendering_schema_invalid",
                    field_id="claim_renderings",
                    failing_item_count=1,
                )
            claim_id = str(rendering.get("claim_id") or "")
            if claim_id not in expected_claim_ids:
                raise S3MemoWriterContractError(
                    failure_family="authority",
                    failure_subtype="claim_ref_invalid",
                    field_id="claim_renderings.claim_id",
                    failing_item_count=1,
                )
            if claim_id in analysis_by_claim_id:
                raise S3MemoWriterContractError(
                    failure_family="cardinality",
                    failure_subtype="claim_ref_duplicate",
                    field_id="claim_renderings.claim_id",
                    failing_item_count=1,
                )
            text = rendering.get("analysis_text_zh_cn")
            if not isinstance(text, str) or not text.strip():
                raise S3MemoWriterContractError(
                    failure_family="text",
                    failure_subtype="analysis_text_blank",
                    field_id="claim_renderings.analysis_text_zh_cn",
                    failing_item_count=1,
                )
            text = text.strip()
            if len(text) > 320:
                raise S3MemoWriterContractError(
                    failure_family="text",
                    failure_subtype="analysis_text_over_max_unicode_characters",
                    field_id="claim_renderings.analysis_text_zh_cn",
                    failing_item_count=1,
                )
            if "图表假设" in text or "图表关系" in text:
                raise S3MemoWriterContractError(
                    failure_family="semantic",
                    failure_subtype="graph_terminology_invalid",
                    field_id="claim_renderings.analysis_text_zh_cn",
                    failing_item_count=1,
                )
            analysis_by_claim_id[claim_id] = text
        if set(analysis_by_claim_id) != set(expected_claim_ids):
            raise S3MemoWriterContractError(
                failure_family="cardinality",
                failure_subtype="claim_rendering_cardinality_mismatch",
                field_id="claim_renderings",
                failing_item_count=1,
            )

        sections: list[dict[str, Any]] = []
        rendered_texts: list[str] = []
        exact_task_ids: list[str] = []
        for specialist in specialists:
            cell_id = str(specialist["program_cell_id"])
            claim_renderings: list[dict[str, Any]] = []
            for claim in specialist.get("judgment_layer", ()):
                claim_id = str(claim["claim_id"])
                analysis_text = analysis_by_claim_id[claim_id]
                status = str(claim.get("epistemic_status") or "")
                qualification = str(claim.get("qualification") or "").strip()
                rendered_text = (
                    f"{qualification}；{analysis_text}"
                    if status in {"hypothesis", "cannot_infer"} and qualification
                    else analysis_text
                )
                claim_renderings.append(
                    {
                        "claim_id": claim_id,
                        "rendered_text_zh_cn": rendered_text,
                        "epistemic_status": status,
                        "scope_digest": canonical_digest(claim["scope"]),
                        "qualification_preserved": True,
                    }
                )
                rendered_texts.append(rendered_text)
            task_refs = [
                str(task["task_id"])
                for task in specialist.get("what_would_change", ())
                if isinstance(task, Mapping)
            ]
            exact_task_ids.extend(task_refs)
            sections.append(
                {
                    "program_cell_id": cell_id,
                    "claim_renderings": claim_renderings,
                    "what_would_change_task_refs": task_refs,
                }
            )
        limitations = sorted(
            {
                str(boundary)
                for _, claim in claims_in_order
                for boundary in claim.get("cannot_support", ())
                if isinstance(boundary, str) and boundary.strip()
            }
        )
        return {
            "title_zh_cn": "NVDA 三单元内部研究备忘录",
            "executive_summary_zh_cn": "；".join(rendered_texts),
            "sections": sections,
            "limitations_zh_cn": limitations,
            "consumed_lead_digest": lead_digest,
            "consumed_claim_surface_digest": canonical_digest(claim_surface),
            "exact_claim_ids": expected_claim_ids,
            "exact_WWC_task_ids": exact_task_ids,
            "source_calls": 0,
            "tool_calls": 0,
        }

    @classmethod
    def _assemble_memo_writer_v3_output(
        cls,
        provider_output: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        if set(provider_output) != {"claim_renderings"}:
            raise S3MemoWriterContractError(
                failure_family="shape",
                failure_subtype="top_level_keys_mismatch",
                field_id="top_level",
                failing_item_count=1,
            )
        specialists = payload.get("specialist_heads")
        lead = payload.get("cross_cell_lead")
        lead_digest = str(payload.get("cross_cell_lead_digest") or "")
        scoped_surface = payload.get("scoped_identity_surface")
        if (
            not isinstance(specialists, list)
            or not isinstance(lead, Mapping)
            or not isinstance(scoped_surface, Mapping)
        ):
            raise S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            )
        indexes = S3ThreeCellBoundedAgentExecutor._scoped_identity_indexes(
            specialists,
            scoped_surface,
        )
        claims_in_order = [
            (
                str(row["program_cell_id"]),
                claim,
                CellScopedResearchIdentityPolicy.ref(
                    "claim",
                    str(row["program_cell_id"]),
                    str(claim["claim_id"]),
                ),
            )
            for row in specialists
            for claim in row.get("judgment_layer", ())
            if isinstance(row, Mapping) and isinstance(claim, Mapping)
        ]
        expected_keys = [ref.runtime_key for _, _, ref in claims_in_order]
        renderings = provider_output.get("claim_renderings")
        if not isinstance(renderings, list) or len(renderings) != len(
            expected_keys
        ):
            raise S3MemoWriterContractError(
                failure_family="cardinality",
                failure_subtype="claim_rendering_cardinality_mismatch",
                field_id="claim_renderings",
                failing_item_count=1,
            )
        analysis_by_key: dict[tuple[str, str, str], str] = {}
        for rendering in renderings:
            if not isinstance(rendering, Mapping) or set(rendering) != {
                "claim_ref",
                "analysis_text_zh_cn",
            }:
                raise S3MemoWriterContractError(
                    failure_family="shape",
                    failure_subtype="claim_rendering_schema_invalid",
                    field_id="claim_renderings",
                    failing_item_count=1,
                )
            raw_ref = rendering.get("claim_ref")
            if isinstance(raw_ref, str):
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind="claim",
                        failure_subtype="raw_local_id_cross_cell_ambiguous",
                        failing_item_count=1,
                    )
                )
            parsed = CellScopedResearchIdentityPolicy.parse(
                raw_ref,
                expected_kind="claim",
            )
            if isinstance(parsed, ScopedIdentityViolation):
                raise S3ScopedIdentityContractError(parsed)
            if parsed.runtime_key not in indexes["claim"]:
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind="claim",
                        failure_subtype="unknown_scoped_ref",
                        failing_item_count=1,
                    )
                )
            if parsed.runtime_key in analysis_by_key:
                raise S3ScopedIdentityContractError(
                    ScopedIdentityViolation(
                        identity_kind="claim",
                        failure_subtype="scoped_ref_duplicate",
                        failing_item_count=1,
                    )
                )
            text = rendering.get("analysis_text_zh_cn")
            if not isinstance(text, str) or not text.strip():
                raise S3MemoWriterContractError(
                    failure_family="text",
                    failure_subtype="analysis_text_blank",
                    field_id="claim_renderings.analysis_text_zh_cn",
                    failing_item_count=1,
                )
            text = text.strip()
            if len(text) > 320:
                raise S3MemoWriterContractError(
                    failure_family="text",
                    failure_subtype=(
                        "analysis_text_over_max_unicode_characters"
                    ),
                    field_id="claim_renderings.analysis_text_zh_cn",
                    failing_item_count=1,
                )
            if "图表假设" in text or "图表关系" in text:
                raise S3MemoWriterContractError(
                    failure_family="semantic",
                    failure_subtype="graph_terminology_invalid",
                    field_id="claim_renderings.analysis_text_zh_cn",
                    failing_item_count=1,
                )
            analysis_by_key[parsed.runtime_key] = text
        if set(analysis_by_key) != set(expected_keys):
            raise S3ScopedIdentityContractError(
                ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="unknown_scoped_ref",
                    failing_item_count=1,
                )
            )

        sections: list[dict[str, Any]] = []
        rendered_texts: list[str] = []
        exact_task_refs: list[dict[str, str]] = []
        numeric_contracts = payload.get(
            "case_numeric_authority_contracts"
        )
        numeric_policies = {
            policy.program_cell_id: policy
            for policy in (
                CaseNumericAuthorityPolicy.from_prompt_contract(
                    row
                )
                for row in (
                    numeric_contracts
                    if isinstance(numeric_contracts, list)
                    else ()
                )
            )
        }
        identity_projection = payload.get(
            "case_delivery_identity_projection"
        )
        if payload.get("s4_case_runtime") is not None and (
            not isinstance(numeric_contracts, list)
            or not numeric_contracts
            or not isinstance(identity_projection, Mapping)
        ):
            raise ValueError(
                "s4_case_runtime_writer_mandatory_numeric_identity_"
                "projection_missing"
            )
        identity_policy = (
            CaseDeliveryIdentityPolicy.from_projection(
                identity_projection
            )
            if isinstance(identity_projection, Mapping)
            else None
        )
        for specialist in specialists:
            cell_id = str(specialist["program_cell_id"])
            facts_by_id = {
                str(fact.get("fact_id") or ""): fact
                for fact in specialist.get("fact_layer", ())
                if isinstance(fact, Mapping)
            }
            claim_renderings: list[dict[str, Any]] = []
            for claim in specialist.get("judgment_layer", ()):
                claim_ref = CellScopedResearchIdentityPolicy.ref(
                    "claim", cell_id, str(claim["claim_id"])
                )
                analysis_text = analysis_by_key[claim_ref.runtime_key]
                status = str(claim.get("epistemic_status") or "")
                qualification = str(
                    claim.get("qualification") or ""
                ).strip()
                rendered_text = (
                    f"{qualification}；{analysis_text}"
                    if status in {"hypothesis", "cannot_infer"}
                    and qualification
                    else analysis_text
                )
                numeric_policy = numeric_policies.get(cell_id)
                if numeric_policy is not None:
                    numeric_refs = [
                        str(ref)
                        for fact_id in claim.get(
                            "support_fact_ids", ()
                        )
                        for ref in facts_by_id.get(
                            str(fact_id), {}
                        ).get("support_refs", ())
                        if facts_by_id.get(
                            str(fact_id), {}
                        ).get("support_type")
                        == "Numeric"
                    ]
                    clauses = (
                        numeric_policy.rendered_clauses_for_refs(
                            numeric_refs
                        )
                    )
                    if clauses:
                        rendered_text = (
                            "；".join(clauses)
                            + "；"
                            + rendered_text
                        )
                claim_renderings.append(
                    {
                        "claim_ref": claim_ref.to_payload(),
                        "rendered_text_zh_cn": rendered_text,
                        "epistemic_status": status,
                        "scope_digest": canonical_digest(claim["scope"]),
                        "qualification_preserved": True,
                    }
                )
                rendered_texts.append(rendered_text)
            task_refs = [
                CellScopedResearchIdentityPolicy.ref(
                    "what_would_change",
                    cell_id,
                    str(task["task_id"]),
                ).to_payload()
                for task in specialist.get("what_would_change", ())
                if isinstance(task, Mapping)
            ]
            exact_task_refs.extend(task_refs)
            sections.append(
                {
                    "program_cell_id": cell_id,
                    "claim_renderings": claim_renderings,
                    "what_would_change_task_refs": task_refs,
                }
            )
        limitations = sorted(
            {
                str(boundary)
                for _, claim, _ in claims_in_order
                for boundary in claim.get("cannot_support", ())
                if isinstance(boundary, str) and boundary.strip()
            }
        )
        return {
            "title_zh_cn": (
                identity_policy.title_zh_cn
                if identity_policy is not None
                else "NVDA 三单元内部研究备忘录"
            ),
            "executive_summary_zh_cn": "；".join(rendered_texts),
            "sections": sections,
            "limitations_zh_cn": limitations,
            "consumed_lead_digest": lead_digest,
            "consumed_claim_surface_digest": canonical_digest(
                S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
                    specialists
                )
            ),
            "consumed_scoped_identity_surface_digest": canonical_digest(
                scoped_surface
            ),
            "exact_claim_refs": [
                ref.to_payload() for _, _, ref in claims_in_order
            ],
            "exact_WWC_task_refs": exact_task_refs,
            "source_calls": 0,
            "tool_calls": 0,
        }

    @classmethod
    def _validate_node_output(
        cls,
        node_id: str,
        output: Mapping[str, Any],
        payload: Mapping[str, Any],
        *,
        output_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
    ) -> None:
        if node_id.startswith("domain_specialist:"):
            cell_input = payload.get("cell_input")
            if not isinstance(cell_input, Mapping):
                raise ValueError("s3_bounded_node_specialist_input_missing")
            S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
                output,
                cell_input,
                output_contract_ref=output_contract_ref,
            )
            return
        if node_id == "research_lead":
            digests = payload.get("specialist_output_digests")
            specialists = payload.get("specialist_outputs")
            if not isinstance(digests, Mapping) or not isinstance(specialists, list):
                raise ValueError("s3_bounded_node_lead_digest_input_missing")
            S3ThreeCellBoundedAgentExecutor._validate_lead_output(
                output,
                digests,
                specialist_outputs=specialists,
                scoped_identity_surface=(
                    payload.get("scoped_identity_surface")
                    if isinstance(
                        payload.get("scoped_identity_surface"), Mapping
                    )
                    else None
                ),
                output_contract_ref=output_contract_ref,
            )
            return
        if node_id == "memo_writer":
            S3ThreeCellBoundedAgentExecutor._validate_writer_output(
                output,
                str(payload.get("cross_cell_lead_digest") or ""),
                specialist_outputs=(
                    payload.get("specialist_heads")
                    if isinstance(payload.get("specialist_heads"), list)
                    else None
                ),
                cross_cell_lead=(
                    payload.get("cross_cell_lead")
                    if isinstance(payload.get("cross_cell_lead"), Mapping)
                    else None
                ),
                scoped_identity_surface=(
                    payload.get("scoped_identity_surface")
                    if isinstance(
                        payload.get("scoped_identity_surface"), Mapping
                    )
                    else None
                ),
                case_numeric_authority_contracts=(
                    payload.get("case_numeric_authority_contracts")
                    if isinstance(
                        payload.get(
                            "case_numeric_authority_contracts"
                        ),
                        list,
                    )
                    else None
                ),
                case_delivery_identity_projection=(
                    payload.get("case_delivery_identity_projection")
                    if isinstance(
                        payload.get(
                            "case_delivery_identity_projection"
                        ),
                        Mapping,
                    )
                    else None
                ),
                output_contract_ref=output_contract_ref,
            )
            return
        if node_id == "verifier":
            if output_contract_ref in {
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
            }:
                S3ThreeCellBoundedAgentExecutor._validate_owner_grade_verifier_input(
                    payload
                )
            S3ThreeCellBoundedAgentExecutor._validate_verifier_output(
                output,
                str(payload.get("cross_cell_lead_digest") or ""),
                str(payload.get("writer_digest") or ""),
                output_contract_ref=output_contract_ref,
                local_semantic_issues=[
                    str(value)
                    for value in payload.get("local_semantic_issues", ())
                    if isinstance(value, str)
                ],
                specialist_outputs=(
                    [
                        {
                            "program_cell_id": cell_id,
                            "judgment_layer": list(
                                payload["specialist_claim_cards"][cell_id][
                                    "claim_cards"
                                ]
                            ),
                            "what_would_change": list(
                                payload["specialist_claim_cards"][cell_id][
                                    "what_would_change"
                                ]
                            ),
                        }
                        for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS
                    ]
                    if isinstance(
                        payload.get("specialist_claim_cards"), Mapping
                    )
                    and isinstance(
                        payload.get("scoped_identity_surface"), Mapping
                    )
                    else None
                ),
                scoped_identity_surface=(
                    payload.get("scoped_identity_surface")
                    if isinstance(
                        payload.get("scoped_identity_surface"), Mapping
                    )
                    else None
                ),
            )
            return
        raise ValueError("s3_bounded_node_unknown_node")

    @classmethod
    def _agent_id(cls, node_id: str) -> str:
        if node_id.startswith("domain_specialist:"):
            cell_id = node_id.split(":", 1)[1]
            try:
                return cls._SPECIALIST_AGENT_BY_CELL[cell_id]
            except KeyError as exc:
                raise ValueError("s3_bounded_node_unknown_specialist_cell") from exc
        return {
            "research_lead": "research_lead",
            "memo_writer": "memo_writer",
            "verifier": "verifier",
        }[node_id]

    @classmethod
    def _version_bindings(
        cls, node_id: str, admission: S3ThreeCellBoundedAgentAdmission
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from sec_agent.agent_registry import select_agent_definition_versions
        from sec_agent.research_skills import select_skill_pack_version

        agent_version = select_agent_definition_versions([cls._agent_id(node_id)])[0]
        contract = dict(agent_version["contract"])
        skill_pack = select_skill_pack_version(
            agent_id=str(agent_version["agent_id"]),
            registered_skill_ids=tuple(contract.get("skill_ids") or ()),
            execution_profile_version_ref=admission.execution_profile_version_ref,
            allowed_execution_profile_refs=(admission.execution_profile_version_ref,),
        )
        return agent_version, skill_pack

    @staticmethod
    def _max_tokens(
        node_id: str, admission: S3ThreeCellBoundedAgentAdmission
    ) -> int:
        if node_id.startswith("domain_specialist:"):
            return admission.specialist_max_output_tokens
        return {
            "research_lead": admission.lead_max_output_tokens,
            "memo_writer": admission.writer_max_output_tokens,
            "verifier": admission.verifier_max_output_tokens,
        }[node_id]

    @staticmethod
    def _select_fields(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {}
        return {key: value[key] for key in fields if key in value}

    @classmethod
    def _specialist_model_view(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        cell_input = payload.get("cell_input")
        if not isinstance(cell_input, Mapping):
            raise ValueError("s3_bounded_node_specialist_input_missing")
        runtime = cell_input.get("runtime_branch")
        evidence = cell_input.get("evidence_input")
        numeric = cell_input.get("numeric_input")
        graph = cell_input.get("graph_context_input")
        authority = cell_input.get("authority_refs")
        if not all(
            isinstance(value, Mapping)
            for value in (runtime, evidence, numeric, graph, authority)
        ):
            raise ValueError("s3_bounded_specialist_model_view_input_invalid")

        specialist_context = next(
            (
                row
                for row in cell_input.get("role_contexts", ())
                if isinstance(row, Mapping) and row.get("target_node") == "domain_specialist"
            ),
            None,
        )
        if not isinstance(specialist_context, Mapping):
            raise ValueError("s3_bounded_specialist_model_view_authority_missing")

        candidate_bundle = evidence.get("candidate_bundle")
        candidates = (
            candidate_bundle.get("candidates", ())
            if isinstance(candidate_bundle, Mapping)
            else ()
        )
        promotion = evidence.get("promotion_assessment")
        source_boundary = evidence.get("sourcehunter_boundary")
        graph_observation = evidence.get("graph_observation")
        source_followup = evidence.get("source_followup_request")
        fundamental = numeric.get("fundamental_decision_cell")
        decision_cell = graph.get("decision_cell")

        model_view = {
            "program_cell_id": str(cell_input.get("program_cell_id") or ""),
            "decision_contract": cls._select_fields(
                runtime,
                (
                    "decision_question",
                    "mandatory_judgment_chain",
                    "stop_rule",
                    "what_would_change",
                    "branch_state",
                    "observation",
                ),
            ),
            "specialist_authority": {
                "owner_role": runtime.get("owner_role"),
                "evidence_role": runtime.get("evidence_role"),
                "authority": dict(specialist_context.get("authority") or {}),
            },
            "evidence_view": {
                "route_outcome": evidence.get("route_outcome"),
                "candidates_not_evidence": [
                    cls._select_fields(
                        row,
                        (
                            "candidate_id",
                            "document_id",
                            "document_version",
                            "source_policy_ref",
                            "route_id",
                            "source_role",
                            "source_authority_rank",
                            "entity_ref",
                            "period_ref",
                            "section_or_table_ref",
                            "content_ref",
                        ),
                    )
                    for row in candidates
                    if isinstance(row, Mapping)
                ],
                "promotion": cls._select_fields(
                    promotion,
                    (
                        "decision",
                        "candidate_refs",
                        "context_refs",
                        "rejected_refs",
                        "typed_gap_codes",
                        "accepted_evidence_refs",
                        "evidence_gate_owner_ref",
                    ),
                ),
                "source_boundary": cls._select_fields(
                    source_boundary,
                    (
                        "status",
                        "trigger_reason",
                        "boundary_contract_ref",
                        "source_followup_request_ref",
                        "exact_network_admission_required",
                        "network_execution_authorized",
                        "external_tool_execution_authorized",
                    ),
                ),
                "graph_observation": cls._select_fields(
                    graph_observation,
                    (
                        "program_cell_id",
                        "candidate_id",
                        "observation_class",
                        "relation_hypothesis",
                        "source_followup_required",
                        "direct_evidence_authorized",
                        "numeric_authority",
                    ),
                ) if graph_observation is not None else None,
                "source_followup_request": cls._select_fields(
                    source_followup,
                    (
                        "program_cell_id",
                        "originating_graph_observation_ref",
                        "target_route_id",
                        "objective",
                        "status",
                        "execution_admission",
                    ),
                ) if source_followup is not None else None,
            },
            "numeric_view": {
                "decision_boundary": cls._select_fields(
                    fundamental,
                    (
                        "availability",
                        "typed_cannot_infer",
                        "support_boundary",
                        "specialist_input_eligible",
                        "narrative_fill_authorized",
                    ),
                ),
                "selected_financial_rows": [
                    {
                        **cls._select_fields(
                            row,
                            (
                                "financial_row_id",
                                "evidence_ref",
                                "normalized_value",
                                "scale_multiplier",
                                "authority_scope",
                            ),
                        ),
                        "selector": cls._select_fields(
                            row.get("selector"),
                            (
                                "entity_ref",
                                "segment_ref",
                                "period",
                                "currency",
                                "unit",
                                "row_label",
                                "metric_family",
                            ),
                        ),
                    }
                    for row in numeric.get("selected_financial_rows", ())
                    if isinstance(row, Mapping)
                ],
                "derived_metrics": [
                    {
                        **cls._select_fields(
                            row,
                            (
                                "derived_metric_id",
                                "metric_family",
                                "formula",
                                "formula_version_ref",
                                "evidence_refs",
                                "rounding_rule",
                                "result_value",
                                "result_unit",
                                "support_boundary",
                                "cannot_support",
                            ),
                        ),
                        "inputs": [
                            cls._select_fields(
                                metric_input,
                                (
                                    "financial_row_ref",
                                    "evidence_ref",
                                    "metric_family",
                                    "normalized_value",
                                ),
                            )
                            for metric_input in row.get("inputs", ())
                            if isinstance(metric_input, Mapping)
                        ],
                    }
                    for row in numeric.get("derived_metrics", ())
                    if isinstance(row, Mapping)
                ],
            },
            "graph_view": {
                "product_industry": [
                    cls._select_fields(
                        row,
                        (
                            "contract_ref",
                            "status",
                            "candidate_refs",
                            "typed_gaps",
                            "direct_evidence_authorized",
                            "projection_input_ref",
                        ),
                    )
                    for row in graph.get("product_industry_inputs", ())
                    if isinstance(row, Mapping)
                ],
                "method_contracts": [
                    cls._select_fields(
                        row,
                        (
                            "contract_ref",
                            "role_ids",
                            "method_ids",
                            "allowed_output",
                            "forbidden_output",
                            "authority_grants",
                            "contract_version_ref",
                        ),
                    )
                    for row in graph.get("skill_contracts", ())
                    if isinstance(row, Mapping)
                ],
                "edges": [
                    cls._select_fields(
                        row,
                        (
                            "edge_projection_id",
                            "use_case",
                            "edge_type",
                            "authority_mode",
                            "claim_boundary",
                            "forbidden_claims",
                            "evidence_status",
                            "conflict_status",
                            "direct_evidence_authorized",
                            "numeric_authority",
                        ),
                    )
                    for row in graph.get("graph_edges", ())
                    if isinstance(row, Mapping)
                ],
                "market_contexts": [
                    cls._select_fields(
                        row,
                        (
                            "market_context_id",
                            "status",
                            "required_source_families",
                            "context_refs",
                            "authority",
                            "exact_market_fact_authorized",
                        ),
                    )
                    for row in graph.get("market_price_in_contexts", ())
                    if isinstance(row, Mapping)
                ],
                "risk_contexts": [
                    cls._select_fields(
                        row,
                        (
                            "risk_context_id",
                            "risk_type",
                            "graph_edge_projection_ref",
                            "impact_mechanism",
                            "probability_status",
                            "financial_impact_status",
                            "support_boundary",
                            "what_would_change",
                            "evidence_status",
                        ),
                    )
                    for row in graph.get("risk_contexts", ())
                    if isinstance(row, Mapping)
                ],
                "typed_gaps": (
                    list(decision_cell.get("typed_gaps", ()))
                    if isinstance(decision_cell, Mapping)
                    else []
                ),
            },
            "authority_refs": dict(authority),
        }
        s4_case_method = cell_input.get("s4_case_method")
        if isinstance(s4_case_method, Mapping):
            model_view["s4_case_method"] = dict(s4_case_method)
        return model_view

    @classmethod
    def _node_request(
        cls,
        node_id: str,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        common = (
            "Return exactly one native JSON object with no markdown and no duplicate keys. "
            "Use only analysis_input. Do not call tools or sources, add citations, promote "
            "Candidate or Graph context to fact authority, invent numeric precision, or expose "
            "private reasoning. Preserve typed gaps and what-would-change boundaries."
        )
        output_constraints: dict[str, Any] = {}
        output_state_machine: dict[str, Any] | None = None
        if node_id.startswith("domain_specialist:"):
            schema: Mapping[str, Any] = {
                "program_cell_id": "exact input program_cell_id",
                "fact_layer": [
                    {
                        "fact_id": "string",
                        "statement": "string",
                        "support_type": "Evidence|Numeric",
                        "support_refs": ["exact authorized ref"],
                        "boundary": "string",
                    }
                ],
                "explanation_layer": ["string"],
                "judgment_layer": ["string"],
                "remaining_gaps": ["string"],
                "what_would_change": ["string"],
                "terminal_class": "non-empty string",
            }
            role = "You are the exact decision-cell financial research specialist. "
            analysis_input = dict(payload)
            model_view_binding: dict[str, str] = {}
            if (
                admission.output_contract_ref in {
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
                }
            ):
                model_view = cls._specialist_model_view(payload)
                model_view_digest = canonical_digest(model_view)
                analysis_input = {
                    "input_contract_ref": payload.get("input_contract_ref"),
                    "input_digest": payload.get("input_digest"),
                    "model_view_contract_ref": S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
                    "model_view_digest": model_view_digest,
                    "cell_input": model_view,
                    "required_output_layers": list(
                        payload.get("required_output_layers") or ()
                    ),
                }
                model_view_binding = {
                    "model_view_contract_ref": S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
                    "model_view_digest": model_view_digest,
                }
                output_constraints = {
                    "fact_layer_cardinality": "0..3",
                    "explanation_layer_cardinality": "1..3",
                    "judgment_layer_cardinality": "1..2",
                    "remaining_gaps_cardinality": "1..4",
                    "what_would_change_cardinality": "1..3",
                    "maximum_narrative_item_unicode_characters": 320,
                    "maximum_serialized_utf8_bytes": 6000,
                }
                common += (
                    " Obey every cardinality, character, and byte limit; prefer concise "
                    "typed boundaries over repetition."
                )
                if (
                    admission.output_contract_ref
                    in {
                        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
                    }
                ):
                    schema = {
                        **schema,
                        "judgment_layer": [
                            {
                                "claim_id": "unique string",
                                "statement": "string",
                                "epistemic_status": (
                                    "fact_supported|bounded_inference|hypothesis|cannot_infer"
                                ),
                                "support_fact_ids": ["exact fact_id"],
                                "context_refs": ["exact Candidate or Graph context ref"],
                                "scope": {
                                    "entity_ref": "string",
                                    "business_scope_kind": (
                                        "company_total|segment|product|value_chain|unknown"
                                    ),
                                    "business_scope_ref": "string",
                                    "period": "string",
                                    "metric_or_mechanism": "string",
                                    "attribution_level": (
                                        "company_total|segment|product|cross_chain|none"
                                    ),
                                },
                                "qualification": "string; required for hypothesis",
                                "cannot_support": ["non-empty boundary for cannot_infer"],
                            }
                        ],
                        "what_would_change": [
                            {
                                "task_id": "unique string",
                                "claim_id": "exact claim_id",
                                "source_target": {
                                    "source_type": "string",
                                    "entity_or_owner": "string",
                                    "document_event_or_dataset": "string",
                                },
                                "metric_or_observation": "string",
                                "decision_rule": {
                                    "rule_type": "string",
                                    "comparator_or_condition": "string",
                                    "threshold_or_observation": "string",
                                },
                                "time_window": {
                                    "as_of": "string",
                                    "start_or_trigger": "string",
                                    "deadline_or_review_date": "string",
                                },
                                "expected_claim_transition": "string",
                                "fallback_stop_condition": "string",
                                "authority_refs": ["exact routing ref"],
                            }
                        ],
                    }
                    common += (
                        " The judgment_layer follows "
                        f"{S3_OWNER_GRADE_CLAIM_CARD_CONTRACT_REF}; what_would_change "
                        f"follows {S3_ACTIONABLE_WHAT_WOULD_CHANGE_CONTRACT_REF}."
                    )
        elif node_id == "research_lead":
            schema: Mapping[str, Any] = {
                "cell_heads": [
                    {
                        "program_cell_id": "exact cell id",
                        "specialist_output_digest": "exact supplied digest",
                    }
                ],
                "cross_cell_dependencies": ["string"],
                "conflict_adjudications": ["string"],
                "variant_view": "non-empty string",
                "remaining_gaps": ["string"],
            }
            role = "You are the cross-cell Research Lead. "
            analysis_input = dict(payload)
            model_view_binding = {}
            if (
                admission.output_contract_ref
                in {
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
                }
            ):
                schema = {
                    "cell_heads": [
                        {
                            "program_cell_id": "exact cell id",
                            "specialist_output_digest": "exact supplied digest",
                            "terminal_class": "exact Specialist terminal_class",
                            "evidence_fact_count": "integer recomputed from Specialist",
                            "numeric_fact_count": "integer recomputed from Specialist",
                            "claim_state_counts": {
                                status: "integer" for status in S3_OWNER_GRADE_CLAIM_STATUSES
                            },
                        }
                    ],
                    "cross_cell_dependencies": [
                        {
                            "dependency_id": "unique string",
                            "statement": "string",
                            "claim_ids": ["exact claim_id"],
                        }
                    ],
                    "conflict_adjudications": [
                        {
                            "adjudication_id": "unique string",
                            "involved_claim_ids": ["exact claim_id"],
                            "terminal_state_summary": "string",
                            "fact_presence_summary": (
                                "facts_present|no_facts_present|mixed_fact_presence"
                            ),
                            "resolution_status": "string",
                            "statement": "string",
                        }
                    ],
                    "variant_view": {
                        "statement": "string",
                        "claim_ids": ["exact claim_id"],
                        "what_would_change_task_ids": ["exact task_id"],
                    },
                    "remaining_gaps": [
                        {
                            "gap_id": "unique string",
                            "statement": "string",
                            "claim_ids": ["exact claim_id"],
                            "what_would_change_task_ids": ["exact task_id"],
                        }
                    ],
                }
        elif node_id == "memo_writer":
            schema = {
                "title_zh_cn": "string",
                "executive_summary_zh_cn": "string",
                "sections": [
                    {"program_cell_id": "exact cell id", "content_zh_cn": "string"}
                ],
                "limitations_zh_cn": ["string"],
                "consumed_lead_digest": "exact supplied digest",
                "source_calls": 0,
                "tool_calls": 0,
            }
            role = "You are the no-source and no-tool internal Memo Writer. "
            analysis_input = dict(payload)
            model_view_binding = {}
            if (
                admission.output_contract_ref
                == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
            ):
                claim_surface = S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
                    list(payload.get("specialist_heads") or ())
                )
                schema = {
                    "title_zh_cn": "exactly NVDA 三单元内部研究备忘录",
                    "executive_summary_zh_cn": (
                        "join every rendered_text_zh_cn exactly with ； in section and claim order"
                    ),
                    "sections": [
                        {
                            "program_cell_id": "exact cell id",
                            "claim_renderings": [
                                {
                                    "claim_id": "exact claim_id",
                                    "rendered_text_zh_cn": "string",
                                    "epistemic_status": "exact upstream status",
                                    "scope_digest": "canonical digest of exact upstream scope",
                                    "qualification_preserved": True,
                                }
                            ],
                            "what_would_change_task_refs": ["exact task_id"],
                        }
                    ],
                    "limitations_zh_cn": [
                        "every unique upstream cannot_support string exactly once in sorted order"
                    ],
                    "consumed_lead_digest": "exact supplied digest",
                    "consumed_claim_surface_digest": canonical_digest(claim_surface),
                    "exact_claim_ids": ["every exact upstream claim_id once"],
                    "exact_WWC_task_ids": ["every exact upstream task_id once"],
                    "source_calls": 0,
                    "tool_calls": 0,
                }
        elif node_id == "verifier":
            schema = {
                "findings": [
                    {
                        "layer": "exact required layer",
                        "status": "pass|review_required|fail",
                        "issues": ["string"],
                    }
                ],
                "bound_lead_digest": "exact supplied digest",
                "bound_writer_digest": "exact supplied digest",
                "decision": "accept_for_internal_review|repair|reject",
            }
            role = "You are the four-layer independent Verifier. "
            analysis_input = dict(payload)
            model_view_binding = {}
            if (
                admission.output_contract_ref
                in S3_TYPED_VERIFIER_OUTPUT_CONTRACT_REFS
            ):
                S3ThreeCellBoundedAgentExecutor._validate_owner_grade_verifier_input(
                    payload
                )
                schema = {
                    "findings": [
                        {
                            "layer": "exact required layer",
                            "status": "pass|review_required|fail",
                            "issue_codes": ["typed issue code"],
                            "artifact_or_claim_refs": [
                                CellScopedResearchIdentityPolicy.wire_schema(
                                    "claim"
                                )
                            ],
                            "repair_owner": (
                                "JSON null when status is pass; otherwise a "
                                "nonblank string naming a real repair owner"
                            ),
                        }
                    ],
                    "bound_lead_digest": "exact supplied digest",
                    "bound_writer_digest": "exact supplied digest",
                    "decision": "accept_for_internal_review|repair|reject",
                }
                output_state_machine = {
                    "contract_ref": S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
                    "finding_rules": {
                        "pass": {
                            "issue_codes": "must_be_empty",
                            "artifact_or_claim_refs": "must_be_empty",
                            "repair_owner": "must_be_JSON_null",
                        },
                        "review_required": {
                            "issue_codes": "must_be_nonempty_typed_strings",
                            "artifact_or_claim_refs": "must_be_nonempty_exact_refs",
                            "repair_owner": (
                                "must_be_nonblank_string_and_not_literal_none"
                            ),
                        },
                        "fail": {
                            "issue_codes": "must_be_nonempty_typed_strings",
                            "artifact_or_claim_refs": "must_be_nonempty_exact_refs",
                            "repair_owner": (
                                "must_be_nonblank_string_and_not_literal_none"
                            ),
                        },
                    },
                    "decision_rules": {
                        "accept_for_internal_review": (
                            "iff every layer is pass and local_semantic_issues is empty"
                        ),
                        "repair": (
                            "iff at least one layer is review_required and no layer is fail"
                        ),
                        "reject": "iff any layer is fail",
                    },
                    "literal_JSON_examples": {
                        "pass_repair_owner": None,
                        "review_required_repair_owner": "research_lead",
                        "fail_repair_owner": "specialist",
                        "literal_string_none_allowed": False,
                    },
                    "normalization_or_silent_rewrite_allowed": False,
                }
                output_constraints.update(
                    {
                        "exact_ref_contract_ref": (
                            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
                        ),
                        "artifact_or_claim_refs_current_supported_kind": (
                            "claim"
                        ),
                        "deterministic_owned_checks": [
                            "lead_and_writer_digest_binding",
                            "claim_scope_digest_derivation",
                            "typed_scoped_reference_membership",
                        ],
                        "semantic_finding_policy": {
                            "hard_integrity": (
                                "flag only an unsupported material claim, "
                                "numeric attribution, scope overreach, omitted "
                                "material counterevidence, or changed "
                                "epistemic qualification"
                            ),
                            "quality_finding": (
                                "an explicitly disclosed unresolved conflict "
                                "or company-total metric that remains clearly "
                                "unattributed may be retained as analytical "
                                "quality debt and is not by itself an integrity "
                                "failure"
                            ),
                            "scope_digest_mismatch": (
                                "deterministic-owned; do not emit unless "
                                "analysis_input contains an explicit local "
                                "mismatch observation"
                            ),
                        },
                    }
                )
                common += (
                    " Obey output_state_machine exactly; derive decision from finding "
                    "statuses and never label a finding pass while attaching issues, refs, "
                    "or a repair owner. Emit JSON null (not the string \"none\") for "
                    "repair_owner on every pass finding; emit a nonblank real-owner "
                    "string for review_required or fail. Use only exact typed scoped "
                    "Claim refs from analysis_input. Treat deterministic-owned digest "
                    "and scope bindings as authoritative. Do not turn an explicitly "
                    "preserved cannot-infer conflict or clearly company-total, "
                    "unattributed metric into an integrity failure by itself."
                )
        else:
            raise ValueError("s3_bounded_node_unknown_node")
        request = {
            "node_id": node_id,
            "analysis_input": analysis_input,
            "required_output_schema": schema,
            "required_top_level_keys": list(schema),
            "output_constraints": output_constraints,
            **(
                {"output_state_machine": output_state_machine}
                if output_state_machine is not None
                else {}
            ),
            "additional_properties_allowed": False,
        }
        if (
            admission.case_numeric_authority_policy_ref
            in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
        ):
            numeric_contracts = payload.get(
                "case_numeric_authority_contracts"
            )
            identity_projection = payload.get(
                "case_delivery_identity_projection"
            )
            if (
                not isinstance(numeric_contracts, list)
                or not numeric_contracts
                or not isinstance(identity_projection, Mapping)
            ):
                raise ValueError(
                    "s4_case_verifier_numeric_identity_contract_missing"
                )
            identity_policy = CaseDeliveryIdentityPolicy.from_projection(
                identity_projection
            )
            numeric_policy = CaseNumericAuthorityPolicy.from_prompt_contract(
                numeric_contracts[0]
            )
            request["case_numeric_authority_contracts"] = deepcopy(
                numeric_contracts
            )
            request["case_delivery_identity_projection"] = deepcopy(
                identity_projection
            )
            common += (
                " "
                + numeric_policy.provider_narrative_instruction()
                + (
                    " This rule applies to issue codes and repair text. Numeric "
                    "truth is independently recomputed by local L1 validators."
                )
                + identity_policy.provider_identity_boundary_instruction()
            )
        return role + common, request, model_view_binding

    @staticmethod
    def _stop(
        state: Mapping[str, Any],
        node_id: str,
        failure_code: str,
        *,
        segmented_specialist_shape: Mapping[str, Any] | None = None,
        segmented_specialist_text: Mapping[str, Any] | None = None,
        segmented_specialist_authority: Mapping[str, Any] | None = None,
        segmented_specialist_fact_authority: Mapping[str, Any] | None = None,
        segmented_specialist_claim_fact_link: Mapping[str, Any] | None = None,
        segmented_specialist_task_claim_link: Mapping[str, Any] | None = None,
        segmented_specialist_WWC_judgment_atom: (
            Mapping[str, Any] | None
        ) = None,
        segmented_specialist_what_would_change_authority: (
            Mapping[str, Any] | None
        ) = None,
        segmented_specialist_epistemic_status: Mapping[str, Any] | None = None,
        specialist_local_assembly_capacity: Mapping[str, Any] | None = None,
        research_lead_contract: Mapping[str, Any] | None = None,
        memo_writer_contract: Mapping[str, Any] | None = None,
        scoped_identity_contract: Mapping[str, Any] | None = None,
        verifier_state_machine: Mapping[str, Any] | None = None,
        case_numeric_authority: Mapping[str, Any] | None = None,
        case_delivery_identity: Mapping[str, Any] | None = None,
        strict_truth_kernel: Mapping[str, Any] | None = None,
        fact_candidate_pool: Mapping[str, Any] | None = None,
    ) -> None:
        receipts = [
            dict(row)
            for row in state.get("usage_receipts", ())
            if isinstance(row, Mapping)
        ]
        raise BoundedAgentExecutionError(
            node_id,
            usage_receipts=receipts,
            estimated_cost_usd=float(state.get("spent_usd") or 0.0),
            failure_codes=(failure_code,),
            segmented_specialist_shape=segmented_specialist_shape,
            segmented_specialist_text=segmented_specialist_text,
            segmented_specialist_authority=segmented_specialist_authority,
            segmented_specialist_fact_authority=(
                segmented_specialist_fact_authority
            ),
            segmented_specialist_claim_fact_link=(
                segmented_specialist_claim_fact_link
            ),
            segmented_specialist_task_claim_link=(
                segmented_specialist_task_claim_link
            ),
            segmented_specialist_WWC_judgment_atom=(
                segmented_specialist_WWC_judgment_atom
            ),
            segmented_specialist_what_would_change_authority=(
                segmented_specialist_what_would_change_authority
            ),
            segmented_specialist_epistemic_status=(
                segmented_specialist_epistemic_status
            ),
            specialist_local_assembly_capacity=(
                specialist_local_assembly_capacity
            ),
            research_lead_contract=research_lead_contract,
            memo_writer_contract=memo_writer_contract,
            scoped_identity_contract=scoped_identity_contract,
            verifier_state_machine=verifier_state_machine,
            case_numeric_authority=case_numeric_authority,
            case_delivery_identity=case_delivery_identity,
            strict_truth_kernel=strict_truth_kernel,
            fact_candidate_pool=fact_candidate_pool,
            provider_output_captures=[
                dict(row)
                for row in state.get("provider_output_captures", ())
                if isinstance(row, Mapping)
            ],
            local_fact_receipts=[
                dict(row)
                for row in state.get("local_fact_receipts", ())
                if isinstance(row, Mapping)
            ],
        )


def build_s3_three_cell_bounded_agent_executor_for_admission(
    admission: S3ThreeCellBoundedAgentAdmission,
    *,
    chat_completion_fn: Callable[..., Mapping[str, Any]] | None = None,
    responses_completion_fn: Callable[
        ..., Mapping[str, Any]
    ] | None = None,
) -> S3ThreeCellBoundedAgentExecutor:
    """Build the only provider adapter explicitly bound by an exact S3 admission."""

    admission.assert_profile_admissible()
    if not admission.execution_enabled:
        raise ValueError("s3_exact_executor_requires_enabled_admission")
    if admission.transport_ref not in (
        S3_THREE_CELL_DEEPSEEK_SEGMENTED_TRANSPORT_REF,
        *S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS,
    ):
        raise ValueError("s3_bounded_admission_transport_unsupported")
    return S3ThreeCellBoundedAgentExecutor(
        DeepSeekS3ThreeCellNodeExecutor(
            chat_completion_fn=chat_completion_fn,
            responses_completion_fn=responses_completion_fn,
            strict_truth_kernel_adapter=(
                StrictTruthKernelJsonSchemaAdapter()
                if admission.strict_truth_kernel_policy_ref
                == S4_STRICT_TRUTH_KERNEL_POLICY_REF
                else None
            ),
        )
    )


def build_bounded_agent_executor_for_admission(
    admission: BoundedAgentAdmission,
) -> DeepSeekBoundedAgentExecutor:
    """Build only the executor adapter explicitly bound by an exact admission."""

    admission.assert_profile_admissible()
    admission.assert_specialist_transport_binding()
    transport_ref = admission.resolved_specialist_transport_ref()
    if transport_ref == BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF:
        return DeepSeekBoundedAgentExecutor()
    if transport_ref == BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF:
        return DeepSeekBoundedAgentExecutor(segmented_specialist_lead=True)
    if transport_ref == BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF:
        return DeepSeekBoundedAgentExecutor(
            native_json_schema_adapter=NativeJsonSchemaResponseAdapter()
        )
    raise ValueError("bounded_admission_specialist_transport_unsupported")
