from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any

from evidence.structured_text import structured_object_preview
from retrieval.text import tokenize

INDEXED_FILTER_FIELDS = {
    "filing_type",
    "fiscal_year",
    "form_type",
    "object_type",
    "section",
    "source_tier",
    "source_type",
    "ticker",
}


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
        self._filter_index = _build_filter_index(self.records)

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
            if not candidate_indices:
                return []
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
        indexed = _indexed_filter_indices(self._filter_index, filters)
        if indexed is not None:
            self._filter_cache[cache_key] = indexed
            return indexed
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


def _build_filter_index(records: list[dict[str, Any]]) -> dict[str, dict[Any, tuple[int, ...]]]:
    mutable: dict[str, dict[Any, list[int]]] = {field: {} for field in INDEXED_FILTER_FIELDS}
    for idx, record in enumerate(records):
        metadata = record.get("metadata", {})
        for field in INDEXED_FILTER_FIELDS:
            value = _normalize_filter_value(field, _record_filter_value(record, metadata, field))
            mutable[field].setdefault(value, []).append(idx)
    return {
        field: {value: tuple(indices) for value, indices in values.items()}
        for field, values in mutable.items()
    }


def _indexed_filter_indices(
    filter_index: dict[str, dict[Any, tuple[int, ...]]],
    filters: dict[str, Any],
) -> list[int] | None:
    if any(key not in filter_index for key in filters):
        return None
    matched: set[int] | None = None
    for key, expected in filters.items():
        values = expected if isinstance(expected, (list, tuple, set)) else [expected]
        key_matches: set[int] = set()
        for value in values:
            key_matches.update(filter_index[key].get(_normalize_filter_value(key, value), ()))
        matched = key_matches if matched is None else matched & key_matches
        if not matched:
            return []
    return sorted(matched or set())


def _record_matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    metadata = record.get("metadata", {})
    for key, expected in filters.items():
        actual = _record_filter_value(record, metadata, key)
        if isinstance(expected, (list, tuple, set)):
            expected_values = {_normalize_filter_value(key, item) for item in expected}
            if _normalize_filter_value(key, actual) not in expected_values:
                return False
        elif _normalize_filter_value(key, actual) != _normalize_filter_value(key, expected):
            return False
    return True


def _record_filter_value(record: dict[str, Any], metadata: dict[str, Any], key: str) -> Any:
    if key in {"form_type", "source_type", "filing_type"}:
        value = metadata.get(key, record.get(key))
        if value:
            return value
        return _form_type_from_source_id(record.get("source_evidence_id") or record.get("evidence_id") or record.get("object_id"))
    if key == "source_tier":
        return metadata.get(key, record.get(key)) or "primary_sec_filing"
    return metadata.get(key, record.get(key))


def _normalize_filter_value(key: str, value: Any) -> Any:
    if key in {"form_type", "source_type", "filing_type"}:
        return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")
    if key == "ticker":
        return str(value or "").upper().strip()
    if key == "fiscal_year":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def _form_type_from_source_id(value: Any) -> str:
    text = str(value or "").upper()
    if "_10Q_" in text:
        return "10-Q"
    if "_10K_" in text:
        return "10-K"
    return ""
