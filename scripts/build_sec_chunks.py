from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from connectors import read_sec_filing_manifest_jsonl  # noqa: E402
from ingestion import build_chunks_for_filing, write_chunks_jsonl  # noqa: E402


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
        default="1,1A,7,7A,8",
        help="Comma-separated 10-K item codes to emit.",
    )
    parser.add_argument("--target-words", type=int, default=900)
    parser.add_argument("--overlap-words", type=int, default=150)
    parser.add_argument("--min-words", type=int, default=80)
    parser.add_argument("--limit", type=int, help="Optional max filings to parse.")
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

    all_chunks = []
    per_filing_summary = []
    for record in records:
        chunks = build_chunks_for_filing(
            record,
            output_items=output_items,
            target_words=args.target_words,
            overlap_words=args.overlap_words,
            min_words=args.min_words,
        )
        all_chunks.extend(chunks)

        section_counts = Counter(chunk.item_code for chunk in chunks)
        block_ids = {chunk.block_id for chunk in chunks}
        split_block_ids = {
            chunk.block_id for chunk in chunks if chunk.block_part_count > 1
        }
        per_filing_summary.append(
            {
                "ticker": record.ticker,
                "fiscal_year": record.fiscal_year,
                "chunks": len(chunks),
                "blocks": len(block_ids),
                "split_blocks": len(split_block_ids),
                "sections": dict(sorted(section_counts.items())),
            }
        )

    write_chunks_jsonl(all_chunks, REPO_ROOT / args.output)

    aggregate = defaultdict(int)
    for chunk in all_chunks:
        aggregate[chunk.item_code] += 1

    block_ids = {chunk.block_id for chunk in all_chunks}
    split_block_ids = {
        chunk.block_id for chunk in all_chunks if chunk.block_part_count > 1
    }

    summary = {
        "input_records": len(records),
        "output": str(REPO_ROOT / args.output),
        "chunks": len(all_chunks),
        "blocks": len(block_ids),
        "split_blocks": len(split_block_ids),
        "section_chunk_counts": dict(sorted(aggregate.items())),
        "filings": per_filing_summary,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
