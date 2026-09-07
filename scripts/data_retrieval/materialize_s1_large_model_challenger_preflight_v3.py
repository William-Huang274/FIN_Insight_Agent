from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from retrieval.large_model_challenger import (  # noqa: E402
    evaluate_large_model_resource_gate,
)
from scripts.data_retrieval.materialize_s1_large_model_challenger_preflight_v2 import (  # noqa: E402
    _bound_ref,
    _existing_parent,
    _hardware_receipt,
    _read_json,
    _resolve,
    _sha256,
    _write_json,
)


PROGRAM = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_large_model_challenger_program_v1_2.json"
)
OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_large_model_challenger_preflight_result_v1_2.json"
)


def _verify_predecessor_bindings(program: Mapping[str, Any]) -> None:
    predecessor = program.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise ValueError("large_model_challenger_predecessor_binding_missing")
    for ref_key, sha_key in (
        ("program_ref", "program_sha256"),
        ("preflight_result_ref", "preflight_result_sha256"),
        ("independent_audit_failure_ref", "independent_audit_failure_sha256"),
    ):
        raw_ref = predecessor.get(ref_key)
        raw_sha = predecessor.get(sha_key)
        if not isinstance(raw_ref, str) or not isinstance(raw_sha, str):
            raise ValueError("large_model_challenger_predecessor_binding_invalid")
        path = _resolve(raw_ref)
        if not path.is_file() or _sha256(path) != raw_sha:
            raise ValueError(
                f"large_model_challenger_predecessor_digest_mismatch:{ref_key}"
            )


def _artifact_locator(path: Path, *, model_id: str) -> dict[str, Any]:
    return {
        "status": "present_unverified" if path.is_dir() else "absent",
        "local_dir": str(path),
        "model_id": model_id,
        "caller_status_is_diagnostic_only": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the zero-call S1 large-model preflight whose gate "
            "independently recomputes local identity v3."
        )
    )
    parser.add_argument("--program", default=PROGRAM)
    parser.add_argument("--model-storage-root", default="Z:/hf_models")
    parser.add_argument("--embedding-model-dir")
    parser.add_argument("--reranker-model-dir")
    parser.add_argument("--output", default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    program_path = _resolve(args.program)
    program = _read_json(program_path)
    _verify_predecessor_bindings(program)
    primary_embedding = program["candidates"]["primary_embedding"]
    primary_reranker = program["candidates"]["primary_reranker"]
    embedding_dir = _resolve(
        args.embedding_model_dir or primary_embedding["default_local_dir"]
    )
    reranker_dir = _resolve(
        args.reranker_model_dir or primary_reranker["default_local_dir"]
    )
    storage_path = _existing_parent(_resolve(args.model_storage_root))
    disk = shutil.disk_usage(storage_path)
    storage = {
        "requested_root": str(_resolve(args.model_storage_root)),
        "observed_existing_parent": str(storage_path),
        "total_bytes": int(disk.total),
        "used_bytes": int(disk.used),
        "free_bytes": int(disk.free),
    }
    locators = {
        primary_embedding["model_key"]: _artifact_locator(
            embedding_dir, model_id=primary_embedding["model_id"]
        ),
        primary_reranker["model_key"]: _artifact_locator(
            reranker_dir, model_id=primary_reranker["model_id"]
        ),
    }
    gate = evaluate_large_model_resource_gate(
        program,
        hardware=_hardware_receipt(),
        storage=storage,
        model_artifacts=locators,
    )
    output = {
        "schema_version": (
            "fin_ia_s1_large_model_challenger_preflight_result_v1_2"
        ),
        "recorded_at": "2026-08-24",
        "program_id": program["program_id"],
        "program_ref": program_path.relative_to(ROOT).as_posix(),
        "program_sha256": _sha256(program_path),
        "predecessor": dict(program["predecessor"]),
        "identity_contract": dict(program["artifact_identity_contract"]),
        "implementation_refs": [
            _bound_ref(ROOT / "src/retrieval/model_identity.py"),
            _bound_ref(ROOT / "src/retrieval/large_model_challenger.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/"
                "materialize_s1_large_model_challenger_preflight_v3.py"
            ),
        ],
        **gate,
        "known_boundary": (
            "This zero-call preflight does not download or load a model, "
            "compute vectors or scores, inspect COST or hidden references, "
            "grant Evidence or NumericFact authority, qualify S1, or promote "
            "a runtime. A suitable host must still open a new recorded "
            "candidate-ceiling-first attempt."
        ),
    }
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {
                "status": output["status"],
                "device": output["hardware"].get("device_name"),
                "total_memory_bytes": output["hardware"].get(
                    "total_memory_bytes"
                ),
                "resource_blockers": output["resource_blockers"],
                "artifact_blockers": output["artifact_blockers"],
                "calls": output["calls"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
