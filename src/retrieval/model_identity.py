from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

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
ACQUISITION_MANIFEST_NAME = "fin_ia_model_acquisition_manifest_v1_0.json"
ACQUISITION_MANIFEST_SCHEMA_VERSION = (
    "fin_ia_local_model_acquisition_manifest_v1_0"
)
_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")


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


def _identity_rows_relative(
    model_dir: Path,
    files: Sequence[Path],
) -> list[dict[str, Any]]:
    return [
        {
            "name": path.relative_to(model_dir).as_posix(),
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


def _read_acquisition_manifest(
    model_dir: Path,
    *,
    expected_model_id: str,
) -> tuple[dict[str, Any], Path, tuple[Path, ...]]:
    manifest_path = model_dir / ACQUISITION_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError("local_model_acquisition_manifest_missing")
    model_root = model_dir.resolve()
    if manifest_path.resolve().parent != model_root:
        raise ValueError("local_model_acquisition_manifest_path_invalid")
    try:
        raw: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("local_model_acquisition_manifest_invalid") from exc
    if not isinstance(raw, dict):
        raise ValueError("local_model_acquisition_manifest_invalid")
    if raw.get("schema_version") != ACQUISITION_MANIFEST_SCHEMA_VERSION:
        raise ValueError("local_model_acquisition_manifest_schema_invalid")
    if raw.get("model_id") != expected_model_id:
        raise ValueError("local_model_acquisition_manifest_model_id_mismatch")
    revision = raw.get("resolved_revision")
    if not isinstance(revision, str) or not _REVISION_PATTERN.fullmatch(revision):
        raise ValueError("local_model_acquisition_manifest_revision_invalid")
    if raw.get("acquisition_tool") != "huggingface_hub.snapshot_download":
        raise ValueError("local_model_acquisition_manifest_tool_invalid")
    manifest_rows = raw.get("files")
    if not isinstance(manifest_rows, list) or not manifest_rows:
        raise ValueError("local_model_acquisition_manifest_files_invalid")

    by_relative_path: dict[str, Mapping[str, Any]] = {}
    for row in manifest_rows:
        if not isinstance(row, Mapping):
            raise ValueError("local_model_acquisition_manifest_files_invalid")
        relative_text = row.get("path")
        if not isinstance(relative_text, str) or not relative_text:
            raise ValueError("local_model_acquisition_manifest_path_invalid")
        relative = Path(relative_text)
        if (
            relative.is_absolute()
            or "\\" in relative_text
            or relative.as_posix() != relative_text
            or relative_text.startswith("./")
            or ".." in relative.parts
            or relative_text == ACQUISITION_MANIFEST_NAME
            or relative_text in by_relative_path
        ):
            raise ValueError("local_model_acquisition_manifest_path_invalid")
        by_relative_path[relative_text] = row

    actual_by_relative_path: dict[str, Path] = {}
    for path in model_dir.rglob("*"):
        if not path.is_file() or path == manifest_path:
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(model_root):
            raise ValueError("local_model_acquisition_file_path_invalid")
        relative_text = path.relative_to(model_dir).as_posix()
        actual_by_relative_path[relative_text] = path
    if set(by_relative_path) != set(actual_by_relative_path):
        raise ValueError("local_model_acquisition_manifest_file_set_mismatch")

    files: list[Path] = []
    for relative_text in sorted(actual_by_relative_path):
        path = actual_by_relative_path[relative_text]
        row = by_relative_path[relative_text]
        expected_bytes = row.get("bytes")
        expected_sha256 = row.get("sha256")
        if (
            not isinstance(expected_bytes, int)
            or expected_bytes < 0
            or not isinstance(expected_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        ):
            raise ValueError("local_model_acquisition_manifest_files_invalid")
        if path.stat().st_size != expected_bytes:
            raise ValueError(
                f"local_model_acquisition_file_size_mismatch:{relative_text}"
            )
        if _sha256_file(path) != expected_sha256:
            raise ValueError(
                f"local_model_acquisition_file_digest_mismatch:{relative_text}"
            )
        files.append(path)
    return dict(raw), manifest_path, tuple(files)


def _local_model_identity_v3(
    model_dir: Path,
    *,
    model_id: str,
    identity_schema: str,
    missing_error: str,
    tokenizer_error: str,
) -> dict[str, Any]:
    manifest, manifest_path, acquisition_files = _read_acquisition_manifest(
        model_dir,
        expected_model_id=model_id,
    )
    config = model_dir / "config.json"
    if not config.is_file():
        raise ValueError(missing_error)
    weight_layout = resolve_local_weight_layout(
        model_dir,
        missing_error=missing_error,
    )
    _tokenizer_files(model_dir, missing_error=tokenizer_error)
    body = {
        "identity_schema": identity_schema,
        "model_id": model_id,
        "directory_name": model_dir.name,
        "resolved_revision": manifest["resolved_revision"],
        "acquisition_tool": manifest["acquisition_tool"],
        "artifact_closure": "manifest_exact_recursive_all_regular_files",
        "weight_layout": (
            "indexed_shards" if weight_layout.sharded else "consolidated"
        ),
        "files": _identity_rows_relative(
            model_dir,
            (manifest_path, *acquisition_files)
        ),
    }
    return {**body, "model_digest": canonical_digest(body)}


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


def local_embedding_model_identity_v3(
    model_dir: Path,
    expected_name: str,
) -> dict[str, Any]:
    return _local_model_identity_v3(
        model_dir,
        model_id=expected_name,
        identity_schema="local_embedding_model_identity_v3",
        missing_error=f"local_embedding_model_v3_incomplete:{expected_name}",
        tokenizer_error="local_embedding_model_v3_tokenizer_files_missing",
    )


def local_cross_encoder_model_identity_v3(
    model_dir: Path,
    *,
    model_id: str,
) -> dict[str, Any]:
    return _local_model_identity_v3(
        model_dir,
        model_id=model_id,
        identity_schema="local_cross_encoder_model_identity_v3",
        missing_error="local_cross_encoder_model_v3_files_missing",
        tokenizer_error="local_cross_encoder_model_v3_tokenizer_files_missing",
    )


__all__ = [
    "ACQUISITION_MANIFEST_NAME",
    "ACQUISITION_MANIFEST_SCHEMA_VERSION",
    "LocalWeightLayout",
    "local_cross_encoder_model_identity_v2",
    "local_cross_encoder_model_identity_v3",
    "local_embedding_model_identity_v2",
    "local_embedding_model_identity_v3",
    "resolve_local_weight_layout",
]
