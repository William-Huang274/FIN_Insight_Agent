from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.runtime_readiness import run_r0_r11_readiness


def main() -> None:
    args = parse_args()
    report = run_r0_r11_readiness(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        include_cloud_gates=args.include_cloud_gates,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] == "fail":
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local R0-R11 readiness gates before cloud/Milvus full-chain validation.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "reports" / "quality" / "r0_r11_readiness_local")
    parser.add_argument("--include-cloud-gates", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
