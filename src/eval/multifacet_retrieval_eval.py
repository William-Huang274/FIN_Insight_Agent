from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from .retrieval_eval import ndcg_at_k


@dataclass(frozen=True)
class GoldFacet:
    facet_id: str
    query: str
    relevant_evidence_ids: tuple[str, ...]
    tags: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "GoldFacet":
        relevant_ids = tuple(record.get("relevant_evidence_ids") or [])
        if not relevant_ids:
            raise ValueError(f"Gold facet has no relevant evidence ids: {record}")
        return cls(
            facet_id=record["facet_id"],
            query=record["query"],
            relevant_evidence_ids=relevant_ids,
            tags=tuple(record.get("tags") or []),
        )


@dataclass(frozen=True)
class MultiFacetGoldQuery:
    query_id: str
    query: str
    facets: tuple[GoldFacet, ...]
    relevant_evidence_ids: tuple[str, ...]
    ticker: str | None = None
    fiscal_year: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    label_source: str | None = None
    decomposition_source: str | None = None

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "MultiFacetGoldQuery":
        facets = tuple(GoldFacet.from_record(item) for item in record.get("facets") or [])
        if not facets:
            raise ValueError(f"Multi-facet query has no facets: {record}")
        explicit_relevant = tuple(record.get("relevant_evidence_ids") or [])
        facet_relevant = tuple(
            dict.fromkeys(
                evidence_id
                for facet in facets
                for evidence_id in facet.relevant_evidence_ids
            )
        )
        relevant_ids = explicit_relevant or facet_relevant
        if not relevant_ids:
            raise ValueError(f"Multi-facet query has no relevant evidence ids: {record}")
        return cls(
            query_id=record["query_id"],
            query=record["query"],
            facets=facets,
            relevant_evidence_ids=relevant_ids,
            ticker=record.get("ticker"),
            fiscal_year=record.get("fiscal_year"),
            tags=tuple(record.get("tags") or []),
            label_source=record.get("label_source"),
            decomposition_source=record.get("decomposition_source"),
        )

    def filters(self, mode: str) -> dict[str, Any] | None:
        if mode == "none":
            return None
        if mode != "ticker_year":
            raise ValueError(f"Unsupported filter mode: {mode}")
        filters: dict[str, Any] = {}
        if self.ticker:
            filters["ticker"] = self.ticker
        if self.fiscal_year is not None:
            filters["fiscal_year"] = self.fiscal_year
        return filters or None

    def decomposition_queries(self, include_original: bool = True) -> list[str]:
        queries = [facet.query for facet in self.facets]
        if include_original:
            return [self.query, *queries]
        return queries


