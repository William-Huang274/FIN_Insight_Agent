from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterator

from evidence.structured_text import structured_object_preview, structured_object_search_text
from indexing.build_object_bm25_index import compact_structured_object_record


SCHEMA_VERSION = "sec_agent_object_sqlite_fts_v0.1"
SQLITE_INDEX_NAME = "records.sqlite"
_SEC_FORM_TYPES = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
_SEC_FORM_ID_RE = re.compile(r"(?:^|[^A-Z0-9])(?P<form>10-?K|10-?Q|8-?K|20-?F|40-?F|6-?K)(?:[^A-Z0-9]|$)")


def build_object_sqlite_fts_index(
    structured_dir: str | Path,
    output_dir: str | Path,
    *,
    prefix: str,
    workers: int = 1,
    batch_bytes: int = 4 * 1024 * 1024,
    insert_batch_size: int = 5000,
    progress_every: int = 100000,
    journal_mode: str = "WAL",
    synchronous: str = "NORMAL",
    optimize_fts: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    structured_path = Path(structured_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    db_path = output_path / SQLITE_INDEX_NAME
    tmp_path = output_path / f"{SQLITE_INDEX_NAME}.tmp"
    for path in (tmp_path, Path(str(tmp_path) + "-wal"), Path(str(tmp_path) + "-shm")):
        if path.exists():
            path.unlink()

    journal_mode = _normalise_sqlite_pragma(
        journal_mode,
        allowed={"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"},
        default="WAL",
    )
    synchronous = _normalise_sqlite_pragma(
        synchronous,
        allowed={"OFF", "NORMAL", "FULL", "EXTRA"},
        default="NORMAL",
    )
    con = sqlite3.connect(str(tmp_path))
    con.execute(f"PRAGMA journal_mode={journal_mode}")
    con.execute(f"PRAGMA synchronous={synchronous}")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-200000")
    _create_schema(con)

    next_idx = 1
    record_count = 0
    object_counts = {"table": 0, "metric": 0, "claim": 0}
    next_progress = max(1, int(progress_every))
    pending: list[tuple[Any, ...]] = []
    work_items = _iter_structured_work_items(structured_path, prefix, batch_bytes=max(1, int(batch_bytes)))
    try:
        for result in _iter_sqlite_batch_results(work_items, workers=max(1, int(workers))):
            for row in result["rows"]:
                pending.append((next_idx, *row))
                next_idx += 1
            record_count += int(result["record_count"])
            for key, value in result["object_counts"].items():
                object_counts[key] = object_counts.get(key, 0) + int(value)
            while len(pending) >= insert_batch_size:
                _insert_rows(con, pending[:insert_batch_size])
                del pending[:insert_batch_size]
            if progress_every and record_count >= next_progress:
                print(
                    json.dumps({"progress": record_count, "object_counts": object_counts}, ensure_ascii=False),
                    file=sys.stderr,
                    flush=True,
                )
                while record_count >= next_progress:
                    next_progress += max(1, int(progress_every))
        if pending:
            _insert_rows(con, pending)
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "structured_dir": str(structured_path),
            "prefix": prefix,
            "records": record_count,
            "object_counts": object_counts,
            "index_type": "sqlite_fts5",
            "record_files": [SQLITE_INDEX_NAME],
            "workers": max(1, int(workers)),
            "batch_bytes": max(1, int(batch_bytes)),
            "insert_batch_size": max(1, int(insert_batch_size)),
            "journal_mode": journal_mode,
            "synchronous": synchronous,
            "optimize_fts": bool(optimize_fts),
            "elapsed_sec": round(time.perf_counter() - started, 3),
        }
        con.execute("INSERT INTO object_index_metadata(payload_json) VALUES (?)", [json.dumps(metadata, ensure_ascii=False)])
        if optimize_fts:
            con.execute("INSERT INTO object_records_fts(object_records_fts) VALUES ('optimize')")
        con.commit()
    finally:
        con.close()

    if db_path.exists():
        previous = output_path / f"{SQLITE_INDEX_NAME}.previous"
        if previous.exists():
            previous.unlink()
        db_path.replace(previous)
    tmp_path.replace(db_path)
    (output_path / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def _normalise_sqlite_pragma(value: str, *, allowed: set[str], default: str) -> str:
    normalised = str(value or default).strip().upper()
    if normalised not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"Unsupported SQLite pragma value {value!r}; expected one of: {allowed_values}")
    return normalised


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        DROP TABLE IF EXISTS object_records;
        DROP TABLE IF EXISTS object_index_metadata;
        DROP TABLE IF EXISTS object_records_fts;

        CREATE TABLE object_records (
            idx INTEGER PRIMARY KEY,
            object_id TEXT,
            object_type TEXT,
            source_evidence_id TEXT,
            ticker TEXT,
            fiscal_year INTEGER,
            form_type TEXT,
            source_type TEXT,
            source_tier TEXT,
            section TEXT,
            subsection TEXT,
            period TEXT,
            period_end TEXT,
            period_type TEXT,
            duration_months INTEGER,
            fiscal_period TEXT,
            preview TEXT,
            periods_json TEXT,
            metric_family TEXT,
            record_json TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE object_records_fts USING fts5(
            search_text,
            content='object_records',
            content_rowid='idx',
            tokenize='unicode61'
        );

        CREATE TABLE object_index_metadata (
            payload_json TEXT NOT NULL
        );

        CREATE INDEX idx_object_records_ticker_year_form_object
            ON object_records(ticker, fiscal_year, form_type, object_type);
        CREATE INDEX idx_object_records_source_tier
            ON object_records(source_tier);
        CREATE INDEX idx_object_records_section
            ON object_records(section);
        CREATE INDEX idx_object_records_metric_family
            ON object_records(metric_family);
        """
    )


def _insert_rows(con: sqlite3.Connection, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    con.executemany(
        """
        INSERT INTO object_records (
            idx, object_id, object_type, source_evidence_id, ticker, fiscal_year,
            form_type, source_type, source_tier, section, subsection, period,
            period_end, period_type, duration_months, fiscal_period, preview,
            periods_json, metric_family, record_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [row[:-1] for row in rows],
    )
    con.executemany("INSERT INTO object_records_fts(rowid, search_text) VALUES (?, ?)", [(row[0], row[-1]) for row in rows])
    con.commit()


def _iter_structured_work_items(structured_path: Path, prefix: str, *, batch_bytes: int) -> Iterator[dict[str, Any]]:
    for suffix in ("tables", "metrics", "claims"):
        path = structured_path / f"{prefix}_{suffix}.jsonl"
        file_size = path.stat().st_size
        start = 0
        while start < file_size:
            end = min(file_size, start + batch_bytes)
            yield {"path": str(path), "start": start, "end": end}
            start = end


def _iter_sqlite_batch_results(
    work_items: Iterator[dict[str, Any]],
    *,
    workers: int,
) -> Iterator[dict[str, Any]]:
    if workers <= 1:
        for item in work_items:
            yield _build_sqlite_rows_from_range(item)
        return

    max_pending = max(workers * 2, 1)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending: set[Future] = set()

        def submit_next() -> bool:
            try:
                item = next(work_items)
            except StopIteration:
                return False
            pending.add(executor.submit(_build_sqlite_rows_from_range, item))
            return True

        for _ in range(max_pending):
            if not submit_next():
                break

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                submit_next()


def _build_sqlite_rows_from_range(item: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(item.get("path") or ""))
    start = int(item.get("start") or 0)
    end = int(item.get("end") or 0)
    rows: list[tuple[Any, ...]] = []
    object_counts = {"table": 0, "metric": 0, "claim": 0}
    with path.open("rb") as handle:
        handle.seek(start)
        if start > 0:
            handle.readline()
        while True:
            pos = handle.tell()
            if pos >= end:
                break
            raw_line = handle.readline()
            if not raw_line:
                break
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:byte={pos}") from exc
            object_type = str(record.get("object_type") or "")
            if object_type in object_counts:
                object_counts[object_type] += 1
            rows.append(_sqlite_row(record))
    return {"record_count": len(rows), "object_counts": object_counts, "rows": rows}


def _sqlite_row(record: dict[str, Any]) -> tuple[Any, ...]:
    compact = compact_structured_object_record(record)
    metadata = compact.get("metadata") if isinstance(compact.get("metadata"), dict) else {}
    periods = compact.get("periods") or compact.get("candidate_periods") or []
    form_type = _normalize_form_type(compact.get("form_type") or metadata.get("form_type"))
    if not form_type:
        form_type = _form_type_from_source_id(compact.get("source_evidence_id") or compact.get("object_id"))
    source_type = _normalize_form_type(compact.get("source_type") or metadata.get("source_type") or form_type)
    source_tier = compact.get("source_tier") or metadata.get("source_tier") or "primary_sec_filing"
    record_json = json.dumps(compact, ensure_ascii=False)
    search_text = structured_object_search_text(record)
    return (
        _str_or_none(compact.get("object_id")),
        _str_or_none(compact.get("object_type")),
        _str_or_none(compact.get("source_evidence_id")),
        _str_or_none(compact.get("ticker")).upper() if compact.get("ticker") else None,
        _int_or_none(compact.get("fiscal_year")),
        form_type,
        source_type,
        _str_or_none(source_tier),
        _str_or_none(compact.get("section")),
        _str_or_none(compact.get("subsection")),
        _str_or_none(compact.get("period")),
        _str_or_none(compact.get("period_end") or metadata.get("period_end")),
        _str_or_none(compact.get("period_type") or metadata.get("period_type")),
        _int_or_none(compact.get("duration_months") or metadata.get("duration_months")),
        _str_or_none(compact.get("fiscal_period") or metadata.get("fiscal_period")),
        _str_or_none(compact.get("preview") or structured_object_preview(record)),
        json.dumps(periods, ensure_ascii=False),
        _str_or_none(compact.get("metric_family")),
        record_json,
        search_text,
    )


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


def _form_type_from_source_id(value: Any) -> str:
    match = _SEC_FORM_ID_RE.search(str(value or "").upper())
    if not match:
        return ""
    form = _normalize_form_type(match.group("form"))
    return form if form in _SEC_FORM_TYPES else ""


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
