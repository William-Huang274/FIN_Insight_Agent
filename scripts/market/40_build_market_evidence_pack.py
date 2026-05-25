from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.market_snapshot import build_market_evidence_pack  # noqa: E402


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _default_paths(output_root: str, snapshot_id: str, window: str) -> tuple[Path, Path, Path]:
    root = Path(output_root)
    analytics = root / "analytics" / f"{snapshot_id}_{window.lower()}_analytics.jsonl"
    snapshot = root / "snapshots" / f"{snapshot_id}_snapshot.jsonl"
    evidence = root / "evidence_packs" / f"{snapshot_id}_{window.lower()}_market_evidence.jsonl"
    return analytics, snapshot, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact market snapshot evidence pack rows.")
    parser.add_argument("--output-root", default="data/processed_private/market")
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--analytics", default="")
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--window", default="3M")
    parser.add_argument("--tickers", default="")
    parser.add_argument("--max-rows", type=int, default=30)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.snapshot_id:
        default_analytics, default_snapshot, default_output = _default_paths(
            args.output_root,
            args.snapshot_id,
            args.window,
        )
    else:
        default_analytics = default_snapshot = default_output = Path("")
    analytics = Path(args.analytics) if args.analytics else default_analytics
    snapshot = Path(args.snapshot) if args.snapshot else default_snapshot
    output = Path(args.output) if args.output else default_output
    if not analytics or not snapshot or not output:
        parser.error("Provide --snapshot-id or explicit --analytics, --snapshot, and --output paths.")

    summary = build_market_evidence_pack(
        analytics_path=analytics,
        snapshot_path=snapshot,
        output_path=output,
        tickers=_split_csv(args.tickers),
        max_rows=args.max_rows,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
