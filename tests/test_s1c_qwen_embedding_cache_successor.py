from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _runner():
    path = ROOT / "scripts/data_retrieval/materialize_s1c_qwen_embedding_cache_successor.py"
    spec = spec_from_file_location("qwen_cache_successor", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(identity: str) -> dict:
    return {"compiled_object_id": identity, "model_text": identity}


def test_embedding_successor_reuses_exact_prefix_and_returns_only_append() -> None:
    additions = _runner()._validate_successor_prefix(
        [_row("A"), _row("B")],
        [_row("A"), _row("B"), _row("C")],
    )
    assert [row["compiled_object_id"] for row in additions] == ["C"]


def test_embedding_successor_fails_closed_on_prefix_drift() -> None:
    with pytest.raises(ValueError, match="embedding_successor_base_prefix_drift"):
        _runner()._validate_successor_prefix(
            [_row("A"), _row("B")],
            [_row("A"), _row("X"), _row("C")],
        )
