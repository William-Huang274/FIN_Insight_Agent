from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s4_source_grounded_bounded_agent_input,
    resolve_s4_case_runtime_binding_for_admission,
)
from apps.workbench.backend.application.research_runtime import (
    FIN01_S3_PROGRAM_CELL_CONTRACTS,
    ExecutionProfileVersion,
    Fin01ResearchRuntime,
    ProfileArtifactResult,
    ProfileExecutionResult,
)
from sec_agent.s4_case_runtime import load_s4_source_grounded_input_pack


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_result_"
    "validation_after_six_node_completion_zero_call_root_cause_"
    "disposition_v1_0.json"
)
R9_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_exact_live_execution_failure_result_v1_0.json"
)
R9_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_fresh_exact_admission_r9.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_aware_artifact_"
    "lineage_validation_and_typed_subtype_minimum_zero_call_"
    "implementation_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
S4_LINEAGE_KEYS = (
    "S4_T02_case_pack",
    "S4_T02_method_contract",
    "S4_T03_runtime_binding",
    "S4_T04_source_grounded_input",
    "S4_research_profile_overlay",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _r9_profile_v3_input() -> Any:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(R9_ADMISSION)
    )
    binding, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )
    assert overlay is not None
    return build_s4_source_grounded_bounded_agent_input(
        binding,
        load_s4_source_grounded_input_pack(ROOT, "DELL"),
        case_id=str(admission.case_id),
        case_version=int(admission.case_version or 0),
        query="Zero-call R9 lineage-contract audit.",
        decision_surface_contract_ref="zero-call-R9-lineage-audit:v1",
        research_profile_overlay=overlay,
    )


def _content_free_profile_result(input_pack: Any) -> ProfileExecutionResult:
    cell_ids = [
        row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
    ]
    node_topology = [
        *(f"domain_specialist:{cell_id}" for cell_id in cell_ids),
        "research_lead",
        "memo_writer",
        "verifier",
    ]
    payloads = {
        kind: {"artifact_ref": f"logical:{kind}"}
        for kind in BOUNDED_AGENT_ARTIFACT_TYPES
    }
    payloads["bounded_agent_manifest"].update(
        {
            "case_id": input_pack.case_id,
            "input_digest": input_pack.input_digest,
            "adapter_direct_canonical_writes": 0,
            "observed_counts": {
                "model_calls": 12,
                "provider_calls": 12,
                "network_calls": 12,
                "external_tool_calls": 0,
                "source_network_calls": 0,
                "live_case_head_writes": 0,
            },
            "hard_boundaries": {
                "candidate_is_evidence": 0,
                "graph_edge_is_evidence": 0,
                "writer_source_or_tool_calls": 0,
                "adapter_direct_canonical_writes": 0,
                "live_business_case_head_writes": 0,
                "release_admission": 0,
            },
            "program_cell_ids": cell_ids,
            "node_topology": node_topology,
        }
    )
    payloads["bounded_agent_trace"].update(
        {"lineage": input_pack.lineage}
    )
    payloads["bounded_agent_report"].update(
        {"writer_source_calls": 0, "writer_tool_calls": 0}
    )
    payloads["bounded_agent_verification"].update(
        {
            "verification": {
                "findings": [
                    {"layer": layer}
                    for layer in (
                        "deterministic_integrity",
                        "semantic_fidelity",
                        "financial_coherence",
                        "visual_delivery",
                    )
                ]
            }
        }
    )
    payloads["bounded_agent_judgment"].update(
        {
            "specialist_outputs": [
                {"program_cell_id": cell_id} for cell_id in cell_ids
            ]
        }
    )
    return ProfileExecutionResult(
        execution_profile_version_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
        ),
        case_id=input_pack.case_id,
        artifact_type=BOUNDED_AGENT_ARTIFACT_TYPES[0],
        payload=payloads[BOUNDED_AGENT_ARTIFACT_TYPES[0]],
        artifacts=tuple(
            ProfileArtifactResult(
                artifact_type=kind,
                payload=payloads[kind],
            )
            for kind in BOUNDED_AGENT_ARTIFACT_TYPES[1:]
        ),
    )


def test_R9_disposition_binds_immutable_failure_and_zero_call_scope() -> None:
    decision = _load(DECISION)
    source = decision["source_failure"]
    authority = decision["authority"]

    assert source["result_sha256"] == _sha256(R9_RESULT)
    assert source["admission_file_sha256"] == _sha256(R9_ADMISSION)
    assert source["completed_logical_nodes"] == 6
    assert source["model_provider_network_calls"] == [12, 12, 12]
    assert source["restricted_R9_text_read_in_this_decision"] is False
    assert authority[
        "zero_call_code_contract_and_deterministic_fixture_audit_authorized"
    ] is True
    assert authority["runtime_repair_or_validator_change_authorized"] is False
    assert all(
        value == 0 for value in decision["observed_counts"].values()
    )


