from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from apps.workbench.backend.api.v1.research_retrieval import (
    build_research_retrieval_router,
)
from retrieval.candidate_retriever import CandidateCorpus, retrieve_query_plan
from retrieval.contracts import (
    RetrievalContractError,
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.query_plan import (
    compile_query_facet_plan,
    compile_query_facet_plan_for_request,
)
from sec_agent.runtime_resource_registry import resolve_registered_runtime_resource


KERNEL_PATH = resolve_registered_runtime_resource(
    ROOT, "application.config.current_financial_research_kernel"
)
SNAPSHOT_PATH = resolve_registered_runtime_resource(
    ROOT, "application.result.current_research_retrieval_snapshot"
)
RANKING_PROJECTION_PATH = resolve_registered_runtime_resource(
    ROOT, "application.result.current_s1c_ranking_comparison_projection"
)


def _kernel():
    return load_financial_research_kernel(
        json.loads(KERNEL_PATH.read_text(encoding="utf-8"))
    )


def _evidence_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ-DELL-DEMAND-001",
        "cell_id": "DELL-DEMAND-CELL-001",
        "requester_role": "demand_specialist",
        "evidence_domain": "demand",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": ["DELL"],
        "requested_facet_ids": ["orders_and_backlog"],
        "metric_intents": ["orders", "backlog"],
        "product_intents": ["AI-optimized servers"],
        "period": {
            "start_date": None,
            "end_date": "2026-08-06",
            "fiscal_years": [],
        },
        "granularity": "quarter_and_fiscal_year",
        "unit": "reported_source_unit",
        "acceptable_sources": ["10-K", "10-Q", "8-K"],
        "acceptable_proxy": False,
        "forbidden_proxy": ["unbound industry demand"],
        "stop_condition": "return candidates or a typed gap",
        "clarification_policy": "return_typed_gap",
    }
    payload.update(overrides)
    return payload


def _record(
    evidence_id: str,
    ticker: str,
    publication_date: str,
    text: str,
    *,
    source_type: str = "10-Q",
    subsection: str = "Management discussion",
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "source_type": source_type,
        "source_tier": "primary_sec_filing",
        "ticker": ticker,
        "company": ticker,
        "fiscal_year": 2026,
        "period_end": "2026-06-30",
        "publication_date": publication_date,
        "section": "Item 2. Management's Discussion and Analysis",
        "subsection": subsection,
        "evidence_type": "management_discussion",
        "topics": [],
        "text": text,
        "source_url": f"https://example.test/{evidence_id}",
        "metadata": {"accession_number": evidence_id},
    }


def test_three_cases_compile_through_one_core_without_answer_urls() -> None:
    kernel = _kernel()
    plans = {
        case_key: compile_query_facet_plan(kernel, case_key)
        for case_key in ("DELL", "MU", "NVDA")
    }

    assert {len(plan.lanes) for plan in plans.values()} == {17}
    assert {len({lane.slot_id for lane in plan.lanes}) for plan in plans.values()} == {9}
    assert len({plan.plan_digest for plan in plans.values()}) == 3
    assert all(
        "http" not in lane.lexical_query
        and "sec.gov" not in lane.lexical_query
        for plan in plans.values()
        for lane in plan.lanes
    )
    assert all(
        lane.publication_date_lte == "2026-08-06"
        for plan in plans.values()
        for lane in plan.lanes
    )
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert {
        row["case_key"]: row["retrieval"]["query_plan_digest"]
        for row in snapshot["cases"]
    } == {key: plan.plan_digest for key, plan in plans.items()}


def test_evidence_request_selects_only_requested_facet_and_hard_constraints() -> None:
    kernel = _kernel()
    request = load_evidence_request(_evidence_request(), kernel)
    plan = compile_query_facet_plan_for_request(kernel, request)

    assert [lane.facet_id for lane in plan.lanes] == ["orders_and_backlog"]
    assert plan.lanes[0].evidence_owner_tickers == ("DELL",)
    assert plan.lanes[0].source_types == ("10-K", "10-Q", "8-K")
    assert request.metric_intents == ("orders", "backlog")
    assert "AI-optimized servers" in plan.lanes[0].lexical_query
    assert "AI-optimized servers" in plan.lanes[0].semantic_query


