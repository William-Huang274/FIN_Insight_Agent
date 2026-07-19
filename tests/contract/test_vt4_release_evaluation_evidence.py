from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOGFOOD_PATH = (
    REPO_ROOT
    / "reports"
    / "release_evidence"
    / "fin_ia_0_1_vt4_p36_internal_dogfood_result_v1_0.json"
)
EVALUATION_PATH = (
    REPO_ROOT
    / "reports"
    / "release_evidence"
    / "fin_ia_0_1_vt4_product_evaluation_v1_0.json"
)
ROLLBACK_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt4_rollback_release_note_v1_0.json"
)
RELEASE_DECISION_PATH = (
    REPO_ROOT
    / "reports"
    / "release_evidence"
    / "fin_ia_0_1_vt4_p07_5_release_decision_v1_0.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_dogfood_records_full_fixture_path_without_research_or_release_claim() -> None:
    dogfood = _load(DOGFOOD_PATH)

    assert dogfood["status"] == "fixture_full_path_pass_calibrated_research_validity_pending"
    path = dogfood["vertical_path"]
    assert path["decision_surface"]["cell_count"] == 10
    assert path["evidence"]["slot_count"] == 10
    assert path["workpaper"]["judgment_count"] == 10
    assert path["workpaper"]["explicit_gap_count"] == 10
    assert path["deliverable"]["material_claim_count"] == 10
    assert path["deliverable"]["explicit_gap_count"] == 10
    assert path["trace"]["bidirectional_projection"] == "pass"
    assert dogfood["stage_acceptance"]["calibrated"].startswith("pending_")
    assert dogfood["research_outcome"] == {
        "sector_research_validity": "not_claimed",
        "senior_R2_review": "not_run",
        "confidence_calibration": "not_run",
        "RG3_research_outcome": "blocked",
    }
    boundaries = dogfood["hard_boundaries"]
    assert all(boundaries[key] == 0 for key in (
        "network_calls",
        "model_calls",
        "provider_calls",
        "tool_invocations",
        "paid_full_chain",
        "real_business_case_writes",
        "release_admission",
    ))
    assert boundaries["production_readiness"] == "not_admitted"
    assert boundaries["legacy_global_authority"] == "retained"


def test_evaluation_reports_observations_but_never_claims_time_saved() -> None:
    evaluation = _load(EVALUATION_PATH)

    assert evaluation["status"] == "observed_internal_fixture_metrics_only_human_baseline_pending"
    observations = evaluation["observations"]
    assert observations["time_to_workpaper"]["observed_seconds"] > 0
    assert observations["time_to_workpaper"]["baseline_seconds"] is None
    assert observations["time_to_workpaper"]["time_saved_claim"].startswith("not_permitted_")
    assert observations["time_to_reviewed_deliverable"]["time_saved_claim"] == "not_made"
    assert observations["review_burden"]["human_baseline"] == "not_established"
    assert observations["repeated_work"]["discarded_historical_case_count"] == 1
    assert observations["tool_model_cost"] == {
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "tool_invocations": 0,
        "paid_call_count": 0,
        "commercial_data_spend": 0,
    }
    assert evaluation["release_gate_effect"] == {
        "RG4_review_product_value": "blocked_human_baseline_pending",
        "release_admission": "not_granted",
    }


def test_rollback_contract_retains_authority_and_audit_history_but_stays_blocked() -> None:
    rollback = _load(ROLLBACK_PATH)

    assert rollback["status"] == "bounded_rollback_drill_pass_known_gaps_frozen_release_still_blocked"
    contract = rollback["rollback"]
    assert contract["target_release_id"] == "REL-FND-001"
    assert contract["legacy_global_authority"] == "retained"
    assert contract["production_readiness"] == "not_admitted"
    assert contract["canonical_audit_history"] == "retain_immutable"
    assert contract["data_deletion"] == "forbidden"
    assert contract["feature_flag_disable_test"] == "pass_new_lane_read_and_write_fail_closed"
    assert contract["projection_fallback_test"] == "pass_legacy_browser_shell_available"
    assert contract["rollback_drill"] == "pass_bounded_local_fixture"
    assert contract["rollback_result_sha256"] == "48da7073ab1bf1a11db90dd7b578d7ddaf227b4c4f29df4db40695eec26a0cc8"
    assert rollback["release_note"]["release_decision"] == "blocked_pending_P07_5_RG1_to_RG5"
    assert rollback["release_note"]["FIN_0_1_INTERNAL_ALPHA_RELEASED"] is False
    assert {item["gate"] for item in rollback["known_gaps"]} == {
        "RG1_vertical_path",
        "RG3_research_outcome",
        "RG4_review_product_value",
    }
    assert rollback["stage_acceptance"]["full"].startswith("pass_")


def test_p07_5_blocks_release_on_rg1_rg3_rg4_and_preserves_internal_demo_scope() -> None:
    decision = _load(RELEASE_DECISION_PATH)

    assert decision["status"] == "FIN_0_1_INTERNAL_ALPHA_BLOCKED"
    assert len(decision["candidate"]["manifest_sha256"]) == 64
    assert set(decision["candidate"]["manifest_sha256"]) != {"0"}
    gates = decision["independent_gate_disposition"]
    assert gates["RG1_vertical_path"]["status"] == "blocked"
    assert gates["RG2_evidence_numeric_integrity"]["status"] == "pass_internal_fixture_candidate"
    assert gates["RG3_research_outcome"]["status"] == "blocked"
    assert gates["RG4_review_product_value"]["status"] == "blocked"
    assert gates["RG5_release_rollback"]["status"] == "pass_bounded_internal_fixture"
    assert decision["blocking_gates"] == [
        "RG1_vertical_path",
        "RG3_research_outcome",
        "RG4_review_product_value",
    ]
    assert decision["release_decision"] == {
        "FIN_0_1_INTERNAL_ALPHA_RELEASED": False,
        "release_admission": "not_issued",
        "development_mode": "fixture_shadow_internal_only",
        "production_readiness": "not_admitted",
        "legacy_global_authority": "retained",
        "rollback_target": "REL-FND-001_with_legacy_global_authority_retained",
    }
    assert all(value == 0 for value in decision["hard_boundaries"].values())
