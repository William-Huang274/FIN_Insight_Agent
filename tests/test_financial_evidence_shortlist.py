import json
from pathlib import Path
from types import SimpleNamespace

from retrieval.financial_evidence_shortlist import rank_financial_evidence_shortlist


ROOT = Path(__file__).resolve().parents[1]


def _ontology() -> dict:
    return json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_0.json"
        ).read_text(encoding="utf-8")
    )


def _ontology_v1_1() -> dict:
    return json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_1.json"
        ).read_text(encoding="utf-8")
    )


def _ontology_v1_2() -> dict:
    return json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
        ).read_text(encoding="utf-8")
    )


def _lane(facet: str, slot: str = "operating_performance") -> SimpleNamespace:
    return SimpleNamespace(
        facet_id=facet,
        slot_id=slot,
        subject_ticker="MU",
        evidence_owner_tickers=("MU",),
        relationship_constraints=("subject_self_disclosure",),
    )


def _object(
    identity: str,
    text: str,
    *,
    kind: str = "claim",
    section: str = "Item 2",
    metric: str = "Revenue",
    source_tier: str = "primary_sec_filing",
) -> dict:
    return {
        "compiled_object_id": identity,
        "object_kind": kind,
        "model_text": text,
        "structured_projection": (
            {
                "metric_row_label": metric,
                "metric_row_cells": ["100", "80"],
                "header_lines": ["Three Months Ended"],
            }
            if kind == "metric_row"
            else {}
        ),
        "base_object_view": {
            "ticker": "MU",
            "section": section,
            "subsection": "",
            "source_type": "10-Q",
            "source_tier": source_tier,
            "publication_date": "2026-06-25",
        },
    }


def test_metric_exact_route_beats_generic_result_background() -> None:
    objects = {
        "metric": _object("metric", "Revenue 100 80", kind="metric_row"),
        "generic": _object(
            "generic",
            "Revenue may vary in the future.",
            section="Item 1A. Risk Factors",
        ),
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("generic", "metric"),
        objects_by_id=objects,
        lane=_lane("reported_results"),
        route_membership={
            "metric": [{"route_id": "typed_metric_row_exact", "rank": 3}],
            "generic": [{"route_id": "qwen3_embedding_0_6b_dense", "rank": 1}],
        },
        cross_encoder_ranks_by_id={"metric": {"qwen": 20}, "generic": {"qwen": 1}},
    )
    assert ranking[0]["compiled_object_id"] == "metric"


def test_direct_shipment_beats_generic_supply_risk_for_upstream_facet() -> None:
    objects = {
        "shipment": _object(
            "shipment",
            "HBM4 is in high-volume shipments for our lead customer platform.",
        ),
        "risk": _object(
            "risk",
            "Suppliers may allocate capacity to other customers.",
            section="Item 1A. Risk Factors",
        ),
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("risk", "shipment"),
        objects_by_id=objects,
        lane=_lane("upstream_capacity_context", "capacity_inputs_execution"),
        route_membership={
            "shipment": [{"route_id": "bm25_need_lexical", "rank": 4}],
            "risk": [{"route_id": "bm25_need_lexical", "rank": 1}],
        },
        cross_encoder_ranks_by_id={},
    )
    assert ranking[0]["compiled_object_id"] == "shipment"


def test_binding_volume_commitment_beats_customer_concentration_background() -> None:
    objects = {
        "binding": _object(
            "binding",
            "Customer agreements include binding commitments for specific volumes over multi-year contract terms.",
        ),
        "concentration": _object(
            "concentration",
            "A significant portion of revenue is concentrated with certain customers.",
            section="Item 1A. Risk Factors",
        ),
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("concentration", "binding"),
        objects_by_id=objects,
        lane=_lane("subject_relationship_disclosure", "relationship_attribution"),
        route_membership={
            "binding": [{"route_id": "bm25_need_lexical", "rank": 8}],
            "concentration": [{"route_id": "bm25_need_lexical", "rank": 1}],
        },
        cross_encoder_ranks_by_id={},
    )
    assert ranking[0]["compiled_object_id"] == "binding"


