from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import (
    RetrievalContractError,
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.object_view_compiler import compile_object_store
from retrieval.route_compiler import (
    compile_retrieval_execution_plan,
    load_query_object_fact_route_policy,
)


KERNEL_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json"
)
POLICY_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json"
)


def _kernel_payload() -> dict[str, object]:
    return json.loads(KERNEL_PATH.read_text(encoding="utf-8"))


def _policy_payload() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _kernel():
    return load_financial_research_kernel(_kernel_payload())


def _policy():
    kernel = _kernel()
    return load_query_object_fact_route_policy(_policy_payload(), kernel)


def _request(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ-DELL-MIXED-001",
        "cell_id": "DELL-MIXED-CELL-001",
        "requester_role": "research_lead",
        "evidence_domain": "financial_research",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": ["DELL"],
        "requested_facet_ids": ["reported_results", "cash_generation"],
        "metric_intents": ["revenue", "free cash flow"],
        "product_intents": ["AI-optimized servers"],
        "period": {
            "start_date": None,
            "end_date": "2026-08-06",
            "fiscal_years": [2025, 2026],
        },
        "granularity": "quarter_and_fiscal_year",
        "unit": "reported_source_unit",
        "acceptable_sources": ["10-K", "10-Q", "8-K"],
        "acceptable_proxy": False,
        "forbidden_proxy": ["unbound industry demand"],
        "stop_condition": "return candidates, typed facts, or typed gaps",
        "clarification_policy": "return_typed_gap",
    }
    value.update(overrides)
    return value


def test_route_policy_covers_every_kernel_facet_once_and_keeps_database_lane() -> None:
    policy = _policy()
    assert len(policy.query_families) == 11
    assert len(policy.family_by_facet()) == 17
    assert {row.storage_route for row in policy.metric_routes} == {
        "company_financial_fact_mart",
        "market_snapshot_fact_mart",
    }
    assert policy.authority["fact_request_is_not_numeric_fact"] is True
    assert policy.authority["typed_fact_executor_required_for_numeric_authority"] is True


def test_mixed_request_splits_narrative_and_database_siblings_without_authority() -> None:
    kernel = _kernel()
    request = load_evidence_request(_request(), kernel)
    plan = compile_retrieval_execution_plan(_policy(), request)
    assert [row.query_family_id for row in plan.narrative_requests] == [
        "reported_results",
        "cash_conversion",
    ]
    assert {row.metric_id for row in plan.typed_fact_requests} == {
        "revenue",
        "free_cash_flow",
    }
    assert all(row.numeric_fact_authority is False for row in plan.typed_fact_requests)
    assert all(
        row.execution_status == "typed_store_unavailable"
        for row in plan.typed_fact_requests
    )
    assert {
        row["gap_code"]
        for row in plan.typed_gaps
    } == {"typed_fact_store_unavailable"}
    assert plan.plan_digest == compile_retrieval_execution_plan(
        _policy(), request
    ).plan_digest


def test_available_fact_store_changes_execution_state_not_numeric_authority() -> None:
    kernel = _kernel()
    request = load_evidence_request(_request(), kernel)
    plan = compile_retrieval_execution_plan(
        _policy(),
        request,
        fact_store_availability={"company_financial_fact_mart": True},
    )
    assert all(
        row.execution_status == "ready_for_typed_fact_executor"
        for row in plan.typed_fact_requests
    )
    assert not plan.typed_gaps
    assert all(row.numeric_fact_authority is False for row in plan.typed_fact_requests)


def test_demand_and_relationship_attribution_are_not_one_query_family() -> None:
    family_by_facet = _policy().family_by_facet()
    assert family_by_facet["orders_and_backlog"].family_id == (
        "customer_demand_read_through"
    )
    assert family_by_facet["counterparty_direct_mention"].family_id == (
        "relationship_attribution"
    )


def test_policy_fails_closed_when_one_facet_is_mapped_twice() -> None:
    payload = deepcopy(_policy_payload())
    payload["query_families"][1]["facet_ids"].append("orders_and_backlog")
    with pytest.raises(RetrievalContractError, match="facet_route_overlap"):
        load_query_object_fact_route_policy(payload, _kernel())


