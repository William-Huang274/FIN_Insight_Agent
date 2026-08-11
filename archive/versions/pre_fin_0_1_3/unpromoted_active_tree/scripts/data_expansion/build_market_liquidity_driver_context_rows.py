from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.market_snapshot import build_market_liquidity_driver_context_rows  # noqa: E402


MANIFEST_DIR = REPO_ROOT / "data" / "manifests"
DEFAULT_OUTPUT_ROWS = MANIFEST_DIR / "market_liquidity_driver_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "market_liquidity_driver_context_summary_v0_1.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project market evidence pack rows into L3 market-liquidity driver context rows."
    )
    parser.add_argument("--market-evidence", required=True, help="Market evidence JSONL path.")
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    summary = build_market_liquidity_driver_context_rows(
        market_evidence_path=args.market_evidence,
        output_path=args.output_rows,
        summary_path=args.output_summary,
        max_rows=args.max_rows or None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
