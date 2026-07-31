from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_evidence_role_taxonomy_runtime_plan_alignment_"
    "zero_call_root_cause_disposition_v1_0.json"
)
DELL_PACK = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t02_dell_oem_exact_case_pack_v1_0.json"
)
MU_PACK = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t02_mu_hbm_exact_case_pack_v1_0.json"
)
FAILURE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_dell_exact_r2_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pack_role_groups(path: Path) -> list[dict]:
    return [
        {
            "program_cell_id": row["program_cell_id"],
            "owner_role": row["owner_role"],
            "source_evidence_roles": row["required_evidence_roles"],
        }
        for row in _load(path)["program_cells"]
    ]


def _decision_role_groups(case_ticker: str) -> list[dict]:
    return [
        {
            "program_cell_id": row["program_cell_id"],
            "owner_role": row["owner_role"],
            "source_evidence_roles": row["source_evidence_roles"],
        }
        for row in _load(DECISION)["case_role_groups"][case_ticker]
    ]


def test_decision_binds_the_exact_failure_and_stops_before_implementation() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert decision["status"] == (
        "pass_zero_call_program_cell_keyed_case_role_group_mapping_selected_"
        "implementation_pending"
    )
    assert decision["source_evidence"]["failed_execution_result_sha256"] == (
        _sha256(FAILURE)
    )
    assert decision["source_evidence"]["failure_code"] == (
        "s3_required_evidence_role_slot_missing"
    )
    assert authority["zero_call_root_cause_disposition_authorized"] is True
    assert authority["runtime_code_schema_or_dispatch_implementation_authorized"] is False
    assert authority["replacement_admission_or_second_exact_execution_authorized"] is False
    assert authority["model_provider_network_source_or_external_tool_calls_authorized"] is False


def test_program_cell_is_the_cross_case_axis_and_source_roles_remain_exact() -> None:
    decision = _load(DECISION)
    identity = decision["identity_decomposition"]
    selected = decision["selected_contract"]

    assert identity["cross_case_semantic_axis"] == "program_cell_id"
    assert identity["generic_role_name_may_join_S4_canonical_slots"] is False
    assert selected["authoritative_group_key"] == "program_cell_id"
    assert selected["resolution_key"] == [
        "program_cell_id",
        "exact_evidence_role",
    ]
    assert selected["mapping_is_derived_not_hand_authored_by_ticker"] is True
    assert {
        "role_rename",
        "synthetic_generic_slot",
        "representative_role_selection",
        "ticker_conditional_mapping",
        "silent_missing_role_drop",
    }.issubset(set(selected["forbidden_behaviors"]))


def test_dell_and_mu_mappings_are_exact_case_pack_projections() -> None:
    assert _decision_role_groups("DELL") == _pack_role_groups(DELL_PACK)
    assert _decision_role_groups("MU") == _pack_role_groups(MU_PACK)
    assert [
        len(row["source_evidence_roles"])
        for row in _load(DECISION)["case_role_groups"]["DELL"]
    ] == [4, 5, 5]
    assert [
        len(row["source_evidence_roles"])
        for row in _load(DECISION)["case_role_groups"]["MU"]
    ] == [4, 5, 5]


def test_selected_dispatch_contract_closes_the_t03_t04_blind_spot() -> None:
    boundary = _load(DECISION)["implementation_boundary"]
    acceptance = _load(DECISION)["future_implementation_acceptance"]

    assert boundary["shared_dispatch_entrypoint_required"] is True
    assert boundary["actual_Runtime_and_exact_preflight_must_call_same_dispatcher"] is True
    assert boundary["S4_runtime_plan_must_carry_role_group_digest"] is True
    assert boundary["S4_source_grounded_path_may_use_S3_fixture_candidate_sets"] is False
    assert boundary["one_shared_Runtime_preserved"] is True
    assert boundary["new_Case_specific_Runtime_allowed"] is False
    assert acceptance["model_provider_network_source_external_tool_calls_allowed"] == [
        0,
        0,
        0,
        0,
        0,
    ]
    assert acceptance["replacement_admission_allowed"] is False


def test_rejected_shortcuts_and_next_action_are_frozen() -> None:
    decision = _load(DECISION)
    rejected = {
        row["option"]
        for row in decision["alternatives"]
        if row["decision"] == "rejected"
    }

    assert {
        "rename_or_duplicate_S4_Canonical_slots_to_S3_generic_roles",
        "choose_one_representative_case_role_per_cell",
        "add_DELL_ticker_conditionals_or_fallbacks_in_EvidenceService",
        "skip_all_pre_adapter_evidence_alignment_for_S4",
    } == rejected
    assert decision["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "admissions_issued": 0,
        "admissions_consumed": 0,
        "work_units_attempts_runs_or_artifacts_created": 0,
        "canonical_writes": 0,
    }
    assert decision["next_action"] == (
        "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-DISPATCH-"
        "PREFLIGHT-ZERO-CALL-IMPLEMENTATION"
    )
