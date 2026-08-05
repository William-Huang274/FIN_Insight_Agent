from __future__ import annotations

from typing import Any, Mapping, Sequence

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
    "fin_ia_0_1_2_s4_t05_current_case_agent_exact_execution_envelope_v1_0"
)
INPUT_CAPACITY_CONTRACT_REF = (
    "fin_0_1_2.S4.T05.current_case_agent_compiled_capacity:v1"
)
MAXIMUM_INPUT_TOKENS = 108000
MAXIMUM_OUTPUT_TOKENS = 10000
MAXIMUM_TOTAL_COST_USD = 0.06
COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS = 117931
SUPPORTED_CASES = {"DELL", "MU", "NVDA"}


class Fin012S4T05CurrentCaseAgentExecutionError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Fin012S4T05CurrentCaseAgentExecutionError(code)


def _bound_current_evidence_digest(
    input_pack: S3ThreeCellBoundedAgentInputPack,
    *,
    case_key: str,
) -> str:
    """Read the current Evidence binding from the case's frozen lineage family."""

    lineage_key = (
        "T04_financial_pack"
        if case_key == "NVDA"
        else "S4_T04_source_grounded_input"
    )
    row = input_pack.lineage.get(lineage_key)
    _require(
        isinstance(row, Mapping)
        and len(str(row.get("digest") or "")) == 64,
        "s4_t05_current_case_evidence_lineage_missing",
    )
    return str(row["digest"])


def prepare_current_case_agent_execution(
    input_pack: S3ThreeCellBoundedAgentInputPack,
    evidence_pack: Mapping[str, Any],
    *,
    case_key: str,
    principal: CasePrincipal,
    execution_identity: str,
    attempt_no: int = 1,
) -> S3ThreeCellPreparedExecution:
    _require(case_key in SUPPORTED_CASES, "s4_t05_current_case_unsupported")
    current = validate_transfer_evidence_pack(evidence_pack, case_key=case_key)
    expected_prefix = f"fin012-s4-t05-{case_key.lower()}-current-evidence-"
    bound_evidence_digest = _bound_current_evidence_digest(
        input_pack,
        case_key=case_key,
    )
    _require(
        bool(execution_identity.strip())
        and input_pack.company == case_key
        and "oracle" not in input_pack.case_id
        and input_pack.case_id.startswith(expected_prefix)
        and input_pack.decision_surface_contract_ref == T05_TRANSFER_CONTRACT_REF
        and bound_evidence_digest == current["evidence_pack_digest"]
        and input_pack.input_digest
        == canonical_digest(input_pack.model_dump(mode="json", exclude={"input_digest"})),
        "s4_t05_current_case_agent_exact_input_binding_invalid",
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


def compile_current_case_agent_execution_envelope(
    prepared: S3ThreeCellPreparedExecution,
    evidence_pack: Mapping[str, Any],
    *,
    case_key: str,
    admission_ref: str,
    projected_per_call_input_tokens: Sequence[int],
) -> dict[str, Any]:
    current = validate_transfer_evidence_pack(evidence_pack, case_key=case_key)
    bound_evidence_digest = _bound_current_evidence_digest(
        prepared.input_pack,
        case_key=case_key,
    )
    projected = tuple(int(value) for value in projected_per_call_input_tokens)
    _require(
        prepared.input_pack.company == case_key
        and bound_evidence_digest == current["evidence_pack_digest"]
        and len(projected) == 9
        and min(projected) > 0
        and sum(projected) <= MAXIMUM_INPUT_TOKENS,
        "s4_t05_current_case_agent_capacity_or_lineage_invalid",
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
        "status": f"fresh_T05_current_{case_key}_Agent_exact_execution_not_started",
        "case_key": case_key,
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
        # The shared exact runner consumes this historical field name.  Keep it
        # as the wire contract while the surrounding envelope is case-generic.
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
            "per_interaction_estimated_input_tokens": list(projected),
            "aggregate_estimated_input_tokens": sum(projected),
            "maximum_single_interaction_estimated_input_tokens": max(projected),
            "maximum_input_tokens": MAXIMUM_INPUT_TOKENS,
            "input_token_headroom": MAXIMUM_INPUT_TOKENS - sum(projected),
            "cost_derived_absolute_maximum_input_tokens": COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS,
            "reserved_maximum_output_tokens": MAXIMUM_OUTPUT_TOKENS,
            "maximum_total_cost_usd": MAXIMUM_TOTAL_COST_USD,
        },
        "business_promotable": False,
    }
    return {**body, "envelope_digest": canonical_digest(body)}


__all__ = [
    "COST_DERIVED_ABSOLUTE_MAXIMUM_INPUT_TOKENS",
    "INPUT_CAPACITY_CONTRACT_REF",
    "MAXIMUM_INPUT_TOKENS",
    "MAXIMUM_OUTPUT_TOKENS",
    "MAXIMUM_TOTAL_COST_USD",
    "compile_current_case_agent_execution_envelope",
    "prepare_current_case_agent_execution",
]
