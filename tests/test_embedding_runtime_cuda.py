from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from retrieval.embedding_runtime import (
    load_bge_m3_runtime,
    load_qwen_embedding_runtime,
)


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