def test_financial_intent_places_exact_operating_cash_flow_before_proxies() -> None:
    objects = {
        "target": _object(
            "target",
            "Net cash provided by operating activities | 50,344",
            kind="metric_row",
            metric="Net cash provided by operating activities",
        ),
        "lease": _object(
            "lease",
            "Operating cash flow used for operating leases | 185",
            kind="metric_row",
            metric="Operating cash flow used for operating leases",
        ),
        "free": _object(
            "free",
            "Free cash flow | 48,554",
            kind="metric_row",
            metric="Free cash flow",
        ),
    }
    request = {
        "metric_intents": ["operating cash flow"],
        "product_intents": ["cash conversion"],
        "acceptable_proxy": False,
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("lease", "free", "target"),
        objects_by_id=objects,
        lane=_lane("cash_generation", "cash_conversion_balance_sheet"),
        route_membership={
            "lease": [{"route_id": "typed_exact_phrase", "rank": 1}],
            "free": [{"route_id": "typed_metric_row_exact", "rank": 1}],
            "target": [{"route_id": "typed_metric_row_exact", "rank": 8}],
        },
        cross_encoder_ranks_by_id={},
        request=request,
        intent_ontology=_ontology(),
    )
    assert ranking[0]["compiled_object_id"] == "target"
    assert ranking[1]["financial_intent"]["compatibility"] == "incompatible"


def test_financial_intent_pushes_capacity_homonyms_below_supply_commitment() -> None:
    objects = {
        "supply": _object(
            "supply",
            "We paid deposits to secure future supply and capacity from manufacturers.",
        ),
        "paper": _object(
            "paper", "Our commercial paper program had a capacity of $25 billion."
        ),
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("paper", "supply"),
        objects_by_id=objects,
        lane=_lane("upstream_capacity_context", "capacity_inputs_execution"),
        route_membership={
            "paper": [{"route_id": "bm25_need_lexical", "rank": 1}],
            "supply": [{"route_id": "bm25_need_lexical", "rank": 20}],
        },
        cross_encoder_ranks_by_id={},
        request={
            "metric_intents": [],
            "product_intents": ["GPU supply capacity and transition risk"],
            "acceptable_proxy": False,
        },
        intent_ontology=_ontology(),
    )
    assert ranking[0]["compiled_object_id"] == "supply"


def test_composite_gate_places_reported_result_before_product_catalog() -> None:
    objects = {
        "result": _object(
            "result",
            "CMBU revenue increased 257% driven by HBM demand in data center markets.",
        ),
        "catalog": _object(
            "catalog",
            "In addition to HBM, CMBU sales include DDR for the data center market.",
        ),
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("catalog", "result"),
        objects_by_id=objects,
        lane=_lane("reported_results"),
        route_membership={
            "catalog": [{"route_id": "typed_intent_alias_groups", "rank": 1}],
            "result": [{"route_id": "typed_intent_alias_groups", "rank": 20}],
        },
        cross_encoder_ranks_by_id={},
        request={
            "metric_intents": ["revenue"],
            "product_intents": ["HBM and data center business"],
            "acceptable_proxy": False,
        },
        intent_ontology=_ontology_v1_1(),
    )
    assert ranking[0]["compiled_object_id"] == "result"
    assert ranking[0]["composite_compatibility"] == "compatible"
    assert ranking[1]["composite_compatibility"] == "incompatible"


