from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from retrieval.cross_encoder import _required_cuda_device
from retrieval.model_identity import local_cross_encoder_model_identity_v2


def test_cross_encoder_fails_closed_when_cuda_is_unavailable() -> None:
    torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        device=lambda value: value,
    )

    with pytest.raises(RuntimeError, match="local_cross_encoder_cuda_required"):
        _required_cuda_device(torch)


def test_cross_encoder_selects_cuda_without_cpu_fallback() -> None:
    torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True),
        device=lambda value: value,
    )

    assert _required_cuda_device(torch) == "cuda"


def test_cross_encoder_identity_supports_sharded_weights(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model-00001-of-00002.safetensors").write_bytes(b"one")
    (tmp_path / "model-00002-of-00002.safetensors").write_bytes(b"two")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
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

    identity = local_cross_encoder_model_identity_v2(
        tmp_path,
        model_id="Qwen/Qwen3-Reranker-4B",
    )

    assert [row["name"] for row in identity["files"]] == [
        "config.json",
        "model.safetensors.index.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
        "tokenizer.json",
    ]


def test_cross_encoder_sharded_identity_requires_tokenizer_binding(
    tmp_path: Path,
) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model-00001-of-00001.safetensors").write_bytes(b"one")
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "layer.0": "model-00001-of-00001.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="local_cross_encoder_model_v2_tokenizer_files_missing",
    ):
        local_cross_encoder_model_identity_v2(
            tmp_path,
            model_id="Qwen/Qwen3-Reranker-4B",
        )
