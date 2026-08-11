from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.data_expansion.build_channel_offer_context_rows import build_channel_offer_context_rows  # noqa: E402


SUMMARY_SCHEMA_VERSION = "finsight_broad_channel_offer_context_summary_v0_1"

DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_FAMILY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "broad_channel_offer_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "broad_channel_offer_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "broad_channel_offer_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/broad_channel_offers")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build broad CDW/channel offer rows for channel_offer_proxy requirements.")
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--fetch-retries", type=int, default=1)
    parser.add_argument("--max-products-per-probe", type=int, default=1)
    parser.add_argument("--max-search-links", type=int, default=3)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    family_rows = _load_jsonl(args.family_assignments)
    probes = build_probes(matrix_rows=matrix_rows, family_rows=family_rows, tickers=args.tickers)
    result = build_channel_offer_context_rows(
        probes=probes,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        max_products_per_probe=args.max_products_per_probe,
        max_search_links=args.max_search_links,
    )
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *result["rows"]])
    output_attempts = result["attempts"] if args.replace_output else _dedupe_attempts(
        [*_load_jsonl(args.output_attempts), *result["attempts"]]
    )
    summary = build_summary(
        probes=probes,
        rows=output_rows,
        attempts=output_attempts,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
    )
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not result["rows"]:
        return 1
    return 0


def build_probes(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    family_rows: Iterable[Mapping[str, Any]],
    tickers: Iterable[str] = (),
) -> list[dict[str, Any]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    family_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in family_rows:
        if not isinstance(row, Mapping):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            family_by_ticker.setdefault(ticker, []).append(dict(row))
    probes: list[dict[str, Any]] = []
    for company in matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
        if "channel_offer_proxy" not in requirements:
            continue
        family = (family_by_ticker.get(ticker) or [{}])[0]
        company_name = str(company.get("company_name") or ticker).strip()
        product_terms = _unique_strings([*(family.get("query_terms") or []), family.get("family_name") or "", company.get("industry_schema") or ""])
        if not product_terms:
            product_terms = [company_name]
        probes.append(
            {
                "ticker": ticker,
                "company_name": company_name,
                "company_names": _unique_strings([company_name, ticker]),
                "product_terms": product_terms[:8],
                "search_query": f"{company_name} {product_terms[0]} cdw",
                "allow_brand_only_match": True,
            }
        )
    return probes


def build_summary(
    *,
    probes: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
) -> dict[str, Any]:
    required = {str(probe.get("ticker") or "").upper() for probe in probes}
    success = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "required_ticker_count": len(required),
        "success_ticker_count": len(success),
        "unmaterialized_ticker_count": len(required - success),
        "row_count": len(rows),
        "attempt_count": len(attempts),
        "row_source_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "unmaterialized_tickers": sorted(required - success),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "Only parsed public channel SKU/price/availability rows are promoted; no ASP, inventory, sell-through, sales, or share claims.",
    }


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if not key:
            key = "|".join(str(row.get(field) or "") for field in ("ticker", "source_url", "fact_label", "product_or_segment"))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("attempt_id") or "")
        if not key:
            key = "|".join(str(row.get(field) or "") for field in ("ticker", "provider", "url", "status", "reason", "raw_path"))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
