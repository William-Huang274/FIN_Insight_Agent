from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix, load_npz, save_npz

from .query_plan import canonical_digest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_model_identity(model_dir: Path, expected_name: str) -> dict[str, Any]:
    config = model_dir / "config.json"
    weights = [
        path
        for name in ("model.safetensors", "pytorch_model.bin")
        if (path := model_dir / name).is_file()
    ]
    if not config.is_file() or not weights:
        raise ValueError(f"local_model_incomplete:{expected_name}")
    tokenizer_files = [
        path
        for name in (
            "tokenizer.json",
            "tokenizer_config.json",
            "sentencepiece.bpe.model",
        )
        if (path := model_dir / name).is_file()
    ]
    files = [config, *weights, *tokenizer_files]
    body = {
        "model_name": expected_name,
        "directory_name": model_dir.name,
        "files": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    return {**body, "model_digest": canonical_digest(body)}


def load_bge_m3_runtime(model_dir: Path):
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
    from FlagEmbedding import BGEM3FlagModel

    return BGEM3FlagModel(str(model_dir), use_fp16=True, device="cuda")


def load_qwen_embedding_runtime(model_dir: Path):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        str(model_dir),
        device="cuda",
        local_files_only=True,
        trust_remote_code=True,
    )


def load_or_build_bge_m3_cache(
    *,
    objects: Sequence[Mapping[str, Any]],
    object_sha256: str,
    model_dir: Path,
    model_identity: Mapping[str, Any],
    cache_dir: Path,
    maximum_sequence_length: int,
    batch_size: int,
) -> tuple[np.ndarray, csr_matrix, dict[str, Any], Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dense_path = cache_dir / "dense.float16.npy"
    sparse_path = cache_dir / "learned_sparse.float32.npz"
    manifest_path = cache_dir / "manifest.json"
    expected = {
        "schema_version": "fin_ia_s1c_bge_m3_compiled_object_cache_v1_0",
        "object_sha256": object_sha256,
        "object_identity_digest": _object_identity_digest(objects),
        "object_count": len(objects),
        "model_digest": str(model_identity["model_digest"]),
        "maximum_sequence_length": maximum_sequence_length,
        "dense_dtype": "float16",
        "learned_sparse_dtype": "float32",
    }
    cache_hit = False
    if dense_path.is_file() and sparse_path.is_file() and manifest_path.is_file():
        existing = _read_json(manifest_path)
        cache_hit = all(existing.get(key) == value for key, value in expected.items())
    runtime = load_bge_m3_runtime(model_dir)
    if not cache_hit:
        started = time.perf_counter()
        encoded = runtime.encode(
            [str(row["model_text"]) for row in objects],
            batch_size=batch_size,
            max_length=maximum_sequence_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = np.asarray(encoded["dense_vecs"], dtype=np.float16)
        width = int(runtime.tokenizer.vocab_size)
        sparse = sparse_weight_matrix(encoded["lexical_weights"], width=width)
        np.save(dense_path, dense, allow_pickle=False)
        save_npz(sparse_path, sparse, compressed=True)
        elapsed = time.perf_counter() - started
        manifest = {
            **expected,
            "embedding_dimensions": int(dense.shape[1]),
            "sparse_vocabulary_size": int(sparse.shape[1]),
            "sparse_nonzero_count": int(sparse.nnz),
            "build_seconds": round(elapsed, 3),
            "dense_sha256": sha256_file(dense_path),
            "sparse_sha256": sha256_file(sparse_path),
        }
        _write_json(manifest_path, manifest)
    manifest = _read_json(manifest_path)
    dense = np.load(dense_path, mmap_mode="r")
    sparse = load_npz(sparse_path)
    if dense.shape[0] != len(objects) or sparse.shape[0] != len(objects):
        raise ValueError("bge_cache_shape_drift")
    return dense, sparse, {**manifest, "cache_hit": cache_hit}, runtime


def load_or_build_qwen_embedding_cache(
    *,
    objects: Sequence[Mapping[str, Any]],
    object_sha256: str,
    model_dir: Path,
    model_identity: Mapping[str, Any],
    cache_dir: Path,
    maximum_sequence_length: int,
    batch_size: int,
) -> tuple[np.ndarray, dict[str, Any], Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dense_path = cache_dir / "dense.float16.npy"
    manifest_path = cache_dir / "manifest.json"
    expected = {
        "schema_version": "fin_ia_s1c_qwen3_embedding_compiled_object_cache_v1_0",
        "object_sha256": object_sha256,
        "object_identity_digest": _object_identity_digest(objects),
        "object_count": len(objects),
        "model_digest": str(model_identity["model_digest"]),
        "maximum_sequence_length": maximum_sequence_length,
        "dense_dtype": "float16",
    }
    cache_hit = False
    if dense_path.is_file() and manifest_path.is_file():
        existing = _read_json(manifest_path)
        cache_hit = all(existing.get(key) == value for key, value in expected.items())
    runtime = load_qwen_embedding_runtime(model_dir)
    runtime.max_seq_length = maximum_sequence_length
    if not cache_hit:
        started = time.perf_counter()
        dense = runtime.encode(
            [str(row["model_text"]) for row in objects],
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        ).astype(np.float16)
        np.save(dense_path, dense, allow_pickle=False)
        elapsed = time.perf_counter() - started
        manifest = {
            **expected,
            "embedding_dimensions": int(dense.shape[1]),
            "build_seconds": round(elapsed, 3),
            "dense_sha256": sha256_file(dense_path),
        }
        _write_json(manifest_path, manifest)
    manifest = _read_json(manifest_path)
    dense = np.load(dense_path, mmap_mode="r")
    if dense.shape[0] != len(objects):
        raise ValueError("qwen_cache_shape_drift")
    return dense, {**manifest, "cache_hit": cache_hit}, runtime


def _object_identity_digest(objects: Sequence[Mapping[str, Any]]) -> str:
    return canonical_digest([str(row["compiled_object_id"]) for row in objects])


def sparse_weight_matrix(
    rows: Sequence[Mapping[str, Any]], *, width: int
) -> csr_matrix:
    row_indices: list[int] = []
    column_indices: list[int] = []
    values: list[float] = []
    for row_index, weights in enumerate(rows):
        for raw_token, raw_weight in weights.items():
            token = int(raw_token)
            if token < 0 or token >= width:
                raise ValueError("learned_sparse_token_out_of_range")
            weight = float(raw_weight)
            if weight == 0.0:
                continue
            row_indices.append(row_index)
            column_indices.append(token)
            values.append(weight)
    return csr_matrix(
        (np.asarray(values, dtype=np.float32), (row_indices, column_indices)),
        shape=(len(rows), width),
        dtype=np.float32,
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


__all__ = [
    "load_bge_m3_runtime",
    "load_or_build_bge_m3_cache",
    "load_or_build_qwen_embedding_cache",
    "load_qwen_embedding_runtime",
    "local_model_identity",
    "sha256_file",
    "sparse_weight_matrix",
]
