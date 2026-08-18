from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
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
from retrieval.object_view_compiler_v2 import (
    compile_object_store as compile_object_store_v2,
)
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
SUCCESSOR_KERNEL_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_financial_research_kernel_v1_1.json"
)
SUCCESSOR_POLICY_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_1.json"
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


def _successor_kernel():
    return load_financial_research_kernel(
        json.loads(SUCCESSOR_KERNEL_PATH.read_text(encoding="utf-8"))
    )


def _successor_policy():
    kernel = _successor_kernel()
    return load_query_object_fact_route_policy(
        json.loads(SUCCESSOR_POLICY_PATH.read_text(encoding="utf-8")), kernel
    )


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


def test_successor_separates_downstream_demand_from_upstream_capacity() -> None:
    kernel = _successor_kernel()
    policy = _successor_policy()
    assert len(policy.family_by_facet()) == 18
    assert policy.family_by_facet()["downstream_demand_context"].family_id == (
        "customer_demand_read_through"
    )

    downstream = load_evidence_request(
        _request(
            request_id="REQ-DELL-DOWNSTREAM-001",
            target_entities=["MSFT"],
            requested_facet_ids=["downstream_demand_context"],
            metric_intents=[],
        ),
        kernel,
    )
    downstream_plan = compile_retrieval_execution_plan(policy, downstream)
    assert downstream_plan.narrative_requests[0].target_entities == ("MSFT",)

    upstream = load_evidence_request(
        _request(
            request_id="REQ-DELL-UPSTREAM-001",
            target_entities=["MU"],
            requested_facet_ids=["upstream_capacity_context"],
            metric_intents=[],
        ),
        kernel,
    )
    upstream_plan = compile_retrieval_execution_plan(policy, upstream)
    assert upstream_plan.narrative_requests[0].target_entities == ("MU",)


