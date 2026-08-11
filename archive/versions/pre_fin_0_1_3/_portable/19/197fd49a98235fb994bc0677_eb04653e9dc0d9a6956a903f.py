from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_"
    "candidate_pool_planner_independent_fresh_agent_proof_authority_"
    "decision_v1_0.json"
)
NEXT = (
    "S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-"
    "INDEPENDENT-FRESH-AGENT-PROOF"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authority_binds_project_os_implementation_and_current_bytes() -> None:
    decision = _load(DECISION)
    preflight = decision["project_os_preflight"]
    source = decision["source_evidence"]

    assert _sha256(ROOT / preflight["ref"]) == preflight["sha256"]
    assert _load(ROOT / preflight["ref"])["status"] == "pass"
    assert preflight["open_full_chain_blockers"] == 0
    assert _sha256(ROOT / source["implementation_ref"]) == (
        source["implementation_sha256"]
    )
    assert _sha256(ROOT / source["source_worklog_ref"]) == (
        source["source_worklog_sha256"]
    )
    for relative_path, expected in decision["frozen_current_bindings"].items():
        assert _sha256(ROOT / relative_path) == expected


def test_authority_is_one_future_zero_call_proof_package_only() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    observed = decision["observed_counts"]

    assert decision["decision_label"] == (
        "authorize_one_future_independent_zero_call_proof_package_only"
    )
    assert authority["future_independent_zero_call_proof_authorized"] is True
    assert authority["proof_execution_in_current_turn_authorized"] is False
    assert authority["maximum_future_proof_packages"] == 1
    assert authority["required_independent_disposable_runtime_invocations"] == 2
    assert authority["automatic_follow_on_proof_or_repair_packages"] == 0
    assert authority["runtime_source_or_profile_mutation_authorized"] is False
    assert authority["credential_presence_or_value_read_authorized"] is False
    assert authority["model_provider_network_or_source_call_authorized"] is False
    assert authority["admission_issuance_or_consumption_authorized"] is False
    assert authority["exact_live_authorized"] is False
    assert authority["T06_closeout_or_T07_entry_authorized"] is False
    assert set(observed.values()) == {0}


def test_future_proof_is_disposable_read_only_and_deterministic() -> None:
    decision = _load(DECISION)
    proof = decision["future_proof_contract"]

    assert proof["proof_package_id"] == NEXT
    assert proof["independent_invocations"] == 2
    assert proof["invocations_must_use_separate_disposable_runtime_roots"] is True
    assert proof["invocations_must_use_fresh_python_processes"] is True
    assert proof["provider_credential_environment_must_be_scrubbed"] is True
    assert proof["target_canonical_database_or_object_tree_must_be_read_only"] is True
    assert proof["target_WorkUnit_Attempt_Run_or_business_Artifact_writes_allowed"] is False
    assert proof["source_or_runtime_repair_during_proof_allowed"] is False
    assert proof["independent_normalized_outputs_must_be_byte_equal"] is True
    assert set(
        proof["credential_model_provider_network_source_external_tool_calls"]
    ) == {0}


def test_future_proof_matrix_preserves_full_chain_and_l1_boundaries() -> None:
    decision = _load(DECISION)
    positive = decision["required_positive_matrix"]
    negative = decision["required_negative_matrix"]
    stop = decision["success_and_stop_rule"]

    assert positive["candidate_catalog_counts"] == [1, 3, 6, 7, 22]
    assert positive["eligible_at_most_six_preserves_complete_catalog"] is True
    assert positive["eligible_over_six_produces_exactly_six_visible_candidates"] is True
    assert positive["provider_returning_all_six_visible_candidates_is_valid"] is True
    assert positive["local_final_selected_maximum"] == 3
    assert positive["DELL_MU_NVDA_each_nodes_calls_captures_Artifacts"] == [
        6,
        12,
        12,
        9,
    ]
    assert "zero_candidate_catalog_fails_before_provider_with_provider_calls_zero" in negative
    assert "hidden_cross_case_duplicate_and_seventh_provider_candidates_fail_closed" in negative
    assert "numeric_identity_manifest_and_trace_lineage_mutations_fail_closed" in negative
    assert stop["proof_success_closes_RC_P36_084"] is False
    assert stop["proof_success_authorizes_admission_or_live"] is False
    assert stop["proof_success_authorizes_paired_owner_T06_closeout_or_T07"] is False
    assert stop["proof_failure_allows_automatic_patch_or_second_proof"] is False


def test_authority_stops_at_future_independent_zero_call_proof() -> None:
    decision = _load(DECISION)

    assert decision["next_action"] == NEXT
    assert decision["stage_acceptance"]["S4_T06"] == (
        "engineering_pass_live_product_blocked_not_closed"
    )
    assert decision["stage_acceptance"]["S4_T07"] == "not_entered"