def test_mixed_request_allows_one_row_to_satisfy_one_compiled_need() -> None:
    objects = {
        "segment": _object(
            "segment",
            "Segment Result | 2,560 | 3,105 | (545) | (18)",
            kind="metric_row",
            metric="Segment Result",
        ),
        "catalog": _object(
            "catalog",
            "The segment structure includes several product categories.",
        ),
    }
    needs = [
        {
            "need_id": "need::segment-result",
            "need_kind": "metric",
            "facet_id": "reported_results",
            "intent_terms": ["segment result"],
        },
        {
            "need_id": "need::structure-change",
            "need_kind": "product",
            "facet_id": "reported_results",
            "intent_terms": ["segment structure change"],
        },
    ]
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("catalog", "segment"),
        objects_by_id=objects,
        lane=_lane("reported_results"),
        route_membership={
            "segment": [
                {
                    "route_id": "bm25_need_lexical",
                    "need_id": "need::segment-result",
                    "rank": 4,
                }
            ],
            "catalog": [
                {
                    "route_id": "bm25_need_lexical",
                    "need_id": "need::structure-change",
                    "rank": 1,
                }
            ],
        },
        cross_encoder_ranks_by_id={},
        request={
            "metric_intents": ["segment result", "year over year change"],
            "product_intents": ["segment structure change"],
            "acceptable_proxy": False,
        },
        intent_ontology=_ontology_v1_1(),
        retrieval_needs=needs,
    )

    assert ranking[0]["compiled_object_id"] == "segment"
    assert ranking[0]["composite_compatibility"] == "compatible"
    assert ranking[0]["best_retrieval_need"]["need_id"] == (
        "need::segment-result"
    )


def test_metric_product_need_precedes_generic_metric_only_context() -> None:
    objects = {
        "product-result": _object(
            "product-result",
            "AI server revenue increased 80% year over year.",
        ),
        "generic-result": _object(
            "generic-result",
            "Revenue increased 10% year over year.",
        ),
    }
    needs = [
        {
            "need_id": "need::metric-product",
            "need_kind": "metric_product",
            "facet_id": "reported_results",
            "intent_terms": ["revenue", "AI-optimized servers"],
        },
        {
            "need_id": "need::metric",
            "need_kind": "metric",
            "facet_id": "reported_results",
            "intent_terms": ["revenue"],
        },
        {
            "need_id": "need::generic-phrase",
            "need_kind": "exact_phrase",
            "facet_id": "reported_results",
            "intent_terms": ["revenue"],
        },
    ]
    routes = {
        "product-result": [
            {
                "route_id": "typed_intent_alias_groups",
                "need_id": "need::metric-product",
                "rank": 8,
            }
        ],
        "generic-result": [
            {
                "route_id": "bm25_need_lexical",
                "need_id": "need::metric",
                "rank": 1,
            }
        ],
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("generic-result", "product-result"),
        objects_by_id=objects,
        lane=_lane("reported_results"),
        route_membership=routes,
        cross_encoder_ranks_by_id={},
        request={
            "metric_intents": ["revenue"],
            "product_intents": ["AI-optimized servers"],
            "acceptable_proxy": False,
        },
        intent_ontology=_ontology_v1_1(),
        retrieval_needs=needs,
    )

    assert ranking[0]["compiled_object_id"] == "product-result"
    assert ranking[0]["best_retrieval_need"]["need_kind"] == "metric_product"


def test_official_hosted_management_call_is_first_party_authority() -> None:
    objects = {
        "official-call": _object(
            "official-call",
            "AI server profitability was in line with our mid-single-digit operating income rate target.",
            source_tier="official_hosted_management_call_transcript",
        ),
        "unknown-copy": _object(
            "unknown-copy",
            "AI server profitability was in line with our mid-single-digit operating income rate target.",
            source_tier="unclassified_web_copy",
        ),
    }
    need = {
        "need_id": "need::ai-server-margin",
        "need_kind": "metric_product",
        "facet_id": "pricing_and_mix",
        "intent_terms": ["operating margin", "AI-optimized servers"],
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("unknown-copy", "official-call"),
        objects_by_id=objects,
        lane=_lane("pricing_and_mix", "pricing_mix_value_capture"),
        route_membership={
            "official-call": [{"route_id": "bm25_need_lexical", "need_id": need["need_id"], "rank": 1}],
            "unknown-copy": [{"route_id": "bm25_need_lexical", "need_id": need["need_id"], "rank": 1}],
        },
        cross_encoder_ranks_by_id={},
        request={
            "metric_intents": ["operating margin"],
            "product_intents": ["AI-optimized servers"],
            "acceptable_proxy": False,
        },
        intent_ontology=_ontology_v1_2(),
        retrieval_needs=[need],
    )
    assert ranking[0]["compiled_object_id"] == "official-call"
    assert ranking[0]["source_authority_tier"] == 3
    assert ranking[0]["candidate_not_evidence"] is True
    assert ranking[0]["numeric_authority"] is False
