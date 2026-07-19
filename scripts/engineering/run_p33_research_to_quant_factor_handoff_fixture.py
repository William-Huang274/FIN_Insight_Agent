from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.p33_research_to_quant_factor_handoff_fixture import (
    build_p33_research_to_quant_factor_handoff_fixture,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build P33-1.5 Research-to-Quant factor handoff fixture.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument(
        "--no-rebuild-dependencies",
        action="store_true",
        help="Reuse existing S9 artifacts instead of rebuilding dependencies.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest = build_p33_research_to_quant_factor_handoff_fixture(
        root,
        rebuild_dependencies=not args.no_rebuild_dependencies,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if manifest.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
