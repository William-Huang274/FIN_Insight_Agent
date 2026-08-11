from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r10_source_grounded_deterministic_"
    "baseline_materialization_v1_0.json"
)
ASSESSMENT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r10_success_only_paired_assessment_"
    "and_owner_acceptance_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_grounded_baseline_is_exact_once_and_distinct() -> None:
    result = _load(BASELINE)

    assert result["status"].startswith(
        "pass_exact_once_source_grounded_deterministic_baseline"
    )
    assert list(result["terminal_truth"].values())[:3] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert result["terminal_truth"]["exact_deterministic_run_cardinality"] == 1
    assert result["terminal_truth"]["artifact_count"] == 4
    assert result["root_cause_repair"]["legacy_P36_NVDA_preview_used"] is False
    assert result["root_cause_repair"]["case_ticker"] == "DELL"
    assert result["identity"]["research_run_id"] != result["identity"][
        "distinct_from_agent_research_run_id"
    ]
    assert set(result["observed_counts"].values()) == {0, 1}
    assert result["observed_counts"]["baseline_materializations"] == 1
    assert result["boundary"]["baseline_output_body_exposed_to_agent"] is False


def test_paired_assessment_binds_exact_baseline_and_blocks_false_acceptance() -> None:
    assessment = _load(ASSESSMENT)
    source = assessment["source_evidence"]
    layers = assessment["four_layer_assessment"]

    assert source["baseline_result_sha256"] == _sha256(BASELINE)
    assert assessment["status"] == (
        "fail_L1_numeric_and_entity_identity_integrity_"
        "owner_acceptance_ineligible"
    )
    assert layers["L1_hard_integrity"]["status"] == "fail"
    assert layers["L1_hard_integrity"][
        "machine_verifier_false_negative_confirmed"
    ] is True
    assert {
        row["finding_id"]
        for row in layers["L1_hard_integrity"]["findings"]
    } == {
        "agent_numeric_statement_does_not_equal_bound_numeric_authority",
        "dell_report_title_declares_nvda",
    }
    assert layers["L3_analytical_quality"]["agent_gain_over_baseline"][
        "what_would_change_tasks"
    ] == 8
    assert assessment["stage_decision"]["owner_acceptance"] == (
        "not_eligible_while_L1_fails"
    )
    assert assessment["stage_decision"]["S4_T06_unblocked"] is False
    assert assessment["machine_recommendation"] == (
        "do_not_accept_R10_and_do_not_enter_S4_T06"
    )


def test_numeric_findings_preserve_exact_authority_examples() -> None:
    assessment = _load(ASSESSMENT)
    numeric = next(
        row
        for row in assessment["four_layer_assessment"]["L1_hard_integrity"][
            "findings"
        ]
        if row["finding_id"]
        == "agent_numeric_statement_does_not_equal_bound_numeric_authority"
    )

    assert len(numeric["examples"]) == 3
    assert "24400 USD_millions" in numeric["examples"][0][
        "bound_numeric_authority"
    ]
    assert "16132 USD_millions" in numeric["examples"][1][
        "bound_numeric_authority"
    ]
    assert "free cash flow positive 3118 USD_millions" in numeric["examples"][2][
        "bound_numeric_authority"
    ]
