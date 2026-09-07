from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.embedding_runtime import (  # noqa: E402
    load_or_build_qwen_embedding_cache,
    local_model_identity,
    sha256_file,
)


DEFAULT_OBJECTS = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v5/objects.jsonl"
)
DEFAULT_CACHE_DIR = Path(
    "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/"
    "model_cache_v5/qwen3_embedding_0_6b_v1"
)
DEFAULT_RESULT = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_qwen_embedding_cache_materialization_result_v1_0.json"
)
DEFAULT_MODEL_DIR = Path("D:/hf_models/Qwen__Qwen3-Embedding-0.6B")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the current S1 Qwen candidate embedding cache on "
            "CUDA/FP16. This cache has candidate authority only."
        )
    )
    parser.add_argument("--objects", type=Path, default=DEFAULT_OBJECTS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--result-output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--maximum-sequence-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=8)
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"json_object_required:{path}:{line_number}")
            rows.append(value)
    if not rows:
        raise ValueError("compiled_object_store_empty")
    return rows


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    args = _parse_args()
    objects_path = _resolve(args.objects)
    cache_dir = _resolve(args.cache_dir)
    result_path = _resolve(args.result_output)
    model_dir = args.model_dir
    if model_dir is None:
        configured = os.environ.get("FINSIGHT_QWEN_EMBEDDING_MODEL_DIR", "").strip()
        model_dir = Path(configured) if configured else DEFAULT_MODEL_DIR
    model_dir = _resolve(model_dir)

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required_cpu_fallback_forbidden")

    objects = _read_jsonl(objects_path)
    object_sha256 = sha256_file(objects_path)
    model_identity = local_model_identity(model_dir, "Qwen/Qwen3-Embedding-0.6B")
    dense, manifest, runtime = load_or_build_qwen_embedding_cache(
        objects=objects,
        object_sha256=object_sha256,
        model_dir=model_dir,
        model_identity=model_identity,
        cache_dir=cache_dir,
        maximum_sequence_length=args.maximum_sequence_length,
        batch_size=args.batch_size,
    )

    runtime_device = str(runtime.device)
    parameter_dtype = str(next(runtime.parameters()).dtype)
    if not runtime_device.startswith("cuda"):
        raise RuntimeError(f"cuda_runtime_required:{runtime_device}")
    if parameter_dtype != "torch.float16":
        raise RuntimeError(f"fp16_runtime_required:{parameter_dtype}")
    if str(dense.dtype) != "float16":
        raise RuntimeError(f"fp16_cache_required:{dense.dtype}")

    dense_path = cache_dir / "dense.float16.npy"
    manifest_path = cache_dir / "manifest.json"
    result = {
        "schema_version": "fin_ia_s1c_qwen_embedding_cache_materialization_result_v1_0",
        "status": "cuda_fp16_candidate_embedding_cache_materialized",
        "inputs": {
            "objects_ref": _repo_ref(objects_path),
            "objects_sha256": object_sha256,
            "object_count": len(objects),
            "model_id": "Qwen/Qwen3-Embedding-0.6B",
            "model_digest": model_identity["model_digest"],
            "maximum_sequence_length": args.maximum_sequence_length,
            "batch_size": args.batch_size,
        },
        "runtime": {
            "device": runtime_device,
            "parameter_dtype": parameter_dtype,
            "cache_dtype": str(dense.dtype),
            "cpu_fallback_count": 0,
            "model_calls": 0,
            "network_calls": 0,
        },
        "outputs": {
            "dense_cache_ref": _repo_ref(dense_path),
            "dense_cache_sha256": sha256_file(dense_path),
            "cache_manifest_ref": _repo_ref(manifest_path),
            "cache_manifest_sha256": sha256_file(manifest_path),
            "embedding_dimensions": int(dense.shape[1]),
            "cache_hit": bool(manifest["cache_hit"]),
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "embedding_grants_evidence_authority": False,
        },
    }
    _write_json(result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
