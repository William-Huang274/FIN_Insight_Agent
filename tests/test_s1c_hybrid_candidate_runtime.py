from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import (
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.hybrid_candidate_runtime import retrieve_hybrid_candidates
from retrieval.route_compiler import load_query_object_fact_route_policy


def _contracts():
    kernel = load_financial_research_kernel(
        json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json"
            ).read_text(encoding="utf-8")
        )
    )
    route = load_query_object_fact_route_policy(
        json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json"
            ).read_text(encoding="utf-8")
        ),
        kernel,
    )
    request = load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": "REQ::DELL-HYBRID-TEST",
            "cell_id": "CELL::DELL-RESULTS",
            "requester_role": "financial_specialist",
            "evidence_domain": "operating_performance",
            "case_key": "DELL",
            "subject_ticker": "DELL",
            "research_as_of": "2026-08-06",
            "target_entities": ["DELL"],
            "requested_facet_ids": ["reported_results"],
            "metric_intents": ["revenue"],
            "product_intents": ["AI-optimized servers"],
            "period": {
                "start_date": "2025-02-01",
                "end_date": "2026-08-06",
                "fiscal_years": [2026, 2027],
            },
            "granularity": "quarter_and_fiscal_year",
            "unit": "reported_source_unit",
            "acceptable_sources": ["10-K", "10-Q", "8-K"],
            "acceptable_proxy": False,
            "forbidden_proxy": ["unbound industry demand"],
            "stop_condition": "return candidates, typed facts, or typed gaps",
            "clarification_policy": "return_typed_gap",
        },
        kernel,
    )
    return kernel, route, request


def _object(
    identity: str,
    *,
    ticker: str,
    text: str,
    source: str,
    publication_date: str = "2026-05-30",
    fiscal_year: int = 2027,
) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_0",
        "compiled_object_id": identity,
        "object_kind": "claim",
        "model_text": text,
        "base_object_view": {
            "source_record_id": source,
            "ticker": ticker,
            "company": ticker,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": publication_date,
            "period_end": "2026-05-01",
            "fiscal_year": fiscal_year,
            "section": "Results of Operations",
            "subsection": "Quarterly results",
        },
        "lineage_source_record_ids": [source],
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }


def test_hybrid_union_adds_semantic_candidate_but_preserves_hard_filters_and_source_quota() -> None:
    kernel, route, request = _contracts()
    objects = (
        _object(
            "OBJ-BM25",
            ticker="DELL",
            source="SRC-LEXICAL",
            text=(
                "Dell reported revenue and operating income for AI-optimized "
                "servers in the current quarter."
            ),
        ),
        _object(
            "OBJ-QWEN",
            ticker="DELL",
            source="SRC-SEMANTIC",
            text=(
                "Infrastructure demand translated into sharply higher current "
                "quarter sales even though the passage avoids the exact query words."
            ),
        ),
        _object(
            "OBJ-SAME-SOURCE",
            ticker="DELL",
            source="SRC-SEMANTIC",
            text="A second nearby sentence from the same disclosure.",
        ),
        _object(
            "OBJ-WRONG-COMPANY",
            ticker="ORCL",
            source="SRC-ORCL",
            text="AI server revenue operating income current results.",
        ),
        _object(
            "OBJ-FUTURE",
            ticker="DELL",
            source="SRC-FUTURE",
            publication_date="2026-08-07",
            text="AI server revenue operating income current results.",
        ),
    )
    document_embeddings = np.asarray(
        [
            [0.60, 0.40],
            [1.00, 0.00],
            [0.95, 0.05],
            [1.00, 0.00],
            [1.00, 0.00],
        ],
        dtype=np.float32,
    )

    result = retrieve_hybrid_candidates(
        request=request,
        kernel=kernel,
        route_policy=route,
        objects=objects,
        qwen_document_embeddings=document_embeddings,
        qwen_query_embedding=np.asarray([1.0, 0.0], dtype=np.float32),
        first_stage_limit=3,
        candidate_union_limit=4,
        output_limit=3,
        max_candidates_per_source_record=1,
    )

    ids = [row["compiled_object_id"] for row in result["candidates"]]
    assert "OBJ-BM25" in ids
    assert "OBJ-QWEN" in ids
    assert "OBJ-SAME-SOURCE" not in ids
    assert "OBJ-WRONG-COMPANY" not in ids
    assert "OBJ-FUTURE" not in ids
    assert result["summary"]["hard_filter_exclusions"] == {
        "after_research_as_of": 1,
        "outside_evidence_owner_scope": 1,
    }
    assert result["authority"]["database_lane_remains_independent"] is True
    assert all(row["candidate_not_evidence"] is True for row in result["candidates"])
    assert all(row["numeric_authority"] is False for row in result["candidates"])


