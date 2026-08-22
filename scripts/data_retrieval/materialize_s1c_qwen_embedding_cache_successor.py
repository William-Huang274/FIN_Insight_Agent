from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.embedding_runtime import (  # noqa: E402
    load_qwen_embedding_runtime,
    local_model_identity,
    sha256_file,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


DEFAULT_BASE_OBJECTS = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v5/objects.jsonl"
)
DEFAULT_SUCCESSOR_OBJECTS = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v6/objects.jsonl"
)
DEFAULT_BASE_CACHE_DIR = Path(
    "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/"
    "model_cache_v5/qwen3_embedding_0_6b_v1"
)
DEFAULT_SUCCESSOR_CACHE_DIR = Path(
    "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/"
    "model_cache_v6/qwen3_embedding_0_6b_v1"
)
DEFAULT_RESULT = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_0.json"
)
DEFAULT_MODEL_DIR = Path("D:/hf_models/Qwen__Qwen3-Embedding-0.6B")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path}:{line_number}")
            rows.append(value)
    if not rows:
        raise ValueError("compiled_object_store_empty")
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _object_identity_digest(rows: list[Mapping[str, Any]]) -> str:
    return canonical_digest([str(row["compiled_object_id"]) for row in rows])


def _validate_successor_prefix(
    base_objects: list[Mapping[str, Any]],
    successor_objects: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if len(successor_objects) <= len(base_objects):
        raise ValueError("embedding_successor_has_no_append")
    if successor_objects[: len(base_objects)] != base_objects:
        raise ValueError("embedding_successor_base_prefix_drift")
    additions = successor_objects[len(base_objects) :]
    base_ids = {str(row.get("compiled_object_id") or "") for row in base_objects}
    addition_ids = [str(row.get("compiled_object_id") or "") for row in additions]
    if (
        not all(addition_ids)
        or len(addition_ids) != len(set(addition_ids))
        or base_ids.intersection(addition_ids)
    ):
        raise ValueError("embedding_successor_append_identity_invalid")
    return additions


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reuse an exact immutable Qwen object prefix and embed only newly "
            "appended candidate objects on CUDA/FP16."
        )
    )
    parser.add_argument("--base-objects", type=Path, default=DEFAULT_BASE_OBJECTS)
    parser.add_argument(
        "--successor-objects", type=Path, default=DEFAULT_SUCCESSOR_OBJECTS
    )
    parser.add_argument("--base-cache-dir", type=Path, default=DEFAULT_BASE_CACHE_DIR)
    parser.add_argument(
        "--successor-cache-dir", type=Path, default=DEFAULT_SUCCESSOR_CACHE_DIR
    )
    parser.add_argument("--result-output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--maximum-sequence-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    base_objects_path = _resolve(args.base_objects)
    successor_objects_path = _resolve(args.successor_objects)
    base_cache_dir = _resolve(args.base_cache_dir)
    successor_cache_dir = _resolve(args.successor_cache_dir)
    result_path = _resolve(args.result_output)
    model_dir = args.model_dir
    if model_dir is None:
        configured = os.environ.get("FINSIGHT_QWEN_EMBEDDING_MODEL_DIR", "").strip()
        model_dir = Path(configured) if configured else DEFAULT_MODEL_DIR
    model_dir = _resolve(model_dir)

    base_objects = _read_jsonl(base_objects_path)
    successor_objects = _read_jsonl(successor_objects_path)
    additions = _validate_successor_prefix(base_objects, successor_objects)
    base_manifest = _read_json(base_cache_dir / "manifest.json")
    if base_manifest.get("object_sha256") != sha256_file(base_objects_path):
        raise ValueError("embedding_successor_base_manifest_object_drift")
    if int(base_manifest.get("object_count") or 0) != len(base_objects):
        raise ValueError("embedding_successor_base_manifest_count_drift")
    base_dense = np.load(base_cache_dir / "dense.float16.npy", mmap_mode="r")
    if base_dense.shape[0] != len(base_objects) or str(base_dense.dtype) != "float16":
        raise ValueError("embedding_successor_base_dense_invalid")

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required_cpu_fallback_forbidden")
    model_identity = local_model_identity(model_dir, "Qwen/Qwen3-Embedding-0.6B")
    if str(base_manifest.get("model_digest") or "") != model_identity["model_digest"]:
        raise ValueError("embedding_successor_model_identity_drift")
    runtime = load_qwen_embedding_runtime(model_dir)
    runtime.max_seq_length = args.maximum_sequence_length
    runtime_device = str(runtime.device)
    parameter_dtype = str(next(runtime.parameters()).dtype)
    if not runtime_device.startswith("cuda"):
        raise RuntimeError(f"cuda_runtime_required:{runtime_device}")
    if parameter_dtype != "torch.float16":
        raise RuntimeError(f"fp16_runtime_required:{parameter_dtype}")

    started = time.perf_counter()
    appended_dense = runtime.encode(
        [str(row["model_text"]) for row in additions],
        batch_size=args.batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype(np.float16)
    if appended_dense.shape != (len(additions), base_dense.shape[1]):
        raise ValueError("embedding_successor_append_shape_invalid")
    successor_cache_dir.mkdir(parents=True, exist_ok=True)
    dense_path = successor_cache_dir / "dense.float16.npy"
    np.save(
        dense_path,
        np.concatenate((np.asarray(base_dense), appended_dense), axis=0),
        allow_pickle=False,
    )
    elapsed = time.perf_counter() - started
    dense = np.load(dense_path, mmap_mode="r")
    if dense.shape[0] != len(successor_objects) or str(dense.dtype) != "float16":
        raise ValueError("embedding_successor_dense_invalid")

    manifest = {
        "schema_version": "fin_ia_s1c_qwen3_embedding_compiled_object_cache_v1_1",
        "object_sha256": sha256_file(successor_objects_path),
        "object_identity_digest": _object_identity_digest(successor_objects),
        "object_count": len(successor_objects),
        "model_digest": model_identity["model_digest"],
        "maximum_sequence_length": args.maximum_sequence_length,
        "dense_dtype": "float16",
        "embedding_dimensions": int(dense.shape[1]),
        "build_seconds": round(elapsed, 3),
        "dense_sha256": sha256_file(dense_path),
        "successor_strategy": "exact_base_prefix_reuse_plus_cuda_fp16_append",
        "predecessor": {
            "objects_ref": _repo_ref(base_objects_path),
            "objects_sha256": sha256_file(base_objects_path),
            "dense_ref": _repo_ref(base_cache_dir / "dense.float16.npy"),
            "dense_sha256": sha256_file(base_cache_dir / "dense.float16.npy"),
            "object_count": len(base_objects),
        },
        "append": {
            "object_count": len(additions),
            "execution_device": runtime_device,
            "parameter_dtype": parameter_dtype,
            "output_dtype": str(appended_dense.dtype),
            "cpu_fallback_count": 0,
        },
    }
    manifest_path = successor_cache_dir / "manifest.json"
    _write_json(manifest_path, manifest)

    result = {
        "schema_version": "fin_ia_s1c_qwen_embedding_cache_successor_result_v1_0",
        "status": "cuda_fp16_append_only_candidate_embedding_cache_materialized",
        "recorded_at": "2026-08-23",
        "inputs": {
            "base_objects_ref": _repo_ref(base_objects_path),
            "base_objects_sha256": sha256_file(base_objects_path),
            "successor_objects_ref": _repo_ref(successor_objects_path),
            "successor_objects_sha256": sha256_file(successor_objects_path),
            "base_dense_ref": _repo_ref(base_cache_dir / "dense.float16.npy"),
            "base_dense_sha256": sha256_file(base_cache_dir / "dense.float16.npy"),
            "model_id": "Qwen/Qwen3-Embedding-0.6B",
            "model_digest": model_identity["model_digest"],
        },
        "runtime": {
            "device": runtime_device,
            "parameter_dtype": parameter_dtype,
            "cache_dtype": str(dense.dtype),
            "base_object_count_reused": len(base_objects),
            "new_object_count_embedded": len(additions),
            "cpu_fallback_count": 0,
            "model_generation_calls": 0,
            "network_calls": 0,
        },
        "outputs": {
            "dense_cache_ref": _repo_ref(dense_path),
            "dense_cache_sha256": sha256_file(dense_path),
            "cache_manifest_ref": _repo_ref(manifest_path),
            "cache_manifest_sha256": sha256_file(manifest_path),
            "object_count": int(dense.shape[0]),
            "embedding_dimensions": int(dense.shape[1]),
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "embedding_grants_evidence_authority": False,
            "base_prefix_reuse_exactly_validated": True,
        },
    }
    _write_json(result_path, result)
    print(result_path)
    print(json.dumps(result["runtime"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
