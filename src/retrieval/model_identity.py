from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .query_plan import canonical_digest


_TOKENIZER_FILE_NAMES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "tokenizer.model",
    "sentencepiece.bpe.model",
    "vocab.json",
    "merges.txt",
    "special_tokens_map.json",
)


@dataclass(frozen=True)
class LocalWeightLayout:
    files: tuple[Path, ...]
    sharded: bool


def resolve_local_weight_layout(
    model_dir: Path,
    *,
    missing_error: str,
    single_weight_names: Sequence[str] = (
        "model.safetensors",
        "pytorch_model.bin",
    ),
) -> LocalWeightLayout:
    """Return a deterministic, path-safe local Hugging Face weight layout.

    Consolidated weights retain their historical filename order.  Sharded
    weights are bound through the checked index plus every referenced shard;
    an index may not escape the model directory or silently omit a shard.
    """

    consolidated = tuple(
        path
        for name in single_weight_names
        if (path := model_dir / name).is_file()
    )
    if consolidated:
        return LocalWeightLayout(files=consolidated, sharded=False)

    index_candidates = tuple(
        path
        for name in (
            "model.safetensors.index.json",
            "pytorch_model.bin.index.json",
        )
        if (path := model_dir / name).is_file()
    )
    if not index_candidates:
        raise ValueError(missing_error)
    if len(index_candidates) != 1:
        raise ValueError("local_model_weight_index_ambiguous")

    index_path = index_candidates[0]
    try:
        payload: Any = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("local_model_weight_index_invalid") from exc
    weight_map = payload.get("weight_map") if isinstance(payload, dict) else None
    if not isinstance(weight_map, dict) or not weight_map:
        raise ValueError("local_model_weight_index_invalid")

    raw_names = set()
    for raw_name in weight_map.values():
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("local_model_weight_index_invalid")
        name = raw_name.strip()
        candidate = Path(name)
        if (
            candidate.name != name
            or candidate.is_absolute()
            or "/" in name
            or "\\" in name
            or name in {".", ".."}
        ):
            raise ValueError("local_model_weight_shard_path_invalid")
        raw_names.add(name)

    expected_suffix = (
        ".safetensors"
        if index_path.name == "model.safetensors.index.json"
        else ".bin"
    )
    if any(not name.endswith(expected_suffix) for name in raw_names):
        raise ValueError("local_model_weight_shard_type_invalid")

    model_root = model_dir.resolve()
    shards: list[Path] = []
    for name in sorted(raw_names):
        path = model_dir / name
        if not path.is_file():
            raise ValueError(f"local_model_weight_shard_missing:{name}")
        if path.resolve().parent != model_root:
            raise ValueError("local_model_weight_shard_path_invalid")
        shards.append(path)
    return LocalWeightLayout(files=(index_path, *shards), sharded=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _identity_rows(files: Sequence[Path]) -> list[dict[str, Any]]:
    return [
        {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in files
    ]


def _tokenizer_files(model_dir: Path, *, missing_error: str) -> tuple[Path, ...]:
    files = tuple(
        path
        for name in _TOKENIZER_FILE_NAMES
        if (path := model_dir / name).is_file()
    )
    if not files:
        raise ValueError(missing_error)
    return files


def local_embedding_model_identity_v2(
    model_dir: Path,
    expected_name: str,
) -> dict[str, Any]:
    """Bind a complete local embedding artifact without changing frozen v1 code."""

    config = model_dir / "config.json"
    if not config.is_file():
        raise ValueError(f"local_embedding_model_v2_incomplete:{expected_name}")
    weight_layout = resolve_local_weight_layout(
        model_dir,
        missing_error=f"local_embedding_model_v2_incomplete:{expected_name}",
    )
    tokenizer_files = _tokenizer_files(
        model_dir,
        missing_error="local_embedding_model_v2_tokenizer_files_missing",
    )
    body = {
        "identity_schema": "local_embedding_model_identity_v2",
        "model_name": expected_name,
        "directory_name": model_dir.name,
        "weight_layout": (
            "indexed_shards" if weight_layout.sharded else "consolidated"
        ),
        "files": _identity_rows(
            (config, *weight_layout.files, *tokenizer_files)
        ),
    }
    return {**body, "model_digest": canonical_digest(body)}


def local_cross_encoder_model_identity_v2(
    model_dir: Path,
    *,
    model_id: str,
) -> dict[str, Any]:
    """Bind a complete local reranker artifact without changing frozen v1 code."""

    config = model_dir / "config.json"
    if not config.is_file():
        raise ValueError("local_cross_encoder_model_v2_files_missing")
    weight_layout = resolve_local_weight_layout(
        model_dir,
        missing_error="local_cross_encoder_model_v2_files_missing",
    )
    tokenizer_files = _tokenizer_files(
        model_dir,
        missing_error="local_cross_encoder_model_v2_tokenizer_files_missing",
    )
    body = {
        "identity_schema": "local_cross_encoder_model_identity_v2",
        "model_id": model_id,
        "directory_name": model_dir.name,
        "weight_layout": (
            "indexed_shards" if weight_layout.sharded else "consolidated"
        ),
        "files": _identity_rows(
            (config, *weight_layout.files, *tokenizer_files)
        ),
    }
    return {**body, "model_digest": canonical_digest(body)}


__all__ = [
    "LocalWeightLayout",
    "local_cross_encoder_model_identity_v2",
    "local_embedding_model_identity_v2",
    "resolve_local_weight_layout",
]
