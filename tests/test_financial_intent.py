from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.financial_intent import (  # noqa: E402
    concept_aliases,
    evaluate_financial_intent,
    intent_alias_groups,
    validate_financial_intent_ontology,
)


ONTOLOGY = ROOT / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_0.json"
ONTOLOGY_V1_1 = ROOT / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_1.json"
ONTOLOGY_V1_2 = ROOT / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"


def _ontology() -> dict:
    return json.loads(ONTOLOGY.read_text(encoding="utf-8"))


def _ontology_v1_1() -> dict:
    return json.loads(ONTOLOGY_V1_1.read_text(encoding="utf-8"))


def _ontology_v1_2() -> dict:
    return json.loads(ONTOLOGY_V1_2.read_text(encoding="utf-8"))


def _row(text: str, *, kind: str = "claim", metric: str = "") -> dict:
    return {
        "compiled_object_id": "COBJ::TEST",
        "object_kind": kind,
        "model_text": text,
        "structured_projection": {"metric_row_label": metric} if metric else {},
    }


def test_ontology_resolves_metric_and_product_alias_groups() -> None:
    ontology = _ontology()
    validate_financial_intent_ontology(ontology)
    concept, aliases = concept_aliases(
        "operating cash flow", family="metric_concepts", ontology=ontology
    )
    assert concept == "operating_cash_flow"
    assert "net cash provided by operating activities" in aliases
    groups = intent_alias_groups(
        metric_intents=("revenue",),
        product_intents=("AI-optimized servers",),
        ontology=ontology,
    )
    assert any("AI server" in group for group in groups)


def test_exact_operating_cash_flow_beats_lease_and_free_cash_flow_proxies() -> None:
    ontology = _ontology()
    exact = evaluate_financial_intent(
        _row(
            "Net cash provided by operating activities | 50,344",
            kind="metric_row",
            metric="Net cash provided by operating activities",
        ),
        metric_intents=("operating cash flow",),
        product_intents=("cash conversion",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    lease = evaluate_financial_intent(
        _row(
            "Operating cash flow used for operating leases | 185",
            kind="metric_row",
            metric="Operating cash flow used for operating leases",
        ),
        metric_intents=("operating cash flow",),
        product_intents=("cash conversion",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    free_cash = evaluate_financial_intent(
        _row("Free cash flow | 48,554", kind="metric_row", metric="Free cash flow"),
        metric_intents=("operating cash flow",),
        product_intents=("cash conversion",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    assert exact.compatibility == "compatible"
    assert lease.compatibility == "incompatible"
    assert free_cash.compatibility == "incompatible"


def test_gpu_manufacturing_capacity_is_separated_from_capacity_homonyms() -> None:
    ontology = _ontology()
    supply = evaluate_financial_intent(
        _row(
            "We may provide deposits to secure future supply and capacity from our manufacturers."
        ),
        metric_intents=(),
        product_intents=("GPU supply capacity and transition risk",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    commercial_paper = evaluate_financial_intent(
        _row("Our commercial paper program had a capacity of $25.0 billion."),
        metric_intents=(),
        product_intents=("GPU supply capacity and transition risk",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    cloud_lease = evaluate_financial_intent(
        _row("The cloud capacity agreement can be assumed after a default."),
        metric_intents=(),
        product_intents=("GPU supply capacity and transition risk",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    assert supply.compatibility == "compatible"
    assert commercial_paper.compatibility == "incompatible"
    assert cloud_lease.compatibility == "incompatible"


def test_ai_server_reported_result_requires_metric_and_product_surfaces() -> None:
    ontology = _ontology()
    direct = evaluate_financial_intent(
        _row("We recognized $16.1 billion of AI server revenue."),
        metric_intents=("revenue", "operating income"),
        product_intents=("AI-optimized servers",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    gross_margin = evaluate_financial_intent(
        _row("Product gross margin increased 10% to $12.3 billion."),
        metric_intents=("revenue", "operating income"),
        product_intents=("AI-optimized servers",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    assert direct.compatibility == "compatible"
    assert gross_margin.compatibility == "incompatible"


def test_claim_primary_metric_rejects_later_requested_explanatory_metric() -> None:
    result = evaluate_financial_intent(
        _row("Gross margin increased due to a higher mix of Data Center revenue."),
        metric_intents=("revenue",),
        product_intents=("data center platform",),
        acceptable_proxy=False,
        ontology=_ontology(),
    )
    assert result.observed_metric_concept == "gross_margin"
    assert result.metric_compatibility == "incompatible"
    assert result.compatibility == "incompatible"


def test_broad_dram_term_is_proxy_not_hbm_business_proof() -> None:
    result = evaluate_financial_intent(
        _row("Total reported DRAM revenue was $28.58 billion in 2025."),
        metric_intents=("revenue",),
        product_intents=("HBM and data center business",),
        acceptable_proxy=False,
        ontology=_ontology_v1_1(),
    )
    assert result.metric_compatibility == "compatible"
    assert result.product_compatibility == "abstain"
    assert result.matched_product_proxy_terms == ("DRAM",)
    assert result.compatibility == "abstain"


def test_current_ontology_maps_operating_income_rate_to_operating_margin() -> None:
    result = evaluate_financial_intent(
        _row("AI server profitability was in line with our mid-single-digit operating income rate target."),
        metric_intents=("operating margin",),
        product_intents=("AI-optimized servers",),
        acceptable_proxy=False,
        ontology=_ontology_v1_2(),
    )
    assert result.schema_version == "fin_ia_financial_intent_evaluation_v1_2"
    assert result.observed_metric_concept == "operating_margin"
    assert result.metric_compatibility == "compatible"
    assert result.product_compatibility == "compatible"
    assert result.compatibility == "compatible"


def test_price_volume_mix_bridge_requires_full_bridge_surface() -> None:
    ontology = _ontology_v1_2()
    direct = evaluate_financial_intent(
        _row("The price-volume-mix bridge reconciles the year-over-year revenue change."),
        metric_intents=("price-volume-mix bridge",),
        product_intents=(),
        acceptable_proxy=False,
        ontology=ontology,
    )
    generic_mix = evaluate_financial_intent(
        _row("Gross margin declined because of a shift in product mix."),
        metric_intents=("price-volume-mix bridge",),
        product_intents=(),
        acceptable_proxy=False,
        ontology=ontology,
    )
    assert direct.compatibility == "compatible"
    assert generic_mix.compatibility == "incompatible"
