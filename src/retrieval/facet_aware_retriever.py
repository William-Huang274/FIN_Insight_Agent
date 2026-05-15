from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


SearchFn = Callable[[str, int], list[dict[str, Any]]]


def facet_aware_rrf(
    query_texts: list[str],
    search_fn: SearchFn,
    *,
    top_k: int = 10,
    candidate_k: int = 20,
    rrf_k: int = 60,
    original_query_weight: float = 0.75,
    facet_query_weight: float = 1.0,
    first_query_is_original: bool = True,
) -> list[dict[str, Any]]:
    if not query_texts:
        return []

    scores: dict[str, float] = defaultdict(float)
    records: dict[str, dict[str, Any]] = {}
    rank_features: dict[str, dict[str, Any]] = defaultdict(dict)

    for query_index, query_text in enumerate(query_texts):
        source = _source_name(query_index, first_query_is_original)
        weight = (
            original_query_weight
            if first_query_is_original and query_index == 0
            else facet_query_weight
        )
        results = search_fn(query_text, candidate_k)
        for result in results:
            evidence_id = result["evidence_id"]
            rank = int(result["rank"])
            scores[evidence_id] += weight / (rrf_k + rank)
            records.setdefault(evidence_id, result)
            rank_features[evidence_id][f"{source}_rank"] = rank
            rank_features[evidence_id][f"{source}_score"] = result.get("score")
            rank_features[evidence_id][f"{source}_query"] = query_text

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    fused_results: list[dict[str, Any]] = []
    for rank, (evidence_id, score) in enumerate(ranked, start=1):
        base = dict(records[evidence_id])
        base["rank"] = rank
        base["score"] = score
        base["facet_fusion"] = rank_features[evidence_id]
        fused_results.append(base)
    return fused_results


def facet_aware_round_robin(
    query_texts: list[str],
    search_fn: SearchFn,
    *,
    top_k: int = 10,
    candidate_k: int = 20,
    first_query_is_original: bool = True,
    original_first: bool = False,
) -> list[dict[str, Any]]:
    if not query_texts:
        return []

    source_results: list[tuple[str, str, list[dict[str, Any]]]] = []
    for query_index, query_text in enumerate(query_texts):
        source_results.append(
            (
                _source_name(query_index, first_query_is_original),
                query_text,
                search_fn(query_text, candidate_k),
            )
        )

    if first_query_is_original and len(source_results) > 1 and not original_first:
        source_order = [*range(1, len(source_results)), 0]
    else:
        source_order = list(range(len(source_results)))

    positions = [0 for _ in source_results]
    seen: set[str] = set()
    fused_results: list[dict[str, Any]] = []

    while len(fused_results) < top_k:
        appended = False
        for source_index in source_order:
            source, query_text, results = source_results[source_index]
            while positions[source_index] < len(results):
                result = results[positions[source_index]]
                positions[source_index] += 1
                evidence_id = result["evidence_id"]
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                base = dict(result)
                base["rank"] = len(fused_results) + 1
                base["facet_fusion"] = {
                    "strategy": "round_robin",
                    "source": source,
                    "source_rank": result.get("rank"),
                    "source_score": result.get("score"),
                    "source_query": query_text,
                }
                fused_results.append(base)
                appended = True
                break
            if len(fused_results) >= top_k:
                break
        if not appended:
            break
    return fused_results


def _source_name(query_index: int, first_query_is_original: bool) -> str:
    if first_query_is_original:
        return "original" if query_index == 0 else f"facet_{query_index:02d}"
    return f"facet_{query_index + 1:02d}"
