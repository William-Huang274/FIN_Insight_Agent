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
