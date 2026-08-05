from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

from materialize_fin_ia_0_1_3_repair_closeout_s0_03_financial_truth_oracle import (  # noqa: E402
    materialize,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_semantic_truth_oracle import (  # noqa: E402
    LAYER_ANALYSIS_QUALITY,
    LAYER_FINANCIAL_TRUTH,
    LAYER_PRODUCT_USABILITY,
    LAYER_SHAPE,
    classify_stage_finding,
    evaluate_financial_truth,
)


POLICY_REF = Path(
    "configs/runtime/fin_ia_0_1_3_repair_closeout_"
    "financial_semantic_truth_oracle_v1_0.json"
)
FIXTURE_REF = Path(
    "tests/fixtures/fin_0_1_3/"
    "financial_semantic_truth_oracle_three_case_v1.json"
)
DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_03_"
    "financial_semantic_truth_oracle_classification_v1_0.json"
)
ACTIVE_SUITE_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_03_"
    "active_test_suite_successor_v1_0.json"
)
CURRENT_DELL_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_pack_v1_0.json"
)


def _load(ref: Path) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _sha(ref: Path) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _codes(result: dict) -> set[str]:
    return {row["code"] for row in result["findings"]}


def test_policy_has_four_non_substitutable_layers_and_routes() -> None:
    policy = _load(POLICY_REF)
    layers = {row["layer"]: row for row in policy["layers"]}
    assert set(layers) == {
        LAYER_SHAPE,
        LAYER_FINANCIAL_TRUTH,
        LAYER_ANALYSIS_QUALITY,
        LAYER_PRODUCT_USABILITY,
    }
    assert layers[LAYER_SHAPE]["blocks_financial_truth_entry"]
    assert layers[LAYER_FINANCIAL_TRUTH]["blocks_financial_truth_entry"]
    assert not layers[LAYER_ANALYSIS_QUALITY]["blocks_financial_truth_entry"]
    assert layers[LAYER_ANALYSIS_QUALITY]["release_blocking_at_owner_stage"]
    assert layers[LAYER_PRODUCT_USABILITY]["release_blocking_at_owner_stage"]
    assert policy["period_invariants"]["filing_type_never_determines_fact_duration"]


def test_reviewed_dell_mu_nvda_annual_truth_rows_pass() -> None:
    fixture = _load(FIXTURE_REF)
    results = [evaluate_financial_truth(row, row) for row in fixture["reviewed_truth_rows"]]
    assert [row["record_id"].split("_")[0] for row in results] == ["DELL", "MU", "NVDA"]
    assert all(row["status"] == "pass_financial_truth_ceiling" for row in results)
    assert all(row["finding_count"] == 0 for row in results)


def test_known_current_dell_q4_as_annual_and_filed_time_substitution_fail() -> None:
    known = _load(FIXTURE_REF)["known_current_failure"]
    result = evaluate_financial_truth(known["candidate"], known["reviewed_truth"])
    assert result["status"] == "blocked_before_s1_s3"
    assert not result["financial_truth_entry_allowed"]
    assert {
        "fiscal_period_mismatch",
        "period_role_mismatch",
        "source_filed_at_mismatch",
        "annual_duration_out_of_range",
    } <= _codes(result)
    assert result["findings_by_layer"][LAYER_FINANCIAL_TRUTH] >= 4
    assert result["findings_by_layer"][LAYER_ANALYSIS_QUALITY] == 0


def test_known_failure_fixture_is_bound_to_current_dell_numeric_projection() -> None:
    known = _load(FIXTURE_REF)["known_current_failure"]["candidate"]
    pack = _load(CURRENT_DELL_PACK_REF)
    current = next(row for row in pack["numeric_rows"] if row["metric_family"] == "revenue")
    assert current["entity_ref"] == known["entity_ref"] == "DELL"
    assert current["value"] == known["raw_value"] == "23931000000"
    assert current["period"] == "FY2025-FY"
    assert current["source_filed_at"] == known["source_filed_at"] == "2026-06-23"
    assert "period_end=2025-01-31; filed=2025-03-25" in current["citation"]


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"entity_ref": "MU"}, "entity_ref_mismatch"),
        ({"issuer_id": "0000723125"}, "issuer_id_mismatch"),
        ({"period_role": "quarter", "fiscal_period": "Q4"}, "period_role_mismatch"),
        ({"unit": "USD_millions"}, "unit_mismatch"),
        ({"scale_multiplier": "1000000"}, "scale_multiplier_mismatch"),
        ({"normalized_value": "130497000"}, "normalized_value_mismatch"),
        ({"source_filed_at": "2026-06-23"}, "source_filed_at_mismatch"),
    ],
)
def test_material_financial_truth_mutations_fail(mutation: dict, expected_code: str) -> None:
    truth = _load(FIXTURE_REF)["reviewed_truth_rows"][2]
    candidate = deepcopy(truth)
    candidate.update(mutation)
    result = evaluate_financial_truth(candidate, truth)
    assert not result["financial_truth_entry_allowed"]
    assert expected_code in _codes(result)


