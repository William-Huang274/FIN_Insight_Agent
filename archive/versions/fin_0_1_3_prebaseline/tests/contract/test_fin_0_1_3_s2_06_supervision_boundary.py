from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.s2_same_evidence_supervision import compile_supervision_boundary


ROOT = Path(__file__).resolve().parents[2]


def _evaluation(*, complete: bool = True) -> dict:
    return {
        "raw_chain_complete": complete,
        "hidden_scoring_eligible": complete,
        "material_failure": True,
        "findings": [
            {
                "severity": "L1",
                "code": "directional_margin_sharpened_to_unsupported_range",
                "node_ref": "writer",
                "path": "$.sections[2].narrative",
                "tokens": ["4", "6%"],
            },
            {
                "severity": "L3",
                "code": "explicit_counterevidence_surface_empty",
                "node_ref": "specialist[3]",
            },
            {
                "severity": "L2",
                "code": "verifier_missed_material_failure",
                "node_ref": "verifier",
            },
        ],
    }


def test_supervision_boundary_never_rewrites_raw_or_exposes_hidden_gold() -> None:
    boundary = compile_supervision_boundary(
        _evaluation(), raw_run_id="run-DELL", raw_terminal_digest="a" * 64
    )
    encoded = json.dumps(boundary, ensure_ascii=False).lower()
    assert boundary["raw_binding"]["raw_model_only_immutable"] is True
    assert all(row["raw_output_mutated"] is False for row in boundary["corrections"])
    assert all(row["hidden_gold_visible"] is False for row in boundary["corrections"])
    assert "hidden_gold_scoring_objects" not in encoded
    assert "expected_thesis" not in encoded
    assert "strongest_counter_thesis" not in encoded


def test_deterministic_runtime_can_repair_source_precision_but_not_missing_research() -> None:
    boundary = compile_supervision_boundary(
        _evaluation(), raw_run_id="run-DELL", raw_terminal_digest="a" * 64
    )
    by_code = {row["source_finding"]["code"]: row for row in boundary["corrections"]}
    assert by_code["directional_margin_sharpened_to_unsupported_range"]["deterministic_correction_allowed"] is True
    assert by_code["directional_margin_sharpened_to_unsupported_range"]["new_model_call_required"] is False
    assert by_code["explicit_counterevidence_surface_empty"]["deterministic_correction_allowed"] is False
    assert by_code["explicit_counterevidence_surface_empty"]["new_model_call_required"] is True
    assert by_code["verifier_missed_material_failure"]["new_model_call_required"] is True


def test_complete_failed_raw_candidate_can_open_separate_next_case_decision_only() -> None:
    boundary = compile_supervision_boundary(
        _evaluation(), raw_run_id="run-DELL", raw_terminal_digest="a" * 64
    )
    campaign = boundary["campaign_boundary"]
    assert campaign["raw_measurement_complete"] is True
    assert campaign["automatic_next_case"] is False
    assert campaign["next_case_may_be_considered_by_separate_authority"] is True
    assert campaign["corrected_DELL_required_before_MU_raw_measurement"] is False


def test_incomplete_raw_candidate_cannot_open_next_case() -> None:
    boundary = compile_supervision_boundary(
        _evaluation(complete=False), raw_run_id="run-DELL", raw_terminal_digest="a" * 64
    )
    assert boundary["campaign_boundary"]["raw_measurement_complete"] is False
    assert boundary["campaign_boundary"]["next_case_may_be_considered_by_separate_authority"] is False


def test_supervision_boundary_requires_raw_identity_and_findings() -> None:
    with pytest.raises(ValueError, match="s2_06_raw_identity_required"):
        compile_supervision_boundary(_evaluation(), raw_run_id="", raw_terminal_digest="a" * 64)
    with pytest.raises(ValueError, match="s2_06_raw_findings_required"):
        compile_supervision_boundary({}, raw_run_id="run-DELL", raw_terminal_digest="a" * 64)


def test_release_decision_freezes_raw_first_cross_case_fairness_boundary() -> None:
    decision = json.loads(
        (ROOT / "configs/releases/fin_ia_0_1_3_s2_06_dell_supervision_boundary_and_campaign_disposition_v1_0.json").read_text(encoding="utf-8")
    )
    campaign = decision["campaign_disposition"]
    assert campaign["DELL_raw_measurement"] == "complete_quality_fail"
    assert campaign["automatic_next_case"] is False
    assert campaign["MU_raw_admission_may_be_considered_by_separate_authority"] is True
    assert campaign["DELL_correction_required_before_MU_raw"] is False
    assert campaign["DELL_supervisor_model_calls_before_three_case_raw_campaign_complete"] == 0
    assert decision["supervision_boundary"]["supervisor_model_repair"]["may_receive_hidden_gold"] is False


def test_financial_semantic_invariants_return_to_originating_model_without_hidden_gold() -> None:
    evaluation = _evaluation()
    evaluation["findings"].extend(
        [
            {
                "severity": "L1",
                "code": "trailing_pe_recast_as_single_quarter_earnings_multiple",
                "node_ref": "writer",
            },
            {
                "severity": "L1",
                "code": "combined_deposits_commitments_recast_as_cash_or_refundable_prepayment",
                "node_ref": "specialist[0]",
            },
            {
                "severity": "L1",
                "code": "average_fcf_margin_recast_as_marginal_revenue_sensitivity",
                "node_ref": "specialist[5]",
            },
            {
                "severity": "L3",
                "code": "unsupported_historical_valuation_comparison",
                "node_ref": "writer",
            },
        ]
    )
    boundary = compile_supervision_boundary(
        evaluation, raw_run_id="run-MU", raw_terminal_digest="b" * 64
    )
    by_code = {row["source_finding"]["code"]: row for row in boundary["corrections"]}
    for code in (
        "trailing_pe_recast_as_single_quarter_earnings_multiple",
        "combined_deposits_commitments_recast_as_cash_or_refundable_prepayment",
        "average_fcf_margin_recast_as_marginal_revenue_sensitivity",
    ):
        assert by_code[code]["primary_owner"] == "originating_model_node"
        assert by_code[code]["deterministic_correction_allowed"] is False
        assert by_code[code]["new_model_call_required"] is True
        assert by_code[code]["hidden_gold_visible"] is False
    assert by_code["unsupported_historical_valuation_comparison"]["correction_class"] == "uncalibrated_valuation_reference"
    assert by_code["unsupported_historical_valuation_comparison"]["new_model_call_required"] is False
