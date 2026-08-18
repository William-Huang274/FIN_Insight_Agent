from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.evaluation_assets import load_qualification_preregistration  # noqa: E402
from retrieval.qualification_runtime import (  # noqa: E402
    load_qualification_runtime_bundle,
)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
    temporary.replace(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize label-free VS5 qualification Runtime inputs."
    )
    parser.add_argument(
        "--preregistration",
        default="eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json",
    )
    parser.add_argument(
        "--overlay",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_overlay_v1_0.json",
    )
    parser.add_argument(
        "--output-root",
        default="eval_sets/fin_0_1_3_s1/inputs",
    )
    parser.add_argument(
        "--public-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_inputs_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg_path = _resolve(args.preregistration)
    overlay_path = _resolve(args.overlay)
    prereg = load_qualification_preregistration(prereg_path)
    bundle = load_qualification_runtime_bundle(
        repo_root=ROOT,
        preregistration=prereg,
        overlay_path=overlay_path,
    )
    output_root = _resolve(args.output_root)
    bindings: list[dict[str, Any]] = []
    for split, rows in bundle.inputs_by_split.items():
        path = output_root / split / "vs5_qualification_inputs_v1_0.jsonl"
        _write_jsonl(path, [row.model_dump(mode="json") for row in rows])
        bindings.append(
            {
                "split": split,
                "ref": _relative(path),
                "sha256": _sha256(path),
                "example_count": len(rows),
                "visibility": "runtime_visible",
            }
        )
    result = {
        "schema_version": "fin_ia_s1_vs5_qualification_runtime_inputs_result_v1_0",
        "status": "qualification_runtime_inputs_materialized_references_separate",
        "recorded_at": "2026-08-18",
        "bound_inputs": {
            "preregistration_ref": _relative(prereg_path),
            "preregistration_sha256": _sha256(prereg_path),
            "overlay_ref": _relative(overlay_path),
            "overlay_sha256": _sha256(overlay_path),
        },
        "outputs": bindings,
        "summary": {
            "split_count": len(bindings),
            "example_count": sum(row["example_count"] for row in bindings),
            "case_count": len(prereg.cases),
            "references_present_in_runtime_inputs": False,
            "candidate_is_not_evidence": True,
            "numeric_fact_authority": False,
            "generation_model_calls": 0,
            "network_calls": 0,
            "learned_vector_calls": 0,
        },
        "authority": {
            "qualification_execution_authorized": False,
            "next_gate": "evaluator_only_reference_and_cuda_execution_binding",
        },
    }
    _write_json(_resolve(args.public_result), result)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
