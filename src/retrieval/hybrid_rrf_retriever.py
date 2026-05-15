from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .bm25_retriever import BM25Retriever
from .dense_retriever import DenseRetriever


class HybridRRFRetriever:
    def __init__(
        self,
        bm25_index_dir: str | Path,
        dense_index_dir: str | Path,
        *,
        rrf_k: int = 60,
        bm25_top_k: int = 30,
        dense_top_k: int = 30,
        device: str | None = None,
    ) -> None:
        self.bm25 = BM25Retriever(bm25_index_dir)
        self.dense = DenseRetriever(dense_index_dir, device=device)
        self.rrf_k = rrf_k
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        bm25_results = self.bm25.search(query, top_k=self.bm25_top_k, filters=filters)
        dense_results = self.dense.search(query, top_k=self.dense_top_k, filters=filters)
        return reciprocal_rank_fusion(
            {"bm25": bm25_results, "dense": dense_results},
            top_k=top_k,
            rrf_k=self.rrf_k,
        )


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[dict[str, Any]]],
    *,
    top_k: int = 10,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    records: dict[str, dict[str, Any]] = {}
    rank_features: dict[str, dict[str, Any]] = defaultdict(dict)

    for source, results in ranked_lists.items():
        for result in results:
            evidence_id = result["evidence_id"]
            rank = int(result["rank"])
            scores[evidence_id] += 1.0 / (rrf_k + rank)
            records.setdefault(evidence_id, result)
            rank_features[evidence_id][f"{source}_rank"] = rank
            rank_features[evidence_id][f"{source}_score"] = result.get("score")

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    fused_results: list[dict[str, Any]] = []
    for rank, (evidence_id, score) in enumerate(ranked, start=1):
        base = dict(records[evidence_id])
        base["rank"] = rank
        base["score"] = score
        base["fusion"] = rank_features[evidence_id]
        fused_results.append(base)
    return fused_results
