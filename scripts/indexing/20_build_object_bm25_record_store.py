from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from indexing.build_object_bm25_index import compact_structured_object_record  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a DuckDB metadata/payload store for ObjectBM25 records.")
    parser.add_argument("--index-dir", required=True, help="ObjectBM25 index directory containing records.jsonl.")
    parser.add_argument("--output-name", default="records.duckdb")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--duckdb-threads", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    parser.add_argument("--max-records", type=int, default=0, help="Optional diagnostic cap.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    index_dir = _repo_path(args.index_dir)
    source_path = _preferred_source_path(index_dir)
    output_path = index_dir / args.output_name
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if tmp_path.exists():
        tmp_path.unlink()
    wal_path = Path(str(tmp_path) + ".wal")
    if wal_path.exists():
        wal_path.unlink()
    count = 0
    pending: list[tuple[Any, ...]] = []
    import duckdb
    import pyarrow as pa

    con = duckdb.connect(str(tmp_path))
    try:
        con.execute(f"PRAGMA threads={max(1, int(args.duckdb_threads))}")
        con.execute("DROP TABLE IF EXISTS object_records")
        con.execute("DROP TABLE IF EXISTS object_record_store_metadata")
        con.execute(
            """
            CREATE TABLE object_records (
                idx INTEGER,
                object_id VARCHAR,
                object_type VARCHAR,
                source_evidence_id VARCHAR,
                ticker VARCHAR,
                fiscal_year INTEGER,
                form_type VARCHAR,
                source_type VARCHAR,
                source_tier VARCHAR,
                section VARCHAR,
                subsection VARCHAR,
                period VARCHAR,
                period_end VARCHAR,
                period_type VARCHAR,
                duration_months INTEGER,
                fiscal_period VARCHAR,
                preview VARCHAR,
                periods_json VARCHAR,
                metric_family VARCHAR
            )
            """
        )
        for record in _iter_source_records(source_path):
            compact = record if _source_is_compact(source_path) else compact_structured_object_record(record)
            pending.append(_db_row(count, compact))
            count += 1
            if len(pending) >= args.batch_size:
                _insert_rows(con, pending, pa)
                pending.clear()
            if args.max_records and count >= args.max_records:
                break
        if pending:
            _insert_rows(con, pending, pa)
        _create_indexes(con)
        metadata = {
            "schema_version": "sec_agent_object_bm25_record_store_v0.1",
            "source_path": str(source_path),
            "record_count": count,
            "elapsed_sec": round(time.perf_counter() - started, 3),
        }
        con.execute("CREATE TABLE object_record_store_metadata AS SELECT ? AS payload_json", [json.dumps(metadata, ensure_ascii=False)])
    finally:
        con.close()
    old_wal_path = Path(str(output_path) + ".wal")
    if old_wal_path.exists():
        old_wal_path.unlink()
    if output_path.exists():
        output_path.replace(output_path.with_name(f"{output_path.name}.previous"))
    tmp_path.replace(output_path)
    print(
        json.dumps(
            {
                "status": "completed",
                "source_path": str(source_path),
                "output_path": str(output_path),
                "records": count,
                "source_bytes": source_path.stat().st_size,
                "output_bytes": output_path.stat().st_size,
                "elapsed_sec": round(time.perf_counter() - started, 3),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _insert_rows(con: Any, rows: list[tuple[Any, ...]], pa: Any) -> None:
    columns = [
        "idx",
        "object_id",
        "object_type",
        "source_evidence_id",
        "ticker",
        "fiscal_year",
        "form_type",
        "source_type",
        "source_tier",
        "section",
        "subsection",
        "period",
        "period_end",
        "period_type",
        "duration_months",
        "fiscal_period",
        "preview",
        "periods_json",
        "metric_family",
    ]
    table = pa.Table.from_pylist([dict(zip(columns, row)) for row in rows])
    con.register("object_record_batch", table)
    try:
        con.execute("INSERT INTO object_records SELECT * FROM object_record_batch")
    finally:
        con.unregister("object_record_batch")


def _preferred_source_path(index_dir: Path) -> Path:
    for name in ("records.slim.pkl", "records.slim.jsonl", "records.jsonl"):
        candidate = index_dir / name
        if candidate.exists():
            return candidate
    return index_dir / "records.jsonl"


def _source_is_compact(path: Path) -> bool:
    return path.name.startswith("records.slim")


def _create_indexes(con: Any) -> None:
    con.execute("CREATE INDEX idx_object_records_idx ON object_records(idx)")
    con.execute("CREATE INDEX idx_object_records_filter_scope ON object_records(ticker, fiscal_year, form_type, source_tier)")
    con.execute("CREATE INDEX idx_object_records_object_type ON object_records(object_type)")
    con.execute("CREATE INDEX idx_object_records_section ON object_records(section)")


def _db_row(idx: int, record: dict[str, Any]) -> tuple[Any, ...]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    form_type = _normalize_form_type(record.get("form_type") or metadata.get("form_type"))
    source_type = _normalize_form_type(record.get("source_type") or metadata.get("source_type") or form_type)
    periods = record.get("periods") or record.get("candidate_periods") or []
    return (
        idx,
        _str_or_none(record.get("object_id")),
        _str_or_none(record.get("object_type")),
        _str_or_none(record.get("source_evidence_id")),
        _str_or_none(record.get("ticker")).upper() if record.get("ticker") else None,
        _int_or_none(record.get("fiscal_year")),
        form_type,
        source_type,
        _str_or_none(record.get("source_tier") or metadata.get("source_tier") or "primary_sec_filing"),
        _str_or_none(record.get("section")),
        _str_or_none(record.get("subsection")),
        _str_or_none(record.get("period")),
        _str_or_none(record.get("period_end") or metadata.get("period_end")),
        _str_or_none(record.get("period_type") or metadata.get("period_type")),
        _int_or_none(record.get("duration_months") or metadata.get("duration_months")),
        _str_or_none(record.get("fiscal_period") or metadata.get("fiscal_period")),
        _str_or_none(record.get("preview")),
        json.dumps(periods, ensure_ascii=False),
        _str_or_none(record.get("metric_family")),
    )


def _iter_source_records(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix == ".pkl":
        yield from _iter_pickle_records(path)
    else:
        yield from _iter_jsonl(path)


def _iter_pickle_records(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("rb") as handle:
        while True:
            try:
                yield pickle.load(handle)
            except EOFError:
                break


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _normalize_form_type(value: Any) -> str:
    return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
