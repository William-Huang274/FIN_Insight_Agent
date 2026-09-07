from __future__ import annotations

from scripts.qualification.run_s1_pgvector_candidate_plane import (
    _aggregate_ranking,
    _filter_clause,
    _first_target_rank,
    _postgres_lexical_query,
    _query_text,
    _target_ids,
    canonical_digest,
    qrel_filter,
)


def _qrel() -> dict[str, object]:
    return {
        "qrel_id": "q1",
        "evidence_owner_ticker": "msft",
        "publication_date_lte": "2026-08-06",
        "reporting_fiscal_years": [2025, 2026],
        "form_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing"],
        "sparse_query_texts": ["Azure AI capacity", "Azure AI capacity", "capex"],
        "target_current_source_record_ids": ["SOURCE::1"],
    }


def test_qrel_filter_preserves_financial_scope() -> None:
    filters = qrel_filter(_qrel())

    assert filters.ticker == "MSFT"
    assert filters.publication_date_lte == "2026-08-06"
    assert filters.fiscal_years == (2025, 2026)
    assert filters.source_types == ("10-Q", "8-K")
    assert filters.source_tiers == ("primary_sec_filing",)

    clause, parameters = _filter_clause(filters)
    assert clause == (
        "ticker = %s AND publication_date <= %s::date "
        "AND (fiscal_year IS NULL OR fiscal_year = ANY(%s)) AND source_type = ANY(%s) "
        "AND source_tier = ANY(%s)"
    )
    assert parameters == [
        "MSFT",
        "2026-08-06",
        [2025, 2026],
        ["10-Q", "8-K"],
        ["primary_sec_filing"],
    ]


def test_query_and_targets_are_deduplicated_without_label_leakage() -> None:
    qrel = _qrel()

    assert _query_text(qrel) == "Azure AI capacity capex"
    assert _target_ids(qrel) == ("SOURCE::1",)
    assert "SOURCE::1" not in _query_text(qrel)

    postgres_query, token_count = _postgres_lexical_query(_query_text(qrel))
    assert postgres_query == "azure OR ai OR capacity OR capex"
    assert token_count == 4


def test_first_target_rank_uses_lineage_not_compiled_identity() -> None:
    rows = [
        {
            "compiled_object_id": "COBJ::noise",
            "lineage_source_record_ids": ["SOURCE::noise"],
        },
        {
            "compiled_object_id": "COBJ::target-view",
            "lineage_source_record_ids": ["SOURCE::1", "SOURCE::duplicate"],
        },
    ]

    assert _first_target_rank(rows, ["SOURCE::1"]) == 2
    assert _first_target_rank(rows, ["SOURCE::missing"]) is None


def test_ranking_aggregate_denominator_keeps_eligible_misses() -> None:
    rows = [
        {"qrel_id": "q1", "eligible_target_count": 1, "target_rank": 2},
        {"qrel_id": "q2", "eligible_target_count": 2, "target_rank": None},
        {"qrel_id": "q3", "eligible_target_count": 0, "target_rank": None},
    ]

    result = _aggregate_ranking(rows)

    assert result["qrel_count"] == 3
    assert result["eligible_qrel_count"] == 2
    assert result["target_in_top_16"] == 1
    assert result["target_in_top_64"] == 1
    assert result["mean_reciprocal_rank_eligible"] == 0.25
    assert result["zero_eligible_target_qrel_ids"] == ["q3"]


def test_canonical_digest_is_order_sensitive_for_embedding_alignment() -> None:
    assert canonical_digest(["A", "B"]) != canonical_digest(["B", "A"])
