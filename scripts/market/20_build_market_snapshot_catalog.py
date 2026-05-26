from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.market_snapshot import build_market_snapshot_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a DuckDB catalog over market snapshot artifacts.")
    parser.add_argument("--output-root", default="data/processed_private/market")
    parser.add_argument("--catalog-path", default="")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    summary = build_market_snapshot_catalog(
        output_root=args.output_root,
        catalog_path=args.catalog_path or None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