def test_object_compiler_separates_claim_metric_rows_and_parent_context() -> None:
    parent = {
        "document_id": "CURRENT_DOC::DELL::10_Q::TEST",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "source_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-05-30",
        "period_end": "2026-05-01",
        "fiscal_year": 2026,
    }
    record = {
        "evidence_id": "DELL_TEST_RECORD_001",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "source_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-05-30",
        "period_end": "2026-05-01",
        "fiscal_year": 2026,
        "section": "Item 2. Management Discussion",
        "subsection": "Results of Operations",
        "metadata": {"parent_document_id": parent["document_id"]},
        "text": (
            "Demand for AI-optimized servers increased during the quarter, while "
            "management said conversion still depended on component availability.\n"
            "[TABLE_START id=7 rows=3]\n"
            "Fiscal Quarter Ended\n"
            "May 1, 2026 | May 2, 2025\n"
            "(in millions, except percentages)\n"
            "Net revenue | $ | 24,000 | $ | 22,000\n"
            "Gross margin | 22.0% | 21.0%\n"
            "[TABLE_END]"
        ),
    }
    result = compile_object_store(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=_policy(),
    )
    assert result.summary["object_kind_counts"] == {
        "bounded_parent_context": 1,
        "claim": 1,
        "metric_row": 2,
    }
    rows = [row for row in result.objects if row["object_kind"] == "metric_row"]
    assert {row["structured_projection"]["metric_row_label"] for row in rows} == {
        "Net revenue",
        "Gross margin",
    }
    assert all(row["numeric_authority"] is False for row in rows)
    assert all("May 1, 2026" in row["model_text"] for row in rows)
    assert all("[TABLE_START" not in row["model_text"] for row in rows)


def test_nonfinancial_table_is_not_misrepresented_as_metric_rows() -> None:
    parent = {
        "document_id": "CURRENT_DOC::DELL::10_K::PEOPLE",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-03-01",
        "period_end": "2026-01-31",
        "fiscal_year": 2026,
    }
    record = {
        "evidence_id": "DELL_PEOPLE_TABLE",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-03-01",
        "period_end": "2026-01-31",
        "fiscal_year": 2026,
        "section": "Business",
        "subsection": "Executive Officers",
        "metadata": {"parent_document_id": parent["document_id"]},
        "text": (
            "[TABLE_START id=3 rows=2]\n"
            "Name | Age | Position\n"
            "Example Person | 58 | Chief Executive Officer\n"
            "[TABLE_END]"
        ),
    }
    result = compile_object_store(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=_policy(),
    )
    assert result.summary["object_kind_counts"] == {"bounded_parent_context": 1}
    assert result.summary["diagnostic_counts"] == {
        "nonfinancial_table_not_compiled_as_metric_rows": 1
    }


def test_current_runtime_exposes_database_sibling_as_typed_s2_gap() -> None:
    service = ResearchRetrievalService.from_runtime_paths(ROOT)
    projection = service.execute_request(
        "DELL",
        _request(
            requested_facet_ids=["reported_results"],
            metric_intents=["revenue"],
            period={
                "start_date": None,
                "end_date": "2026-08-06",
                "fiscal_years": [],
            },
        ),
        ResearchRetrievalPrincipal(
            mode="current",
            permissions=frozenset({"current_product:read"}),
        ),
    )
    assert projection["schema_version"] == (
        "fin_ia_request_scoped_retrieval_projection_v1_1"
    )
    assert projection["summary"]["typed_fact_request_count"] == 1
    assert projection["summary"]["typed_fact_store_ready_count"] == 0
    assert projection["execution_plan"]["typed_fact_requests"][0][
        "storage_route"
    ] == "company_financial_fact_mart"
    assert projection["execution_plan"]["typed_fact_requests"][0][
        "numeric_fact_authority"
    ] is False
    assert any(
        row["gap_code"] == "typed_fact_store_unavailable"
        and row["owning_stage"] == "S2"
        for row in projection["typed_gaps"]
    )
