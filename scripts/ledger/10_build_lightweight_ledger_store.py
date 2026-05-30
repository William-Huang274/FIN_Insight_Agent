from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable, Iterator


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (SRC_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sec_agent.ledger_store import LEDGER_STORE_CASE_ID, LedgerStoreWriter, normalize_ledger_fact_values  # noqa: E402
from cloud import sec_agent_interactive as interactive  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a DuckDB lightweight ledger store from structured SEC objects.")
    parser.add_argument("--structured-dir", default="data/processed_private/structured_objects")
    parser.add_argument("--prefix", default="sec_investment_coverage_mixed_with_8k_fy2023_2027")
    parser.add_argument("--output-path", default="data/processed_private/ledger/sec_investment_coverage_mixed_with_8k_fy2023_2027_ledger.duckdb")
    parser.add_argument("--max-rows", type=int, default=0, help="Optional diagnostic cap over source structured records.")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--source-batch-size", type=int, default=1000, help="Structured source records per worker task.")
    parser.add_argument(
        "--source-batch-bytes",
        type=int,
        default=32 * 1024 * 1024,
        help="Approximate byte range per worker task when --max-rows is not set.",
    )
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes for ledger row extraction.")
    parser.add_argument("--progress-every", type=int, default=50000, help="Print progress to stderr every N source records.")
    parser.add_argument("--duckdb-threads", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    parser.add_argument("--years", default="", help="Optional comma-separated fiscal years to keep after ledger extraction.")
    parser.add_argument("--metric-families", default="", help="Optional comma-separated metric families to keep after ledger extraction.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    structured_dir = _repo_path(args.structured_dir)
    output_path = _repo_path(args.output_path)
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    _remove_duckdb_path(tmp_path)
    keep_years = {int(item) for item in _csv_items(args.years) if item.isdigit()}
    keep_families = set(_csv_items(args.metric_families))
    source_records = 0
    extracted_rows = 0
    next_progress = max(1, int(args.progress_every))
    pending: list[list[Any]] = []
    batch_iter = _iter_source_work_items(
        structured_dir,
        args.prefix,
        batch_size=max(1, int(args.source_batch_size)),
        batch_bytes=max(1, int(args.source_batch_bytes)),
        max_rows=max(0, int(args.max_rows)),
    )
    with LedgerStoreWriter(tmp_path, duckdb_threads=max(1, int(args.duckdb_threads))) as writer:
        for result in _iter_ledger_batch_results(
            batch_iter,
            workers=max(1, int(args.workers)),
            keep_years=keep_years,
            keep_families=keep_families,
        ):
            source_records += int(result["source_record_count"])
            extracted_rows += int(result["ledger_row_count"])
            pending.extend(result["row_values"])
            while len(pending) >= args.batch_size:
                flush_rows = pending[: args.batch_size]
                writer.append_row_values(flush_rows)
                del pending[: args.batch_size]
            if args.progress_every and source_records >= next_progress:
                print(
                    json.dumps(
                        {
                            "progress": source_records,
                            "ledger_rows_extracted": extracted_rows,
                            "ledger_rows_written": writer.row_count,
                        },
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )
                while source_records >= next_progress:
                    next_progress += max(1, int(args.progress_every))
        if pending:
            writer.append_row_values(pending)
        summary = writer.finalize(
            metadata={
                "structured_dir": str(structured_dir),
                "prefix": args.prefix,
                "source_record_count": source_records,
                "ledger_row_count_extracted": extracted_rows,
                "years": sorted(keep_years),
                "metric_families": sorted(keep_families),
                "workers": max(1, int(args.workers)),
                "source_batch_size": max(1, int(args.source_batch_size)),
                "source_batch_bytes": max(1, int(args.source_batch_bytes)),
                "write_batch_size": max(1, int(args.batch_size)),
                "duckdb_threads": max(1, int(args.duckdb_threads)),
                "elapsed_sec": round(time.perf_counter() - started, 3),
            }
        )
    _replace_duckdb_path(tmp_path, output_path)
    print(
        json.dumps(
            {
                "status": "completed",
                "output_path": str(output_path),
                "source_record_count": source_records,
                "ledger_fact_count": summary["row_count"],
                "elapsed_sec": round(time.perf_counter() - started, 3),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _iter_source_work_items(
    structured_dir: Path,
    prefix: str,
    *,
    batch_size: int,
    batch_bytes: int,
    max_rows: int,
) -> Iterator[dict[str, Any]]:
    if max_rows:
        for batch in _iter_source_record_batches(structured_dir, prefix, batch_size=batch_size, max_rows=max_rows):
            yield {"kind": "records", "records": batch}
        return

    for suffix in ("metrics", "tables"):
        path = structured_dir / f"{prefix}_{suffix}.jsonl"
        file_size = path.stat().st_size
        start = 0
        while start < file_size:
            end = min(file_size, start + batch_bytes)
            yield {"kind": "byte_range", "path": str(path), "start": start, "end": end}
            start = end


def _iter_source_record_batches(
    structured_dir: Path,
    prefix: str,
    *,
    batch_size: int,
    max_rows: int,
) -> Iterator[list[tuple[str, int, str]]]:
    batch: list[tuple[str, int, str]] = []
    emitted = 0
    for suffix in ("metrics", "tables"):
        path = structured_dir / f"{prefix}_{suffix}.jsonl"
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if max_rows and emitted >= max_rows:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                batch.append((str(path), line_number, stripped))
                emitted += 1
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
        if max_rows and emitted >= max_rows:
            break
    if batch:
        yield batch


def _iter_ledger_batch_results(
    batches: Iterator[dict[str, Any]],
    *,
    workers: int,
    keep_years: set[int],
    keep_families: set[str],
) -> Iterator[dict[str, Any]]:
    years = sorted(keep_years)
    families = sorted(keep_families)
    if workers <= 1:
        for batch in batches:
            yield _build_ledger_work_item(batch, years, families)
        return

    max_pending = max(workers * 2, 1)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending: set[Future] = set()

        def submit_next() -> bool:
            try:
                batch = next(batches)
            except StopIteration:
                return False
            pending.add(executor.submit(_build_ledger_work_item, batch, years, families))
            return True

        for _ in range(max_pending):
            if not submit_next():
                break

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                submit_next()


def _build_ledger_work_item(
    item: dict[str, Any],
    keep_years: list[int],
    keep_families: list[str],
) -> dict[str, Any]:
    kind = str(item.get("kind") or "")
    if kind == "records":
        return _build_ledger_batch(item.get("records") or [], keep_years, keep_families)
    if kind == "byte_range":
        return _build_ledger_file_range(
            str(item.get("path") or ""),
            int(item.get("start") or 0),
            int(item.get("end") or 0),
            keep_years,
            keep_families,
        )
    raise ValueError(f"Unsupported ledger work item kind: {kind}")


def _build_ledger_file_range(
    source_path: str,
    start: int,
    end: int,
    keep_years: list[int],
    keep_families: list[str],
) -> dict[str, Any]:
    years = set(keep_years)
    families = set(keep_families)
    row_values: list[list[Any]] = []
    source_record_count = 0
    path = Path(source_path)
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
            source_record_count += 1
            try:
                record = json.loads(stripped.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {source_path}:byte={pos}") from exc
            for row in _filter_rows(_ledger_rows_from_record(record), keep_years=years, keep_families=families):
                row_values.append(normalize_ledger_fact_values(row))
    return {
        "source_record_count": source_record_count,
        "ledger_row_count": len(row_values),
        "row_values": row_values,
    }


def _build_ledger_batch(
    batch: list[tuple[str, int, str]],
    keep_years: list[int],
    keep_families: list[str],
) -> dict[str, Any]:
    years = set(keep_years)
    families = set(keep_families)
    row_values: list[list[Any]] = []
    for source_path, line_number, line in batch:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {source_path}:{line_number}") from exc
        for row in _filter_rows(_ledger_rows_from_record(record), keep_years=years, keep_families=families):
            row_values.append(normalize_ledger_fact_values(row))
    return {
        "source_record_count": len(batch),
        "ledger_row_count": len(row_values),
        "row_values": row_values,
    }


def _ledger_rows_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    object_type = str(record.get("object_type") or "")
    if object_type == "metric":
        row = interactive._ledger_row_from_metric(LEDGER_STORE_CASE_ID, record)
        if not row:
            return []
        return [row, *interactive._ledger_growth_rate_rows_from_metric(LEDGER_STORE_CASE_ID, record, row)]
    if object_type == "table":
        return interactive._ledger_rows_from_table(LEDGER_STORE_CASE_ID, record, set())
    return []


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    keep_years: set[int],
    keep_families: set[str],
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if keep_years:
            try:
                year = int(row.get("fiscal_year"))
            except (TypeError, ValueError):
                continue
            if year not in keep_years:
                continue
        if keep_families and str(row.get("metric_family") or "") not in keep_families:
            continue
        out.append(row)
    return out


def _csv_items(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _remove_duckdb_path(path: Path) -> None:
    for candidate in (path, Path(str(path) + ".wal")):
        if candidate.exists():
            candidate.unlink()


def _replace_duckdb_path(tmp_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    old_wal = Path(str(output_path) + ".wal")
    if old_wal.exists():
        old_wal.unlink()
    previous_path = output_path.with_name(f"{output_path.name}.previous")
    if previous_path.exists():
        previous_path.unlink()
    if output_path.exists():
        output_path.replace(previous_path)
    tmp_path.replace(output_path)
    tmp_wal = Path(str(tmp_path) + ".wal")
    if tmp_wal.exists():
        tmp_wal.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
