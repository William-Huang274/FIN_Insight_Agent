from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ingestion.official_source_capture import capture_plan  # noqa: E402


def _resolve(value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (ROOT / value).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a bounded official-source plan before parsing."
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()

    plan = json.loads(_resolve(args.plan).read_text(encoding="utf-8"))
    result = capture_plan(
        plan,
        output_root=_resolve(args.output_root),
        attempt_id=str(args.attempt_id),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].endswith("official_sources_captured") else 2


if __name__ == "__main__":
    raise SystemExit(main())
