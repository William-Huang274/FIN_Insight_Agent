from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.candidate_retriever import CandidateCorpus, retrieve_query_plan
from retrieval.contracts import load_financial_research_kernel
from retrieval.query_plan import compile_query_facet_plan


KERNEL_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json"
)
SNAPSHOT_PATH = (
    ROOT
    / "configs"
    / "runtime"
    / "fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
)


def _kernel():
    return load_financial_research_kernel(
        json.loads(KERNEL_PATH.read_text(encoding="utf-8"))
    )


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
        "reviewed_label_occurrences_missing_from_historical_corpus"
    ] > 0
    assert all(
        candidate["candidate_state"] == "candidate_not_evidence"
        for lane in projection["lanes"]
        for candidate in lane["candidates"]
    )
    rendered = json.dumps(projection, ensure_ascii=False)
    assert "reviewed_pack_match" not in rendered
    assert "matched_source_record_ids" not in rendered
    assert "reviewed_evaluation" not in rendered
