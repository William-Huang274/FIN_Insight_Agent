from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.external_source_evidence import (  # noqa: E402
    compile_external_source_candidate_review,
)
from retrieval.source_use_policy import SourceUsePolicy  # noqa: E402


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("external_source_candidate_review_json_not_object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compile_plan(plan: dict) -> dict:
    terminal_path = _resolve(str(plan.get("ladder_terminal_ref") or ""))
    policy_path = _resolve(str(plan.get("source_use_policy_ref") or ""))
    if (
        _sha256(terminal_path) != str(plan.get("ladder_terminal_sha256") or "")
        or _sha256(policy_path) != str(plan.get("source_use_policy_sha256") or "")
    ):
        raise ValueError("external_source_candidate_review_file_binding_invalid")
    return compile_external_source_candidate_review(
        ladder_terminal=_load(terminal_path),
        plan=plan,
        source_use_policy=SourceUsePolicy.from_mapping(_load(policy_path)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile an exhaustive, capture-bound review of external ladder "
            "proposals into Evidence candidates."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compile_plan(_load(args.plan.resolve()))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"result_digest={result['result_digest']}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
