from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping, Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_qrels_owner_acceptance import (  # noqa: E402
    materialize_internal_qrels_owner_acceptance,
)


DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_internal_qrels_owner_acceptance_v1_0.json"
)


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == encoded:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    decision = materialize_internal_qrels_owner_acceptance(repo_root=ROOT)
    _write_atomic(args.output.resolve(), decision)
    print(
        json.dumps(
            {
                "status": decision["status"],
                "accepted_qrels": decision["owner_decision"][
                    "accepted_qrel_count"
                ],
                "decision_digest": decision["decision_digest"],
                "output": args.output.resolve().as_posix(),
                "next": decision["recommended_next"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
