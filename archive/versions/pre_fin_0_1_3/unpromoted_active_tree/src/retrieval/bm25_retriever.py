from __future__ import annotations

import json
import pickle
import re
import sqlite3
import heapq
from pathlib import Path
from typing import Any

from .text import tokenize

INDEXED_FILTER_FIELDS = {
    "evidence_type",
    "filing_type",
    "fiscal_year",
    "form_type",
    "section",
    "source_tier",
    "source_type",
    "ticker",
}
_SEC_FORM_TYPES = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
_SEC_FORM_ID_RE = re.compile(r"(?:^|[^A-Z0-9])(?P<form>10-?K|10-?Q|8-?K|20-?F|40-?F|6-?K)(?:[^A-Z0-9]|$)")


class BM25Retriever:
    def __init__(self, index_dir: str | Path) -> None:
        path = Path(index_dir)
        self.index_dir = path
        self.sqlite_fts_path = path / "records.sqlite"
        self.sqlite_fts_metadata = _sqlite_fts_metadata(self.sqlite_fts_path)
        self._sqlite_fts_con: sqlite3.Connection | None = None
        self.streaming_records_path: Path | None = None
        self.storage_mode = "rank_bm25_pickle"
        if self.sqlite_fts_metadata:
            self.bm25 = None
            self.records: list[dict[str, Any]] = []
            self.record_count = int(self.sqlite_fts_metadata.get("records") or 0)
            self._filter_index: dict[str, dict[Any, tuple[int, ...]]] = {}
            self.storage_mode = "sqlite_fts"
        else:
            try:
                with (path / "bm25.pkl").open("rb") as f:
                    self.bm25 = pickle.load(f)
                self.records = _read_jsonl(path / "records.jsonl")
                self.record_count = len(self.records)
                self._filter_index = _build_filter_index(self.records)
            except MemoryError:
                records_path = path / "records.jsonl"
                if not records_path.exists():
                    raise
                self.bm25 = None
                self.records = []
                self.record_count = 0
                self._filter_index = {}
                self.streaming_records_path = records_path
                self.storage_mode = "streaming_jsonl_lexical"
        self._filter_cache: dict[str, list[int]] = {}

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self.sqlite_fts_metadata:
            return self._search_sqlite_fts(query, top_k=top_k, filters=filters)
        if self.streaming_records_path is not None:
            return self._search_streaming_jsonl(query, top_k=top_k, filters=filters)
        candidate_indices = self._filtered_indices(filters)
        if candidate_indices is None:
            scores = self.bm25.get_scores(tokenize(query))
            candidate_indices = range(len(self.records))
            ranked = sorted(
                ((idx, float(scores[idx])) for idx in candidate_indices),
                key=lambda item: item[1],
                reverse=True,
            )[:top_k]
        else:
            candidate_indices = list(candidate_indices)
            if not candidate_indices:
                return []
            scores = self.bm25.get_batch_scores(tokenize(query), candidate_indices)
            ranked = sorted(
                ((idx, float(score)) for idx, score in zip(candidate_indices, scores)),
                key=lambda item: item[1],
                reverse=True,
            )[:top_k]
        return [self._format_result(idx, score, rank) for rank, (idx, score) in enumerate(ranked, start=1)]

    def _search_sqlite_fts(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        where, params = _sqlite_filter_where(filters)
        fts_query = _sqlite_fts_query(query)
        limit = max(1, int(top_k))
        if fts_query:
            clauses = ["bm25_records_fts MATCH ?"]
            sql_params: list[Any] = [fts_query]
            clauses.extend(where)
            sql_params.extend(params)
            sql = (
                "SELECT r.record_json, bm25(bm25_records_fts) AS raw_score "
                "FROM bm25_records_fts "
                "JOIN bm25_records r ON r.idx = bm25_records_fts.rowid "
                "WHERE " + " AND ".join(clauses) + " "
                "ORDER BY raw_score ASC LIMIT ?"
            )
            sql_params.append(limit)
        else:
            clauses = where or ["1=1"]
            sql = (
                "SELECT r.record_json, 0.0 AS raw_score "
                "FROM bm25_records r WHERE " + " AND ".join(clauses) + " "
                "ORDER BY r.idx LIMIT ?"
            )
            sql_params = [*params, limit]
        rows = self._sqlite_fts_connection().execute(sql, sql_params).fetchall()
        return [
            self._format_result_from_record(json.loads(row["record_json"]), -float(row["raw_score"] or 0.0), rank)
            for rank, row in enumerate(rows, start=1)
        ]

    def _search_streaming_jsonl(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if self.streaming_records_path is None:
            return []
        query_terms = _streaming_query_terms(query)
        heap: list[tuple[float, int, dict[str, Any]]] = []
        serial = 0
        limit = max(1, int(top_k))
        with self.streaming_records_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {self.streaming_records_path}:{line_number}") from exc
                if filters and not _record_matches(record, filters):
                    continue
                score = _streaming_lexical_score(record, query_terms)
                if query_terms and score <= 0:
                    continue
                serial += 1
                entry = (score, serial, record)
                if len(heap) < limit:
                    heapq.heappush(heap, entry)
                elif entry[0] > heap[0][0]:
                    heapq.heapreplace(heap, entry)
        ranked = sorted(heap, key=lambda item: (item[0], -item[1]), reverse=True)
        return [
            self._format_result_from_record(record, float(score), rank)
            for rank, (score, _serial, record) in enumerate(ranked, start=1)
        ]

    def _sqlite_fts_connection(self) -> sqlite3.Connection:
        if self._sqlite_fts_con is None:
            con = sqlite3.connect(str(self.sqlite_fts_path))
            con.row_factory = sqlite3.Row
            self._sqlite_fts_con = con
        return self._sqlite_fts_con

    def _filtered_indices(self, filters: dict[str, Any] | None):
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
        return self._format_result_from_record(record, score, rank)

    def _format_result_from_record(self, record: dict[str, Any], score: float, rank: int) -> dict[str, Any]:
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


def _sqlite_fts_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        con = sqlite3.connect(str(path))
        try:
            table_count = con.execute(
                "SELECT count(*) FROM sqlite_master WHERE type IN ('table', 'virtual table') AND name='bm25_records_fts'"
            ).fetchone()[0]
            if not table_count:
                return {}
            row = con.execute("SELECT payload_json FROM bm25_index_metadata LIMIT 1").fetchone()
        finally:
            con.close()
    except Exception:
        return {}
    if not row:
        return {}
    try:
        metadata = json.loads(row[0])
    except json.JSONDecodeError:
        return {}
    return metadata if int(metadata.get("records") or 0) > 0 else {}


def _sqlite_filter_where(filters: dict[str, Any] | None) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    for key, expected in (filters or {}).items():
        if key not in INDEXED_FILTER_FIELDS:
            continue
        column = "form_type" if key == "filing_type" else key
        values = expected if isinstance(expected, (list, tuple, set)) else [expected]
        values = [_normalize_filter_value(key, value) for value in values]
        values = [value for value in values if value not in (None, "")]
        if not values:
            continue
        placeholders = ", ".join("?" for _ in values)
        where.append(f"r.{column} IN ({placeholders})")
        params.extend(values)
    return where, params


def _sqlite_fts_query(query: str) -> str:
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokenize(query):
        for part in re.findall(r"[A-Za-z0-9]+", token):
            term = part.lower().strip()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            terms.append(term)
            if len(terms) >= 32:
                break
        if len(terms) >= 32:
            break
    return " OR ".join(f'"{term}"' for term in terms)


def _streaming_query_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokenize(str(query or "").replace("_", " ")):
        for part in re.findall(r"[A-Za-z0-9]+", token):
            term = part.lower().strip()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            terms.append(term)
            if len(terms) >= 48:
                return terms
    return terms


def _streaming_lexical_score(record: dict[str, Any], query_terms: list[str]) -> float:
    if not query_terms:
        return 1.0
    metadata = record.get("metadata", {}) if isinstance(record.get("metadata"), dict) else {}
    parts = [
        record.get("ticker"),
        record.get("company"),
        record.get("fiscal_year"),
        record.get("section"),
        record.get("subsection"),
        record.get("evidence_type"),
        " ".join(str(item) for item in record.get("topics") or []),
        metadata.get("category"),
        metadata.get("block_type"),
        record.get("text"),
    ]
    text = " ".join(str(part or "") for part in parts).lower().replace("_", " ")
    score = 0.0
    for term in query_terms:
        count = text.count(term)
        if count:
            score += min(float(count), 8.0)
            if term in {"capex", "revenue", "margin", "backlog", "orders", "cloud", "ai"}:
                score += 1.5
    return score


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
    return records


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
        value = (
            metadata.get(key)
            or record.get(key)
            or metadata.get("form_type")
            or record.get("form_type")
            or record.get("source_type")
        )
        if value:
            return value
        return _form_type_from_source_id(record.get("source_evidence_id") or record.get("evidence_id") or record.get("object_id"))
    if key == "source_tier":
        return metadata.get(key, record.get(key)) or "primary_sec_filing"
    return metadata.get(key, record.get(key))


def _normalize_filter_value(key: str, value: Any) -> Any:
    if key in {"form_type", "source_type", "filing_type"}:
        return _normalize_form_type(value)
    if key == "ticker":
        return str(value or "").upper().strip()
    if key == "fiscal_year":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def _form_type_from_source_id(value: Any) -> str:
    match = _SEC_FORM_ID_RE.search(str(value or "").upper())
    if not match:
        return ""
    form = _normalize_form_type(match.group("form"))
    return form if form in _SEC_FORM_TYPES else ""


def _normalize_form_type(value: Any) -> str:
    text = str(value or "").upper().strip()
    return (
        text.replace("10K", "10-K")
        .replace("10Q", "10-Q")
        .replace("8K", "8-K")
        .replace("20F", "20-F")
        .replace("40F", "40-F")
        .replace("6K", "6-K")
    )


def _preview(text: str, max_chars: int = 280) -> str:
    text = " ".join(text.split())
    return text[:max_chars] + ("..." if len(text) > max_chars else "")