def test_R9_profile_v3_lineage_reproduces_exact_current_subtype() -> None:
    decision = _load(DECISION)
    reconstruction = decision["deterministic_reconstruction"]
    input_pack = _r9_profile_v3_input()

    assert tuple(input_pack.lineage) == S4_LINEAGE_KEYS
    assert reconstruction["reconstructed_lineage_keys"] == list(
        S4_LINEAGE_KEYS
    )
    assert reconstruction["current_validator_exact_subtype"] == (
        "s3_bounded_agent_T02_T07_lineage_missing"
    )
    if IMPLEMENTATION.exists():
        pytest.skip("historical rejection is frozen; implementation owns pass")

    runtime = object.__new__(Fin01ResearchRuntime)
    bound = runtime._bind_profile_artifact_refs(
        _content_free_profile_result(input_pack),
        research_run_id="zero-call-R9-lineage-audit-run",
    )
    profile = ExecutionProfileVersion(
        execution_profile_id="zero-call-R9-lineage-audit",
        execution_profile_version=1,
        execution_profile_version_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
        ),
        work_unit_type="zero-call-R9-lineage-audit",
        execution_mode="zero_call",
        worker_ref="zero-call",
        artifact_type=BOUNDED_AGENT_ARTIFACT_TYPES[0],
        model_calls_allowed=True,
        network_calls_allowed=True,
        external_tool_calls_allowed=False,
        direct_canonical_writes_allowed=False,
    )
    with pytest.raises(
        ValueError,
        match="^s3_bounded_agent_T02_T07_lineage_missing$",
    ):
        runtime._validate_profile_result(
            profile,
            bound,
            case_id=input_pack.case_id,
        )


def test_selected_contract_dispatches_exact_S3_and_S4_lineage_families() -> None:
    selected = _load(DECISION)["selected_minimum_implementation_contract"]
    dispatch = selected["lineage_family_dispatch"]

    assert selected["contract_ref"] == (
        "fin01.bounded_agent."
        "profile_aware_artifact_lineage_validation:v1"
    )
    assert len(dispatch["legacy_S3_without_s4_case_runtime"]["exact_keys"]) == 6
    assert len(
        dispatch["S4_base_case_runtime_without_overlay"]["exact_keys"]
    ) == 4
    assert tuple(
        dispatch[
            "S4_versioned_research_profile_with_overlay"
        ]["exact_keys"]
    ) == S4_LINEAGE_KEYS
    assert selected["typed_safe_failure_subtype"][
        "raw_exception_message_field_value_provider_text_or_stack_persisted"
    ] is False
    assert selected["terminal_semantics"][
        "lineage_integrity_remains_L1_hard_fail_closed"
    ] is True
    assert selected["terminal_semantics"][
        "new_Specialist_Lead_Writer_or_Verifier_transport_version_required"
    ] is False


def test_disposition_rejects_bypass_and_stays_inside_T05() -> None:
    decision = _load(DECISION)
    rejected = {
        row["option"]: row["decision"]
        for row in decision["rejected_and_deferred_alternatives"]
    }

    assert rejected[
        "delete_the_lineage_gate_or_accept_any_mapping_for_S4"
    ] == "rejected"
    assert rejected[
        "rewrite_the_S4_trace_to_fake_legacy_S3_T02_T07_keys"
    ] == "rejected"
    assert rejected[
        "add_a_DELL_R9_specific_bypass_or_company_branch"
    ] == "rejected"
    assert rejected[
        "atomize_dependency_conflict_Writer_Verifier_or_redesign_all_node_outputs_in_T05"
    ] == "deferred_to_S4_T10_to_S5"
    assert decision["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert decision["stage_acceptance"]["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-R9-PROFILE-AWARE-ARTIFACT-LINEAGE-VALIDATION-"
        "AND-TYPED-SUBTYPE-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )


def test_backlogs_route_only_to_separately_authorized_implementation() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T05"
    )

    if IMPLEMENTATION.exists():
        assert program["next_action"]["item_id"] == (
            detailed["current_next_action"]
        )
        assert task["RC_P36_066_implementation_completed"] is True
    else:
        assert program["next_action"]["item_id"] == decision["next_action"]
        assert detailed["current_next_action"] == decision["next_action"]
    assert task["RC_P36_066_disposition_sha256"] == _sha256(DECISION)
    assert program["next_action"][
        "S4_T05_RC_P36_066_disposition_sha256"
    ] == _sha256(DECISION)
    assert task["selected_profile_aware_lineage_contract_ref"] == (
        decision["selected_minimum_implementation_contract"]["contract_ref"]
    )
    assert task["R9_second_execution_authorized"] is False