@pytest.mark.parametrize(
    ("facet_id", "target"),
    [
        ("downstream_demand_context", "MU"),
        ("upstream_capacity_context", "MSFT"),
        ("downstream_demand_context", "DELL"),
        ("upstream_capacity_context", "DELL"),
    ],
)
def test_successor_related_facets_fail_closed_on_wrong_economic_role(
    facet_id: str,
    target: str,
) -> None:
    with pytest.raises(
        RetrievalContractError,
        match=f"evidence_request_facet_has_no_target:{facet_id}",
    ):
        load_evidence_request(
            _request(
                request_id=f"REQ-DELL-{facet_id}-{target}",
                target_entities=[target],
                requested_facet_ids=[facet_id],
                metric_intents=[],
            ),
            _successor_kernel(),
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


def test_empty_table_does_not_swallow_following_narrative_claims() -> None:
    parent = {
        "document_id": "CURRENT_DOC::TSM::6_K::EMPTY_TABLE",
        "ticker": "TSM",
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "source_type": "6-K",
        "source_tier": "primary_global_public_disclosure",
        "publication_date": "2026-07-16",
        "period_end": "2026-06-30",
        "fiscal_year": 2026,
    }
    claim = (
        "Our business in the second quarter was supported by strong demand for "
        "leading-edge process technologies, including the ramp of two-nanometer."
    )
    record = {
        **parent,
        "evidence_id": "TSM_EMPTY_TABLE_THEN_CLAIM",
        "section": "6-K current official disclosure",
        "subsection": "Earnings Release",
        "metadata": {"parent_document_id": parent["document_id"]},
        "text": (
            "[TABLE_START id=1 rows=0]\n"
            "[TABLE_END]\n"
            f"{claim}\n"
            "[TABLE_START id=2 rows=0]\n"
            "[TABLE_END]"
        ),
    }
    result = compile_object_store(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=_policy(),
    )
    claims = [row for row in result.objects if row["object_kind"] == "claim"]
    assert [row["model_text"] for row in claims] == [claim]
    assert result.summary["diagnostic_counts"] == {
        "financial_table_has_no_compilable_metric_row": 2
    }


def test_compiled_objects_share_reporting_period_binding_with_snapshot_candidates() -> None:
    parent = {
        "document_id": "CURRENT_DOC::DELL::8_K::Q1",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "source_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "publication_date": "2026-05-28",
        "period_end": "2026-05-28",
        "fiscal_year": 2026,
    }
    record = {
        **parent,
        "evidence_id": "DELL_Q1_FY27_RESULTS",
        "section": "Exhibit 99.1 Earnings Release",
        "subsection": "Quarterly results",
        "metadata": {
            "parent_document_id": parent["document_id"],
            "reported_period_end": "2026-05-01",
            "reported_fiscal_year": 2027,
        },
        "text": (
            "Dell reported strong AI-optimized server revenue during the quarter "
            "while noting that mix and pricing still constrained profitability."
        ),
    }

    result = compile_object_store(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=_policy(),
    )

    assert result.objects
    assert all(
        row["schema_version"] == "fin_ia_compiled_financial_object_view_v1_2"
        and row["base_object_view"]["period_end"] == "2026-05-01"
        and row["base_object_view"]["fiscal_year"] == 2027
        for row in result.objects
    )


def test_successor_claim_compiler_reflows_pdf_lines_and_keeps_late_claims() -> None:
    parent = {
        "document_id": "CURRENT_DOC::DELL::TRANSCRIPT::WRAPPED",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "source_type": "EARNINGS_CALL_TRANSCRIPT",
        "source_tier": "official_hosted_management_call_transcript",
        "publication_date": "2026-05-28",
        "period_end": "2026-05-01",
        "fiscal_year": 2027,
    }
    filler = "\n".join(
        f"Management discussed operating topic {index} and the related financial implications for the current quarter."
        for index in range(1, 20)
    )
    target = (
        "AI server profitability was in line with our mid-\n"
        "single-digit operating income rate target."
    )
    record = {
        **parent,
        "evidence_id": "DELL_TRANSCRIPT_WRAPPED_PAGE",
        "section": "Fiscal year 2027 first quarter results transcript",
        "subsection": "Transcript page 4",
        "metadata": {"parent_document_id": parent["document_id"]},
        "text": f"{filler}\n{target}",
    }
    policy = replace(
        _policy(),
        object_compiler={
            **dict(_policy().object_compiler),
            "claim_segmentation_mode": "sentence_with_wrapped_line_reflow_v1",
            "claim_overflow_policy": "emit_typed_diagnostic_and_fail_qualification",
            "max_claims_per_source_record": 96,
        },
    )
    result = compile_object_store(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=policy,
    )
    target_rows = [
        row
        for row in result.objects
        if "AI server profitability" in str(row.get("model_text") or "")
    ]
    assert len(target_rows) == 1
    assert "mid-single-digit" in target_rows[0]["model_text"]
    binding = target_rows[0]["base_object_view"]["focus_binding"]
    assert binding["mode"] == "offset_bound_text"
    assert record["text"][binding["char_start"] : binding["char_end"]] == target
    assert result.summary["diagnostic_counts"].get(
        "claim_unit_limit_exceeded", 0
    ) == 0


def test_successor_claim_compiler_makes_overflow_explicit() -> None:
    parent = {
        "document_id": "CURRENT_DOC::DELL::TRANSCRIPT::OVERFLOW",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "source_type": "EARNINGS_CALL_TRANSCRIPT",
        "source_tier": "official_hosted_management_call_transcript",
        "publication_date": "2026-05-28",
        "period_end": "2026-05-01",
        "fiscal_year": 2027,
    }
    record = {
        **parent,
        "evidence_id": "DELL_TRANSCRIPT_OVERFLOW_PAGE",
        "section": "Transcript",
        "subsection": "Page",
        "metadata": {"parent_document_id": parent["document_id"]},
        "text": (
            "First material sentence contains enough financial context for a claim object and explicitly discusses current-quarter operating performance. "
            "Second material sentence contains enough financial context for another object and explicitly discusses the next-quarter margin outlook."
        ),
    }
    policy = replace(
        _policy(),
        object_compiler={
            **dict(_policy().object_compiler),
            "claim_segmentation_mode": "sentence_with_wrapped_line_reflow_v1",
            "claim_overflow_policy": "emit_typed_diagnostic_and_fail_qualification",
            "max_claims_per_source_record": 1,
        },
    )
    result = compile_object_store(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=policy,
    )
    assert result.summary["diagnostic_counts"] == {
        "claim_unit_limit_exceeded": 1
    }


def test_table_period_rows_are_headers_and_business_unit_context_is_retained() -> None:
    parent = {
        "document_id": "CURRENT_DOC::MU::8_K::GROUPED_TABLE",
        "ticker": "MU",
        "company": "Micron Technology, Inc.",
        "source_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "publication_date": "2026-03-18",
        "period_end": "2026-03-18",
        "fiscal_year": 2026,
    }
    record = {
        **parent,
        "evidence_id": "MU_GROUPED_METRIC_TABLE",
        "section": "Exhibit 99.1 Earnings Release",
        "subsection": "Quarterly Business Unit Financial Results",
        "metadata": {"parent_document_id": parent["document_id"]},
        "text": (
            "[TABLE_START id=3 rows=7]\n"
            "Quarterly Business Unit Financial Results\n"
            "FQ2-26 | FQ1-26 | FQ2-25\n"
            "Cloud Memory Business Unit\n"
            "Revenue | $ | 7,749 | $ | 5,284 | $ | 2,947\n"
            "Gross margin | 74 | % | 66 | % | 55 | %\n"
            "Core Data Center Business Unit\n"
            "Revenue | $ | 5,687 | $ | 2,379 | $ | 1,830\n"
            "Gross margin | 74 | % | 51 | % | 47 | %\n"
            "[TABLE_END]"
        ),
    }
    result = compile_object_store(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=_policy(),
    )
    rows = [row for row in result.objects if row["object_kind"] == "metric_row"]
    assert len(rows) == 4
    assert all(row["structured_projection"]["metric_row_label"] != "FQ2-26" for row in rows)
    assert [row["structured_projection"]["row_context_lines"] for row in rows] == [
        ["Cloud Memory Business Unit"],
        ["Cloud Memory Business Unit"],
        ["Core Data Center Business Unit"],
        ["Core Data Center Business Unit"],
    ]
    assert "Row context: Cloud Memory Business Unit" in rows[0]["model_text"]


def test_table_rows_use_local_intro_instead_of_stale_record_subsection() -> None:
    parent = {
        "document_id": "CURRENT_DOC::NVDA::10_K::LOCAL_TABLE_CONTEXT",
        "ticker": "NVDA",
        "company": "NVIDIA Corporation",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-02-25",
        "period_end": "2026-01-25",
        "fiscal_year": 2026,
    }
    record = {
        **parent,
        "evidence_id": "NVDA_LOCAL_TABLE_CONTEXT",
        "section": "Item 7. Management's Discussion and Analysis",
        # This deliberately represents the stale broad heading that caused
        # debt rows to masquerade as gross-margin material in the real store.
        "subsection": "Gross Profit and Gross Margin",
        "metadata": {"parent_document_id": parent["document_id"]},
        "text": (
            "Gross Profit and Gross Margin\n"
            "Gross margin improved during the year.\n"
            "[TABLE_START id=1 rows=2]\n"
            "Year Ended\n"
            "January 25, 2026 | January 26, 2025\n"
            "Gross margin | 75.0% | 73.0%\n"
            "[TABLE_END]\n"
            "Outstanding Indebtedness and Commercial Paper Program\n"
            "Our aggregate debt maturities by year payable are as follows:\n"
            "[TABLE_START id=2 rows=3]\n"
            "January 25, 2026\n"
            "(In millions)\n"
            "Due in one year | $ | 1,000\n"
            "Due in one to five years | 2,750\n"
            "[TABLE_END]"
        ),
    }

    result = compile_object_store_v2(
        records=[record],
        parents_by_id={parent["document_id"]: parent},
        policy=_policy(),
    )
    debt_rows = [
        row
        for row in result.objects
        if row["object_kind"] == "metric_row"
        and str(row["structured_projection"]["metric_row_label"]).startswith("Due")
    ]
    assert len(debt_rows) == 2
    assert all(
        row["structured_projection"]["table_title"]
        == "Outstanding Indebtedness and Commercial Paper Program"
        for row in debt_rows
    )
    assert all(
        row["structured_projection"]["table_title_source"]
        == "local_pre_table_heading"
        for row in debt_rows
    )
    assert all(
        "aggregate debt maturities" in row["model_text"]
        and "Gross Profit and Gross Margin" not in row["model_text"]
        for row in debt_rows
    )


def test_current_runtime_exposes_database_sibling_as_typed_s2_gap(
    tmp_path: Path,
) -> None:
    service = ResearchRetrievalService(
        snapshot=json.loads(
            (
                ROOT
                / "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
            ).read_text(encoding="utf-8")
        ),
        kernel=_kernel_payload(),
        route_policy=_policy_payload(),
        company_financial_fact_mart_path=tmp_path / "missing.sqlite",
    )
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
        "fin_ia_request_scoped_retrieval_projection_v1_2"
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
    assert projection["typed_fact_results"] == []
