from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Callable


@dataclass(frozen=True)
class GoldQuery:
    query_id: str
    query: str
    relevant_evidence_ids: tuple[str, ...]
    ticker: str | None = None
    fiscal_year: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    label_source: str | None = None

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "GoldQuery":
        relevant_ids = tuple(record.get("relevant_evidence_ids") or [])
        if not relevant_ids:
            raise ValueError(f"Gold query has no relevant evidence ids: {record}")
        return cls(
            query_id=record["query_id"],
            query=record["query"],
            relevant_evidence_ids=relevant_ids,
            ticker=record.get("ticker"),
            fiscal_year=record.get("fiscal_year"),
            tags=tuple(record.get("tags") or []),
            label_source=record.get("label_source"),
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


def load_gold_queries(path: str | Path) -> list[GoldQuery]:
    gold_path = Path(path)
    queries: list[GoldQuery] = []
    with gold_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                queries.append(GoldQuery.from_record(json.loads(stripped)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid gold query at {gold_path}:{line_number}") from exc
    return queries


def evaluate_retriever(
    queries: list[GoldQuery],
    search_fn: Callable[[GoldQuery, int], list[dict[str, Any]]],
    *,
    k_values: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, Any]:
    max_k = max(k_values)
    per_query = []
    for gold_query in queries:
        results = search_fn(gold_query, max_k)
        ranked_ids = [result["evidence_id"] for result in results]
        per_query.append(score_query(gold_query, ranked_ids, results, k_values))
    return summarize_scores(per_query, k_values)


def score_query(
    gold_query: GoldQuery,
    ranked_ids: list[str],
    results: list[dict[str, Any]],
    k_values: tuple[int, ...],
) -> dict[str, Any]:
    relevant = set(gold_query.relevant_evidence_ids)
    relevant_ranks = [
        rank for rank, evidence_id in enumerate(ranked_ids, start=1) if evidence_id in relevant
    ]
    best_rank = min(relevant_ranks) if relevant_ranks else None
    score: dict[str, Any] = {
        "query_id": gold_query.query_id,
        "query": gold_query.query,
        "ticker": gold_query.ticker,
        "fiscal_year": gold_query.fiscal_year,
        "tags": list(gold_query.tags),
        "relevant_evidence_ids": list(gold_query.relevant_evidence_ids),
        "top_evidence_ids": ranked_ids[: max(k_values)],
        "best_rank": best_rank,
        "reciprocal_rank": 1.0 / best_rank if best_rank else 0.0,
    }
    for k in k_values:
        top_k = set(ranked_ids[:k])
        matched = sorted(relevant & top_k)
        score[f"hit@{k}"] = bool(matched)
        score[f"recall@{k}"] = len(matched) / len(relevant)
        score[f"matched@{k}"] = matched
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


def summarize_scores(
    per_query: list[dict[str, Any]],
    k_values: tuple[int, ...],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "query_count": len(per_query),
        "mrr": mean(item["reciprocal_rank"] for item in per_query) if per_query else 0.0,
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
    misses = [item["query_id"] for item in per_query if not item[f"hit@{max(k_values)}"]]
    return {"summary": summary, "misses_at_max_k": misses, "per_query": per_query}