def test_related_entity_request_compiles_the_disclosure_owner_alias_not_subject_alias() -> None:
    kernel = _kernel()
    request = load_evidence_request(
        _evidence_request(
            request_id="REQ-DELL-TSM-CAPACITY-001",
            target_entities=["TSM"],
            requested_facet_ids=["upstream_capacity_context"],
            metric_intents=["capacity", "yield"],
            acceptable_sources=["10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"],
        ),
        kernel,
    )
    lane = compile_query_facet_plan_for_request(kernel, request).lanes[0]

    assert lane.evidence_owner_tickers == ("TSM",)
    assert any('"TSMC"' in query for query in lane.exact_queries)
    assert all('"Dell' not in query for query in lane.exact_queries)
    assert "Taiwan Semiconductor Manufacturing Company Limited" in lane.semantic_query


def test_evidence_request_fails_closed_on_unknown_facet_and_cross_case_target() -> None:
    kernel = _kernel()
    with pytest.raises(RetrievalContractError, match="facet_unknown"):
        load_evidence_request(
            _evidence_request(requested_facet_ids=["made_up_facet"]), kernel
        )
    with pytest.raises(RetrievalContractError, match="target_out_of_case_scope"):
        load_evidence_request(_evidence_request(target_entities=["ORCL"]), kernel)
    with pytest.raises(RetrievalContractError, match="intent_surface_invalid"):
        load_evidence_request(
            _evidence_request(metric_intents=["use qrel target_id from https://sec.gov"]),
            kernel,
        )


def test_candidate_generation_filters_wrong_identity_future_and_navigation() -> None:
    kernel = _kernel()
    plan = compile_query_facet_plan(kernel, "DELL")
    corpus = CandidateCorpus(
        records=(
            _record(
                "good-demand",
                "DELL",
                "2026-05-28",
                "AI server orders and backlog increased while customer readiness made shipments non-linear. " * 4,
            ),
            _record(
                "wrong-company",
                "AAPL",
                "2026-05-28",
                "AI server orders and backlog increased. " * 6,
            ),
            _record(
                "future-demand",
                "DELL",
                "2026-08-07",
                "AI server orders and backlog increased. " * 6,
            ),
            _record(
                "navigation",
                "DELL",
                "2026-05-28",
                "The presentation may be downloaded from the site and can be accessed at the archive. " * 5,
                subsection="Conference call information",
            ),
        ),
        records_scanned=4,
        invalid_records_excluded=0,
    )

    result = retrieve_query_plan(kernel, plan, corpus)
    demand = next(
        row
        for row in result["lane_results"]
        if row["lane"]["facet_id"] == "orders_and_backlog"
    )
    assert [row["source_record_id"] for row in demand["candidates"]] == [
        "good-demand"
    ]
    assert demand["exclusion_counts"]["outside_evidence_owner_scope"] >= 1
    assert demand["exclusion_counts"]["published_after_research_as_of"] >= 1
    assert demand["exclusion_counts"]["boilerplate_or_navigation"] >= 1
    assert result["summary"]["hard_constraint_failures"] == []


def test_related_company_context_does_not_claim_subject_allocation() -> None:
    kernel = _kernel()
    plan = compile_query_facet_plan(kernel, "DELL")
    corpus = CandidateCorpus(
        records=(
            _record(
                "nvda-capacity",
                "NVDA",
                "2026-05-20",
                "Advanced packaging capacity and HBM supply constrain shipments and product availability. " * 5,
            ),
        ),
        records_scanned=1,
        invalid_records_excluded=0,
    )

    result = retrieve_query_plan(kernel, plan, corpus)
    capacity = next(
        row
        for row in result["lane_results"]
        if row["lane"]["facet_id"] == "upstream_capacity_context"
    )
    candidate = capacity["candidates"][0]
    assert candidate["evidence_owner_ticker"] == "NVDA"
    assert candidate["relationship_direction"] == "supplier_to_subject"
    assert candidate["source_role"] == "related_entity_context"
    assert candidate["subject_mention_state"] == "no_direct_subject_mention"
    assert "不证明" in candidate["business_boundary_zh"]


