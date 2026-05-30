from __future__ import annotations

import json
import pickle
import sys
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterator

from rank_bm25 import BM25Okapi

from evidence.structured_text import structured_object_preview, structured_object_search_text
from retrieval.text import tokenize


def build_object_bm25_index(
    structured_dir: str | Path,
    output_dir: str | Path,
    prefix: str = "sec_tech_10k",
    record_mode: str = "full",
    write_slim_jsonl: bool = True,
    workers: int = 1,
    batch_bytes: int = 32 * 1024 * 1024,
    progress_every: int = 0,
) -> dict[str, Any]:
    structured_path = Path(structured_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    record_mode = str(record_mode or "full").strip().lower()
    if record_mode not in {"full", "compact"}:
        raise ValueError(f"Unsupported record_mode: {record_mode}")

    records_path = output_path / "records.jsonl"
    slim_pkl_path = output_path / "records.slim.pkl"
    slim_jsonl_path = output_path / "records.slim.jsonl"
    bm25_path = output_path / "bm25.pkl"
    tmp_paths = [
        bm25_path.with_suffix(bm25_path.suffix + ".tmp"),
        slim_pkl_path.with_suffix(slim_pkl_path.suffix + ".tmp"),
        slim_jsonl_path.with_suffix(slim_jsonl_path.suffix + ".tmp"),
        records_path.with_suffix(records_path.suffix + ".tmp"),
    ]
    for tmp_path in tmp_paths:
        if tmp_path.exists():
            tmp_path.unlink()

    tokenized_corpus: list[list[str]] = []
    counts: dict[str, int] = {"table": 0, "metric": 0, "claim": 0}
    slim_jsonl_handle = None
    records_handle = None
    record_count = 0
    try:
        if write_slim_jsonl:
            slim_jsonl_handle = slim_jsonl_path.with_suffix(slim_jsonl_path.suffix + ".tmp").open("w", encoding="utf-8")
        if record_mode == "full":
            records_handle = records_path.with_suffix(records_path.suffix + ".tmp").open("w", encoding="utf-8")
        with slim_pkl_path.with_suffix(slim_pkl_path.suffix + ".tmp").open("wb") as slim_pickle:
            work_items = _iter_structured_work_items(structured_path, prefix, batch_bytes=max(1, int(batch_bytes)))
            for result in _iter_object_batch_results(
                work_items,
                workers=max(1, int(workers)),
                include_full_records=record_mode == "full",
            ):
                tokenized_corpus.extend(result["tokenized_corpus"])
                for key, value in result["object_counts"].items():
                    counts[key] = counts.get(key, 0) + int(value)
                for compact in result["compact_records"]:
                    pickle.dump(compact, slim_pickle, protocol=pickle.HIGHEST_PROTOCOL)
                    if slim_jsonl_handle is not None:
                        slim_jsonl_handle.write(json.dumps(compact, ensure_ascii=False))
                        slim_jsonl_handle.write("\n")
                if records_handle is not None:
                    for line in result["record_lines"]:
                        records_handle.write(line)
                        records_handle.write("\n")
                record_count += int(result["record_count"])
                if progress_every and record_count >= progress_every and record_count % progress_every < int(result["record_count"]):
                    print(json.dumps({"progress": record_count, "object_counts": counts}, ensure_ascii=False), file=sys.stderr)
    finally:
        if slim_jsonl_handle is not None:
            slim_jsonl_handle.close()
        if records_handle is not None:
            records_handle.close()

    bm25 = BM25Okapi(tokenized_corpus)

    with bm25_path.with_suffix(bm25_path.suffix + ".tmp").open("wb") as f:
        pickle.dump(bm25, f)
    bm25_path.with_suffix(bm25_path.suffix + ".tmp").replace(bm25_path)
    slim_pkl_path.with_suffix(slim_pkl_path.suffix + ".tmp").replace(slim_pkl_path)
    if write_slim_jsonl:
        slim_jsonl_path.with_suffix(slim_jsonl_path.suffix + ".tmp").replace(slim_jsonl_path)
    else:
        stale_slim_jsonl = output_path / "records.slim.jsonl"
        if stale_slim_jsonl.exists():
            stale_slim_jsonl.unlink()
    if record_mode == "full":
        records_path.with_suffix(records_path.suffix + ".tmp").replace(records_path)

    if record_mode == "compact":
        stale_full_records = output_path / "records.jsonl"
        if stale_full_records.exists():
            stale_full_records.unlink()

    record_files = ["records.slim.pkl"]
    if write_slim_jsonl:
        record_files.append("records.slim.jsonl")
    if record_mode == "full":
        record_files.insert(0, "records.jsonl")

    metadata = {
        "structured_dir": str(structured_path),
        "prefix": prefix,
        "records": record_count,
        "object_counts": counts,
        "index_type": "rank_bm25",
        "record_mode": record_mode,
        "record_files": record_files,
        "workers": max(1, int(workers)),
        "batch_bytes": max(1, int(batch_bytes)),
    }
    (output_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata


def _iter_structured_work_items(structured_path: Path, prefix: str, *, batch_bytes: int) -> Iterator[dict[str, Any]]:
    for suffix in ("tables", "metrics", "claims"):
        path = structured_path / f"{prefix}_{suffix}.jsonl"
        file_size = path.stat().st_size
        start = 0
        while start < file_size:
            end = min(file_size, start + batch_bytes)
            yield {"path": str(path), "start": start, "end": end}
            start = end


def _iter_object_batch_results(
    work_items: Iterator[dict[str, Any]],
    *,
    workers: int,
    include_full_records: bool,
) -> Iterator[dict[str, Any]]:
    if workers <= 1:
        for item in work_items:
            yield _build_object_batch_from_range(item, include_full_records)
        return

    max_pending = max(workers * 2, 1)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending: set[Future] = set()

        def submit_next() -> bool:
            try:
                item = next(work_items)
            except StopIteration:
                return False
            pending.add(executor.submit(_build_object_batch_from_range, item, include_full_records))
            return True

        for _ in range(max_pending):
            if not submit_next():
                break

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                submit_next()


def _build_object_batch_from_range(item: dict[str, Any], include_full_records: bool) -> dict[str, Any]:
    path = Path(str(item.get("path") or ""))
    start = int(item.get("start") or 0)
    end = int(item.get("end") or 0)
    compact_records: list[dict[str, Any]] = []
    record_lines: list[str] = []
    tokenized_corpus: list[list[str]] = []
    counts: dict[str, int] = {"table": 0, "metric": 0, "claim": 0}
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
            object_type = record.get("object_type")
            if object_type in counts:
                counts[object_type] += 1
            tokenized_corpus.append(tokenize(structured_object_search_text(record)))
            compact_records.append(compact_structured_object_record(record))
            if include_full_records:
                record_lines.append(json.dumps(record, ensure_ascii=False))
    return {
        "record_count": len(tokenized_corpus),
        "object_counts": counts,
        "tokenized_corpus": tokenized_corpus,
        "compact_records": compact_records,
        "record_lines": record_lines,
    }


def compact_structured_object_record(record: dict[str, Any]) -> dict[str, Any]:
    object_type = str(record.get("object_type") or "")
    compact: dict[str, Any] = {
        "object_id": record.get("object_id"),
        "object_type": object_type,
        "source_evidence_id": record.get("source_evidence_id"),
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "section": record.get("section"),
        "subsection": record.get("subsection"),
        "source_type": record.get("source_type"),
        "form_type": record.get("form_type"),
        "source_tier": record.get("source_tier"),
        "period_end": record.get("period_end"),
        "period_type": record.get("period_type"),
        "duration_months": record.get("duration_months"),
        "fiscal_period": record.get("fiscal_period"),
        "metadata": _compact_metadata(record.get("metadata")),
        "preview": structured_object_preview(record),
    }
    if object_type == "metric":
        _copy_present(
            compact,
            record,
            (
                "metric_name",
                "raw_value",
                "value",
                "unit",
                "period",
                "period_role",
                "segment",
                "row_label",
                "column_label",
                "extraction_method",
                "metric_family",
            ),
        )
    elif object_type == "table":
        _copy_present(
            compact,
            record,
            (
                "table_id",
                "title",
                "candidate_periods",
            ),
        )
        if record.get("text_before"):
            compact["text_before"] = _truncate_text(record.get("text_before"), 400)
        if record.get("text_after"):
            compact["text_after"] = _truncate_text(record.get("text_after"), 400)
        periods = sorted(
            {
                str(cell.get("period") or "")
                for cell in record.get("cells") or []
                if str(cell.get("period") or "")
            }
        )
        if periods:
            compact["periods"] = periods
    elif object_type == "claim":
        _copy_present(
            compact,
            record,
            (
                "claim_text",
                "claim_type",
                "polarity",
                "entities",
                "metrics_mentioned",
                "extraction_method",
            ),
        )
    return {key: value for key, value in compact.items() if value not in (None, "", [], {})}


def _copy_present(target: dict[str, Any], source: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        value = source.get(key)
        if value not in (None, "", [], {}):
            target[key] = value


def _compact_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    keep = {
        "form_type",
        "source_type",
        "source_tier",
        "period_end",
        "period_type",
        "duration_months",
        "fiscal_period",
    }
    return {key: value.get(key) for key in keep if value.get(key) not in (None, "", [], {})}


def _truncate_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    rows.extend(_iter_jsonl(path))
    return rows


def _iter_structured_records(structured_path: Path, prefix: str):
    for suffix in ("tables", "metrics", "claims"):
        path = structured_path / f"{prefix}_{suffix}.jsonl"
        yield from _iter_jsonl(path)


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
