from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.vertical_source_lane_package import (  # noqa: E402
    build_vertical_lane_packages,
    write_vertical_lane_packages,
)


DEFAULT_REGISTRY_PATH = Path("data/manifests/vertical_source_lane_registry_v0_1.json")
DEFAULT_OUTPUT_DIR = Path("docs/internal/vnext_20260610/vertical_lanes")
DEFAULT_MANIFESTS_DIR = Path("data/manifests")
DEFAULT_FIXTURES_DIR = Path("tests/fixtures")
DEFAULT_SUMMARY_PATH = Path("data/manifests/vertical_lane_package_summary_v0_1.json")


def main() -> int:
    args = parse_args()
    registry = json.loads(args.registry_path.read_text(encoding="utf-8"))
    lane_ids = args.lane_id or ["V2", "V3", "V4", "V5", "V6", "V7", "V8"]
    if args.include_v1 and "V1" not in lane_ids:
        lane_ids = ["V1", *lane_ids]
    packages = build_vertical_lane_packages(registry, lane_ids=lane_ids)
    summary = write_vertical_lane_packages(
        packages,
        output_dir=args.output_dir,
        manifests_dir=args.manifests_dir,
        fixtures_dir=args.fixtures_dir,
        summary_path=args.summary_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build vertical source lane packages from the lane registry.")
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--fixtures-dir", type=Path, default=DEFAULT_FIXTURES_DIR)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--lane-id", action="append")
    parser.add_argument("--include-v1", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
