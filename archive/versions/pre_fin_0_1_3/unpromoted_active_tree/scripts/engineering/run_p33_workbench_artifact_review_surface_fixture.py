from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.p33_workbench_artifact_review_surface_fixture import (
    build_p33_workbench_artifact_review_surface_fixture,
)


def main() -> int:
    manifest = build_p33_workbench_artifact_review_surface_fixture(REPO_ROOT)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if manifest.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
