from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import json
import pytest

from retrieval.embedding_runtime import (
    load_bge_m3_runtime,
    load_qwen_embedding_runtime,
    local_model_identity,
)
from retrieval.model_identity import local_embedding_model_identity_v2


def test_bge_runtime_is_constructed_on_cuda_with_fp16(monkeypatch) -> None:
    captured = {}

    def fake_model(path: str, **kwargs):
        captured.update(path=path, **kwargs)
        return object()

    monkeypatch.setitem(
        __import__("sys").modules,
        "FlagEmbedding",
        SimpleNamespace(BGEM3FlagModel=fake_model),
    )
    load_bge_m3_runtime(Path("D:/models/bge"))
    assert captured["device"] == "cuda"
    assert captured["use_fp16"] is True


def test_qwen_runtime_moves_model_to_cuda_and_half_precision(monkeypatch) -> None:
    captured = {}

    class FakeSentenceTransformer:
        def __init__(self, path: str, **kwargs):
            captured.update(path=path, **kwargs)
            captured["half_calls"] = 0

        def half(self):
            captured["half_calls"] += 1
            return self

    monkeypatch.setitem(
        __import__("sys").modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    load_qwen_embedding_runtime(Path("D:/models/qwen"))
    assert captured["device"] == "cuda"
    assert captured["local_files_only"] is True
    assert captured["half_calls"] == 1


def test_single_file_model_identity_keeps_historical_shape(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")

    identity = local_model_identity(tmp_path, "Qwen/example")

    assert list(identity) == [
        "model_name",
        "directory_name",
        "files",
        "model_digest",
    ]
    assert [row["name"] for row in identity["files"]] == [
        "config.json",
        "model.safetensors",
        "tokenizer.json",
    ]


def test_sharded_model_identity_binds_index_and_every_shard(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model-00001-of-00002.safetensors").write_bytes(b"one")
    (tmp_path / "model-00002-of-00002.safetensors").write_bytes(b"two")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "layer.1": "model-00002-of-00002.safetensors",
                    "layer.0": "model-00001-of-00002.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )

    identity = local_embedding_model_identity_v2(
        tmp_path,
        "Qwen/Qwen3-Embedding-4B",
    )

    assert [row["name"] for row in identity["files"]] == [
        "config.json",
        "model.safetensors.index.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
        "tokenizer.json",
    ]


def test_sharded_model_identity_rejects_missing_shard(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {"layer.0": "missing.safetensors"}}),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match="local_model_weight_shard_missing:missing.safetensors"
    ):
        local_embedding_model_identity_v2(
            tmp_path,
            "Qwen/Qwen3-Embedding-4B",
        )


def test_sharded_model_identity_rejects_path_escape(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {"layer.0": "../outside.safetensors"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="local_model_weight_shard_path_invalid"):
        local_embedding_model_identity_v2(
            tmp_path,
            "Qwen/Qwen3-Embedding-4B",
        )
