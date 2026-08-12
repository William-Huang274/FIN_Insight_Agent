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
