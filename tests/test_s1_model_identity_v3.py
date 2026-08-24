from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from retrieval import model_identity as model_identity_module
from retrieval.model_identity import (
    ACQUISITION_MANIFEST_NAME,
    ACQUISITION_MANIFEST_SCHEMA_VERSION,
    local_cross_encoder_model_identity_v3,
    local_embedding_model_identity_v3,
)


def _write_manifest(
    model_dir: Path,
    *,
    model_id: str,
    revision: str = "a" * 40,
) -> None:
    files = []
    for path in sorted(
        (path for path in model_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(model_dir).as_posix(),
    ):
        relative = path.relative_to(model_dir).as_posix()
        files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (model_dir / ACQUISITION_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema_version": ACQUISITION_MANIFEST_SCHEMA_VERSION,
                "model_id": model_id,
                "resolved_revision": revision,
                "acquisition_tool": "huggingface_hub.snapshot_download",
                "files": files,
            }
        ),
        encoding="utf-8",
    )


def _write_remote_code_model(model_dir: Path, *, model_id: str) -> None:
    (model_dir / "sentence_transformers").mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"weights")
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    (model_dir / "modules.json").write_text("[]", encoding="utf-8")
    (model_dir / "modeling_fin.py").write_text(
        "MODEL_KIND = 'embedding'\n",
        encoding="utf-8",
    )
    (model_dir / "sentence_transformers" / "config.json").write_text(
        "{}",
        encoding="utf-8",
    )
    _write_manifest(model_dir, model_id=model_id)


def test_v3_identity_binds_manifest_revision_and_recursive_remote_code(
    tmp_path: Path,
) -> None:
    model_id = "Qwen/Qwen3-Embedding-4B"
    _write_remote_code_model(tmp_path, model_id=model_id)

    identity = local_embedding_model_identity_v3(tmp_path, model_id)

    assert identity["model_id"] == model_id
    assert identity["resolved_revision"] == "a" * 40
    assert identity["artifact_closure"] == (
        "manifest_exact_recursive_all_regular_files"
    )
    assert [row["name"] for row in identity["files"]] == [
        ACQUISITION_MANIFEST_NAME,
        "config.json",
        "model.safetensors",
        "modeling_fin.py",
        "modules.json",
        "sentence_transformers/config.json",
        "tokenizer.json",
    ]


def test_v3_identity_rejects_caller_model_id_not_bound_by_acquisition(
    tmp_path: Path,
) -> None:
    _write_remote_code_model(
        tmp_path,
        model_id="Qwen/Qwen3-Embedding-4B",
    )

    with pytest.raises(
        ValueError,
        match="local_model_acquisition_manifest_model_id_mismatch",
    ):
        local_embedding_model_identity_v3(
            tmp_path,
            "attacker/arbitrary-model-id",
        )


def test_v3_identity_rejects_remote_code_drift_after_manifest(
    tmp_path: Path,
) -> None:
    model_id = "Qwen/Qwen3-Embedding-4B"
    _write_remote_code_model(tmp_path, model_id=model_id)
    (tmp_path / "modeling_fin.py").write_text(
        "MODEL_KIND = 'reranking'\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="local_model_acquisition_file_digest_mismatch:modeling_fin.py",
    ):
        local_embedding_model_identity_v3(tmp_path, model_id)


def test_v3_identity_rejects_unmanifested_runtime_file(tmp_path: Path) -> None:
    model_id = "Qwen/Qwen3-Embedding-4B"
    _write_remote_code_model(tmp_path, model_id=model_id)
    (tmp_path / "new_remote_module.py").write_text(
        "raise RuntimeError('unbound')\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="local_model_acquisition_manifest_file_set_mismatch",
    ):
        local_embedding_model_identity_v3(tmp_path, model_id)


def test_v3_identity_rejects_symlinked_nested_directory(
    tmp_path: Path,
) -> None:
    model_id = "Qwen/Qwen3-Embedding-4B"
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    _write_remote_code_model(model_dir, model_id=model_id)
    external = tmp_path / "external-remote-code"
    external.mkdir()
    (external / "modeling_external.py").write_text(
        "MODEL_KIND = 'mutable_external'\n",
        encoding="utf-8",
    )
    linked = model_dir / "linked_remote_code"
    try:
        linked.symlink_to(external, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable on this host: {exc}")

    with pytest.raises(
        ValueError,
        match=(
            "local_model_acquisition_link_or_reparse_forbidden:"
            "linked_remote_code"
        ),
    ):
        local_embedding_model_identity_v3(model_dir, model_id)


def test_windows_reparse_attribute_is_classified_as_link_like(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reparse_flag = 0x400
    monkeypatch.setattr(
        model_identity_module.stat,
        "FILE_ATTRIBUTE_REPARSE_POINT",
        reparse_flag,
        raising=False,
    )

    class ReparseEntry:
        def lstat(self) -> SimpleNamespace:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR,
                st_file_attributes=reparse_flag,
            )

    assert model_identity_module._is_link_or_reparse(ReparseEntry()) is True


def test_v3_identity_requires_immutable_commit_revision(tmp_path: Path) -> None:
    model_id = "Qwen/Qwen3-Embedding-4B"
    _write_remote_code_model(tmp_path, model_id=model_id)
    manifest_path = tmp_path / ACQUISITION_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resolved_revision"] = "main"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="local_model_acquisition_manifest_revision_invalid",
    ):
        local_embedding_model_identity_v3(tmp_path, model_id)


def test_v3_cross_encoder_identity_binds_sharded_weight_closure(
    tmp_path: Path,
) -> None:
    model_id = "Qwen/Qwen3-Reranker-4B"
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model-00001-of-00002.safetensors").write_bytes(b"one")
    (tmp_path / "model-00002-of-00002.safetensors").write_bytes(b"two")
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "layer.0": "model-00001-of-00002.safetensors",
                    "layer.1": "model-00002-of-00002.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )
    _write_manifest(tmp_path, model_id=model_id)

    identity = local_cross_encoder_model_identity_v3(
        tmp_path,
        model_id=model_id,
    )

    assert identity["weight_layout"] == "indexed_shards"
    assert "model.safetensors.index.json" in {
        row["name"] for row in identity["files"]
    }