def test_duration_and_formula_recalculation_mutations_fail() -> None:
    truth = _load(FIXTURE_REF)["reviewed_truth_rows"][2]
    duration = deepcopy(truth)
    duration["duration_days"] = 91
    assert "duration_days_mismatch" in _codes(evaluate_financial_truth(duration, truth))

    formula = deepcopy(truth)
    formula["formula"] = {
        "operator": "divide",
        "input_values": ["97858000000", "130497000000"],
        "output_value": "80",
        "tolerance": "0.0001",
    }
    assert "formula_recalculation_mismatch" in _codes(evaluate_financial_truth(formula, truth))


def test_shape_analysis_and_usability_findings_are_not_conflated() -> None:
    truth = _load(FIXTURE_REF)["reviewed_truth_rows"][1]
    candidate = deepcopy(truth)
    candidate["source_locator"] = ""
    result = evaluate_financial_truth(candidate, truth)
    shape = next(row for row in result["findings"] if row["code"] == "required_field_missing")
    assert shape["layer"] == LAYER_SHAPE
    assert shape["blocks_financial_truth_entry"]

    analysis = classify_stage_finding(
        code="generic_claim_language",
        layer=LAYER_ANALYSIS_QUALITY,
        detail="company-specific mechanism is absent",
    )
    usability = classify_stage_finding(
        code="repair_action_not_executable",
        layer=LAYER_PRODUCT_USABILITY,
        detail="reviewer cannot execute a targeted repair",
    )
    assert analysis.owner == "S2_S3_research_quality"
    assert usability.owner == "S4_product_workflow"
    assert not analysis.blocks_financial_truth_entry
    assert not usability.blocks_financial_truth_entry
    with pytest.raises(ValueError, match="unknown_oracle_layer"):
        classify_stage_finding(code="bad", layer="other", detail="bad")


def test_materialized_decision_closes_classification_not_underlying_dell_truth() -> None:
    materialized = materialize()
    decision = _load(DECISION_REF)
    body = dict(decision)
    digest = body.pop("decision_digest")
    assert digest == canonical_digest(body)
    assert materialized["decision_sha256"] == _sha(DECISION_REF)
    assert decision["stage_truth"]["FIN_0_1_3_S0"] == "complete"
    assert decision["stage_truth"]["FIN_0_1_3_S1"] == "not_started_entry_authorized_for_repair_only"
    assert not decision["reviewed_fixture_result"]["current_DELL_product_truth_pass"]
    assert decision["reviewed_fixture_result"]["current_DELL_repair_owner"] == "013-S1-01"
    assert decision["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_or_source_calls": 0,
        "business_runs": 0,
        "business_artifacts": 0,
        "current_data_rows_rewritten": 0,
    }
    for binding in decision["source_bindings"]:
        assert _sha(Path(binding["ref"])) == binding["sha256"]
    rubric = next(
        row
        for row in decision["source_bindings"]
        if row["role"] == "current_research_quality_layer_requirement_successor"
    )
    assert rubric["ref"].endswith(
        "FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md"
    )


def test_active_suite_successor_selects_all_three_current_s0_tests() -> None:
    materialize()
    suite = _load(ACTIVE_SUITE_REF)
    body = dict(suite)
    digest = body.pop("suite_digest")
    assert digest == canonical_digest(body)
    assert [row["stage"] for row in suite["selected_tests"]] == [
        "013-S0-01", "013-S0-02", "013-S0-03"
    ]
    assert not suite["current_DELL_financial_truth_pass"]
    assert not suite["model_or_full_chain_authorized"]
    assert suite["next_action"].startswith("FIN-0.1.3-013-S1-01")
