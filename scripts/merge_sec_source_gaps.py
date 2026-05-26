from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


SPECIFICITY_BY_REASON = {
    "ticker_not_found_in_sec_reference": 100,
    "no_earnings_release_exhibit_for_item_2_02_8k": 96,
    "no_item_2_02_8k_for_filing_year": 95,
    "no_8k_for_filing_year": 94,
    "no_8k_filings_available": 93,
    "earnings_release_8k_not_selected": 90,
    "sec_8k_earnings_download_error": 80,
    "selected_8k_exhibit_html_missing": 75,
    "cached_8k_missing_item_2_02": 70,
    "invalid_8k_earnings_metadata_identity": 60,
    "no_cached_8k_earnings_metadata": 20,
    "no_8k_earnings_cache_root": 10,
}


SOURCE_PRIORITY = {
    "download_sec_8k_earnings": 30,
    "sec_edgar_connector": 25,
    "build_sec_8k_earnings_manifest": 10,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge structured SEC source-gap JSONL reports into one planner/coverage input. "
            "Discovery-stage gaps outrank manifest cache-absence gaps for the same ticker/year/form/tier."
        )
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Input source-gap JSONL path. Repeat for downloader and manifest gap files.",
    )
    parser.add_argument(
        "--output",
        default="data/processed_private/source_gaps/sec_tech_8k_earnings_pilot_source_gaps_merged_2026_2027.jsonl",
        help="Merged output JSONL path.",
    )
    parser.add_argument(
        "--allow-missing-inputs",
        action="store_true",
        help="Skip absent inputs instead of failing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_paths = [_repo_path(path) for path in args.input]
    rows = read_gap_inputs(input_paths, allow_missing=args.allow_missing_inputs)
    merged = merge_source_gaps(rows)
    output_path = _repo_path(args.output)
    write_jsonl(merged, output_path)
    summary = {
        "output": str(output_path),
        "inputs": [str(path) for path in input_paths],
        "input_rows": len(rows),
        "merged_rows": len(merged),
        "reason_counts": dict(sorted(Counter(str(row.get("reason_code") or "unknown") for row in merged).items())),
        "tickers": sorted({str(row.get("ticker") or "").upper() for row in merged if row.get("ticker")}),
        "years": sorted({int(row["year"]) for row in merged if _int_or_none(row.get("year")) is not None}),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def read_gap_inputs(paths: list[Path], *, allow_missing: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            if allow_missing:
                continue
            raise FileNotFoundError(f"source gap input not found: {path}")
        rows.extend(read_jsonl(path))
    return rows


def merge_source_gaps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, int, str, str, str], dict[str, Any]] = {}
    discarded_reasons: dict[tuple[str, int, str, str, str], list[str]] = {}
    for raw in rows:
        row = normalize_gap_row(raw)
        if row is None:
            continue
        key = source_gap_key(row)
        current = best_by_key.get(key)
        if current is None or gap_rank(row) > gap_rank(current):
            if current is not None:
                discarded_reasons.setdefault(key, []).append(str(current.get("reason_code") or "unknown"))
            best_by_key[key] = row
        else:
            discarded_reasons.setdefault(key, []).append(str(row.get("reason_code") or "unknown"))
    merged = []
    for key, row in best_by_key.items():
        discarded = sorted(set(discarded_reasons.get(key) or []))
        if discarded:
            row = {**row, "discarded_gap_reasons": discarded}
        merged.append(row)
    return sorted(
        merged,
        key=lambda row: (
            str(row.get("ticker") or ""),
            int(row.get("year") or 0),
            str(row.get("form_type") or ""),
            str(row.get("source_tier") or ""),
        ),
    )


def normalize_gap_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    ticker = str(row.get("ticker") or "").upper().strip()
    year = _int_or_none(row.get("year") or row.get("filing_year") or row.get("fiscal_year"))
    form_type = str(row.get("form_type") or row.get("source_type") or "").upper().strip()
    reason_code = str(row.get("reason_code") or row.get("reason") or "").strip()
    if not ticker or year is None or not form_type or not reason_code:
        return None
    normalized = {
        "schema_version": "sec_source_gap_merged_v0.1",
        "status": str(row.get("status") or "missing").strip() or "missing",
        "ticker": ticker,
        "year": int(year),
        "filing_year": int(year),
        "form_type": form_type,
        "source_tier": str(row.get("source_tier") or "").strip(),
        "category": str(row.get("category") or "").strip(),
        "category_slug": str(row.get("category_slug") or "").strip(),
        "reason_code": reason_code,
        "reason": str(row.get("reason") or reason_code).strip(),
        "source": str(row.get("source") or "").strip(),
    }
    for key in (
        "accession_number",
        "filing_date",
        "filing_items",
        "metadata_path",
        "html_path",
        "exhibit_document",
        "after_date",
        "error",
    ):
        if row.get(key) not in (None, ""):
            normalized[key] = row.get(key)
    if isinstance(row.get("diagnostics"), dict):
        normalized["diagnostics"] = row["diagnostics"]
    return normalized


def source_gap_key(row: dict[str, Any]) -> tuple[str, int, str, str, str]:
    return (
        str(row.get("ticker") or "").upper(),
        int(row.get("year") or 0),
        str(row.get("form_type") or "").upper(),
        str(row.get("source_tier") or ""),
        str(row.get("category_slug") or ""),
    )


def gap_rank(row: dict[str, Any]) -> tuple[int, int, int]:
    reason = str(row.get("reason_code") or "")
    source = str(row.get("source") or "")
    diagnostics_score = 1 if isinstance(row.get("diagnostics"), dict) and row["diagnostics"] else 0
    return (
        SPECIFICITY_BY_REASON.get(reason, 50),
        SOURCE_PRIORITY.get(source, 0),
        diagnostics_score,
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            f.write("\n")


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
