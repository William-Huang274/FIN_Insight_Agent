from __future__ import annotations

import argparse
import json
import re
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
    parser.add_argument(
        "--gap-output",
        default="data/processed_private/source_gaps/sec_tech_8k_earnings_pilot_manifest_gaps_2026_2027.jsonl",
        help="Output structured manifest-stage source gap JSONL.",
    )
    return parser.parse_args()


def load_config_defaults(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    companies = config.get("companies", [])
    years = [int(year) for year in config.get("years", [])]
    expected_scope = [
        {
            "ticker": str(company["ticker"]).upper(),
            "category": str(company.get("category") or company.get("category_slug") or "uncategorized"),
            "category_slug": str(company.get("category_slug") or company.get("category") or "uncategorized"),
            "year": int(year),
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
        }
        for year in years
        for company in companies
        if company.get("ticker")
    ]
    return {
        "years": years,
        "tickers": [str(company["ticker"]).upper() for company in companies],
        "categories": [str(company["category_slug"]) for company in companies],
        "expected_scope": expected_scope,
    }


def collect_8k_earnings_manifest(
    root: str | Path,
    *,
    years: Iterable[int] | None = None,
    tickers: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    require_html: bool = True,
) -> list[SecFilingManifestRecord]:
    records, _ = collect_8k_earnings_manifest_with_gaps(
        root,
        years=years,
        tickers=tickers,
        categories=categories,
        require_html=require_html,
    )
    return records


def collect_8k_earnings_manifest_with_gaps(
    root: str | Path,
    *,
    years: Iterable[int] | None = None,
    tickers: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    require_html: bool = True,
    expected_scope: Iterable[dict[str, Any]] | None = None,
) -> tuple[list[SecFilingManifestRecord], list[dict[str, Any]]]:
    root_path = Path(root)
    year_filter = {int(year) for year in years or []}
    ticker_filter = {str(ticker).upper() for ticker in tickers or []}
    category_filter = {str(category) for category in categories or []}
    records: list[SecFilingManifestRecord] = []
    gaps: list[dict[str, Any]] = []
    if not root_path.exists():
        return records, _expected_scope_gaps(
            expected_scope,
            records,
            gaps,
            fallback_reason="no_8k_earnings_cache_root",
        )
    for metadata_path in sorted(root_path.glob("*/*/*/*/metadata.json")):
        metadata = _read_json(metadata_path)
        year = _int_or_none(metadata.get("filing_year") or metadata.get("fiscal_year"))
        ticker = str(metadata.get("ticker") or "").upper().strip()
        category_slug = str(metadata.get("category_slug") or "").strip()
        if year is None or not ticker or not category_slug:
            gaps.append(_gap_from_metadata(metadata_path, metadata, "invalid_8k_earnings_metadata_identity"))
            continue
        if year_filter and year not in year_filter:
            continue
        if ticker_filter and ticker not in ticker_filter:
            continue
        if category_filter and category_slug not in category_filter:
            continue
        if not _filing_items_include_earnings_release(metadata.get("filing_items")):
            gaps.append(_gap_from_metadata(metadata_path, metadata, "cached_8k_missing_item_2_02"))
            continue
        html_path = Path(str(metadata.get("local_html_path") or metadata.get("local_exhibit_path") or ""))
        if not html_path.is_absolute():
            html_path = (metadata_path.parent / html_path).resolve()
        if require_html and not html_path.exists():
            gap = _gap_from_metadata(metadata_path, metadata, "selected_8k_exhibit_html_missing")
            gap["html_path"] = str(html_path)
            gaps.append(gap)
            continue
        records.append(_record_from_metadata(year, ticker, category_slug, html_path, metadata_path, metadata))
    deduped = _dedupe_records(records)
    gaps = _dedupe_gaps(
        _expected_scope_gaps(
            expected_scope,
            deduped,
            gaps,
            fallback_reason="no_cached_8k_earnings_metadata",
        )
    )
    return deduped, gaps


def main() -> None:
    args = parse_args()
    config_defaults = load_config_defaults(REPO_ROOT / args.config if args.config else None)
    years = parse_years(args.years) or config_defaults.get("years")
    tickers = parse_csv(args.tickers, upper=True) or config_defaults.get("tickers")
    categories = parse_csv(args.categories) or config_defaults.get("categories")
    records, gaps = collect_8k_earnings_manifest_with_gaps(
        REPO_ROOT / args.root,
        years=years,
        tickers=tickers,
        categories=categories,
        require_html=not args.allow_missing_html,
        expected_scope=config_defaults.get("expected_scope") or [],
    )
    output_path = REPO_ROOT / args.output
    write_sec_filing_manifest_jsonl(records, output_path)
    if args.gap_output:
        write_jsonl(gaps, REPO_ROOT / args.gap_output)
    summary = {
        "output": str(output_path),
        "records": len(records),
        "gap_output": str(REPO_ROOT / args.gap_output) if args.gap_output else "",
        "gaps": len(gaps),
        "years": sorted({record.fiscal_year for record in records}),
        "tickers": sorted({record.ticker for record in records}),
        "categories": sorted({record.category_slug for record in records}),
        "source_tiers": sorted({record.source_tier for record in records}),
        "gap_reasons": sorted({str(gap.get("reason_code") or "") for gap in gaps}),
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


def _gap_from_metadata(metadata_path: Path, metadata: dict[str, Any], reason_code: str) -> dict[str, Any]:
    year = _int_or_none(metadata.get("filing_year") or metadata.get("fiscal_year"))
    ticker = str(metadata.get("ticker") or "").upper().strip()
    category_slug = str(metadata.get("category_slug") or "").strip()
    return {
        "schema_version": "sec_8k_earnings_source_gap_v0.1",
        "source": "build_sec_8k_earnings_manifest",
        "status": "missing",
        "ticker": ticker,
        "year": year,
        "filing_year": year,
        "form_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "category": metadata.get("category") or category_slug,
        "category_slug": category_slug,
        "reason_code": reason_code,
        "reason": reason_code,
        "metadata_path": str(metadata_path),
        "accession_number": metadata.get("accession_number"),
        "filing_date": metadata.get("filing_date"),
        "filing_items": metadata.get("filing_items"),
        "exhibit_document": metadata.get("exhibit_document"),
    }


def _expected_scope_gaps(
    expected_scope: Iterable[dict[str, Any]] | None,
    records: list[SecFilingManifestRecord],
    gaps: list[dict[str, Any]],
    *,
    fallback_reason: str,
) -> list[dict[str, Any]]:
    out = list(gaps)
    covered = {
        (record.ticker.upper(), int(record.fiscal_year), record.category_slug)
        for record in records
    }
    existing_gap_keys = {
        (
            str(gap.get("ticker") or "").upper(),
            _int_or_none(gap.get("year") or gap.get("filing_year")),
            str(gap.get("category_slug") or ""),
        )
        for gap in gaps
    }
    for item in expected_scope or []:
        ticker = str(item.get("ticker") or "").upper().strip()
        year = _int_or_none(item.get("year") or item.get("filing_year"))
        category_slug = str(item.get("category_slug") or "").strip()
        if not ticker or year is None:
            continue
        key = (ticker, int(year), category_slug)
        if key in covered or key in existing_gap_keys:
            continue
        out.append(
            {
                "schema_version": "sec_8k_earnings_source_gap_v0.1",
                "source": "build_sec_8k_earnings_manifest",
                "status": "missing",
                "ticker": ticker,
                "year": int(year),
                "filing_year": int(year),
                "form_type": "8-K",
                "source_tier": str(item.get("source_tier") or "company_authored_unaudited_sec_filing"),
                "category": item.get("category") or category_slug,
                "category_slug": category_slug,
                "reason_code": fallback_reason,
                "reason": fallback_reason,
            }
        )
    return out


def _dedupe_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, int | None, str, str], dict[str, Any]] = {}
    for gap in gaps:
        key = (
            str(gap.get("ticker") or "").upper(),
            _int_or_none(gap.get("year") or gap.get("filing_year")),
            str(gap.get("category_slug") or ""),
            str(gap.get("reason_code") or gap.get("reason") or ""),
        )
        best_by_key.setdefault(key, gap)
    return sorted(
        best_by_key.values(),
        key=lambda gap: (
            str(gap.get("ticker") or "").upper(),
            int(gap.get("year") or gap.get("filing_year") or 0),
            str(gap.get("reason_code") or ""),
        ),
    )


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


def _filing_items_include_earnings_release(value: Any) -> bool:
    normalized = re.sub(r"\s+", "", str(value or "").lower())
    return "2.02" in normalized or "item2.02" in normalized


if __name__ == "__main__":
    main()
