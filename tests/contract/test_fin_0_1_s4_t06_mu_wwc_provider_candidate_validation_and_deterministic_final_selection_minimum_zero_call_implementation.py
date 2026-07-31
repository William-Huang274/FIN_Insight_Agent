from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_wwc_provider_candidate_"
    "validation_and_deterministic_final_selection_minimum_zero_call_"
    "implementation_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
EXPECTED_NEXT = (
    "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-DETERMINISTIC-"
    "FINAL-SELECTION-INDEPENDENT-FRESH-AGENT-PROOF-DECISION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_implementation_consumes_one_zero_call_bundle_only() -> None:
    implementation = _load(IMPLEMENTATION)
    assert implementation["status"] == (
        "pass_WWC_candidate_validation_stable_top3_and_zero_call_"
        "full_chain_proven_independent_fresh_proof_pending"
    )
    authority = implementation["authority"]
    assert authority["implementation_bundles_consumed"] == 1
    assert authority["automatic_follow_on_implementation_bundles"] == 0
    assert not authority[
        "new_admission_R8_or_replacement_exact_live_authorized"
    ]
    assert implementation["next_action"] == EXPECTED_NEXT
    assert implementation["next_action_authorized"] is False


def test_implementation_binds_current_runtime_and_test_bytes() -> None:
    implementation = _load(IMPLEMENTATION)
    for binding in implementation["runtime_changes"].values():
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_contract_separates_candidates_from_final_tasks() -> None:
    contract = _load(IMPLEMENTATION)["implemented_contract"]
    assert contract["provider_candidate_cardinality"] == {
        "minimum": 1,
        "maximum": 6,
    }
    assert contract["final_selected_cardinality"] == {
        "minimum": 1,
        "maximum": 3,
    }
    assert contract["all_candidates_validated_before_selection"]
    assert not contract["invalid_candidate_silent_drop"]
    assert contract["exact_duplicate_candidate_fail_closed"]
    assert contract["permutation_stable_selection"]


def test_full_chain_and_final_artifact_audit_are_recorded() -> None:
    verification = _load(IMPLEMENTATION)["verification"]
    assert set(verification["three_case_full_fake"]) == {
        "DELL",
        "MU",
        "NVDA",
    }
    assert set(
        tuple(row)
        for row in verification["three_case_full_fake"].values()
    ) == {(6, 12, 12, 9)}
    assert verification["downstream_failure_capture_sequences"] == {
        "Research_Lead": 10,
        "Writer": 11,
        "Verifier": 12,
    }
    assert verification["terminal_failure_result_materialized"]
    assert "manifest lineage digest" in verification[
        "final_nine_artifact_L1_mutations_rejected"
    ]
    assert "trace lineage payload" in verification[
        "final_nine_artifact_L1_mutations_rejected"
    ]


def test_backlogs_advance_only_to_independent_zero_call_proof() -> None:
    assert _load(PROGRAM_BACKLOG)["next_action"]["item_id"] == EXPECTED_NEXT
    assert _load(S4_BACKLOG)["current_next_action"] == EXPECTED_NEXT
