from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from connectors import SecFilingManifestRecord, read_sec_filing_manifest_jsonl  # noqa: E402
from ingestion import build_chunks_for_filing  # noqa: E402


def parse_csv(raw: str | None, upper: bool = False) -> list[str] | None:
    if not raw:
        return None
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if upper:
        values = [value.upper() for value in values]
    return values


def parse_years(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse cached SEC HTML filings into section-aware chunks."
    )
    parser.add_argument(
        "--manifest",
        default="data/processed_private/manifests/sec_tech_10k_manifest.jsonl",
        help="Input SEC filing manifest JSONL.",
    )
    parser.add_argument(
        "--output",
        default="data/processed_private/chunks/sec_tech_10k_chunks.jsonl",
        help="Output chunks JSONL.",
    )
    parser.add_argument("--years", help="Optional comma-separated fiscal years.")
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter.")
    parser.add_argument(
        "--items",
        help="Comma-separated item codes to emit. Defaults are form-specific.",
    )
    parser.add_argument("--target-words", type=int, default=900)
    parser.add_argument("--overlap-words", type=int, default=150)
    parser.add_argument("--min-words", type=int, default=80)
    parser.add_argument("--limit", type=int, help="Optional max filings to parse.")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for filing-level parsing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    year_filter = set(parse_years(args.years) or [])
    ticker_filter = set(parse_csv(args.tickers, upper=True) or [])
    output_items = parse_csv(args.items, upper=True)

    manifest = read_sec_filing_manifest_jsonl(REPO_ROOT / args.manifest)
    records = [
        record
        for record in manifest
        if (not year_filter or record.fiscal_year in year_filter)
        and (not ticker_filter or record.ticker in ticker_filter)
    ]
    if args.limit is not None:
        records = records[: args.limit]

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_output_path = output_path.with_suffix(output_path.suffix + ".tmp")

    per_filing_summary = []

    aggregate = defaultdict(int)
    form_counts = Counter()
    block_ids = set()
    split_block_ids = set()
    table_block_ids = set()
    chunk_count = 0

    worker_count = max(1, int(args.workers or 1))
    work_items = [
        (
            record.model_dump(mode="json"),
            output_items,
            args.target_words,
            args.overlap_words,
            args.min_words,
        )
        for record in records
    ]
    results = (
        map(_build_chunk_lines_for_record, work_items)
        if worker_count == 1
        else _parallel_chunk_results(work_items, worker_count)
    )

    with tmp_output_path.open("w", encoding="utf-8") as f:
        for result in results:
            for line in result["lines"]:
                f.write(line)
                f.write("\n")
            per_filing_summary.append(result["summary"])
            chunk_count += int(result["summary"]["chunks"])
            for item_code, count in result["section_counts"].items():
                aggregate[item_code] += int(count)
            for form_type, count in result["form_counts"].items():
                form_counts[form_type] += int(count)
            block_ids.update(result["block_ids"])
            split_block_ids.update(result["split_block_ids"])
            table_block_ids.update(result["table_block_ids"])
    tmp_output_path.replace(output_path)

    summary = {
        "input_records": len(records),
        "output": str(output_path),
        "chunks": chunk_count,
        "blocks": len(block_ids),
        "split_blocks": len(split_block_ids),
        "table_blocks": len(table_block_ids),
        "section_chunk_counts": dict(sorted(aggregate.items())),
        "form_chunk_counts": dict(sorted(form_counts.items())),
        "filings": per_filing_summary,
        "workers": worker_count,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _parallel_chunk_results(
    work_items: list[tuple[dict[str, Any], list[str] | None, int, int, int]],
    worker_count: int,
):
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        yield from executor.map(_build_chunk_lines_for_record, work_items, chunksize=1)


def _build_chunk_lines_for_record(
    work_item: tuple[dict[str, Any], list[str] | None, int, int, int]
) -> dict[str, Any]:
    record_payload, output_items, target_words, overlap_words, min_words = work_item
    record = SecFilingManifestRecord.model_validate(record_payload)
    chunks = build_chunks_for_filing(
        record,
        output_items=output_items,
        target_words=target_words,
        overlap_words=overlap_words,
        min_words=min_words,
    )
    section_counts = Counter(chunk.item_code for chunk in chunks)
    form_counts = Counter(chunk.form_type for chunk in chunks)
    block_ids = {chunk.block_id for chunk in chunks}
    split_block_ids = {chunk.block_id for chunk in chunks if chunk.block_part_count > 1}
    table_block_ids = {chunk.block_id for chunk in chunks if chunk.contains_table}
    return {
        "lines": [chunk.to_jsonl_line() for chunk in chunks],
        "summary": {
            "ticker": record.ticker,
            "fiscal_year": record.fiscal_year,
            "form_type": record.form_type,
            "period_end": record.period_end,
            "period_type": record.period_type,
            "fiscal_period": record.fiscal_period,
            "chunks": len(chunks),
            "blocks": len(block_ids),
            "split_blocks": len(split_block_ids),
            "table_blocks": len(table_block_ids),
            "sections": dict(sorted(section_counts.items())),
        },
        "section_counts": dict(section_counts),
        "form_counts": dict(form_counts),
        "block_ids": list(block_ids),
        "split_block_ids": list(split_block_ids),
        "table_block_ids": list(table_block_ids),
    }


if __name__ == "__main__":
    main()
