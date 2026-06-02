from __future__ import annotations

import json
import pickle
import re
import sqlite3
from itertools import combinations
from pathlib import Path
from typing import Any

from evidence.structured_text import structured_object_preview, structured_object_search_text
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

SQLITE_FILTERED_SCAN_LIMIT = 50000


class ObjectBM25Retriever:
    def __init__(self, index_dir: str | Path) -> None:
        path = Path(index_dir)
        self.index_dir = path
        self.sqlite_fts_path = path / "records.sqlite"
        self.sqlite_fts_metadata = _sqlite_fts_metadata(self.sqlite_fts_path)
        self._sqlite_fts_con: sqlite3.Connection | None = None
        record_store_path = path / "records.duckdb"
        self._record_store_con: Any | None = None
        self._record_cache: dict[int, dict[str, Any]] = {}
        self._record_store_filter_cache: dict[str, list[dict[str, Any]]] = {}
        if self.sqlite_fts_metadata:
            self.bm25 = None
            self.record_count = int(self.sqlite_fts_metadata.get("records") or 0)
            self.record_store_path = None
            self.records_path = self.sqlite_fts_path
            self.records: list[dict[str, Any]] = []
            self._filter_index: dict[str, dict[Any, tuple[int, ...]]] = {}
        else:
            with (path / "bm25.pkl").open("rb") as f:
                self.bm25 = pickle.load(f)
            self.record_count = _bm25_record_count(self.bm25)
            self.record_store_path = (
                record_store_path if _record_store_is_usable(record_store_path, expected_count=self.record_count) else None
            )
            self.records_path = _preferred_records_path(path)
            if self.record_store_path is not None:
                self.records = []
                self._filter_index = {}
            else:
                self.records = _read_records(self.records_path)
                self.record_count = len(self.records)
                self._filter_index = _build_filter_index(self.records)
        self._filter_cache: dict[str, list[int]] = {}

    def search(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self.sqlite_fts_metadata:
            return self._search_sqlite_fts(query, top_k=top_k, filters=filters)
        if self.record_store_path is not None and _filters_are_indexed(filters):
            return self._search_record_store(query, top_k=top_k, filters=filters)
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

    def _search_record_store(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        candidate_rows = self._record_store_candidate_rows(filters)
        if candidate_rows is None:
            scores = self.bm25.get_scores(tokenize(query))
            ranked = sorted(
                ((idx, float(scores[idx]), None) for idx in range(self.record_count)),
                key=lambda item: item[1],
                reverse=True,
            )[:top_k]
        else:
            if not candidate_rows:
                return []
            candidate_indices = [int(row["idx"]) for row in candidate_rows]
            scores = self.bm25.get_batch_scores(tokenize(query), candidate_indices)
            ranked = sorted(
                (
                    (int(row["idx"]), self._adjust_score_from_meta(row, float(score), query), row)
                    for row, score in zip(candidate_rows, scores)
                ),
                key=lambda item: item[1],
                reverse=True,
            )[:top_k]
        records = self._records_for_indices([idx for idx, _score, _meta in ranked])
        return [
            self._format_result(idx, score, rank, record=records[idx])
            for rank, (idx, score, _meta) in enumerate(ranked, start=1)
        ]

    def _search_sqlite_fts(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        filtered_fts_results = self._search_sqlite_filtered_required_fts(query, top_k=top_k, filters=filters)
        if filtered_fts_results:
            return filtered_fts_results
        filtered_results = self._search_sqlite_filtered_candidates(query, top_k=top_k, filters=filters)
        if filtered_results is not None:
            return filtered_results
        where, params = _sqlite_filter_where(filters)
        fts_query = _sqlite_fts_query(query)
        limit = max(1, int(top_k))
        if fts_query:
            clauses = ["object_records_fts MATCH ?"]
            sql_params: list[Any] = [fts_query]
            clauses.extend(where)
            sql_params.extend(params)
            sql = (
                "SELECT r.record_json, r.period, r.periods_json, bm25(object_records_fts) AS raw_score "
                "FROM object_records_fts "
                "JOIN object_records r ON r.idx = object_records_fts.rowid "
                "WHERE " + " AND ".join(clauses) + " "
                "ORDER BY raw_score ASC LIMIT ?"
            )
            sql_params.append(limit)
        else:
            clauses = where or ["1=1"]
            sql = (
                "SELECT r.record_json, r.period, r.periods_json, 0.0 AS raw_score "
                "FROM object_records r WHERE " + " AND ".join(clauses) + " "
                "ORDER BY r.idx LIMIT ?"
            )
            sql_params = [*params, limit]
        result = self._sqlite_fts_connection().execute(sql, sql_params)
        rows = result.fetchall()
        out: list[dict[str, Any]] = []
        for rank, row in enumerate(rows, start=1):
            record = json.loads(row["record_json"])
            meta = {
                **record,
                "period": row["period"],
                "periods_json": row["periods_json"],
            }
            score = self._adjust_score_from_meta(meta, -float(row["raw_score"] or 0.0), query)
            out.append(self._format_result_from_record(record, score, rank))
        return out

    def _search_sqlite_filtered_required_fts(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        where, params = _sqlite_filter_where(filters)
        if not where:
            return []
        required_queries = _sqlite_required_fts_queries(query)
        if not required_queries:
            return []
        for required_query in required_queries:
            clauses = ["object_records_fts MATCH ?"]
            sql_params: list[Any] = [required_query]
            clauses.extend(where)
            sql_params.extend(params)
            sql = (
                "SELECT r.record_json, r.period, r.periods_json, bm25(object_records_fts) AS raw_score "
                "FROM object_records_fts "
                "JOIN object_records r ON r.idx = object_records_fts.rowid "
                "WHERE " + " AND ".join(clauses) + " "
                "ORDER BY raw_score ASC LIMIT ?"
            )
            sql_params.append(max(1, int(top_k)))
            rows = self._sqlite_fts_connection().execute(sql, sql_params).fetchall()
            if rows:
                out: list[dict[str, Any]] = []
                for rank, row in enumerate(rows, start=1):
                    record = json.loads(row["record_json"])
                    meta = {**record, "period": row["period"], "periods_json": row["periods_json"]}
                    score = self._adjust_score_from_meta(meta, -float(row["raw_score"] or 0.0), query)
                    out.append(self._format_result_from_record(record, score, rank))
                return out
        return []

    def _search_sqlite_filtered_candidates(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]] | None:
        where, params = _sqlite_filter_where(filters)
        if not where:
            return None
        limit = max(int(top_k), SQLITE_FILTERED_SCAN_LIMIT) + 1
        sql = (
            "SELECT r.record_json, r.period, r.periods_json "
            "FROM object_records r "
            "WHERE " + " AND ".join(where) + " "
            "ORDER BY r.idx LIMIT ?"
        )
        rows = self._sqlite_fts_connection().execute(sql, [*params, limit]).fetchall()
        if len(rows) > SQLITE_FILTERED_SCAN_LIMIT:
            return None
        ranked: list[tuple[dict[str, Any], float, dict[str, Any]]] = []
        for row in rows:
            record = json.loads(row["record_json"])
            meta = {
                **record,
                "period": row["period"],
                "periods_json": row["periods_json"],
            }
            score = _sqlite_python_score(record, query)
            score = self._adjust_score_from_meta(meta, score, query)
            ranked.append((record, score, meta))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return [
            self._format_result_from_record(record, score, rank)
            for rank, (record, score, _meta) in enumerate(ranked[: max(1, int(top_k))], start=1)
        ]

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
            periods = {str(period) for period in record.get("periods") or record.get("candidate_periods") or []}
            if not periods:
                periods = {str(cell.get("period") or "") for cell in record.get("cells") or []}
            if periods & years:
                return score + 2.0
        return score

    def _filtered_indices(self, filters: dict[str, Any] | None) -> list[int] | None:
        if not filters:
            return None
        self._ensure_records_loaded()
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

    def _format_result(
        self,
        idx: int,
        score: float,
        rank: int,
        record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = record or (self.records[idx] if self.records else self._record_for_idx(idx))
        return self._format_result_from_record(record, score, rank)

    def _format_result_from_record(self, record: dict[str, Any], score: float, rank: int) -> dict[str, Any]:
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

    def _adjust_score_from_meta(self, meta: dict[str, Any], score: float, query: str) -> float:
        years = set(re.findall(r"\b(?:19|20)\d{2}\b", query))
        if not years:
            return score
        period = str(meta.get("period") or "")
        object_type = meta.get("object_type")
        if object_type == "metric" and period:
            return score + 6.0 if period in years else score - 4.0
        if object_type == "table":
            periods = set()
            try:
                periods = {str(item) for item in json.loads(str(meta.get("periods_json") or "[]"))}
            except json.JSONDecodeError:
                periods = set()
            if periods & years:
                return score + 2.0
        return score

    def _record_store_candidate_rows(self, filters: dict[str, Any] | None) -> list[dict[str, Any]] | None:
        if not filters:
            return None
        cache_key = json.dumps(filters, sort_keys=True, ensure_ascii=False)
        if cache_key in self._record_store_filter_cache:
            return self._record_store_filter_cache[cache_key]
        where: list[str] = []
        params: list[Any] = []
        for key, expected in filters.items():
            values = expected if isinstance(expected, (list, tuple, set)) else [expected]
            values = [_normalize_filter_value(key, value) for value in values]
            placeholders = ", ".join("?" for _ in values)
            where.append(f"{key} IN ({placeholders})")
            params.extend(values)
        sql = (
            "SELECT idx, object_type, period, periods_json "
            "FROM object_records WHERE " + " AND ".join(where) + " ORDER BY idx"
        )
        result = self._record_store_connection().execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        self._record_store_filter_cache[cache_key] = rows
        return rows

    def _record_for_idx(self, idx: int) -> dict[str, Any]:
        if idx in self._record_cache:
            return self._record_cache[idx]
        result = self._record_store_connection().execute("SELECT * FROM object_records WHERE idx = ?", [int(idx)])
        columns = [desc[0] for desc in result.description]
        row = result.fetchone()
        if not row:
            raise IndexError(idx)
        values = dict(zip(columns, row))
        record = _record_from_store_values(values)
        self._record_cache[idx] = record
        return record

    def _records_for_indices(self, indices: list[int]) -> dict[int, dict[str, Any]]:
        missing = [int(idx) for idx in indices if int(idx) not in self._record_cache]
        if missing:
            placeholders = ", ".join("?" for _ in missing)
            result = self._record_store_connection().execute(
                f"SELECT * FROM object_records WHERE idx IN ({placeholders})",
                missing,
            )
            columns = [desc[0] for desc in result.description]
            for row in result.fetchall():
                values = dict(zip(columns, row))
                idx = int(values.get("idx"))
                self._record_cache[idx] = _record_from_store_values(values)
        return {int(idx): self._record_cache[int(idx)] for idx in indices}

    def _record_store_connection(self) -> Any:
        if self._record_store_con is None:
            import duckdb

            self._record_store_con = duckdb.connect(str(self.record_store_path), read_only=True)
        return self._record_store_con

    def _sqlite_fts_connection(self) -> sqlite3.Connection:
        if self._sqlite_fts_con is None:
            con = sqlite3.connect(str(self.sqlite_fts_path))
            con.row_factory = sqlite3.Row
            self._sqlite_fts_con = con
        return self._sqlite_fts_con

    def close(self) -> None:
        if self._record_store_con is not None:
            self._record_store_con.close()
            self._record_store_con = None
        if self._sqlite_fts_con is not None:
            self._sqlite_fts_con.close()
            self._sqlite_fts_con = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _ensure_records_loaded(self) -> None:
        if self.records:
            return
        self.records = _read_records(self.records_path)
        self.record_count = len(self.records)
        self._filter_index = _build_filter_index(self.records)


def _record_from_store_values(values: dict[str, Any]) -> dict[str, Any]:
    payload_json = values.pop("payload_json", None)
    if payload_json:
        return json.loads(payload_json)
    record = {key: value for key, value in values.items() if value is not None}
    periods_json = record.pop("periods_json", "")
    if periods_json:
        try:
            record["periods"] = json.loads(periods_json)
        except json.JSONDecodeError:
            pass
    record.pop("idx", None)
    return record


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


def _preferred_records_path(path: Path) -> Path:
    for name in ("records.slim.pkl", "records.slim.jsonl", "records.jsonl"):
        candidate = path / name
        if candidate.exists():
            return candidate
    return path / "records.jsonl"


def _bm25_record_count(bm25: Any) -> int:
    doc_freqs = getattr(bm25, "doc_freqs", None)
    if isinstance(doc_freqs, list):
        return len(doc_freqs)
    idf = getattr(bm25, "idf", None)
    if isinstance(idf, list):
        return len(idf)
    return 0


def _filters_are_indexed(filters: dict[str, Any] | None) -> bool:
    return not filters or all(key in INDEXED_FILTER_FIELDS for key in filters)


def _record_store_is_usable(path: Path, *, expected_count: int) -> bool:
    if not path.exists():
        return False
    try:
        import duckdb

        con = duckdb.connect(str(path), read_only=True)
        try:
            table_count = con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_name='object_record_store_metadata'"
            ).fetchone()[0]
            if not table_count:
                return False
            row = con.execute("SELECT payload_json FROM object_record_store_metadata LIMIT 1").fetchone()
        finally:
            con.close()
    except Exception:
        return False
    if not row:
        return False
    try:
        metadata = json.loads(row[0])
    except json.JSONDecodeError:
        return False
    row_count = int(metadata.get("record_count") or 0)
    return row_count > 0 and (not expected_count or row_count == expected_count)


def _sqlite_fts_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        con = sqlite3.connect(str(path))
        try:
            table_count = con.execute(
                "SELECT count(*) FROM sqlite_master WHERE type IN ('table', 'virtual table') AND name='object_records_fts'"
            ).fetchone()[0]
            if not table_count:
                return {}
            row = con.execute("SELECT payload_json FROM object_index_metadata LIMIT 1").fetchone()
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


def _sqlite_required_fts_queries(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokenize(query):
        for part in re.findall(r"[A-Za-z0-9]+", token):
            term = part.lower().strip()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            terms.append(term)
    if len(terms) < 2:
        return []
    non_year_terms = [term for term in terms if not re.fullmatch(r"(?:19|20)\d{2}", term)]
    year_terms = [term for term in terms if re.fullmatch(r"(?:19|20)\d{2}", term)]
    base = non_year_terms or terms
    queries: list[list[str]] = []
    if 2 <= len(base) <= 4:
        queries.append(base + year_terms[:1])
    if len(base) > 3:
        for idx in range(0, len(base) - 2):
            window = base[idx : idx + 3]
            if window not in queries:
                queries.append(window + year_terms[:1])
    if 3 < len(base) <= 6:
        for combo in combinations(base, 3):
            query_terms = list(combo)
            if query_terms not in queries:
                queries.append(query_terms + year_terms[:1])
    if len(base) > 4:
        head = base[:4]
        if head not in queries:
            queries.append(head + year_terms[:1])
    out: list[str] = []
    for query_terms in queries[:6]:
        if len(query_terms) < 2:
            continue
        out.append(" AND ".join(f'"{term}"' for term in query_terms))
    return out


def _sqlite_python_score(record: dict[str, Any], query: str) -> float:
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokenize(query):
        for part in re.findall(r"[A-Za-z0-9]+", token):
            term = part.lower().strip()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            terms.append(term)
    if not terms:
        return 0.0
    text = structured_object_search_text(record).lower()
    score = 0.0
    for term in terms:
        count = text.count(term)
        if count:
            score += min(count, 5)
    compact_query = " ".join(terms)
    if compact_query and compact_query in text:
        score += 6.0
    return score


def _read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".pkl":
        return _read_pickle_records(path)
    return _read_jsonl(path)


def _read_pickle_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        while True:
            try:
                records.append(pickle.load(handle))
            except EOFError:
                break
    return records


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
