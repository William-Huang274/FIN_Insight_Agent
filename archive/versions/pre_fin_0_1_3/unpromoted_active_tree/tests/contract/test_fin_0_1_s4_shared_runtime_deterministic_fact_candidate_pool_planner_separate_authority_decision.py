from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_"
    "candidate_pool_planner_separate_authority_decision_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
NEXT = (
    "S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-"
    "MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authority_binds_project_os_sources_and_current_runtime() -> None:
    decision = _load(DECISION)
    preflight = decision["project_os_preflight"]
    source = decision["source_evidence"]

    assert _sha256(ROOT / preflight["ref"]) == preflight["sha256"]
    assert _load(ROOT / preflight["ref"])["status"] == "pass"
    assert preflight["open_full_chain_blockers"] == 0
    for ref_key, sha_key in (
        ("exact_live_failure_result_ref", "exact_live_failure_result_sha256"),
        ("project_disposition_ref", "project_disposition_sha256"),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]
    for relative_path, expected in decision["baseline_runtime_bindings"].items():
        assert _sha256(ROOT / relative_path) == expected


def test_authority_is_one_future_zero_call_bundle_only() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    counts = decision["observed_counts"]

    assert decision["decision_label"].startswith("authorize_one_future_zero_call")
    assert authority["future_zero_call_implementation_authorized"] is True
    assert authority["implementation_in_current_turn_authorized"] is False
    assert authority["maximum_zero_call_structural_bundles"] == 1
    assert authority["automatic_follow_on_repair_bundles"] == 0
    assert authority["model_provider_or_execution_network_calls_authorized"] is False
    assert authority["admission_issuance_or_consumption_authorized"] is False
    assert authority["single_node_canary_or_exact_live_authorized"] is False
    assert authority["paired_assessment_or_owner_acceptance_authorized"] is False
    assert authority["T06_closeout_or_T07_entry_authorized"] is False
    assert authority["R8_R9_or_second_replacement_authorized"] is False
    assert set(counts.values()) == {0}


def test_candidate_pool_contract_removes_model_cardinality_ownership() -> None:
    decision = _load(DECISION)
    contract = decision["future_implementation_contract"]

    assert contract["contract_family"] == "specialist_fact_atoms"
    assert contract["provider_candidate_generation_allowed"] is False
    assert contract["local_candidate_pool_generation_required"] is True
    assert contract["local_candidate_pool_maximum"] == 6
    assert contract["provider_visible_allowed_support_maximum"] == 6
    assert contract["provider_returned_candidate_maximum"] == 6
    assert contract["local_final_selected_maximum"] == 3
    assert contract["candidate_profile_key"] == [
        "research_profile_ref",
        "program_cell_id",
    ]
    assert "profile_must_not_key_on_ticker_inside_runtime_selection_logic" in (
        contract["typed_profile_constraints"]
    )
    assert contract["silent_truncation_allowed"] is False
    assert contract["provider_order_as_selection_signal_allowed"] is False
    assert contract["historical_failed_output_replay_or_promotion_allowed"] is False


def test_authority_requires_typed_coverage_and_full_three_case_proof() -> None:
    decision = _load(DECISION)
    matrix = decision["required_zero_call_proof_matrix"]
    stop = decision["acceptance_and_stop_rule"]

    assert matrix["candidate_catalog_counts"] == [0, 1, 3, 6, 7, 22]
    assert (
        "eligible_count_twenty_two_produces_exactly_six_visible_candidates"
        in matrix["positive_requirements"]
    )
    assert (
        "DELL_MU_NVDA_each_reaches_6_nodes_12_calls_12_captures_9_Artifacts"
        in matrix["positive_requirements"]
    )
    assert "minimum_coverage_over_six_fails_closed" in matrix["negative_requirements"]
    assert (
        "numeric_identity_manifest_and_trace_lineage_mutations_fail_closed"
        in matrix["negative_requirements"]
    )
    assert stop["implementation_success_authorizes_fresh_proof"] is False
    assert stop["fresh_proof_requires_separate_authority"] is True
    assert stop["implementation_or_fresh_proof_success_authorizes_live"] is False
    assert stop["T06_live_product_passed"] is False
    assert stop["T06_closed"] is False
    assert stop["T07_entered"] is False


def test_backlogs_advance_only_to_authorized_zero_call_implementation() -> None:
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)

    assert program["next_action"]["item_id"] == NEXT
    assert detailed["current_next_action"] == NEXT
