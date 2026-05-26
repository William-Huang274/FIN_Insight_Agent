from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from connectors import (  # noqa: E402
    SecFilingManifestRecord,
    read_sec_filing_manifest_jsonl,
    write_sec_filing_manifest_jsonl,
)


PERIOD_RANK = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compose a fiscal-year-aware mixed SEC manifest from annual 10-K filings "
            "plus each ticker's latest available 10-Q after its latest selected 10-K."
        )
    )
    parser.add_argument(
        "--annual-manifest",
        required=True,
        help="Input annual 10-K manifest JSONL.",
    )
    parser.add_argument(
        "--interim-manifest",
        required=True,
        help="Input interim 10-Q manifest JSONL.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output mixed manifest JSONL.",
    )
    parser.add_argument(
        "--annual-years",
        required=True,
        help="Comma-separated fiscal years to include from the annual manifest.",
    )
    parser.add_argument(
        "--summary-output",
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    return parser.parse_args()


def parse_years(raw: str) -> set[int]:
    years = {int(value.strip()) for value in raw.split(",") if value.strip()}
    if not years:
        raise ValueError("--annual-years must include at least one fiscal year")
    return years


def select_mixed_records(
    annual_records: list[SecFilingManifestRecord],
    interim_records: list[SecFilingManifestRecord],
    annual_years: set[int],
) -> tuple[list[SecFilingManifestRecord], dict[str, Any]]:
    annual_selected = [
        record
        for record in annual_records
        if _form_type(record) == "10-K" and int(record.fiscal_year) in annual_years
    ]
    annual_selected.sort(key=_record_sort_key)

    latest_annual_by_ticker: dict[str, SecFilingManifestRecord] = {}
    for record in annual_selected:
        ticker = record.ticker.upper()
        current = latest_annual_by_ticker.get(ticker)
        if current is None or _record_sort_key(record) > _record_sort_key(current):
            latest_annual_by_ticker[ticker] = record

    interim_by_ticker: dict[str, list[SecFilingManifestRecord]] = {}
    for record in interim_records:
        if _form_type(record) != "10-Q":
            continue
        ticker = record.ticker.upper()
        latest_annual = latest_annual_by_ticker.get(ticker)
        if latest_annual is None:
            continue
        if int(record.fiscal_year) <= int(latest_annual.fiscal_year):
            continue
        interim_by_ticker.setdefault(ticker, []).append(record)

    selected_interim: list[SecFilingManifestRecord] = []
    gaps: list[dict[str, Any]] = []
    for ticker, latest_annual in sorted(latest_annual_by_ticker.items()):
        candidates = interim_by_ticker.get(ticker, [])
        if not candidates:
            gaps.append(
                {
                    "ticker": ticker,
                    "latest_annual_fiscal_year": int(latest_annual.fiscal_year),
                    "reason": "no_10q_after_latest_selected_10k",
                }
            )
            continue
        selected_interim.append(max(candidates, key=_record_sort_key))

    selected = annual_selected + sorted(selected_interim, key=_record_sort_key)
    summary = _build_summary(selected, annual_selected, selected_interim, gaps)
    return selected, summary


def _build_summary(
    selected: list[SecFilingManifestRecord],
    annual_selected: list[SecFilingManifestRecord],
    selected_interim: list[SecFilingManifestRecord],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    form_counts = Counter(_form_type(record) for record in selected)
    tickers = sorted({record.ticker.upper() for record in selected})
    interim_rows = [
        {
            "ticker": record.ticker.upper(),
            "fiscal_year": int(record.fiscal_year),
            "fiscal_period": record.fiscal_period,
            "period_end": record.period_end,
            "filing_date": record.filing_date,
            "fiscal_year_source": record.fiscal_year_source,
            "fiscal_period_source": record.fiscal_period_source,
        }
        for record in sorted(selected_interim, key=lambda item: item.ticker.upper())
    ]
    return {
        "records": len(selected),
        "annual_records": len(annual_selected),
        "interim_records": len(selected_interim),
        "tickers": len(tickers),
        "form_counts": dict(sorted(form_counts.items())),
        "fiscal_years": sorted({int(record.fiscal_year) for record in selected}),
        "source_policy": "SEC_PRIMARY_MIXED_RECENT",
        "interim_selection_policy": "latest_10q_after_latest_selected_10k_by_ticker",
        "interim_rows": interim_rows,
        "interim_gaps": gaps,
    }


def _record_sort_key(record: SecFilingManifestRecord) -> tuple[Any, ...]:
    return (
        record.ticker.upper(),
        int(record.fiscal_year),
        PERIOD_RANK.get(str(record.fiscal_period or "").upper(), 0),
        str(record.period_end or ""),
        str(record.filing_date or ""),
        _form_type(record),
    )


def _form_type(record: SecFilingManifestRecord) -> str:
    return str(record.form_type or record.source_type or "").upper().strip()


def main() -> None:
    args = parse_args()
    annual_records = read_sec_filing_manifest_jsonl(REPO_ROOT / args.annual_manifest)
    interim_records = read_sec_filing_manifest_jsonl(REPO_ROOT / args.interim_manifest)
    selected, summary = select_mixed_records(
        annual_records=annual_records,
        interim_records=interim_records,
        annual_years=parse_years(args.annual_years),
    )

    output_path = REPO_ROOT / args.output
    write_sec_filing_manifest_jsonl(selected, output_path)
    summary["output"] = str(output_path)

    summary_path = (
        REPO_ROOT / args.summary_output
        if args.summary_output
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_output"] = str(summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