def load_multifacet_gold_queries(path: str | Path) -> list[MultiFacetGoldQuery]:
    gold_path = Path(path)
    queries: list[MultiFacetGoldQuery] = []
    with gold_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                queries.append(MultiFacetGoldQuery.from_record(json.loads(stripped)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid multi-facet gold query at {gold_path}:{line_number}") from exc
    return queries


def evaluate_multifacet_retriever(
    queries: list[MultiFacetGoldQuery],
    search_fn: Callable[[MultiFacetGoldQuery, int], list[dict[str, Any]]],
    *,
    k_values: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, Any]:
    max_k = max(k_values)
    per_query = []
    for gold_query in queries:
        results = search_fn(gold_query, max_k)
        ranked_ids = [result["evidence_id"] for result in results]
        per_query.append(score_multifacet_query(gold_query, ranked_ids, results, k_values))
    return summarize_multifacet_scores(per_query, k_values)


def score_multifacet_query(
    gold_query: MultiFacetGoldQuery,
    ranked_ids: list[str],
    results: list[dict[str, Any]],
    k_values: tuple[int, ...],
) -> dict[str, Any]:
    relevant = set(gold_query.relevant_evidence_ids)
    relevant_ranks = [
        rank for rank, evidence_id in enumerate(ranked_ids, start=1) if evidence_id in relevant
    ]
    best_rank = min(relevant_ranks) if relevant_ranks else None
    facet_best_ranks = {
        facet.facet_id: _best_rank_for_ids(ranked_ids, set(facet.relevant_evidence_ids))
        for facet in gold_query.facets
    }
    score: dict[str, Any] = {
        "query_id": gold_query.query_id,
        "query": gold_query.query,
        "ticker": gold_query.ticker,
        "fiscal_year": gold_query.fiscal_year,
        "tags": list(gold_query.tags),
        "label_source": gold_query.label_source,
        "decomposition_source": gold_query.decomposition_source,
        "facet_count": len(gold_query.facets),
        "facets": [
            {
                "facet_id": facet.facet_id,
                "query": facet.query,
                "tags": list(facet.tags),
                "relevant_evidence_ids": list(facet.relevant_evidence_ids),
                "best_rank": facet_best_ranks[facet.facet_id],
            }
            for facet in gold_query.facets
        ],
        "relevant_evidence_ids": list(gold_query.relevant_evidence_ids),
        "top_evidence_ids": ranked_ids[: max(k_values)],
        "best_rank": best_rank,
        "reciprocal_rank": 1.0 / best_rank if best_rank else 0.0,
        "facet_mrr": mean(
            1.0 / rank if rank else 0.0 for rank in facet_best_ranks.values()
        ),
    }
    for k in k_values:
        top_k_ids = ranked_ids[:k]
        top_k = set(top_k_ids)
        matched = sorted(relevant & top_k)
        matched_facets = [
            facet.facet_id
            for facet in gold_query.facets
            if set(facet.relevant_evidence_ids) & top_k
        ]
        score[f"hit@{k}"] = bool(matched)
        score[f"precision@{k}"] = len(matched) / k
        score[f"recall@{k}"] = len(matched) / len(relevant)
        score[f"ndcg@{k}"] = ndcg_at_k(top_k_ids, relevant, k)
        score[f"facet_coverage@{k}"] = len(matched_facets) / len(gold_query.facets)
        score[f"all_facets_hit@{k}"] = len(matched_facets) == len(gold_query.facets)
        score[f"matched@{k}"] = matched
        score[f"matched_facets@{k}"] = matched_facets
    if results:
        score["top_hit"] = {
            key: results[0].get(key)
            for key in (
                "evidence_id",
                "score",
                "ticker",
                "fiscal_year",
                "section",
                "subsection",
                "evidence_type",
                "contains_table",
                "text_preview",
            )
        }
    return score


def summarize_multifacet_scores(
    per_query: list[dict[str, Any]],
    k_values: tuple[int, ...],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "query_count": len(per_query),
        "mrr": mean(item["reciprocal_rank"] for item in per_query) if per_query else 0.0,
        "mean_facet_mrr": mean(item["facet_mrr"] for item in per_query) if per_query else 0.0,
        "mean_facet_count": mean(item["facet_count"] for item in per_query) if per_query else 0.0,
    }
    for k in k_values:
        summary[f"hit_rate@{k}"] = (
            mean(1.0 if item[f"hit@{k}"] else 0.0 for item in per_query)
            if per_query
            else 0.0
        )
        summary[f"mean_recall@{k}"] = (
            mean(item[f"recall@{k}"] for item in per_query) if per_query else 0.0
        )
        summary[f"mean_precision@{k}"] = (
            mean(item[f"precision@{k}"] for item in per_query) if per_query else 0.0
        )
        summary[f"mean_ndcg@{k}"] = (
            mean(item[f"ndcg@{k}"] for item in per_query) if per_query else 0.0
        )
        summary[f"mean_facet_coverage@{k}"] = (
            mean(item[f"facet_coverage@{k}"] for item in per_query) if per_query else 0.0
        )
        summary[f"all_facets_hit_rate@{k}"] = (
            mean(1.0 if item[f"all_facets_hit@{k}"] else 0.0 for item in per_query)
            if per_query
            else 0.0
        )
    misses = [item["query_id"] for item in per_query if not item[f"hit@{max(k_values)}"]]
    facet_misses = [
        item["query_id"]
        for item in per_query
        if not item[f"all_facets_hit@{max(k_values)}"]
    ]
    return {
        "summary": summary,
        "misses_at_max_k": misses,
        "facet_misses_at_max_k": facet_misses,
        "per_query": per_query,
    }


def _best_rank_for_ids(ranked_ids: list[str], relevant: set[str]) -> int | None:
    ranks = [rank for rank, evidence_id in enumerate(ranked_ids, start=1) if evidence_id in relevant]
    return min(ranks) if ranks else None
