from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.research.product_value_bridge import (
    ProductValueBridgeError,
    compile_product_value_bridge,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "configs/financial_facts/fin_ia_0_1_3_s2_dell_product_value_bridge_program_v1_0.json"
PACK = ROOT / "data/workbench_private/fin_0_1_3_s1_dell_direct_source_evidence/r4/successor/pack.json"
QUANTITATIVE = ROOT / "data/workbench_private/fin_0_1_3_s2_task_quantitative_program/dell-r2/full_result.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compile(program: dict | None = None, pack: dict | None = None) -> dict:
    quantitative = _json(QUANTITATIVE)["task_quantitative_projection"]
    return compile_product_value_bridge(
        program=program or _json(PROGRAM),
        evidence_pack=pack or _json(PACK),
        quantitative_projection=quantitative,
        recorded_at="2026-08-24T12:00:00+08:00",
    )


def test_dell_bridge_builds_revenue_surface_but_preserves_pvm_and_profit_gaps() -> None:
    result = _compile()

    assert result["status"] == "bounded_product_value_bridge_with_typed_gaps"
    assert result["bridge_readiness"] == {
        "safe_for_bounded_dynamic_research": True,
        "reported_product_revenue_bridge_available": True,
        "target_company_pvm_calculable": False,
        "product_profit_bridge_calculable": False,
        "s2_stage_qualified": False,
        "checks": result["bridge_readiness"]["checks"],
    }
    assert result["pvm_bridge"]["price_effect_value"] is None
    assert result["pvm_bridge"]["volume_effect_value"] is None
    assert result["pvm_bridge"]["mix_effect_value"] is None
    assert result["product_profit_bridge"][
        "implied_product_operating_profit_value"
    ] is None
    assert {row["gap_id"] for row in result["bridge_gap_receipts"]} == {
        "dell-gap-pricing-asp",
        "dell-gap-pricing-units",
        "dell-gap-price-volume-mix-bridge",
        "dell-gap-product-profit-attribution",
    }
    derived = {
        row["derived_metric_id"]: row
        for row in result["deterministic_source_surface_derivations"]
    }
    assert float(derived["dell_ai_server_share_of_company_revenue_q1_fy27"]["value_decimal"]) == pytest.approx(
        16132 / 43842
    )
    assert not any("asp" in key or "product_operating_profit" in key for key in derived)


def test_bridge_rejects_reviewer_number_not_on_source_surface() -> None:
    program = _json(PROGRAM)
    mutated = deepcopy(program)
    mutated["source_numeric_observations"][0]["source_text_term"] = (
        "AI-optimized servers | $ | 99,999"
    )

    with pytest.raises(
        ProductValueBridgeError,
        match="product_bridge_source_observation_surface_invalid",
    ):
        _compile(program=mutated)


def test_bridge_rejects_silent_product_profit_gap_closure() -> None:
    program = _json(PROGRAM)
    mutated = deepcopy(program)
    mutated["product_profit_bridge_gap"]["closed"] = True

    with pytest.raises(
        ProductValueBridgeError,
        match="product_bridge_profit_gap_invalid",
    ):
        _compile(program=mutated)


def test_bridge_rejects_company_asp_authority_on_bounded_quote() -> None:
    program = _json(PROGRAM)
    mutated = deepcopy(program)
    target = next(
        row
        for row in mutated["source_numeric_observations"]
        if row["observation_id"] == "dell_public_recommended_bundle_price_sample"
    )
    target["target_company_aggregate_authority"] = True

    with pytest.raises(
        ProductValueBridgeError,
        match="product_bridge_source_observation_surface_invalid",
    ):
        _compile(program=mutated)