def test_financial_ranker_demotes_fragment_and_keeps_abstain_as_candidate() -> None:
    kernel, route, request = _contracts()
    objects = (
        _object(
            "OBJ-FRAGMENT",
            ticker="DELL",
            source="SRC-FRAGMENT",
            text="-based revenue and operating income for current AI servers.",
        ),
        _object(
            "OBJ-COMPLETE",
            ticker="DELL",
            source="SRC-COMPLETE",
            text=(
                "Dell reported current-quarter revenue and operating income "
                "growth for AI-optimized servers."
            ),
        ),
        _object(
            "OBJ-ABSTAIN",
            ticker="DELL",
            source="SRC-ABSTAIN",
            text=(
                "The company completed a broad infrastructure platform "
                "transition during the current quarter."
            ),
        ),
    )
    result = retrieve_hybrid_candidates(
        request=request,
        kernel=kernel,
        route_policy=route,
        objects=objects,
        qwen_document_embeddings=np.asarray(
            [[1.0, 0.0], [0.8, 0.2], [0.7, 0.3]], dtype=np.float32
        ),
        qwen_query_embedding=np.asarray([1.0, 0.0], dtype=np.float32),
        first_stage_limit=3,
        candidate_union_limit=3,
        output_limit=3,
        max_candidates_per_source_record=1,
        financial_ranking_enabled=True,
    )

    ids = [row["compiled_object_id"] for row in result["candidates"]]
    assert ids.index("OBJ-COMPLETE") < ids.index("OBJ-FRAGMENT")
    assert "OBJ-ABSTAIN" in ids
    fragment = next(
        row for row in result["candidates"] if row["compiled_object_id"] == "OBJ-FRAGMENT"
    )
    abstain = next(
        row for row in result["candidates"] if row["compiled_object_id"] == "OBJ-ABSTAIN"
    )
    assert fragment["financial_ranking"]["surface_integrity"]["tier"] == 0
    assert (
        abstain["financial_ranking"]["evidence_role"]["abstain_is_not_rejection"]
        is True
    )
    assert result["schema_version"].endswith("v1_1")
    assert result["summary"]["financial_ranking_enabled"] is True
    assert result["query"]["relationship_constraints"] == [
        "subject_self_disclosure"
    ]


def test_hybrid_runtime_preserves_multiple_graph_bound_evidence_owners() -> None:
    kernel, route, _ = _contracts()
    request = load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": "REQ::DELL-RELATED-COUNTEREVIDENCE",
            "cell_id": "CELL::DELL-RELATED-COUNTEREVIDENCE",
            "requester_role": "red_team_critic",
            "evidence_domain": "financial_research",
            "case_key": "DELL",
            "subject_ticker": "DELL",
            "research_as_of": "2026-08-06",
            "target_entities": ["DELL", "NVDA"],
            "requested_facet_ids": ["upstream_or_demand_counterevidence"],
            "metric_intents": [],
            "product_intents": ["GPU supply constraint"],
            "period": {
                "start_date": "2025-02-01",
                "end_date": "2026-08-06",
                "fiscal_years": [2026, 2027],
            },
            "granularity": "quarter_and_fiscal_year",
            "unit": "reported_source_unit",
            "acceptable_sources": ["10-K", "10-Q", "8-K"],
            "acceptable_proxy": False,
            "forbidden_proxy": ["unbound industry demand"],
            "stop_condition": "return candidates, typed facts, or typed gaps",
            "clarification_policy": "return_typed_gap",
        },
        kernel,
    )
    objects = (
        _object(
            "OBJ-DELL-RISK",
            ticker="DELL",
            source="SRC-DELL-RISK",
            text="Large AI orders may create inventory and pricing pressure.",
        ),
        _object(
            "OBJ-NVDA-SUPPLY",
            ticker="NVDA",
            source="SRC-NVDA-SUPPLY",
            text="Supply commitments may exceed demand projections for GPUs.",
        ),
        _object(
            "OBJ-ORCL-NOISE",
            ticker="ORCL",
            source="SRC-ORCL-NOISE",
            text="Supply demand mismatch and inventory correction.",
        ),
    )
    result = retrieve_hybrid_candidates(
        request=request,
        kernel=kernel,
        route_policy=route,
        objects=objects,
        qwen_document_embeddings=np.asarray(
            [[0.8, 0.2], [1.0, 0.0], [1.0, 0.0]], dtype=np.float32
        ),
        qwen_query_embedding=np.asarray([1.0, 0.0], dtype=np.float32),
        first_stage_limit=3,
        candidate_union_limit=3,
        output_limit=3,
        max_candidates_per_source_record=1,
    )

    assert set(result["evidence_owner_tickers"]) == {"DELL", "NVDA"}
    assert {row["ticker"] for row in result["candidates"]} == {"DELL", "NVDA"}
    assert result["summary"]["hard_filter_exclusions"] == {
        "outside_evidence_owner_scope": 1
    }


