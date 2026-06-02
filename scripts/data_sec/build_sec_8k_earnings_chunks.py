from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from connectors import read_sec_filing_manifest_jsonl  # noqa: E402
from ingestion import build_8k_earnings_chunks, write_chunks_jsonl  # noqa: E402


def parse_csv(raw: str | None, upper: bool = False) -> list[str] | None:
    if not raw:
        return None
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return [value.upper() for value in values] if upper else values


def parse_years(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse cached SEC 8-K earnings-release exhibits into source-bounded chunks."
    )
    parser.add_argument(
        "--manifest",
        default="data/processed_private/manifests/sec_tech_8k_earnings_pilot_manifest_2026_2027.jsonl",
        help="Input 8-K earnings manifest JSONL.",
    )
    parser.add_argument(
        "--output",
        default="data/processed_private/chunks/sec_tech_8k_earnings_pilot_chunks_2026_2027.jsonl",
        help="Output chunks JSONL.",
    )
    parser.add_argument("--years", help="Optional comma-separated filing/fiscal years.")
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter.")
    parser.add_argument("--target-words", type=int, default=650)
    parser.add_argument("--overlap-words", type=int, default=100)
    parser.add_argument("--min-words", type=int, default=40)
    parser.add_argument("--limit", type=int, help="Optional max filings to parse.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    year_filter = set(parse_years(args.years) or [])
    ticker_filter = set(parse_csv(args.tickers, upper=True) or [])
    records = [
        record
        for record in read_sec_filing_manifest_jsonl(REPO_ROOT / args.manifest)
        if str(record.form_type or record.source_type or "").upper() == "8-K"
        and record.source_tier == "company_authored_unaudited_sec_filing"
        and (not year_filter or int(record.fiscal_year) in year_filter)
        and (not ticker_filter or record.ticker.upper() in ticker_filter)
    ]
    if args.limit is not None:
        records = records[: args.limit]

    chunks = []
    per_filing_summary = []
    for record in records:
        filing_chunks = build_8k_earnings_chunks(
            record,
            target_words=args.target_words,
            overlap_words=args.overlap_words,
            min_words=args.min_words,
        )
        chunks.extend(filing_chunks)
        per_filing_summary.append(
            {
                "ticker": record.ticker,
                "fiscal_year": record.fiscal_year,
                "filing_date": record.filing_date,
                "accession_number": record.accession_number,
                "exhibit_document": record.metadata.get("exhibit_document"),
                "chunks": len(filing_chunks),
                "block_types": dict(sorted(Counter(chunk.block_type for chunk in filing_chunks).items())),
            }
        )

    output_path = REPO_ROOT / args.output
    write_chunks_jsonl(chunks, output_path)
    summary = {
        "input_records": len(records),
        "output": str(output_path),
        "chunks": len(chunks),
        "tickers": sorted({chunk.ticker for chunk in chunks}),
        "years": sorted({chunk.fiscal_year for chunk in chunks}),
        "source_tier_counts": dict(sorted(Counter(chunk.source_tier for chunk in chunks).items())),
        "block_type_counts": dict(sorted(Counter(chunk.block_type for chunk in chunks).items())),
        "filings": per_filing_summary,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
