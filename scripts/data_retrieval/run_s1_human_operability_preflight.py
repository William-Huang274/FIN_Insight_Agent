from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from retrieval.human_operability import (  # noqa: E402
    compile_human_operability_preflight,
    load_human_operability_program,
)


DEFAULT_PROGRAM = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_human_operability_and_blind_gate_program_v1_0.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile the zero-generation S1 human-operability preflight to stdout."
    )
    parser.add_argument("--program", type=Path, default=DEFAULT_PROGRAM)
    parser.add_argument(
        "--recorded-at", default="2026-08-19T00:00:00+08:00"
    )
    args = parser.parse_args()
    program = load_human_operability_program(args.program)
    result = compile_human_operability_preflight(
        repo_root=ROOT,
        program=program,
        recorded_at=args.recorded_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
