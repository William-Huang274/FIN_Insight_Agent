from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

from retrieval.contracts import load_evidence_request, load_financial_research_kernel
from retrieval.query_plan import compile_query_facet_plan_for_request
from retrieval.route_compiler import load_query_object_fact_route_policy


ROOT = Path(__file__).resolve().parents[1]


def _runner():
    path = ROOT / "scripts/data_retrieval/materialize_s1_dynamic_public_reachability_successor.py"
    spec = spec_from_file_location("s1_dynamic_public_reachability_successor", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_successor_kernel_separates_external_owner_roles() -> None:
    runner = _runner()
    kernel_payload = runner._successor_kernel(
        _json("configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_3.json")
    )
    kernel = load_financial_research_kernel(kernel_payload)
    dell = kernel.cases["DELL"]
    roles = {row.economic_role for row in dell.related_entities}
    assert {
        "industry_market_context",
        "trusted_analysis_context",
        "channel_configuration_context",
    }.issubset(roles)
    assert "PUBLIC_WEB" in kernel.slot_by_id()["pricing_mix_value_capture"].source_types


def test_public_evidence_request_compiles_only_requested_owner_and_facet() -> None:
    runner = _runner()
    kernel_payload = runner._successor_kernel(
        _json("configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_3.json")
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route_payload = runner._successor_route(
        _json("configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_3.json"),
        kernel_ref="configs/retrieval/test-kernel.json",
        kernel_sha256="a" * 64,
    )
    load_query_object_fact_route_policy(route_payload, kernel)
    request = load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": "REQ::DELL::INDUSTRY-PVM::TEST",
            "cell_id": "CELL::value_capture",
            "requester_role": "fundamental_value_capture_analyst",
            "evidence_domain": "financial_research",
            "case_key": "DELL",
            "subject_ticker": "DELL",
            "research_as_of": "2026-08-06",
            "target_entities": ["ORG::13AAFF874F67F30C"],
            "requested_facet_ids": ["industry_pricing_mix_context"],
            "metric_intents": ["shipments", "average_selling_price"],
            "product_intents": ["AI server mix"],
            "period": {
                "start_date": "2025-01-01",
                "end_date": "2026-08-06",
                "fiscal_years": [],
            },
            "granularity": "source_bound_claim",
            "unit": "issuer_or_industry_reported",
            "acceptable_sources": ["PUBLIC_WEB"],
            "acceptable_proxy": True,
            "forbidden_proxy": ["industry fact treated as Dell fact"],
            "stop_condition": "reviewed evidence or typed gap",
            "clarification_policy": "return_typed_gap",
        },
        kernel,
    )
    plan = compile_query_facet_plan_for_request(kernel, request)
    assert len(plan.lanes) == 1
    lane = plan.lanes[0]
    assert lane.facet_id == "industry_pricing_mix_context"
    assert lane.evidence_owner_tickers == ("ORG::13AAFF874F67F30C",)
    assert lane.source_types == ("PUBLIC_WEB",)
    assert "DELL" not in lane.evidence_owner_tickers
