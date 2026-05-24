from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any

from evidence.structured_text import structured_object_preview
from retrieval.text import tokenize


class ObjectBM25Retriever:
    def __init__(self, index_dir: str | Path) -> None:
        path = Path(index_dir)
        with (path / "bm25.pkl").open("rb") as f:
            self.bm25 = pickle.load(f)
        self.records = [
            json.loads(line)
            for line in (path / "records.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self._filter_cache: dict[str, list[int]] = {}

    def search(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        candidate_indices = self._filtered_indices(filters)
        if candidate_indices is None:
            scores = self.bm25.get_scores(tokenize(query))
            candidate_indices = range(len(self.records))
            ranked = sorted(
                ((idx, self._adjust_score(idx, float(scores[idx]), query)) for idx in candidate_indices),
                key=lambda item: item[1],
                reverse=True,
            )[:top_k]
        else:
            candidate_indices = list(candidate_indices)
            scores = self.bm25.get_batch_scores(tokenize(query), candidate_indices)
            ranked = sorted(
                (
                    (idx, self._adjust_score(idx, float(score), query))
                    for idx, score in zip(candidate_indices, scores)
                ),
                key=lambda item: item[1],
                reverse=True,
            )[:top_k]
        return [self._format_result(idx, score, rank) for rank, (idx, score) in enumerate(ranked, start=1)]

    def _adjust_score(self, idx: int, score: float, query: str) -> float:
        years = set(re.findall(r"\b(?:19|20)\d{2}\b", query))
        if not years:
            return score
        record = self.records[idx]
        period = str(record.get("period") or "")
        object_type = record.get("object_type")
        if object_type == "metric" and period:
            return score + 6.0 if period in years else score - 4.0
        if object_type == "table":
            cells = record.get("cells") or []
            if any(str(cell.get("period") or "") in years for cell in cells):
                return score + 2.0
        return score

    def _filtered_indices(self, filters: dict[str, Any] | None) -> list[int] | None:
        if not filters:
            return None
        cache_key = json.dumps(filters, sort_keys=True, ensure_ascii=False)
        if cache_key in self._filter_cache:
            return self._filter_cache[cache_key]
        indices = []
        for idx, record in enumerate(self.records):
            if _record_matches(record, filters):
                indices.append(idx)
        self._filter_cache[cache_key] = indices
        return indices

    def _format_result(self, idx: int, score: float, rank: int) -> dict[str, Any]:
        record = self.records[idx]
        return {
            "rank": rank,
            "score": score,
            "object_id": record["object_id"],
            "object_type": record.get("object_type"),
            "source_evidence_id": record.get("source_evidence_id"),
            "ticker": record.get("ticker"),
            "fiscal_year": record.get("fiscal_year"),
            "section": record.get("section"),
            "subsection": record.get("subsection"),
            "preview": structured_object_preview(record),
            "record": record,
        }


def _record_matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    metadata = record.get("metadata", {})
    for key, expected in filters.items():
        actual = metadata.get(key, record.get(key))
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True
