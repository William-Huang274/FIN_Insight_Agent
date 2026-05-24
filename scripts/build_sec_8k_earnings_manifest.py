from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from connectors import SecFilingManifestRecord, write_sec_filing_manifest_jsonl  # noqa: E402


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
        description="Build a manifest from cached SEC 8-K earnings-release metadata."
    )
    parser.add_argument(
        "--config",
        default="configs/sec_tech_8k_earnings_pilot_2026_2027.yaml",
        help="Optional pilot config used as default years/tickers/categories.",
    )
    parser.add_argument(
        "--root",
        default="data/raw_private/sec_8k_earnings",
        help="SEC 8-K earnings-release raw cache root.",
    )
    parser.add_argument(
        "--output",
        default="data/processed_private/manifests/sec_tech_8k_earnings_pilot_manifest_2026_2027.jsonl",
        help="Output manifest JSONL path.",
    )
    parser.add_argument("--years", help="Optional comma-separated filing-year filter.")
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter.")
    parser.add_argument("--categories", help="Optional comma-separated category_slug filter.")
    parser.add_argument(
        "--allow-missing-html",
        action="store_true",
        help="Include metadata records even if the selected exhibit HTML is missing.",
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
        "tickers": [str(company["ticker"]).upper() for company in companies],
        "categories": [str(company["category_slug"]) for company in companies],
    }


def collect_8k_earnings_manifest(
    root: str | Path,
    *,
    years: Iterable[int] | None = None,
    tickers: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    require_html: bool = True,
) -> list[SecFilingManifestRecord]:
    root_path = Path(root)
    year_filter = {int(year) for year in years or []}
    ticker_filter = {str(ticker).upper() for ticker in tickers or []}
    category_filter = {str(category) for category in categories or []}
    records: list[SecFilingManifestRecord] = []
    if not root_path.exists():
        return records
    for metadata_path in sorted(root_path.glob("*/*/*/*/metadata.json")):
        metadata = _read_json(metadata_path)
        year = _int_or_none(metadata.get("filing_year") or metadata.get("fiscal_year"))
        ticker = str(metadata.get("ticker") or "").upper().strip()
        category_slug = str(metadata.get("category_slug") or "").strip()
        if year is None or not ticker or not category_slug:
            continue
        if year_filter and year not in year_filter:
            continue
        if ticker_filter and ticker not in ticker_filter:
            continue
        if category_filter and category_slug not in category_filter:
            continue
        html_path = Path(str(metadata.get("local_html_path") or metadata.get("local_exhibit_path") or ""))
        if not html_path.is_absolute():
            html_path = (metadata_path.parent / html_path).resolve()
        if require_html and not html_path.exists():
            continue
        records.append(_record_from_metadata(year, ticker, category_slug, html_path, metadata_path, metadata))
    return _dedupe_records(records)


def main() -> None:
    args = parse_args()
    config_defaults = load_config_defaults(REPO_ROOT / args.config if args.config else None)
    years = parse_years(args.years) or config_defaults.get("years")
    tickers = parse_csv(args.tickers, upper=True) or config_defaults.get("tickers")
    categories = parse_csv(args.categories) or config_defaults.get("categories")
    records = collect_8k_earnings_manifest(
        REPO_ROOT / args.root,
        years=years,
        tickers=tickers,
        categories=categories,
        require_html=not args.allow_missing_html,
    )
    output_path = REPO_ROOT / args.output
    write_sec_filing_manifest_jsonl(records, output_path)
    summary = {
        "output": str(output_path),
        "records": len(records),
        "years": sorted({record.fiscal_year for record in records}),
        "tickers": sorted({record.ticker for record in records}),
        "categories": sorted({record.category_slug for record in records}),
        "source_tiers": sorted({record.source_tier for record in records}),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _record_from_metadata(
    year: int,
    ticker: str,
    category_slug: str,
    html_path: Path,
    metadata_path: Path,
    metadata: dict[str, Any],
) -> SecFilingManifestRecord:
    return SecFilingManifestRecord(
        ticker=ticker,
        company=metadata.get("company"),
        cik=metadata.get("cik"),
        fiscal_year=int(metadata.get("fiscal_year") or year),
        fiscal_year_source=metadata.get("fiscal_year_source") or "filing_year",
        category=metadata.get("category") or category_slug,
        category_slug=category_slug,
        form_type="8-K",
        source_type="8-K",
        source_tier=metadata.get("source_tier") or "company_authored_unaudited_sec_filing",
        filing_date=metadata.get("filing_date"),
        report_date=metadata.get("report_date"),
        period_end=metadata.get("period_end") or metadata.get("filing_date"),
        period_type=metadata.get("period_type") or "current_report",
        duration_months=metadata.get("duration_months"),
        fiscal_period=metadata.get("fiscal_period"),
        fiscal_period_source=metadata.get("fiscal_period_source") or "not_applicable",
        accession_number=metadata.get("accession_number"),
        primary_document=metadata.get("primary_document"),
        document_description=metadata.get("document_description"),
        filing_url=metadata.get("filing_url"),
        html_path=str(html_path),
        metadata_path=str(metadata_path),
        cache_layout=metadata.get("cache_layout") or "filing_year/category/ticker/accession",
        metadata=metadata,
    )


def _dedupe_records(records: list[SecFilingManifestRecord]) -> list[SecFilingManifestRecord]:
    best_by_key: dict[tuple[str, int, str, str], SecFilingManifestRecord] = {}
    for record in records:
        key = (
            record.ticker.upper(),
            int(record.fiscal_year),
            str(record.accession_number or ""),
            str(record.metadata.get("exhibit_document") or record.html_path),
        )
        current = best_by_key.get(key)
        if current is None or str(record.filing_date or "") > str(current.filing_date or ""):
            best_by_key[key] = record
    return sorted(
        best_by_key.values(),
        key=lambda record: (record.ticker.upper(), int(record.fiscal_year), str(record.filing_date or "")),
    )


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


if __name__ == "__main__":
    main()
