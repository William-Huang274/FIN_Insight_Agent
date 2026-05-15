from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from connectors import SecEdgarConnector  # noqa: E402


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a SEC filing HTML smoke test.")
    parser.add_argument("--ticker", default="JPM", help="Ticker symbol, e.g. JPM.")
    parser.add_argument("--year", type=int, default=2024, help="Fiscal year by reportDate.")
    parser.add_argument("--form-type", default="10-K", help="SEC form type.")
    parser.add_argument(
        "--cache-dir",
        default=os.getenv("SEC_CACHE_DIR", "data/raw_private/sec"),
        help="Private SEC cache directory.",
    )
    parser.add_argument(
        "--user-agent",
        default=os.getenv("SEC_USER_AGENT"),
        help="SEC User-Agent. Defaults to SEC_USER_AGENT.",
    )
    parser.add_argument("--rate-limit", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    load_env_file(REPO_ROOT / ".env")
    args = parse_args()
    user_agent = args.user_agent or os.getenv("SEC_USER_AGENT")
    if not user_agent:
        user_agent = "FinSight-Agent/0.1 contact@example.com"

    connector = SecEdgarConnector(
        user_agent=user_agent,
        cache_dir=REPO_ROOT / args.cache_dir,
        log_path=REPO_ROOT / "data/logs/download_log.jsonl",
        rate_limit=args.rate_limit,
    )
    result = connector.fetch_filing(
        ticker=args.ticker,
        form_type=args.form_type,
        year=args.year,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
