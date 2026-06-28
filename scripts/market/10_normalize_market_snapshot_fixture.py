from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.market_snapshot import normalize_market_snapshot_fixture  # noqa: E402


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _tickers_from_config(path: str | None) -> list[str]:
    if not path:
        return []
    text = Path(path).read_text(encoding="utf-8")
    return [
        match.strip()
        for match in re.findall(r"^\s*-\s*ticker:\s*([A-Za-z0-9.\-]+)\s*$", text, flags=re.MULTILINE)
        if match.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize an offline market snapshot fixture.")
    parser.add_argument("--input", required=True, help="CSV/JSON/JSONL fixture export path.")
    parser.add_argument("--output-root", default="data/processed_private/market")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--provider", default="manual_fixture")
    parser.add_argument("--tickers", default="")
    parser.add_argument("--tickers-config", default="", help="Optional YAML config with '- ticker: XYZ' entries.")
    parser.add_argument("--benchmark-tickers", default="")
    parser.add_argument("--currency", default="USD")
    parser.add_argument(
        "--per-ticker-as-of",
        action="store_true",
        help="Use each ticker's latest available bar date as snapshot as_of_date.",
    )
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    summary = normalize_market_snapshot_fixture(
        input_path=args.input,
        output_root=args.output_root,
        snapshot_id=args.snapshot_id,
        as_of_date=args.as_of_date,
        provider=args.provider,
        tickers=[*_tickers_from_config(args.tickers_config), *_split_csv(args.tickers)],
        benchmark_tickers=_split_csv(args.benchmark_tickers),
        currency=args.currency,
        per_ticker_as_of=args.per_ticker_as_of,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
