from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_"
    "candidate_pool_planner_minimum_zero_call_implementation_v1_0.json"
)
NEXT = (
    "S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-"
    "INDEPENDENT-FRESH-AGENT-PROOF-DECISION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_implementation_consumes_exactly_one_zero_call_bundle() -> None:
    implementation = _load(IMPLEMENTATION)
    authority = implementation["authority"]
    counts = implementation["observed_counts"]

    assert implementation["status"].startswith(
        "pass_single_zero_call_shared_runtime_bundle_runtime_injected"
    )
    assert authority["maximum_zero_call_structural_bundles"] == 1
    assert authority["implementation_bundles_consumed"] == 1
    assert authority["automatic_follow_on_repair_bundles"] == 0
    assert authority["model_provider_network_or_source_call_authorized"] is False
    assert authority["single_node_canary_or_exact_live_authorized"] is False
    assert authority["admission_issuance_or_consumption_authorized"] is False
    assert authority["T06_closeout_or_T07_entry_authorized"] is False
    assert set(counts.values()) == {0}


def test_implementation_binds_current_runtime_and_profile_bytes() -> None:
    implementation = _load(IMPLEMENTATION)
    authority = implementation["authority"]

    assert _sha256(ROOT / authority["source_authority_ref"]) == (
        authority["source_authority_sha256"]
    )
    for binding in implementation["runtime_changes"].values():
        assert _sha256(ROOT / binding["ref"]) == binding["sha256"]


def test_implemented_contract_owns_cardinality_before_provider() -> None:
    contract = _load(IMPLEMENTATION)["implemented_contract"]

    assert contract["profile_key"] == [
        "research_profile_ref",
        "program_cell_id",
    ]
    assert contract["registered_profile_cell_pairs"] == 9
    assert contract["provider_candidate_generation_allowed"] is False
    assert contract["local_pre_provider_candidate_generation_required"] is True
    assert contract["eligible_count_at_most_six_behavior"] == (
        "complete_eligible_catalog_preserved"
    )
    assert contract["eligible_count_over_six_behavior"] == (
        "typed_coverage_profile_selects_exactly_six"
    )
    assert contract["provider_visible_candidate_maximum"] == 6
    assert contract["provider_returned_candidate_maximum"] == 6
    assert contract["local_final_selected_maximum"] == 3
    assert contract["ticker_branch_or_free_text_or_embedding_ranker_used"] is False
    assert contract["provider_order_used_as_selection_signal"] is False
    assert contract["silent_truncation_used"] is False


def test_three_case_fixture_and_mutation_matrix_are_recorded() -> None:
    verification = _load(IMPLEMENTATION)["verification"]

    assert verification["focused_candidate_pool_tests"] == "15 passed"
    assert verification["catalog_count_matrix"] == [0, 1, 3, 6, 7, 22]
    assert verification["permutation_stability"] is True
    assert verification[
        "profile_scope_digest_unknown_role_overlap_and_minimum_mutations_fail_closed"
    ] is True
    assert verification[
        "hidden_cross_case_duplicate_and_seventh_provider_candidates_fail_closed"
    ] is True
    assert verification["provider_returning_all_six_visible_candidates_is_valid"] is True
    assert verification["pre_provider_planner_fault_provider_calls"] == 0
    assert verification["three_case_full_fake"] == {
        "DELL": [6, 12, 12, 9],
        "MU": [6, 12, 12, 9],
        "NVDA": [6, 12, 12, 9],
    }


def test_stage_remains_live_product_blocked_and_record_stops_at_fresh_proof() -> None:
    implementation = _load(IMPLEMENTATION)
    stage = implementation["stage_acceptance"]

    assert stage["S4_T06"] == "engineering_pass_live_product_blocked_not_closed"
    assert stage["paired_assessment"] == "not_eligible_not_performed"
    assert stage["owner_acceptance"] == "not_eligible_not_performed"
    assert stage["S4_T07"] == "not_entered"
    assert stage["S4"] == "not_passed"
    assert stage["S5"] == "blocked"
    assert implementation["next_action"] == NEXT