def test_earnings_release_candidate_uses_reported_period_not_filing_year() -> None:
    kernel = _kernel()
    request = load_evidence_request(
        _evidence_request(
            request_id="REQ-DELL-FY2027-RESULTS-001",
            requested_facet_ids=["reported_results"],
            metric_intents=["revenue"],
            period={
                "start_date": None,
                "end_date": "2026-08-06",
                "fiscal_years": [2027],
            },
        ),
        kernel,
    )
    plan = compile_query_facet_plan_for_request(kernel, request)
    record = _record(
        "dell-q1-fy2027-earnings",
        "DELL",
        "2026-05-28",
        "Dell reported record quarterly revenue and operating results for fiscal 2027. "
        * 5,
        source_type="8-K",
        subsection="Exhibit 99.1 Earnings Release",
    )
    record["period_end"] = "2026-05-28"
    record["fiscal_year"] = 2026
    record["metadata"] = {
        "accession_number": "0001571996-26-000021",
        "reported_fiscal_year": 2027,
        "reported_fiscal_period": "Q1",
        "reported_period_end": "2026-05-01",
    }

    result = retrieve_query_plan(
        kernel,
        plan,
        CandidateCorpus(
            records=(record,),
            records_scanned=1,
            invalid_records_excluded=0,
        ),
    )
    candidate = result["lane_results"][0]["candidates"][0]

    assert candidate["fiscal_year"] == 2027
    assert candidate["period_end"] == "2026-05-01"
    assert candidate["temporal_binding"] == {
        "reporting_fiscal_year": 2027,
        "reporting_fiscal_year_source": "metadata.reported_fiscal_year",
        "reporting_period_end": "2026-05-01",
        "reporting_period_end_source": "metadata.reported_period_end",
        "source_record_fiscal_year": 2026,
        "source_record_period_end": "2026-05-28",
    }


def test_retired_chunk_alias_is_evaluation_only_and_matches_current_child() -> None:
    kernel = _kernel()
    plan = compile_query_facet_plan(kernel, "DELL")
    record = _record(
        "current-demand-child",
        "DELL",
        "2026-05-28",
        "AI server orders and backlog increased while customer readiness made shipments non-linear. "
        * 4,
    )
    record["metadata"] = {
        "accession_number": "0001571996-26-000021",
        "legacy_source_record_ids": ["retired-demand-chunk"],
    }
    corpus = CandidateCorpus(
        records=(record,),
        records_scanned=1,
        invalid_records_excluded=0,
    )

    result = retrieve_query_plan(
        kernel,
        plan,
        corpus,
        reviewed_targets_by_slot={
            "demand_volume_quality": {"retired-demand-chunk"}
        },
    )
    demand = next(
        row
        for row in result["lane_results"]
        if row["lane"]["facet_id"] == "orders_and_backlog"
    )

    assert demand["evaluation"]["missing_from_source_corpus"] == []
    assert demand["evaluation"]["matched_source_record_ids"] == [
        "retired-demand-chunk"
    ]
    assert demand["candidates"][0]["source_record_id"] == "current-demand-child"
    assert "legacy_source_record_ids" not in demand["candidates"][0]


def test_current_snapshot_is_read_only_candidate_projection() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    service = ResearchRetrievalService(snapshot=snapshot)
    projection = service.get_case(
        "dell",
        ResearchRetrievalPrincipal(
            mode="current",
            permissions=frozenset({"current_product:read"}),
        ),
    )

    assert projection["case_key"] == "DELL"
    assert projection["candidate_state"] == "candidate_not_evidence"
    assert projection["summary"]["slot_count"] == 9
    assert projection["summary"]["hard_constraint_failures"] == []
    assert projection["source_gap_summary"][
        "reviewed_label_occurrences_missing_from_current_corpus"
    ] == 0
    assert all(
        candidate["candidate_state"] == "candidate_not_evidence"
        for lane in projection["lanes"]
        for candidate in lane["candidates"]
    )
    rendered = json.dumps(projection, ensure_ascii=False)
    assert "reviewed_pack_match" not in rendered
    assert "matched_source_record_ids" not in rendered
    assert "reviewed_evaluation" not in rendered


