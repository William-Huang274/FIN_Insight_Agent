from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from connectors import (  # noqa: E402
    collect_sec_filing_manifest,
    write_sec_filing_manifest_jsonl,
)


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
        description="Build a JSONL manifest from cached SEC filing metadata."
    )
    parser.add_argument(
        "--config",
        default="configs/sec_tech_universe.yaml",
        help="Optional universe config used as default years/tickers/categories.",
    )
    parser.add_argument(
        "--root",
        default="data/raw_private/sec",
        help="SEC raw cache root.",
    )
    parser.add_argument(
        "--output",
        default="data/processed_private/manifests/sec_tech_10k_manifest.jsonl",
        help="Output manifest JSONL path.",
    )
    parser.add_argument("--years", help="Optional comma-separated fiscal years.")
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter.")
    parser.add_argument(
        "--categories",
        help="Optional comma-separated category_slug filter.",
    )
    parser.add_argument(
        "--form-types",
        help="Comma-separated form type filter. Defaults to config form_types/form_type.",
    )
    parser.add_argument(
        "--allow-missing-html",
        action="store_true",
        help="Include metadata records even if the corresponding HTML is missing.",
    )
    return parser.parse_args()


def load_config_defaults(path: Path | None) -> dict[str, list[str] | list[int]]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    companies = config.get("companies", [])
    return {
        "years": [int(year) for year in config.get("years", [])],
        "tickers": [company["ticker"].upper() for company in companies],
        "categories": [company["category_slug"] for company in companies],
        "form_types": _config_form_types(config),
    }


def _config_form_types(config: dict) -> list[str]:
    configured = config.get("form_types")
    if isinstance(configured, list):
        values = [str(value).strip().upper() for value in configured if str(value).strip()]
        if values:
            return values
    form_type = str(config.get("form_type") or "10-K").strip().upper()
    return [form_type]


def main() -> None:
    args = parse_args()
    config_defaults = load_config_defaults(REPO_ROOT / args.config if args.config else None)
    years = parse_years(args.years) or config_defaults.get("years")
    tickers = parse_csv(args.tickers, upper=True) or config_defaults.get("tickers")
    categories = parse_csv(args.categories) or config_defaults.get("categories")
    form_types = parse_csv(args.form_types, upper=True) or config_defaults.get("form_types")

    records = collect_sec_filing_manifest(
        root=REPO_ROOT / args.root,
        years=years,
        tickers=tickers,
        categories=categories,
        form_types=form_types,
        require_html=not args.allow_missing_html,
    )
    records_before_dedupe = len(records)
    records = _dedupe_manifest_records(records)
    output_path = REPO_ROOT / args.output
    write_sec_filing_manifest_jsonl(records, output_path)

    summary = {
        "output": str(output_path),
        "records": len(records),
        "records_before_dedupe": records_before_dedupe,
        "duplicates_removed": records_before_dedupe - len(records),
        "years": sorted({record.fiscal_year for record in records}),
        "tickers": sorted({record.ticker for record in records}),
        "categories": sorted({record.category_slug for record in records}),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _dedupe_manifest_records(records):
    best_by_key = {}
    for record in records:
        key = (
            record.ticker.upper(),
            str(record.form_type or record.source_type or "").upper(),
            int(record.fiscal_year),
            record.accession_number or record.primary_document or record.filing_url or record.html_path,
        )
        current = best_by_key.get(key)
        if current is None or _record_preference(record) > _record_preference(current):
            best_by_key[key] = record
    return sorted(
        best_by_key.values(),
        key=lambda record: (
            record.ticker.upper(),
            int(record.fiscal_year),
            str(record.form_type or record.source_type or "").upper(),
            str(record.fiscal_period or ""),
            str(record.period_end or ""),
        ),
    )


def _record_preference(record) -> tuple[int, int, str]:
    cache_year = _cache_directory_year(record.html_path)
    return (
        1 if cache_year == int(record.fiscal_year) else 0,
        1 if record.fiscal_year_source == "document_fiscal_year_focus" else 0,
        str(record.html_path or ""),
    )


def _cache_directory_year(path: str | Path | None) -> int | None:
    if not path:
        return None
    for part in reversed(Path(path).parts):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


if __name__ == "__main__":
    main()
