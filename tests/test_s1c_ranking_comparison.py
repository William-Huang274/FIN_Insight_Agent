from __future__ import annotations

import json

import numpy as np
import pytest

from retrieval.ranking_comparison import (
    RANKING_QREL_SCHEMA_VERSION,
    RankingComparisonError,
    compare_ranking_routes,
    load_ranking_queries,
    sanitized_workbench_projection,
)


def _qrel_payload(*, query_text: str = "Dell AI server orders and backlog") -> dict:
    return {
        "schema_version": RANKING_QREL_SCHEMA_VERSION,
        "policy": {
            "labels_joined_after_candidate_generation": True,
            "target_ids_forbidden_from_query_text": True,
            "candidate_is_not_evidence": True,
        },
        "qrels": [
            {
                "qrel_id": "qrel-1",
                "source_qrel_digest": "a" * 64,
                "case_key": "DELL",
                "subject_ticker": "DELL",
                "evidence_slot_id": "issuer_results_and_management_commentary",
                "evidence_owner_ticker": "DELL",
                "relationship_direction": "subject_self_disclosure",
                "sparse_query_texts": [query_text],
                "semantic_query_texts": [query_text],
                "publication_date_lte": "2026-08-06",
                "reporting_fiscal_years": [2027],
                "form_types": ["8-K", "10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "target_current_source_record_ids": ["target-child"],
                "target_mapping_state": "mapped_current_child",
                "relevance_grade": 3,
            }
        ],
    }


def _record(
    evidence_id: str,
    text: str,
    *,
    ticker: str = "DELL",
    publication_date: str = "2026-05-28",
    fiscal_year: int = 2027,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "ticker": ticker,
        "source_type": "8-K",
        "source_tier": "primary_sec_filing",
        "publication_date": publication_date,
        "fiscal_year": fiscal_year,
        "period_end": "2026-05-01",
        "section": "Results of Operations",
        "subsection": "AI server demand",
        "evidence_type": "management_discussion",
        "topics": [],
        "source_url": f"https://example.test/{evidence_id}",
        "text": text * 8,
        "metadata": {"accession_number": evidence_id},
    }


def test_gold_target_identity_in_query_fails_closed() -> None:
    payload = _qrel_payload(query_text="Find target-child")
    with pytest.raises(RankingComparisonError, match="gold_target_leaked"):
        load_ranking_queries(payload)


def test_all_routes_share_population_and_labels_join_after_generation() -> None:
    query = load_ranking_queries(_qrel_payload())[0]
    records = [
        _record(
            "target-child",
            "Dell reported AI server orders, backlog, revenue and guidance. ",
        ),
        _record(
            "generic-child",
            "Dell corporate overview includes products and general strategy. ",
        ),
        _record(
            "wrong-owner",
            "AI server orders and backlog. ",
            ticker="NVDA",
        ),
        _record(
            "future-child",
            "AI server orders and backlog. ",
            publication_date="2026-08-07",
        ),
    ]
    embeddings = {
        "target-child": np.array([1.0, 0.0], dtype=np.float32),
        "generic-child": np.array([0.0, 1.0], dtype=np.float32),
        "wrong-owner": np.array([1.0, 0.0], dtype=np.float32),
        "future-child": np.array([1.0, 0.0], dtype=np.float32),
    }
    result = compare_ranking_routes(
        records,
        [query],
        embedding_by_record_id=embeddings,
        query_embeddings={
            "qrel-1": np.array([1.0, 0.0], dtype=np.float32)
        },
        top_k=2,
        candidate_pool=2,
    )

    row = result["queries"][0]
    assert row["eligible_records"] == 2
    assert row["exclusion_counts"]["outside_evidence_owner_scope"] == 1
    assert row["exclusion_counts"]["published_after_research_as_of"] == 1
    assert row["labels_joined_after_candidate_generation"] is True
    assert set(row["routes"]) == {
        "sparse_bm25",
        "dense_bge_m3",
        "fusion_rrf_1_1",
        "typed_financial_rerank",
    }
    assert all(
        route["target_in_top_k"] is True for route in row["routes"].values()
    )


def test_workbench_projection_removes_qrel_targets_and_eval_outcome() -> None:
    query = load_ranking_queries(_qrel_payload())[0]
    records = [
        _record(
            "target-child",
            "Dell reported AI server orders, backlog, revenue and guidance. ",
        )
    ]
    vector = np.array([1.0, 0.0], dtype=np.float32)
    result = compare_ranking_routes(
        records,
        [query],
        embedding_by_record_id={"target-child": vector},
        query_embeddings={"qrel-1": vector},
        top_k=1,
        candidate_pool=1,
    )
    projection = sanitized_workbench_projection(result)
    rendered = json.dumps(projection, ensure_ascii=False)

    assert projection["candidate_state"] == "candidate_not_evidence"
    assert projection["same_object_population_count"] == 1
    assert "target_current_source_record_ids" not in rendered
    assert "target_in_top_k" not in rendered
    assert "target_rank" not in rendered
    assert "matched_qrel_ids" not in rendered
    assert "business_diagnostic_code" not in rendered
    assert all(
        str(item["query_id"]).startswith("s1c_")
        and "qrel" not in str(item["query_id"])
        for case in projection["cases"]
        for item in case["queries"]
    )
    assert all(
        len(case["queries"]) <= 3
        and all(
            len(route["candidates"]) <= 1
            for item in case["queries"]
            for route in item["routes"].values()
        )
        for case in projection["cases"]
    )


def test_typed_rerank_is_explicitly_not_neural_cross_encoder() -> None:
    policy = json.loads(
        open(
            "configs/retrieval/fin_ia_0_1_3_s1c_ranking_comparison_policy_v1_0.json",
            encoding="utf-8",
        ).read()
    )
    route = next(
        row for row in policy["routes"] if row["route_id"] == "typed_financial_rerank"
    )
    assert route["kind"] == "deterministic_contract_aware_rerank_not_neural_cross_encoder"
