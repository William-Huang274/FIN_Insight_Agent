from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from .text import tokenize


class BM25Retriever:
    def __init__(self, index_dir: str | Path) -> None:
        path = Path(index_dir)
        with (path / "bm25.pkl").open("rb") as f:
            self.bm25 = pickle.load(f)
        self.records = [
            json.loads(line)
            for line in (path / "records.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        scores = self.bm25.get_scores(tokenize(query))
        candidate_indices = self._filtered_indices(filters)
        if candidate_indices is None:
            candidate_indices = range(len(self.records))

        ranked = sorted(
            ((idx, float(scores[idx])) for idx in candidate_indices),
            key=lambda item: item[1],
            reverse=True,
        )[:top_k]
        return [self._format_result(idx, score, rank) for rank, (idx, score) in enumerate(ranked, start=1)]

    def _filtered_indices(self, filters: dict[str, Any] | None):
        if not filters:
            return None
        indices = []
        for idx, record in enumerate(self.records):
            if _record_matches(record, filters):
                indices.append(idx)
        return indices

    def _format_result(self, idx: int, score: float, rank: int) -> dict[str, Any]:
        record = self.records[idx]
        return {
            "rank": rank,
            "score": score,
            "evidence_id": record["evidence_id"],
            "ticker": record["ticker"],
            "fiscal_year": record.get("fiscal_year"),
            "section": record.get("section"),
            "subsection": record.get("subsection"),
            "evidence_type": record.get("evidence_type"),
            "contains_table": record.get("metadata", {}).get("contains_table", False),
            "text_preview": _preview(record.get("text", "")),
            "record": record,
        }


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
    return value


def _form_type_from_source_id(value: Any) -> str:
    text = str(value or "").upper()
    if "_10Q_" in text:
        return "10-Q"
    if "_10K_" in text:
        return "10-K"
    return ""


def _preview(text: str, max_chars: int = 280) -> str:
    text = " ".join(text.split())
    return text[:max_chars] + ("..." if len(text) > max_chars else "")
