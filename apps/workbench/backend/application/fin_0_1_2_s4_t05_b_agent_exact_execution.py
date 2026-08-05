from __future__ import annotations

from typing import Any, Mapping

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3ThreeCellBoundedAgentInputPack,
)
from apps.workbench.backend.application.case_service import CasePrincipal
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
    predict_work_unit_id,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (
    CONTRACT_REF as T05_TRANSFER_CONTRACT_REF,
    validate_transfer_evidence_pack,
)
from apps.workbench.backend.application.research_runtime import (
    S3ThreeCellPreparedExecution,
    predict_fin01_attempt_and_run_ids,
)
from sec_agent.canonical_runtime.models import canonical_digest


EXECUTION_ENVELOPE_SCHEMA = (
    "fin_ia_0_1_2_s4_t05_b_dell_agent_exact_execution_envelope_v1_0"
)
INPUT_CAPACITY_CONTRACT_REF = (
    "fin_0_1_2.S4.T05_B.DELL.current_agent_compiled_capacity:v1"
)
MAXIMUM_INPUT_TOKENS = 108000
MAXIMUM_OUTPUT_TOKENS = 10000
MAXIMUM_TOTAL_COST_USD = 0.06
COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS = 117931


class Fin012S4T05BAgentExecutionError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def prepare_t05_b_dell_agent_execution(
    input_pack: S3ThreeCellBoundedAgentInputPack,
    evidence_pack: Mapping[str, Any],
    *,
    principal: CasePrincipal,
    execution_identity: str,
    attempt_no: int = 1,
) -> S3ThreeCellPreparedExecution:
    current = validate_transfer_evidence_pack(evidence_pack, case_key="DELL")
    if not execution_identity.strip():
        raise Fin012S4T05BAgentExecutionError(
            "s4_t05_b_agent_execution_identity_missing"
        )
    if (
        input_pack.company != "DELL"
        or "oracle" in input_pack.case_id
        or not input_pack.case_id.startswith(
            "fin012-s4-t05-dell-current-evidence-"
        )
        or input_pack.decision_surface_contract_ref != T05_TRANSFER_CONTRACT_REF
        or input_pack.lineage["S4_T04_source_grounded_input"]["digest"]
        != current["evidence_pack_digest"]
        or input_pack.input_digest
        != canonical_digest(
            input_pack.model_dump(mode="json", exclude={"input_digest"})
        )
    ):
        raise Fin012S4T05BAgentExecutionError(
            "s4_t05_b_agent_exact_input_binding_invalid"
        )
    work_unit_id = predict_work_unit_id(
        tenant_id=principal.tenant_id,
        project_id=principal.project_id,
        case_id=input_pack.case_id,
        contract_version_id=T05_TRANSFER_CONTRACT_REF,
        work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        execution_identity=execution_identity,
    )
    attempt_id, research_run_id = predict_fin01_attempt_and_run_ids(
        work_unit_id=work_unit_id,
        execution_profile_version_ref=S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        attempt_no=attempt_no,
    )
    digest_payload = {
        "case_id": input_pack.case_id,
        "case_version": input_pack.case_version,
        "decision_surface_contract_ref": T05_TRANSFER_CONTRACT_REF,
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "research_run_id": research_run_id,
        "execution_identity": execution_identity,
        "input_digest": input_pack.input_digest,
    }
    return S3ThreeCellPreparedExecution(
        **digest_payload,
        input_pack=input_pack,
        preparation_digest=canonical_digest(digest_payload),
        observed_counts={
            "canonical_writes": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
    )


def compile_t05_b_dell_agent_execution_envelope(
    prepared: S3ThreeCellPreparedExecution,
    evidence_pack: Mapping[str, Any],
    *,
    admission_ref: str,
    projected_per_call_input_tokens: tuple[int, ...],
) -> dict[str, Any]:
    current = validate_transfer_evidence_pack(evidence_pack, case_key="DELL")
    if (
        prepared.input_pack.lineage["S4_T04_source_grounded_input"]["digest"]
        != current["evidence_pack_digest"]
        or len(projected_per_call_input_tokens) != 9
        or min(projected_per_call_input_tokens) <= 0
        or sum(projected_per_call_input_tokens) > MAXIMUM_INPUT_TOKENS
    ):
        raise Fin012S4T05BAgentExecutionError(
            "s4_t05_b_agent_capacity_or_lineage_invalid"
        )
    hard_budget = {
        "semantic_model_calls": 9,
        "provider_calls": 9,
        "execution_network_calls": 9,
        "maximum_transport_attempts_per_call": 1,
        "retry_budget": 0,
        "fallback_budget": 0,
        "provider_hopping_budget": 0,
        "maximum_input_tokens": MAXIMUM_INPUT_TOKENS,
        "maximum_output_tokens": MAXIMUM_OUTPUT_TOKENS,
        "maximum_total_cost_usd": MAXIMUM_TOTAL_COST_USD,
        "maximum_wall_clock_seconds": 900,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "failed_output_business_promotions": 0,
    }
    body = {
        "schema_version": EXECUTION_ENVELOPE_SCHEMA,
        "status": "fresh_T05_B_DELL_Agent_exact_execution_not_started",
        "admission_ref": admission_ref,
        "current_evidence": {
            "evidence_pack_digest": current["evidence_pack_digest"],
            "t03_terminal_digest": current["t03_terminal_digest"],
            "evidence_numeric_gap_counts": [
                len(current["evidence_rows"]),
                len(current["numeric_rows"]),
                len(current["typed_gaps"]),
            ],
        },
        "fresh_t03": {
            "execution_identity": prepared.execution_identity,
            "work_unit_id": prepared.work_unit_id,
            "attempt_id": prepared.attempt_id,
            "research_run_id": prepared.research_run_id,
            "input_digest": prepared.input_digest,
            "preparation_digest": prepared.preparation_digest,
        },
        "hard_budget": hard_budget,
        "input_capacity_contract": {
            "contract_ref": INPUT_CAPACITY_CONTRACT_REF,
            "per_interaction_estimated_input_tokens": list(
                projected_per_call_input_tokens
            ),
            "aggregate_estimated_input_tokens": sum(
                projected_per_call_input_tokens
            ),
            "maximum_single_interaction_estimated_input_tokens": max(
                projected_per_call_input_tokens
            ),
            "maximum_input_tokens": MAXIMUM_INPUT_TOKENS,
            "input_token_headroom": MAXIMUM_INPUT_TOKENS
            - sum(projected_per_call_input_tokens),
            "cost_derived_absolute_maximum_input_tokens": (
                COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS
            ),
            "pricing_assumption_usd_per_million": {
                "input_cache_miss": 0.435,
                "output": 0.87,
            },
            "reserved_maximum_output_tokens": MAXIMUM_OUTPUT_TOKENS,
            "maximum_total_cost_usd": MAXIMUM_TOTAL_COST_USD,
            "minimum_cost_headroom_usd": 0.00432,
            "requires_zero_call_full_chain_capacity_proof": True,
        },
        "observed_counts": {
            "credential_reads_or_probes": 0,
            "admissions_consumed": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_artifacts": 0,
        },
        "business_promotable": False,
    }
    return {**body, "envelope_digest": canonical_digest(body)}


__all__ = [
    "COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS",
    "EXECUTION_ENVELOPE_SCHEMA",
    "Fin012S4T05BAgentExecutionError",
    "INPUT_CAPACITY_CONTRACT_REF",
    "MAXIMUM_INPUT_TOKENS",
    "MAXIMUM_OUTPUT_TOKENS",
    "MAXIMUM_TOTAL_COST_USD",
    "compile_t05_b_dell_agent_execution_envelope",
    "prepare_t05_b_dell_agent_execution",
]
