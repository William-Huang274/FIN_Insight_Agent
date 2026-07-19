from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local FinSight Workbench API and frontend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--fixture-root",
        help="Canonical fixture/runtime root used by the internal product chain.",
    )
    parser.add_argument(
        "--baseline-store",
        help="Separate SQLite store for resumable human baseline and senior review records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.fixture_root:
        fixture_root = Path(args.fixture_root).resolve()
        if not fixture_root.exists():
            raise SystemExit(f"fixture root does not exist: {fixture_root}")
        os.environ["FINSIGHT_P02_FIXTURE_ROOT"] = str(fixture_root)
    if args.baseline_store:
        os.environ["FINSIGHT_HUMAN_BASELINE_STORE"] = str(Path(args.baseline_store).resolve())
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "src"))
    uvicorn.run(
        "apps.workbench.backend.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
