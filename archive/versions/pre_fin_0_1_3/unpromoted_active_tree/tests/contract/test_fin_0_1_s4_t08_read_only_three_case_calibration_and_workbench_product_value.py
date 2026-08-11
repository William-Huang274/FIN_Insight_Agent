from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t08_read_only_three_case_calibration_and_"
    "workbench_product_value_scope_decision_v1_0.json"
)
RESULT_PATH = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t08_read_only_three_case_calibration_and_"
    "workbench_product_value_result_v1_0.json"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_binds_ten_immutable_evidence_files() -> None:
    scope = _load(SCOPE_PATH)
    assert scope["status"] == (
        "pass_scope_frozen_read_only_immutable_evidence_calibration_"
        "authorized_no_product_promotion"
    )
    assert len(scope["immutable_evidence_bindings"]) == 10
    for binding in scope["immutable_evidence_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_scope_is_zero_call_and_forbids_failed_output_promotion() -> None:
    scope = _load(SCOPE_PATH)
    authority = scope["authority"]
    assert authority["failed_or_quarantined_artifact_promotion_authorized"] is False
    assert authority["paired_pass_owner_acceptance_or_R3_creation_authorized"] is False
    assert authority["T05_T06_or_T07_reopen_authorized"] is False
    assert set(scope["hard_budgets"].values()) == {0}
    contract = scope["comparison_contract"]
    assert contract["allowed_evidence_states"] == [
        "measured",
        "qualitative_evidence_only",
        "not_measured",
    ]
    assert "not_measured" in contract["missing_measurement_rule"]


def test_result_binds_scope_and_preserves_case_maturity() -> None:
    result = _load(RESULT_PATH)
    authority = result["authority"]
    assert _sha256(ROOT / authority["scope_decision_ref"]) == (
        authority["scope_decision_sha256"]
    )
    cases = {
        row["case_ticker"]: row for row in result["three_case_calibration"]
    }
    assert set(cases) == {"NVDA", "DELL", "MU"}
    assert cases["NVDA"]["four_layer_result"]["L1_hard_integrity"] == "pass"
    assert cases["NVDA"]["review_and_delivery"]["owner_acceptance"] == (
        "yes_historical_S3_R2"
    )
    assert cases["DELL"]["four_layer_result"]["L1_hard_integrity"].startswith(
        "fail_"
    )
    assert cases["MU"]["four_layer_result"]["L1_hard_integrity"].startswith(
        "fail_"
    )
    assert cases["DELL"]["review_and_delivery"]["DELL_R2"] == "not_proven"
    assert cases["MU"]["review_and_delivery"]["MU_R2"] == "not_proven"


def test_cross_case_metrics_are_exact_and_not_overgeneralized() -> None:
    result = _load(RESULT_PATH)
    totals = result["cross_case_calibration"]["coherent_success_evidence_totals"]
    assert totals["model_provider_calls"] == 36
    assert totals["agent_artifacts_materialized"] == 27
    assert totals["input_output_total_tokens"] == [192515, 20103, 212618]
    assert totals["estimated_cost_usd"] == 0.08207367
    assert totals["predictive_average_or_unit_economics_claim"].startswith(
        "not_authorized"
    )
    admissible = result["cross_case_calibration"]["admissible_product_totals"]
    assert admissible["owner_accepted_R2_cases"] == 1
    assert admissible["owner_accepted_case_tickers"] == ["NVDA"]
    assert admissible["DELL_R2"] is False
    assert admissible["MU_R2"] is False
    assert admissible["NVDA_post_transfer_R3"] is False


def test_workbench_value_distinguishes_measured_qualitative_and_missing() -> None:
    result = _load(RESULT_PATH)
    value = result["Workbench_product_value_calibration"]
    assert value["task_time"]["evidence_state"] == "not_measured"
    assert value["continue_use"]["evidence_state"] == "not_measured"
    assert value["edit_burden"]["evidence_state"] == "qualitative_evidence_only"
    assert value["trust"]["evidence_state"] == "qualitative_evidence_only"
    assert value["trace_and_debug_value"]["evidence_state"] == "measured"
    assert value["task_time"]["result"] is None
    assert value["continue_use"]["result"] is None


def test_t08_pass_does_not_promote_s4_or_substitute_for_human_review() -> None:
    result = _load(RESULT_PATH)
    assert set(result["observed_counts"].values()) == {0}
    disposition = result["T08_disposition"]
    assert disposition["T08"] == "pass_read_only_calibration_complete"
    assert disposition["S4"] == "not_passed"
    assert disposition["FIN_0_1_release"] == "not_qualified"
    assert disposition["release_requirements_weakened"] is False
    assert result["next_action"] == (
        "S4-T09-REAL-HUMAN-OWNER-REVIEW-AND-QUALIFIED-SENIOR-"
        "ELIGIBILITY-SCOPE-DECISION"
    )


def test_t08_progression_contract_requires_a_separate_human_stage() -> None:
    scope = _load(SCOPE_PATH)
    progression = scope["progression_rule"]
    assert progression["T08_completion_is_S4_pass"] is False
    assert progression["T08_completion_is_owner_or_qualified_senior_review"] is False
    assert progression["next_stage_requirement"] == (
        "separate_real_Human_T09_scope_and_eligibility_decision"
    )
