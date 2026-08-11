from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_research_lead_v5_"
    "narrative_quality_and_s3_scope_rebaseline_decision_v1_0.json"
)


def _decision() -> dict:
    return json.loads(DECISION.read_text(encoding="utf-8"))


def test_decision_separates_quality_target_from_hard_integrity() -> None:
    decision = _decision()
    contract = decision["selected_contract"]

    assert decision["root_cause"]["project_owned_contract_grading_defect_confirmed"]
    assert decision["root_cause"]["deepseek_model_fault_confirmed"] is False
    assert contract["research_lead_transport_ref_unchanged"].endswith(":v5")
    assert contract["new_research_profile_ref"].endswith(":v3")
    assert contract["research_lead_per_field_quality_target"] == 320
    assert contract["research_lead_per_field_hard_safety_maximum"] == 512
    assert contract["research_lead_aggregate_narrative_hard_maximum_unchanged"] == 3200
    assert contract["silent_truncation_trim_drop_or_rewrite_allowed"] is False


def test_decision_rebaselines_s3_without_claiming_later_quality_work() -> None:
    scope = _decision()["s3_scope_rebaseline"]

    assert scope["permitted_closeout"] == "R2_with_known_quality_gaps"
    assert "three-case transfer" in scope["S3_must_not_absorb"]
    assert "qualified senior analyst R3" in scope["S3_must_not_absorb"]
    assert "new source-network evidence acquisition" in scope["S3_must_not_absorb"]
    assert "deterministic financial calculation layer" in scope["S3_must_not_absorb"]
    assert "market-consensus variant-view and Alpha proof" in scope["S3_must_not_absorb"]


def test_decision_authorizes_only_one_final_exact_live_and_no_owner_impersonation() -> None:
    decision = _decision()
    authority = decision["authority"]

    assert set(decision["observed_counts"].values()) == {0}
    assert authority[
        "continuous_zero_call_implementation_regression_and_one_final_exact_live_authorized"
    ]
    assert authority["automatic_retry_fallback_or_second_live_execution_authorized"] is False
    assert authority["owner_acceptance_may_be_impersonated_by_codex"] is False
    assert decision["execution_sequence"][-1].endswith("manifest_draft")
