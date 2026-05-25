from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.market_snapshot import validate_market_snapshot  # noqa: E402


def _default_paths(output_root: str, snapshot_id: str, window: str) -> tuple[Path, Path]:
    root = Path(output_root)
    snapshot = root / "snapshots" / f"{snapshot_id}_snapshot.jsonl"
    analytics = root / "analytics" / f"{snapshot_id}_{window.lower()}_analytics.jsonl"
    return snapshot, analytics


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate market snapshot fixture artifacts.")
    parser.add_argument("--output-root", default="data/processed_private/market")
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--analytics", default="")
    parser.add_argument("--window", default="3M")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.snapshot_id:
        default_snapshot, default_analytics = _default_paths(args.output_root, args.snapshot_id, args.window)
    else:
        default_snapshot = default_analytics = Path("")
    snapshot = Path(args.snapshot) if args.snapshot else default_snapshot
    analytics = Path(args.analytics) if args.analytics else default_analytics
    if not snapshot:
        parser.error("Provide --snapshot-id or explicit --snapshot path.")

    summary = validate_market_snapshot(
        snapshot_path=snapshot,
        analytics_path=analytics if analytics else None,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if summary["can_enter_market_snapshot_chain"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
