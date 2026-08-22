from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.research.quantitative_authority import (
    QuantitativeAuthorityError,
    compile_quantitative_authority_state,
    compile_research_estimate,
    compile_research_scenario,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "DELL": (38, 27, 9, 0),
    "MU": (16, 13, 10, 1),
    "NVDA": (19, 15, 10, 0),
}


def _request_results(case_key: str) -> list[dict]:
    path = (
        ROOT
        / "data"
        / "workbench_private"
        / "fin_0_1_3_s1_source_route_truth_replay"
        / f"{case_key.lower()}-r1"
        / "full_result.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["product_projection"]["request_results"]


@pytest.mark.parametrize("case_key", tuple(EXPECTED))
def test_current_three_case_numeric_results_are_separated_by_authority_kind(
    case_key: str,
) -> None:
    result = compile_quantitative_authority_state(
        case_key=case_key,
        request_results=_request_results(case_key),
        recorded_at="2026-08-22",
    )

    expected_reported, expected_derived, expected_gaps, expected_conflicts = (
        EXPECTED[case_key]
    )
    assert result["summary"] == {
        "reported_fact_count": expected_reported,
        "deterministic_derived_metric_count": expected_derived,
        "research_estimate_count": 0,
        "scenario_count": 0,
        "typed_gap_count": expected_gaps,
        "typed_conflict_count": expected_conflicts,
    }
    assert all(
        row["quantitative_kind"] == "reported_fact"
        and row["numeric_fact_authority"] is True
        and row["authority_mode"].startswith("source_bound_")
        for row in result["reported_facts"]
    )
    assert all(
        row["quantitative_kind"] == "deterministic_derived_metric"
        and row["reported_fact_authority"] is False
        and row["numeric_fact_authority"] is False
        and row["deterministic_formula_authority"] is True
        and row["input_authority_refs"]
        and row["formula"]
        for row in result["deterministic_derived_metrics"]
    )


def test_declared_cross_company_targets_are_valid_but_undeclared_ticker_fails() -> None:
    request_results = _request_results("DELL")
    result = compile_quantitative_authority_state(
        case_key="DELL",
        request_results=request_results,
        recorded_at="2026-08-22",
    )
    assert {"DELL", "MU", "NVDA"}.issubset(
        {row["ticker"] for row in result["reported_facts"]}
    )

    mutated = deepcopy(request_results)
    target = next(
        typed
        for request in mutated
        for typed in request["typed_fact_results"]
        if typed["status"] == "resolved" and typed["facts"]
    )
    target["ticker"] = "ORCL"
    target["facts"][0]["ticker"] = "ORCL"
    with pytest.raises(
        QuantitativeAuthorityError,
        match="quantitative_state_typed_result_invalid",
    ):
        compile_quantitative_authority_state(
            case_key="DELL",
            request_results=mutated,
            recorded_at="2026-08-22",
        )


def test_estimate_and_scenario_never_acquire_reported_fact_authority() -> None:
    estimate = compile_research_estimate(
        {
            "case_key": "DELL",
            "metric_id": "ai_server_revenue",
            "period_label": "next_fiscal_year",
            "unit": "USD",
            "lower_bound": "100",
            "central_value": "120",
            "upper_bound": "150",
            "method": "volume_times_price_range",
            "assumption_refs": ["ASSUMPTION::VOLUME", "ASSUMPTION::PRICE"],
            "supporting_authority_refs": ["NUMFACT::SOURCE"],
            "authored_by": "AGENT::VALUE_CAPTURE",
            "confidence": "low",
        }
    )
    scenario = compile_research_scenario(
        {
            "case_key": "DELL",
            "scenario_name": "supply_delay",
            "scenario_type": "downside",
            "time_horizon": "next_fiscal_year",
            "assumption_refs": ["ASSUMPTION::SUPPLY"],
            "output_estimate_refs": [estimate["estimate_id"]],
            "authored_by": "AGENT::VALUE_CAPTURE",
        }
    )

    assert estimate["numeric_fact_authority"] is False
    assert estimate["citation_as_reported_fact_forbidden"] is True
    assert scenario["numeric_fact_authority"] is False
    assert scenario["reported_fact_language_forbidden"] is True
