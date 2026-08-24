from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.large_model_challenger import (  # noqa: E402
    evaluate_large_model_resource_gate,
)
from retrieval.model_identity import (  # noqa: E402
    local_cross_encoder_model_identity_v2,
    local_embedding_model_identity_v2,
)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bound_ref(path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _existing_parent(path: Path) -> Path:
    current = path.resolve()
    while not current.exists() and current != current.parent:
        current = current.parent
    if not current.exists():
        raise ValueError("challenger_storage_root_unavailable")
    return current


def _hardware_receipt() -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        return {
            "cuda_available": False,
            "device_count": 0,
            "device_name": None,
            "total_memory_bytes": 0,
            "free_memory_bytes": 0,
            "torch_version": str(torch.__version__),
            "cuda_runtime_version": str(torch.version.cuda or ""),
        }
    device = torch.cuda.current_device()
    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
    properties = torch.cuda.get_device_properties(device)
    return {
        "cuda_available": True,
        "device_count": torch.cuda.device_count(),
        "device_index": int(device),
        "device_name": properties.name,
        "compute_capability": [properties.major, properties.minor],
        "total_memory_bytes": int(total_bytes),
        "free_memory_bytes": int(free_bytes),
        "torch_version": str(torch.__version__),
        "cuda_runtime_version": str(torch.version.cuda or ""),
    }


def _artifact_state(path: Path, *, model_id: str, kind: str) -> dict[str, Any]:
    if not path.is_dir():
        return {"status": "absent", "local_dir": str(path)}
    try:
        identity = (
            local_embedding_model_identity_v2(path, model_id)
            if kind == "embedding"
            else local_cross_encoder_model_identity_v2(path, model_id=model_id)
        )
    except (OSError, ValueError) as exc:
        return {
            "status": "identity_invalid",
            "local_dir": str(path),
            "model_id": model_id,
            "identity_error": str(exc),
        }
    return {
        "status": "identity_bound",
        "local_dir": str(path),
        "model_id": model_id,
        "model_digest": identity["model_digest"],
        "bound_file_count": len(identity["files"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the zero-call S1 large-model challenger preflight."
    )
    parser.add_argument(
        "--program",
        default="configs/retrieval/fin_ia_0_1_3_s1_large_model_challenger_program_v1_0.json",
    )
    parser.add_argument("--model-storage-root", default="Z:/hf_models")
    parser.add_argument("--embedding-model-dir")
    parser.add_argument("--reranker-model-dir")
    parser.add_argument(
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1_large_model_challenger_preflight_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    program_path = _resolve(args.program)
    program = _read_json(program_path)
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
    artifacts = {
        primary_embedding["model_key"]: _artifact_state(
            embedding_dir,
            model_id=primary_embedding["model_id"],
            kind="embedding",
        ),
        primary_reranker["model_key"]: _artifact_state(
            reranker_dir,
            model_id=primary_reranker["model_id"],
            kind="reranker",
        ),
    }
    gate = evaluate_large_model_resource_gate(
        program,
        hardware=_hardware_receipt(),
        storage=storage,
        model_artifacts=artifacts,
    )
    output = {
        "schema_version": "fin_ia_s1_large_model_challenger_preflight_result_v1_0",
        "recorded_at": "2026-08-24",
        "program_id": program["program_id"],
        "program_ref": program_path.relative_to(ROOT).as_posix(),
        "program_sha256": _sha256(program_path),
        "implementation_refs": [
            _bound_ref(ROOT / "src/retrieval/model_identity.py"),
            _bound_ref(ROOT / "src/retrieval/large_model_challenger.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/materialize_s1_large_model_challenger_preflight.py"
            ),
        ],
        **gate,
        "known_boundary": "This zero-call preflight does not download or load a model, compute vectors or scores, inspect hidden references, grant Evidence or NumericFact authority, qualify S1, or promote a runtime.",
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