def test_owner_balanced_successor_preserves_each_disclosure_owner_for_role_review() -> None:
    kernel, route, _ = _contracts()
    request = load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": "REQ::DELL-MULTI-OWNER-COVERAGE",
            "cell_id": "CELL::DELL-MULTI-OWNER-COVERAGE",
            "requester_role": "red_team_critic",
            "evidence_domain": "financial_research",
            "case_key": "DELL",
            "subject_ticker": "DELL",
            "research_as_of": "2026-08-06",
            "target_entities": ["DELL", "NVDA"],
            "requested_facet_ids": ["upstream_or_demand_counterevidence"],
            "metric_intents": [],
            "product_intents": ["GPU supply constraint"],
            "period": {
                "start_date": "2025-02-01",
                "end_date": "2026-08-06",
                "fiscal_years": [2026, 2027],
            },
            "granularity": "quarter_and_fiscal_year",
            "unit": "reported_source_unit",
            "acceptable_sources": ["10-K", "10-Q", "8-K"],
            "acceptable_proxy": False,
            "forbidden_proxy": ["unbound industry demand"],
            "stop_condition": "return candidates, typed facts, or typed gaps",
            "clarification_policy": "return_typed_gap",
        },
        kernel,
    )
    objects = tuple(
        [
            _object(
                f"OBJ-DELL-{index}",
                ticker="DELL",
                source=f"SRC-DELL-{index}",
                text="AI orders backlog inventory demand risk " * (5 - index),
            )
            for index in range(4)
        ]
        + [
            _object(
                "OBJ-NVDA-LOW-SCORE",
                ticker="NVDA",
                source="SRC-NVDA-LOW-SCORE",
                text="Capacity commitments may exceed demand.",
            )
        ]
    )
    result = retrieve_hybrid_candidates(
        request=request,
        kernel=kernel,
        route_policy=route,
        objects=objects,
        qwen_document_embeddings=np.asarray(
            [[1.0, 0.0]] * 4 + [[0.0, 1.0]], dtype=np.float32
        ),
        qwen_query_embedding=np.asarray([1.0, 0.0], dtype=np.float32),
        first_stage_limit=5,
        candidate_union_limit=5,
        output_limit=2,
        max_candidates_per_source_record=1,
        minimum_candidates_per_owner=1,
        evidence_role_advisory_enabled=True,
    )

    assert {row["ticker"] for row in result["candidates"]} == {"DELL", "NVDA"}
    assert result["summary"]["selected_candidate_count_by_owner"] == {
        "DELL": 1,
        "NVDA": 1,
    }
    assert result["summary"]["owner_floor_unmet"] == []
    assert all(row["evidence_role"]["advisory_only"] for row in result["candidates"])
    assert all(row["evidence_role"]["ranking_effect"] is False for row in result["candidates"])
    assert result["schema_version"].endswith("v1_2")
