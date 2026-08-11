from __future__ import annotations

import argparse
from pathlib import Path
import sys

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FIN 0.1.3 Workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    uvicorn.run(
        "apps.workbench.backend.app:app",
        host=args.host,
        port=args.port,
        reload=False,
    )