def test_typed_request_executes_one_facet_against_current_snapshot() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    service = ResearchRetrievalService(snapshot=snapshot, kernel=_kernel())
    projection = service.execute_request(
        "DELL",
        _evidence_request(),
        ResearchRetrievalPrincipal(
            mode="current",
            permissions=frozenset({"current_product:read"}),
        ),
    )

    assert projection["status"] == "request_scoped_typed_local_retrieval_ready"
    assert projection["summary"]["requested_facet_count"] == 1
    assert projection["summary"]["compiled_lane_count"] == 1
    assert projection["query_plan"]["lanes"][0]["facet_id"] == "orders_and_backlog"
    assert projection["candidate_state"] == "candidate_not_evidence"
    assert projection["summary"]["network_calls"] == 0
    assert projection["summary"]["model_calls"] == 0
    assert all(
        candidate["evidence_owner_ticker"] == "DELL"
        and candidate["source_type"] in {"10-K", "10-Q", "8-K"}
        for candidate in projection["lanes"][0]["candidates"]
    )


def test_typed_request_route_case_mismatch_fails_closed() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    service = ResearchRetrievalService(snapshot=snapshot, kernel=_kernel())
    with pytest.raises(Exception, match="evidence_request_route_case_mismatch"):
        service.execute_request(
            "MU",
            _evidence_request(),
            ResearchRetrievalPrincipal(
                mode="current",
                permissions=frozenset({"current_product:read"}),
            ),
        )


def test_typed_request_api_requires_current_read_permission() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    service = ResearchRetrievalService(snapshot=snapshot, kernel=_kernel())
    app = FastAPI()
    app.include_router(build_research_retrieval_router(service), prefix="/api/v1")
    client = TestClient(app)
    path = "/api/v1/research-cases/DELL/retrieval-requests"

    denied = client.post(path, json=_evidence_request())
    assert denied.status_code == 403
    response = client.post(
        path,
        json=_evidence_request(),
        headers={
            "X-Fin-Product-Mode": "current",
            "X-Fin-Case-Permissions": "current_product:read",
        },
    )
    assert response.status_code == 200
    assert response.json()["summary"]["compiled_lane_count"] == 1
    assert response.json()["runtime_binding"] is None
    assert response.json()["route_execution_truth"] is None
    assert response.headers["etag"].startswith('"evidence-request=')


def test_s1c_ranking_projection_is_consumable_without_gold_identity() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    ranking = json.loads(RANKING_PROJECTION_PATH.read_text(encoding="utf-8"))
    service = ResearchRetrievalService(
        snapshot=snapshot,
        ranking_comparison=ranking,
    )
    projection = service.get_case(
        "NVDA",
        ResearchRetrievalPrincipal(
            mode="current",
            permissions=frozenset({"current_product:read"}),
        ),
    )

    comparison = projection["ranking_comparison"]
    assert comparison["candidate_state"] == "candidate_not_evidence"
    assert comparison["same_object_population_count"] == 1805
    assert set(comparison["route_summaries"]) == {
        "sparse_bm25",
        "dense_bge_m3",
        "fusion_rrf_1_1",
        "typed_financial_rerank",
    }
    rendered = json.dumps(comparison, ensure_ascii=False)
    assert "target_current_source_record_ids" not in rendered
    assert "target_in_top_k" not in rendered
    assert "target_rank" not in rendered
    assert "matched_qrel_ids" not in rendered
    assert all(
        "qrel" not in str(query["query_id"])
        for query in comparison["queries"]
    )
