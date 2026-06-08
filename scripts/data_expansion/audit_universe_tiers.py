from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit universe manifest contracts.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=0)
    parser.add_argument("--require-cik", action="store_true")
    parser.add_argument("--summary-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = _load_jsonl(_resolve(args.manifest))
    summary = audit_universe_manifest(rows, expected_count=args.expected_count, require_cik=args.require_cik)
    if args.summary_output:
        path = _resolve(args.summary_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def audit_universe_manifest(rows: list[Mapping[str, Any]], *, expected_count: int = 0, require_cik: bool = False) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    tickers = [str(row.get("ticker") or "").upper().strip() for row in rows]
    ciks = [str(row.get("cik") or "").strip() for row in rows if str(row.get("cik") or "").strip()]
    ticker_counts = Counter(tickers)
    cik_counts = Counter(ciks)
    duplicate_tickers = sorted([ticker for ticker, count in ticker_counts.items() if ticker and count > 1])
    duplicate_ciks = sorted([cik for cik, count in cik_counts.items() if cik and count > 1])
    if expected_count and len(rows) != expected_count:
        errors.append({"type": "company_count_mismatch", "actual": len(rows), "expected": expected_count})
    if duplicate_tickers:
        errors.append({"type": "duplicate_tickers", "tickers": duplicate_tickers[:50]})
    if duplicate_ciks:
        errors.append({"type": "duplicate_ciks", "ciks": duplicate_ciks[:50]})
    for index, row in enumerate(rows):
        if not row.get("ticker"):
            errors.append({"type": "ticker_required", "index": index})
        if require_cik and not row.get("cik"):
            errors.append({"type": "cik_required", "index": index, "ticker": row.get("ticker")})
        if not row.get("company_name"):
            errors.append({"type": "company_name_required", "index": index, "ticker": row.get("ticker")})
        if not row.get("sector") and not row.get("source_gap"):
            errors.append({"type": "sector_or_source_gap_required", "index": index, "ticker": row.get("ticker")})
    return {
        "schema_version": "fin_agent_universe_manifest_audit_v0.1",
        "status": "fail" if errors else "pass",
        "company_count": len(rows),
        "missing_cik_count": sum(1 for row in rows if not row.get("cik")),
        "sec_download_eligible_count": sum(1 for row in rows if row.get("sec_download_eligible")),
        "errors": errors,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
